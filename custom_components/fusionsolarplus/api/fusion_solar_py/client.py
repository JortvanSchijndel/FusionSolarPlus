"""Client library to the fusion solar API"""

import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from functools import wraps
from urllib.parse import urlencode
import json
import os
from typing import Any, Optional
import re
import requests

from .exceptions import (
    AuthenticationException,
    CaptchaRequiredException,
    FusionSolarException,
)
from .constants import MODULE_SIGNALS
from .encryption import encrypt_password, get_secure_random

ENABLE_FAKE_DATA = False  # True/False » Will give predefined API responses

# global logger object
_LOGGER = logging.getLogger(__name__)

DEC_PRECISION = Decimal("1.00000000")
MAX_JS_NUMBER = Decimal("1.7976931348623157E308")


def _parse_float(value: str) -> float:
    try:
        _d = Decimal(value)
        if _d == MAX_JS_NUMBER:
            _LOGGER.warning("parsing MAX JS NUMBER returning 0.0: '%s'", value)
            return 0.0

        return float(_d.quantize(DEC_PRECISION))
    except Exception:
        _LOGGER.error("cannot parse float from json: '%s'", value, exc_info=True)
        return 0.0


class PowerStatus:
    """Class representing the basic power status"""

    def __init__(
        self,
        current_power_kw: float,
        energy_today_kwh: float = None,
        energy_kwh: float = None,
        **kwargs,
    ):
        """Create a new PowerStatus object
        :param current_power_kw: The currently produced power in kW
        :type current_power_kw: float
        :param energy_today_kwh: The total power produced that day in kWh
        :type energy_today_kwh: float
        :param energy_kwh: The total power ever produced
        :type energy_kwh: float
        :param kwargs: Deprecated parameters
        """
        self.current_power_kw = current_power_kw
        self.energy_today_kwh = energy_today_kwh
        self.energy_kwh = energy_kwh

        if "total_power_today_kwh" in kwargs.keys() and not energy_today_kwh:
            _LOGGER.warning(
                "The parameter 'total_power_today_kwh' is deprecated. Please use "
                "'energy_today_kwh' instead.",
                DeprecationWarning,
            )
            self.energy_today_kwh = kwargs["total_power_today_kwh"]

        if "total_power_kwh" in kwargs.keys() and not energy_kwh:
            _LOGGER.warning(
                "The parameter 'total_power_kwh' is deprecated. Please use "
                "'energy_kwh' instead.",
                DeprecationWarning,
            )
            self.energy_kwh = kwargs["total_power_kwh"]

    @property
    def total_power_today_kwh(self):
        """The total power produced that day in kWh"""
        _LOGGER.warning(
            "The parameter 'total_power_today_kwh' is deprecated. Please use "
            "'energy_today_kwh' instead."
        )
        return self.energy_today_kwh

    @property
    def total_power_kwh(self):
        """The total power ever produced"""
        _LOGGER.warning(
            "The parameter 'total_power_kwh' is deprecated. Please use "
            "'energy_kwh' instead."
        )
        return self.energy_kwh

    def __repr__(self):
        return (
            f"PowerStatus(current_power_kw={self.current_power_kw}, "
            f"energy_today_kwh={self.energy_today_kwh}, "
            f"energy_kwh={self.energy_kwh})"
        )


class BatteryStatus:
    """Class representing the basic battery status"""

    def __init__(
        self,
        state_of_charge: float,
        rated_capacity: float,
        operating_status: str,
        backup_time: str,
        bus_voltage: float,
        total_charged_today_kwh: float,
        total_discharged_today_kwh: float,
        current_charge_discharge_kw: float,
    ):
        """Create a new BatteryStatus object
        :param state_of_charge: The current state of charge in %
        :type state_of_charge: float
        :param rated_capacity: The rated capacity in kWh
        :type rated_capacity: float
        :param operating_status: The operating status
        :type operating_status: str
        :param backup_time: The backup time
        :type backup_time: str
        :param bus_voltage: The bus voltage in V
        :type bus_voltage: float
        :param total_charged_today_kwh: The total energy charged today in kWh
        :type total_charged_today_kwh: float
        :param total_discharged_today_kwh: The total energy discharged today in kWh
        :type total_discharged_today_kwh: float
        :param current_charge_discharge_kw: The current charge/discharge power in kW
        :type current_charge_discharge_kw: float
        """
        self.state_of_charge = state_of_charge
        self.rated_capacity = rated_capacity
        self.operating_status = operating_status
        self.backup_time = backup_time
        self.bus_voltage = bus_voltage
        self.total_charged_today_kwh = total_charged_today_kwh
        self.total_discharged_today_kwh = total_discharged_today_kwh
        self.current_charge_discharge_kw = current_charge_discharge_kw

    def __repr__(self):
        return (
            f"BatteryStatus("
            f"state_of_charge={self.state_of_charge}, "
            f"rated_capacity={self.rated_capacity}, "
            f"operating_status={self.operating_status}, "
            f"backup_time={self.backup_time}, "
            f"bus_voltage={self.bus_voltage}, "
            f"total_charged_today_kwh={self.total_charged_today_kwh}, "
            f"total_discharged_today_kwh={self.total_discharged_today_kwh}, "
            f"current_charge_discharge_kw={self.current_charge_discharge_kw}, "
        )


def logged_in(func):
    """
    Decorator to make sure user is logged in.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # use the is-session-alive feature to check whether the session is active
        if not self.is_session_active():
            _LOGGER.debug("No active session. Resetting session and logging in...")

            # reset the session
            self._session = requests.Session()
            self._configure_session()

        try:
            result = func(self, *args, **kwargs)
        except json.JSONDecodeError:
            # this may indicate that the login failed
            _LOGGER.error("Login apparently failed. Received invalid response.")
            raise FusionSolarException("Failed to reset session and login again.")

        return result

    return wrapper


def with_solver(func):
    """
    Decorator to solve captcha when required
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            result = func(self, *args, **kwargs)
        except CaptchaRequiredException:
            _LOGGER.info("solving captcha and retrying login")
            # don't allow another captcha exception to be caught by this wrapper
            kwargs["allow_captcha_exception"] = False
            # check if captcha is required and populate self._verify_code
            # clear previous verify code if there was one for the check later
            self._captcha_verify_code = None
            captcha_present = self._check_captcha()
            if not captcha_present:
                raise AuthenticationException(
                    "Login failed: Captcha required but captcha not found."
                )

            if self._captcha_verify_code is not None:
                result = func(self, *args, **kwargs)
            else:
                raise AuthenticationException("Login failed: no verify code found.")
        return result

    return wrapper


class FusionSolarClient:
    """The main client to interact with the Fusion Solar API"""

    def __init__(
        self,
        username: str,
        password: str,
        huawei_subdomain: str = "region01eu5",
        session: Optional[requests.Session] = None,
        captcha_model_path: Optional[str] = None,
        captcha_device: Optional[Any] = ["CPUExecutionProvider"],
    ) -> None:
        """Initializes a new FusionSolarClient instance. This is the main
           class to interact with the FusionSolar API.
           The client tests the login credentials as soon as it is initialized
        :param username: The username for the system
        :type username: str
        :param password: The password
        :type password: str
        :param huawei_subdomain: The FusionSolar API uses different subdomains for different regions.
                                 Adapt this based on the first part of the URL when you access your system.
        :type huawei_subdomain: str
        :param session: An optional requests session object. If not set, a new session will be created.
        :type session: requests.Session
        :param captcha_model_path: Path to the weights file for the captcha solver. Only required if you want to use the auto captcha solver
        :type captcha_model_path: str
        :param captcha_device : The device to run the captcha solver on, as list of execution providers. Only required if you want to use the auto captcha solver.
        Please refer to the onnxruntime documentation for more information. https://onnxruntime.ai/docs/execution-providers/
        :type captcha_device: list
        """
        self._user = username
        self._password = password
        self._captcha_verify_code = None
        if session is None:
            self._session = requests.Session()
        else:
            self._session = session

        suffix = ".fusionsolar.huawei.com"

        while huawei_subdomain.endswith(suffix):
            huawei_subdomain = huawei_subdomain[: -len(suffix)]

        self._huawei_subdomain = huawei_subdomain

        # hierarchy: company <- plants <- devices <- subdevices
        self._company_id = None

        if self._huawei_subdomain.startswith("region"):
            self._login_subdomain = self._huawei_subdomain[8:]
        elif self._huawei_subdomain.startswith("uni"):
            self._login_subdomain = self._huawei_subdomain[6:]
        else:
            self._login_subdomain = self._huawei_subdomain

        self._captcha_model_path = captcha_model_path
        self.captcha_device = captcha_device
        self._captcha_solver = None

        # Only login if no session has been provided. The session should hold the cookies for a logged in state
        if session is None:
            self._configure_session()

    def log_out(self):
        """Log out from the FusionSolarAPI"""
        self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/unisess/v1/logout",
            params={
                "service": f"https://{self._huawei_subdomain}.fusionsolar.huawei.com"
            },
        )

    def _check_captcha(self):
        """Checks if the captcha is required for the login.

        Also solves the captcha and places the answer into self._verify_code

        :returns True if captcha is required, False otherwise
        """
        # check if the import is available
        try:
            import bs4
        except ImportError:
            _LOGGER.error(
                "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
            )
            raise Exception("Required libraries for CAPTCHA solving are not available.")

        _LOGGER.debug("Checking if captcha is required")

        url = f"https://{self._login_subdomain}.fusionsolar.huawei.com/"
        params = {
            "service": "%2Funisess%2Fv1%2Fauth%3Fservice%3D%252Fnetecowebext%252Fhome%252Findex.html",
        }
        r = self._session.get(url=url, params=params)
        r.raise_for_status()
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        captcha_exists = soup.find(id="verificationCodeInput")
        if captcha_exists:
            captcha = self._get_captcha()
            self._init_solver()
            self._captcha_verify_code = self._captcha_solver.solve_captcha(captcha)
            r = self._session.post(
                url=f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/preValidVerifycode",
                data={"verifycode": self._captcha_verify_code, "index": 0},
            )
            r.raise_for_status()
            if r.text != "success":
                raise AuthenticationException(
                    "Login failed: captcha prevalidverify fail."
                )
            return True
        else:
            return False

    def _get_captcha(self):
        url = (
            f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/verifycode"
        )
        params = {"timestamp": round(time.time() * 1000)}
        r = self._session.get(url=url, params=params)
        r.raise_for_status()
        image_buffer = r.content
        return image_buffer

    def _init_solver(self):
        if self._captcha_model_path is None:
            raise ValueError(
                "Captcha required but no captcha solver model provided. Please refer to the documentation for more information."
            )
        if self._captcha_solver is not None:
            return

        from .captcha_solver_onnx import Solver

        self._captcha_solver = Solver(self._captcha_model_path)

    def _is_intl_subdomain(self) -> bool:
        """Check if this is the INTL subdomain which uses a different API."""
        return self._huawei_subdomain in ["intl", "la5"]

    def _login_intl(self):
        """Login flow for the INTL subdomain which uses a different API."""
        _LOGGER.debug(f"Using INTL login flow for subdomain: {self._huawei_subdomain}")

        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/dp/uidm/unisso/v1/validate-user"
        url_params = {"service": "/"}

        json_data = {
            "username": self._user,
            "password": self._password,
            "verifycode": self._captcha_verify_code or "",
        }

        headers = {"App-Id": "smartpvms"}

        r = self._session.post(
            url=url, params=url_params, json=json_data, headers=headers
        )
        r.raise_for_status()

        try:
            login_response = r.json()
        except Exception as e:
            _LOGGER.error(f"Retrieved invalid data as login response for {self._huawei_subdomain}.")
            _LOGGER.exception(e)
            raise FusionSolarException(f"Failed to process login response for {self._huawei_subdomain}")

        # INTL uses "code" instead of "errorCode"
        if login_response.get("code") != 0:
            error_msg = login_response.get("payload", {}).get(
                "exceptionMessage", "Unknown error"
            )
            raise AuthenticationException(
                f"Failed to login into FusionSolarAPI ({self._huawei_subdomain}): {error_msg}"
            )

        # Handle the redirect URL from the response
        payload = login_response.get("payload", {})
        redirect_url = payload.get("redirectURL")
        if redirect_url:
            # If redirect URL is relative, prepend the base URL
            if redirect_url.startswith("/"):
                redirect_url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com{redirect_url}"
            _LOGGER.debug(f"Following redirect for {self._huawei_subdomain}: {redirect_url}")
            # Don't follow redirects - we just need the cookies from the first response
            # The final redirect may go to an internal domain that's not publicly accessible
            redirect_response = self._session.get(redirect_url, allow_redirects=False)
            # Accept 302 as success - it means the SSO ticket was accepted
            if redirect_response.status_code not in (200, 302):
                redirect_response.raise_for_status()

    @with_solver
    def _login(self, allow_captcha_exception=True):
        # Use different login flow for INTL subdomain
        if self._is_intl_subdomain():
            return self._login_intl()

        # retrieve the public key in order to test which loging function to use
        key_request = self._session.get(
            f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/pubkey"
        )

        if key_request.status_code != 200:
            _LOGGER.error(
                f"Failed to retrieve public key. Status code = {key_request.status_code}"
            )
            raise FusionSolarException("Failed to retrieve public key.")

        key_data = key_request.json()

        # find the correct login function
        url = f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/v2/validateUser.action"
        url_params = {}
        password = self._password

        if key_data["enableEncrypt"]:
            _LOGGER.debug("Using V3 loging function with encrypted passwords")
            url = f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/v3/validateUser.action"
            _LOGGER.debug(url)
            url_params["timeStamp"] = key_data["timeStamp"]
            url_params["nonce"] = get_secure_random()

            # encrypt the password
            password = encrypt_password(key_data=key_data, password=password)
        else:
            url_params["decision"] = 1
            url_params["service"] = (
                f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/unisess/v1/auth?service=/netecowebext/home/index.html#/LOGIN",
            )

        json_data = {
            "organizationName": "",
            "username": self._user,
            "password": password,
        }

        # add the verify code if it was set
        if self._captcha_verify_code:
            json_data["verifycode"] = self._captcha_verify_code
            self._captcha_verify_code = None

        # send the request
        r = self._session.post(url=url, params=url_params, json=json_data)
        r.raise_for_status()

        try:
            login_response = r.json()
        except Exception as e:
            _LOGGER.error("Retrieved invalid data as login response.")
            _LOGGER.debug(r.json())
            _LOGGER.exception(e)
            raise FusionSolarException("Failed to process login response")

        # in the new login procedure, an errorCode 470 is pointing to a success
        # but requires another request to start the session
        if login_response["errorCode"] == "470":
            resp_multi = login_response.get("respMultiRegionName")
            if not isinstance(resp_multi[1], list) and not resp_multi[1].startswith(
                "/"
            ):
                self.MultiRegionName = self._huawei_subdomain
                # If subdomain end with eu5 eg. region01eu5 remove the eu5 part
                if self._huawei_subdomain.endswith("eu5"):
                    self.MultiRegionName = self._huawei_subdomain[:-3]

                if (
                    self.MultiRegionName.startswith("region")
                    and not self.MultiRegionName == "region05"
                ):
                    pattern = r"(region0?)(\d{1,2})"

                    def repl(match):
                        prefix, num = match.groups()
                        return f"region{int(num):03d}"

                    self.MultiRegionName = re.sub(pattern, repl, self.MultiRegionName)

                key_data = key_request.json()

                # find the correct login function
                url = f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/v2/validateUser.action"
                url_params = {}
                password = self._password

                if key_data["enableEncrypt"]:
                    _LOGGER.debug("Using V3 loging function with encrypted passwords")
                    url = f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/v3/validateUser.action"
                    _LOGGER.debug(url)
                    url_params["timeStamp"] = key_data["timeStamp"]
                    url_params["nonce"] = get_secure_random()

                    # encrypt the password
                    password = encrypt_password(key_data=key_data, password=password)

                json_data = {
                    "organizationName": "",
                    "username": self._user,
                    "password": password,
                    "multiRegionName": self.MultiRegionName,
                }

                self._check_captcha()

                # add the verify code if it was set
                if self._captcha_verify_code:
                    json_data["verifycode"] = self._captcha_verify_code
                    # invalidate verify code after use
                    self._captcha_verify_code = None

                # send the request
                r = self._session.post(url=url, params=url_params, json=json_data)
                r.raise_for_status()
                login_response = r.json()

            _LOGGER.debug("New loging procedure successful, sending additional request")
            target_subdomain = login_response["respMultiRegionName"][1]
            target_url = f"https://{self._login_subdomain}.fusionsolar.huawei.com{target_subdomain}"

            new_procedure_response = self._session.get(target_url)
            new_procedure_response.raise_for_status()

        # make sure that the login worked - NOTE: This may no longer work with the new procedure
        error = None
        if login_response["errorMsg"]:
            error = login_response["errorMsg"]

        if error:
            # only attempt to solve the captcha if it hasn't been tried before and
            # a model path is available
            if (
                "incorrect verification code" in error.lower()
                and allow_captcha_exception
                and self._captcha_model_path
            ):
                raise CaptchaRequiredException(
                    "Login failed: Incorrect verification code."
                )
            raise AuthenticationException(
                f"Failed to login into FusionSolarAPI: {error}"
            )

    def _configure_session(self):
        """Logs into the Fusion Solar API. Raises an exception if the login fails."""
        # check the login credentials right away
        _LOGGER.debug("Logging into Huawei Fusion Solar API")

        # set the user agent
        self._session.headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )

        self._login()

        # get the payload
        payload = self.keep_alive()

        if not payload:
            raise FusionSolarException(
                "Login failed. No payload received from keep-alive."
            )

        # get the main id
        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/organization/v2/company/current",
            params={"_": round(time.time() * 1000)},
        )

        # the new API returns a 500 exception if the subdomain is incorrect
        if r.status_code == 500:
            try:
                data = r.json()

                if (
                    data["exceptionId"] == "Query company failed."
                    or data["exceptionId"] == "bad status"
                ):
                    raise AuthenticationException(
                        "Invalid response received. Please check the correct Huawei subdomain."
                    )
            except json.JSONDecodeError as e:
                _LOGGER.error("Login validation failed. Failed to process response.")
                _LOGGER.exception(e)
                raise AuthenticationException("Failed to log into FusionSolarAPI.")

        r.raise_for_status()

        # catch an incorrect subdomain
        response_text = r.content.decode()

        if not response_text.strip().startswith('{"data":'):
            raise AuthenticationException(
                "Invalid response received. Please check the correct Huawei subdomain."
            )

        response_data = r.json()

        if "data" not in response_data:
            _LOGGER.error(
                f"Failed to retrieve data object. {json.dumps(response_data)}"
            )
            raise AuthenticationException("Failed to login into FusionSolarAPI.")

        self._company_id = r.json()["data"]["moDn"]

        # get the roarand, which is needed for non-GET requests, thus to change device settings
        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/unisess/v1/auth/session"
        )
        r.raise_for_status()

        try:
            self._session.headers["roarand"] = r.json()[
                "csrfToken"
            ]  # needed for post requests, otherwise it will return 401
        except Exception:
            # this currently does not work in the new login procedure
            pass

    def is_session_active(self) -> bool:
        """Tests whether the current session is active. In the web-based application, this
        function is triggered every 10 seconds.

        :return: Indicates whether the current session is active.
        :rtype: bool
        """
        if not self._session:
            return False

        # send the request
        r = self._session.get(
            f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/dpcloud/auth/v1/is-session-alive"
        )
        r.raise_for_status()

        # get the response
        response_data = r.json()

        if "code" not in response_data or response_data["code"] != 0:
            return False
        else:
            return True

    @logged_in
    def keep_alive(self):
        """This function replicates a call sent by the web-based application. Currently,
        the rate at which this function is called is unclear. It seems to be called around
        every 30 seconds.

        :return: This function returns the payload returned by the respective call
        :rtype: str
        """
        r = self._session.get(
            f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/dpcloud/auth/v1/keep-alive"
        )
        r.raise_for_status()

        response_data = r.json()

        if "code" not in response_data or response_data["code"] != 0:
            raise FusionSolarException("Failed to set keep alive.")

        # get the payload
        if "payload" in response_data:
            # save the payload as a session header
            self._session.headers["roarand"] = response_data["payload"]
            return response_data["payload"]

        return None

    @logged_in
    def toggle_device(
        self, device_dn: str, signal: str, password: str, value: str
    ) -> dict:
        # Get randomVal
        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/management/v1/config/change_Pwd"
        payload = {"pwdCode": password}
        r = self._session.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        random_val = data["data"]["check"]

        # Prepare control command
        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal-with-randomval"
        params = {
            "dn": f"{device_dn}",
            "changeValues": json.dumps([{"id": str(signal), "value": value}]),
            "randomVal": random_val,
        }
        encoded = urlencode(params)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        r = self._session.post(url, data=encoded, headers=headers)

        r.raise_for_status()
        return r.json()

    @logged_in
    def get_power_status(self) -> PowerStatus:
        """Retrieve the current power status. This is the complete
           summary across all stations.
        :return: The current status as a PowerStatus object
        """

        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/station/total-real-kpi"
        params = {
            "queryTime": round(time.time() * 1000),
            "timeZone": 1,
            "_": round(time.time() * 1000),
        }

        r = self._session.get(url=url, params=params)
        r.raise_for_status()

        # errors in decoding the object generally mean that the login expired
        # this is handled by @logged_in
        power_obj = r.json()

        power_status = PowerStatus(
            current_power_kw=float(power_obj["data"]["currentPower"]),
            energy_today_kwh=float(power_obj["data"]["dailyEnergy"]),
            energy_kwh=float(power_obj["data"]["cumulativeEnergy"]),
        )

        return power_status

    @logged_in
    def get_current_plant_data(self, plant_id: str) -> dict:
        """Retrieve the current power status and energy balance for a specific plant.
        :return: A dict object containing both datasets
        """

        ts = round(time.time() * 1000)

        # --- First request: real-time KPI ---
        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/station-real-kpi"
        params = {
            "stationDn": plant_id,
            "clientTime": ts,
            "timeZone": 1,
            "_": ts,
        }

        r = self._session.get(url=url, params=params)
        r.raise_for_status()
        power_obj = r.json()

        if "data" not in power_obj:
            raise FusionSolarException("Failed to retrieve plant KPI data.")

        # --- Second request: energy balance ---
        today = datetime.now(timezone.utc).astimezone()
        query_time = int(
            today.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000
        )
        date_str = today.strftime("%Y-%m-%d 00:00:00")

        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v3/overview/energy-balance"
        params = {
            "stationDn": plant_id,
            "timeDim": 2,
            "timeZone": 1.0,
            "timeZoneStr": today.tzname(),
            "queryTime": query_time,
            "dateStr": date_str,
            "_": ts,
        }

        r = self._session.get(url=url, params=params)
        r.raise_for_status()
        energy_obj = r.json()

        if "data" not in energy_obj:
            raise FusionSolarException("Failed to retrieve plant energy balance data.")

        data = power_obj["data"]
        energy = energy_obj["data"]

        data.update(
            {
                "existMeter": energy.get("existMeter", False),
                "existInverter": energy.get("existInverter", True),
                "totalSelfUseEnergy": energy.get("totalSelfUsePower"),
                "totalFeedInEnergy": energy.get("totalOnGridPower"),
                "totalGridImportEnergy": energy.get("totalBuyPower"),
                "totalConsumptionEnergy": energy.get("totalUsePower"),
                "pvSelfConsumptionEnergy": energy.get("selfProvide"),
                "gridImportRatio": energy.get("buyPowerRatio"),
                "pvSelfConsumptionRatio": energy.get("selfUsePowerRatioByUse"),
                "pvSelfConsumptionRatioByProduction": energy.get(
                    "selfUsePowerRatioByProduct"
                ),
            }
        )

        return data

    @logged_in
    def get_plant_ids(self) -> list:
        """Get the ids of all available stations linked
           to this account
        :return: A list of plant ids (strings)
        :rtype: list
        """
        # get the complete object tree
        station_list = self.get_station_list()

        # get the ids
        plant_ids = [obj["dn"] for obj in station_list]

        return plant_ids

    @logged_in
    def get_station_list(self) -> list:
        """Get the list of available PV stations.

        :return: _description_
        :rtype: list
        """
        # get the complete list
        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/station/station-list",
            json={
                "curPage": 1,
                "pageSize": 10,
                "gridConnectedTime": "",
                "queryTime": self._get_day_start_sec(),
                "timeZone": 2,
                "sortId": "createTime",
                "sortDir": "DESC",
                "locale": "en_US",
            },
        )
        r.raise_for_status()

        obj_tree = r.json()

        if not obj_tree["success"]:
            raise FusionSolarException("Failed to retrieve station list")

        # simply return the original object list
        return obj_tree["data"]["list"]

    @logged_in
    def get_device_ids(self) -> list:
        """gets the devices associated to a given parent_id (can be a plant or a company/account)
        returns a dictionary mapping device_type to device_id"""
        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/config/device/v1/device-list"
        params = {
            "conditionParams.parentDn": self._company_id,  # can be a plant or company id
            "conditionParams.mocTypes": "20815,20816,20819,20822,50017,60066,60014,60015,23037,60080,20817,20851",  # specifies the types of devices | 20814 for optimizers, 60080 for chargers, 20817 for backupbox, 20851 for emma
            "_": round(time.time() * 1000),
        }
        r = self._session.get(url=url, params=params)
        r.raise_for_status()
        device_data = r.json()

        devices = []
        for device in device_data["data"]:
            devices += [dict(type=device["mocTypeName"], deviceDn=device["dn"])]

        if ENABLE_FAKE_DATA:
            devices.append({"type": "Power Sensor", "deviceDn": "NE=140517905"})

        return devices

    @logged_in
    def get_historical_data(
        self,
        signal_ids: list[str] = ["30014", "30016", "30017"],
        device_dn: str = None,
        date: datetime = datetime.now(),
    ) -> dict:
        """retrieves historical data for specified signals and device
        possible signal_ids:
        30017 : produced DC in kW
        30016 : daily production in kWh
        30014 : produced AC in kW

        :return: historical data for requested signals and device
        :rtype: dict
        """

        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-history-data"
        params = ()
        for signal_id in signal_ids:
            params += (("signalIds", signal_id),)

        params += (
            ("deviceDn", device_dn),  #
            ("date", int(date.timestamp() * 1000)),
            ("_", round(time.time() * 1000)),
        )
        r = self._session.get(url=url, params=params)
        r.raise_for_status()

        return r.json(parse_float=_parse_float)

    @logged_in
    def get_real_time_data(self, device_dn: str = None) -> dict:
        """retrieves real time data for requested device

        :return: real time data for requested signals and device
        :rtype: dict

        """
        if ENABLE_FAKE_DATA and device_dn == "NE=140517905":
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(
                base_dir, "./fake_requests/standard_powersensor.json"
            )
            with open(json_path) as f:
                data = json.load(f)
            return data
        else:
            url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-realtime-data"
            params = (
                ("deviceDn", device_dn),  #
                ("_", round(time.time() * 1000)),
            )
            r = self._session.get(url=url, params=params)
            r.raise_for_status()

            return r.json()

    @logged_in
    def get_charger_data(self, device_dn: str = None) -> dict:
        """retrieves real time data for requested device

        :return: real time data for requested signals and device
        :rtype: dict

        """
        if ENABLE_FAKE_DATA and device_dn == "NE=140517905":
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, "DTSU666_power_sensor.json")
            with open(json_path) as f:
                power_sensor = json.load(f)
            return power_sensor
        else:
            self.keep_alive()  # Keep Session alive (temporary hot fix)

            # Get First DnID
            url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/dp/pvms/organization/v1/tree"
            payload = {
                "parentDn": device_dn,
                "treeDepth": "device",
                "pageParam": {"needPage": True},
                "filterCond": {"nameType": "device", "mocIdInclude": [60081]},
                "displayCond": {"self": False, "status": True},
            }
            r = self._session.post(url=url, json=payload)
            r.raise_for_status()

            response = r.json()

            dn_id_1 = response["childList"][0]["elementId"]

            # Get Second DnID
            url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details"
            params = (
                ("dn", device_dn),
                ("_", round(time.time() * 1000)),
            )
            r = self._session.get(url=url, params=params)
            r.raise_for_status()

            response = r.json()
            dn_id_2 = str(response.get("data", {}).get("mo", {}).get("dnId"))

            # Get the actual device info
            url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/device/get-realtime-info"
            payload = {
                "conditions": [
                    {"dnId": dn_id_1, "queryAll": True},
                    {"dnId": dn_id_2, "queryAll": True},
                ]
            }
            r = self._session.post(url=url, json=payload)
            r.raise_for_status()

            return r.json()

    @logged_in
    def get_pv_info(
        self, device_dn: str = None
    ) -> dict:  # Doesn't generate the Power Entities for PV only Current & Volt
        if ENABLE_FAKE_DATA and device_dn == "NE=138957388":
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, "./fake_requests/pv_info.json")
            with open(json_path) as f:
                data = json.load(f)
            return data
        else:
            #
            # Get Available PV's
            #
            avail_url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-statistics-signal"
            avail_params = {
                "deviceDn": device_dn,
                "_": round(time.time() * 1000),
            }
            r_avail = self._session.get(url=avail_url, params=avail_params)
            r_avail.raise_for_status()
            avail_data = r_avail.json()

            available_pvs = []
            for signal in avail_data.get("data", {}).get("signalList", []):
                name = signal.get("name", "")
                match = re.search(r"\bPV\d+\b", name)
                if match:
                    pv_id = match.group(0)
                    if pv_id not in available_pvs:
                        available_pvs.append(pv_id)

            #
            # Fetch PV Data
            #
            pv_signal_map = {
                "PV1": [("11001", "11002", "11003")],
                "PV2": [("11004", "11005", "11006")],
                "PV3": [("11007", "11008", "11009")],
                "PV4": [("11010", "11011", "11012")],
                "PV5": [("11013", "11014", "11015")],
                "PV6": [("11016", "11017", "11018")],
                "PV7": [("11019", "11020", "11021")],
                "PV8": [("11022", "11023", "11024")],
                "PV9": [("11025", "11026", "11027")],
                "PV10": [("11028", "11029", "11030")],
                "PV11": [("11031", "11032", "11033")],
                "PV12": [("11034", "11035", "11036")],
                "PV13": [("11037", "11038", "11039")],
                "PV14": [("11040", "11041", "11042")],
                "PV15": [("11043", "11044", "11045")],
                "PV16": [("11046", "11047", "11048")],
                "PV17": [("11049", "11050", "11051")],
                "PV18": [("11052", "11053", "11054")],
                "PV19": [("11055", "11056", "11057")],
                "PV20": [("11058", "11059", "11060")],
            }

            signal_ids = []
            for pv in available_pvs:
                pairs = pv_signal_map.get(pv)
                if pairs:
                    for voltage_id, current_id, power_id in pairs:
                        signal_ids.append(voltage_id)
                        signal_ids.append(current_id)

            params = [("signalIds", sid) for sid in signal_ids]
            params.append(("deviceDn", device_dn))
            params.append(("_", round(time.time() * 1000)))

            url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-real-kpi"

            r = self._session.get(url=url, params=params)
            r.raise_for_status()
            data = r.json()

            signals = data.get("data", {}).get("signals", {})

            #
            # Calculate Power from volt & current
            #
            latest_time = int(time.time())
            for pv in available_pvs:
                pairs = pv_signal_map.get(pv)
                if pairs:
                    for voltage_id, current_id, power_id in pairs:
                        val1 = signals.get(voltage_id, {}).get("realValue")
                        val2 = signals.get(current_id, {}).get("realValue")
                        try:
                            product = float(val1) * float(val2)
                            signals[power_id] = {
                                "value": f"{product:.2f}",
                                "realValue": f"{product:.2f}",
                                "latestTime": latest_time,
                            }
                        except (TypeError, ValueError):
                            continue

            #
            # Return available PVs & data of the PV's
            #
            filtered_signals = {}
            for pv in available_pvs:
                pairs = pv_signal_map.get(pv)
                if pairs:
                    for voltage_id, current_id, power_id in pairs:
                        for sid in (voltage_id, current_id, power_id):
                            if sid in signals:
                                filtered_signals[sid] = signals[sid]

            if not filtered_signals:
                latest_time = int(time.time())
                for pv in available_pvs:
                    pairs = pv_signal_map.get(pv)
                    if pairs:
                        for voltage_id, current_id, power_id in pairs:
                            filtered_signals[voltage_id] = {
                                "value": "0.00",
                                "realValue": "0.00",
                                "latestTime": latest_time,
                            }
                            filtered_signals[current_id] = {
                                "value": "0.00",
                                "realValue": "0.00",
                                "latestTime": latest_time,
                            }
                            filtered_signals[power_id] = {
                                "value": "0.00",
                                "realValue": "0.00",
                                "latestTime": latest_time,
                            }

            return {
                "signals": filtered_signals,
                "available_pvs": available_pvs,
            }

    @logged_in
    def get_alarm_data(self, device_dn: str = None) -> dict:
        """retrieves alarm data for device id
        :return: alarm data for device id
        :rtype: dict
        https://uni004eu5.fusionsolar.huawei.com/rest/pvms/fm/v1/query
        """

        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/fm/v1/query"
        request_data = {
            "dataType": "CURRENT",
            "domainType": "OC_SOLAR",
            "pageNo": 1,
            "pageSize": 10,
            "nativeMeDn": device_dn,
        }
        r = self._session.post(url=url, json=request_data)
        r.raise_for_status()

        return r.json()

    @logged_in
    def get_battery_ids(self, plant_id) -> list:
        """gets the battery ids associated to a given plant id
        :return: A list of battery ids (strings)
        :rtype: list
        """
        plant_flow = self.get_plant_flow(plant_id)
        nodes = plant_flow["data"]["flow"]["nodes"]
        battery_ids = []

        # for node in nodes:
        #     if "energy_store" in node["name"]:
        #         battery_ids.append(node["devIds"][0])

        for node in nodes:
            name = node.get("name", "")
            dev_ids = node.get("devIds")
            logging.debug("Processing node: name=%r devIds=%r", name, dev_ids)
            if "energy_store" in name:
                if isinstance(dev_ids, list) and dev_ids:
                    battery_ids.append(dev_ids[0])
                else:
                    logging.warning(
                        "Node with 'energy_store' in name but devIds is not a non-empty list: %r",
                        node,
                    )

        return battery_ids

    @logged_in
    def get_battery_basic_stats(self, battery_id: str) -> BatteryStatus:
        """Retrieves the basic stats for the given battery.
        :param battery_id: The battery's id
        :type battery_id: str
        :return: The basic stats as a BatteryStatus object
        """
        battery_stats = self.get_battery_status(battery_id)

        # ensure that all values are numeric
        for index in (2, 4, 5, 6, 7, 8):
            if "-" in battery_stats[index]["realValue"]:
                battery_stats[index]["realValue"] = 0

        battery_status = BatteryStatus(
            state_of_charge=float(battery_stats[8]["realValue"]),
            rated_capacity=float(battery_stats[2]["realValue"]),
            operating_status=battery_stats[0]["value"],
            backup_time=battery_stats[3]["value"],
            bus_voltage=float(battery_stats[7]["realValue"]),
            total_charged_today_kwh=float(battery_stats[4]["realValue"]),
            total_discharged_today_kwh=float(battery_stats[5]["realValue"]),
            current_charge_discharge_kw=float(battery_stats[6]["realValue"]),
        )

        return battery_status

    @logged_in
    def get_battery_day_stats(self, battery_id: str, query_time: int = None) -> dict:
        """Retrieves the SOC (state of charge) in % and charge/discharge power in kW of
        the battery for the current day.
        :param battery_id: The battery's id
        :type battery_id: str
        :param query_time: If set, must be set to 00:00:00 of the day the data should
                           be fetched for. If not set, retrieves the data for the
                           current day.
        :type query_time: int
        :return: The complete data structure as a dict
        """
        current_time = round(time.time() * 1000)
        if query_time is not None:
            current_time = query_time
        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-history-data",
            params={
                "signalIds": [
                    "30005",
                    "30007",
                ],  # 30005 is Charge/Discharge power, 30007 is SOC, state of charge in %
                "deviceDn": battery_id,
                "date": current_time,
                "_": current_time,
            },
        )
        r.raise_for_status()
        battery_data = r.json()

        if not battery_data["success"] or "data" not in battery_data:
            raise FusionSolarException(
                f"Failed to retrieve battery day stats for {battery_id}"
            )

        battery_data["data"]["30005"]["name"] = "Charge/Discharge power"
        battery_data["data"]["30007"]["name"] = "SOC"

        return battery_data["data"]

    @logged_in
    def get_battery_module_stats(
        self, battery_id: str, module_id: str = "1", signal_ids: list = None
    ) -> dict:
        """Retrieves the complete stats for the given battery module
        of the latest recorded time. See signals.md for a list of signals.
        :param battery_id: The battery's id
        :type battery_id: str
        :param module_id: The module's id
        :type module_id: str
        :param signal_ids: The signal ids to retrieve. If not set, all signals will be retrieved
        :type signal_ids: list
        :return: The complete data structure as a dict
        """

        if ENABLE_FAKE_DATA:
            if module_id == "1":
                base_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(
                    base_dir, "./fake_requests/battery_module_1.json"
                )
                with open(json_path) as f:
                    data = json.load(f)
                return data["data"]
            elif module_id == "2":
                base_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(
                    base_dir, "./fake_requests/battery_module_2.json"
                )
                with open(json_path) as f:
                    data = json.load(f)
                return data["data"]
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(
                    base_dir, "./fake_requests/battery_module_empty.json"
                )
                with open(json_path) as f:
                    data = json.load(f)
                return data["data"]
        else:
            if signal_ids is None:
                signal_ids = MODULE_SIGNALS[module_id]
            else:
                if not all(
                    signal_id in MODULE_SIGNALS[module_id] for signal_id in signal_ids
                ):
                    raise ValueError(
                        f"One or more unknown signal ids for module {module_id}"
                    )

            signal_ids = ",".join(signal_ids)

            r = self._session.get(
                url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/query-battery-dc",
                params={
                    "sigids": signal_ids,
                    "dn": battery_id,
                    "moduleId": module_id,
                    "_": round(time.time() * 1000),
                },
            )
            r.raise_for_status()
            battery_data = r.json()

            if not battery_data["success"] or "data" not in battery_data:
                raise FusionSolarException(
                    f"Failed to retrieve battery status for {battery_id}"
                )

            return battery_data["data"]

    @logged_in
    def get_battery_status(self, battery_id: str) -> dict:
        """Retrieve the current battery status. This is the complete
           summary across all battery modules.
        :param battery_id: The battery's id
        :type battery_id: str
        :return: The current status as a dict
        """
        if ENABLE_FAKE_DATA:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, "./fake_requests/battery_status.json")
            with open(json_path) as f:
                data = json.load(f)
            return data["data"][1]["signals"]
        else:
            r = self._session.get(
                url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/device-realtime-data",
                params={
                    "deviceDn": battery_id,
                    "_": round(time.time() * 1000),
                },
            )

            r.raise_for_status()
            battery_data = r.json()

            if not battery_data["success"] or "data" not in battery_data:
                raise FusionSolarException(
                    f"Failed to retrieve battery status for {battery_id}"
                )

            return battery_data["data"][1]["signals"]

    @logged_in
    def active_power_control(self, power_setting) -> None:
        """apply active power control.
        This can be useful when electricity prices are
        negative (sunny summer holiday) and you want
        to limit the power exported into the grid"""
        power_setting_options = {
            "No limit": 0,
            "Zero Export Limitation": 5,
            "Limited Power Grid (kW)": 6,
            "Limited Power Grid (%)": 7,
        }
        if power_setting not in power_setting_options:
            raise ValueError("Unknown power setting")

        device_ids = self.get_device_ids()
        dongle_id = list(filter(lambda e: e["type"] == "Dongle", device_ids))[0]["id"]

        url = f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/deviceExt/set-config-signals"
        data = {
            "dn": dongle_id,  # power control needs to be done in the dongle
            # 230190032 stands for "Active Power Control"
            "changeValues": f'[{{"id":"230190032","value":"{power_setting_options[power_setting]}"}}]',
        }

        r = self._session.post(url, data=data)
        r.raise_for_status()

    @logged_in
    def get_plant_flow(self, plant_id: str) -> dict:
        """Retrieves the data for the energy flow
        diagram displayed for each plant
        :param plant_id: The plant's id
        :type plant_id: str
        :return: The complete data structure as a dict
        """

        if ENABLE_FAKE_DATA:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            json_path = os.path.join(base_dir, "./fake_requests/flow.json")
            with open(json_path) as f:
                data = json.load(f)
            return data
        else:
            # https://region01eu5.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/energy-flow?stationDn=NE%3D33594051&_=1652469979488
            r = self._session.get(
                url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/energy-flow",
                params={"stationDn": plant_id, "_": round(time.time() * 1000)},
            )

            r.raise_for_status()
            flow_data = r.json()

            if not flow_data["success"] or "data" not in flow_data:
                raise FusionSolarException(
                    f"Failed to retrieve plant flow for {plant_id}"
                )

            return flow_data

    @logged_in
    def get_plant_stats(self, plant_id: str, query_time: int = None) -> dict:
        """Retrieves the complete plant usage statistics for the current day.
        :param plant_id: The plant's id
        :type plant_id: str
        :param query_time: If set, must be set to 00:00:00 of the day the data should
                           be fetched for. If not set, retrieves the data for the
                           current day.
        :type query_time: int
        :return: _description_
        """
        # set the query time to today
        if not query_time:
            query_time = self._get_day_start_sec()

        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/overview/energy-balance",
            params={
                "stationDn": plant_id,
                "timeDim": 2,
                "queryTime": query_time,  # TODO: this may have changed to micro-seconds ie. timestamp * 1000
                # dateTime=2024-03-07 00:00:00
                "timeZone": 2,  # 1 in no daylight
                "timeZoneStr": "Europe/Vienna",
                "_": round(time.time() * 1000),
            },
        )
        r.raise_for_status()
        plant_data = r.json()

        if not plant_data["success"] or "data" not in plant_data:
            raise FusionSolarException(
                f"Failed to retrieve plant status for {plant_id}"
            )

        # return the plant data
        return plant_data["data"]

    def get_last_plant_data(self, plant_data: dict) -> dict:
        """Extracts the last measurements from the plant data
        The dict contains detailed information about the data of the plant.
        If "existInverter" the "productPower" is reported.
        :param plant_data: The plant's stats data returned by get_plant_stats
        """
        # make sure the object is valid
        if "xAxis" not in plant_data:
            raise FusionSolarException("Invalid plant_data object passed.")

        measurement_times = plant_data["xAxis"]

        # initialize the extracted data
        extracted_data = {}

        # process the complete data
        for key_name in plant_data.keys():
            key_value = plant_data[key_name]

            try:
                # fields to ignore
                if key_name in (
                    "xAxis",
                    "stationTimezone",
                    "clientTimezone",
                    "stationDn",
                ):
                    continue

                if type(key_value) is list:
                    extracted_data[key_name] = self._get_last_value(
                        key_value, measurement_times
                    )

                # Missing data
                elif key_value == "--":
                    extracted_data[key_name] = None

                # Boolean
                elif key_name.startswith("exist"):
                    extracted_data[key_name] = bool(key_value)

                # should be numeric
                else:
                    extracted_data[key_name] = float(key_value)
            # if anything goes wrong, simply store "None" as value
            except Exception:
                _LOGGER.debug(f"Failed to parse {key_name} = {key_value}")
                extracted_data[key_name] = None

        return extracted_data

    def _get_last_value(self, values: list, measurement_times: list):
        """Get the last valid value from a values array where
           missing values are stored as '--'
        :param values: The list of values
        :type values: list
        :param measurement_times: The list of matching timepoints
        :type values: list
        :return: A dict with a "value" and "timepoint"
        """
        # add all found values in a list
        found_values = list()

        for index, value in enumerate(values):
            if value != "--":
                found_values.append(
                    {"time": measurement_times[index], "value": float(values[index])}
                )

        # if it's the last value
        if len(found_values) > 0:
            return found_values[-1]
        else:
            # If nothing is found return "None" for the current time
            return {"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "value": None}

    def _get_day_start_sec(self) -> int:
        """Return the start of the current day in seconds since
           epoche.

        :return: The start of the day ("00:00:00") in seconds
        :rtype: int
        """
        start_today = time.strftime("%Y-%m-%d 00:00:00", time.gmtime())
        struct_time = time.strptime(start_today, "%Y-%m-%d %H:%M:%S")
        seconds = round(time.mktime(struct_time) * 1000)

        return seconds

    @logged_in
    def get_optimizer_stats(self, inverter_id: str):
        """Retrieves the complete list of optimizers and returns real time stats.

        :param inverter_id: The inverter ID
        :return: _description_
        """

        if ENABLE_FAKE_DATA:
            if inverter_id == "NE=138957388":
                base_dir = os.path.dirname(os.path.abspath(__file__))
                json_path = os.path.join(base_dir, "./fake_requests/optimizer.json")
                with open(json_path) as f:
                    data = json.load(f)
                return data["data"]
            else:
                return []
        else:
            r = self._session.get(
                url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/station/v1/layout/optimizer-info",
                params={
                    "inverterDn": inverter_id,
                    "_": round(time.time() * 1000),
                },
            )
            r.raise_for_status()
            optimizer_data = r.json()

            # check for an error - this seems to happen if no optimizer is present
            if "exceptionType" in optimizer_data:
                return []

            if not optimizer_data["success"] or "data" not in optimizer_data:
                raise FusionSolarException(
                    f"Failed to retrieve plant status for {inverter_id}"
                )

            # return the plant data
            return optimizer_data["data"]
