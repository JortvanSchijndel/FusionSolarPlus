"""Main FusionSolar client used by Home Assistant.

Architecture overview for contributors:
- This class owns authentication, session lifecycle and high-level API orchestration.
- Device-specific request/normalization logic lives in sibling `*_api.py` modules.
- Home Assistant sensors should consume normalized coordinator payloads and avoid
  implementing payload parsing logic in entity classes.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal
from functools import wraps
from urllib.parse import urlencode
import json
from typing import Any, Optional
import re
import requests

from .exceptions import (
    AuthenticationException,
    CaptchaRequiredException,
    FusionSolarException,
)
from .encryption import encrypt_password, get_secure_random
from .devices import (
    inverter_api,
    battery_api,
    backupbox_api,
    powersensor_api,
    charger_api,
    plant_api,
    emma_api,
)

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

    ENABLE_FAKE_DATA = ENABLE_FAKE_DATA
    _LOGGER = _LOGGER
    _parse_float = staticmethod(_parse_float)

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
        _LOGGER.debug("Checking if captcha is required")

        url = f"https://{self._login_subdomain}.fusionsolar.huawei.com/unisso/config"
        r = self._session.get(url)
        r.raise_for_status()

        data = r.json()

        if data.get("showVerifyCode", False):
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
            _LOGGER.error(
                f"Retrieved invalid data as login response for {self._huawei_subdomain}."
            )
            _LOGGER.exception(e)
            raise FusionSolarException(
                f"Failed to process login response for {self._huawei_subdomain}"
            )

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
            _LOGGER.debug(
                f"Following redirect for {self._huawei_subdomain}: {redirect_url}"
            )
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
                # If subdomain end with eu5 e.g. region01eu5 remove the eu5 part
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
        if r.status_code == 500 or r.status_code == 400:
            try:
                data = r.json()

                if (
                    data["exceptionId"] == "Query company failed."
                    or data["exceptionId"] == "bad status"
                ):
                    raise AuthenticationException(
                        "Invalid response received. Please check the correct Huawei subdomain."
                    )
            except (json.JSONDecodeError, requests.exceptions.HTTPError) as e:
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
        return plant_api.get_current_plant_data(self, plant_id)

    @logged_in
    def get_plant_ids(self) -> list:
        return plant_api.get_plant_ids(self)

    @logged_in
    def get_station_list(self) -> list:
        return plant_api.get_station_list(self)

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
        return inverter_api.get_historical_data(self, signal_ids, device_dn, date)

    @logged_in
    def get_real_time_data(self, device_dn: str = None) -> dict:
        return inverter_api.get_real_time_data(self, device_dn)

    @logged_in
    def get_inverter_data(self, device_dn: str) -> dict:
        return inverter_api.get_inverter_data(self, device_dn)

    @logged_in
    def get_charger_data(self, device_dn: str = None) -> dict:
        return charger_api.get_charger_data(self, device_dn)

    @logged_in
    def get_charger_config(self, device_dn: str) -> dict:
        """Retrieves configuration parameters for both the charger parent
        and its charging pile child via get-config-info.

        Returns a combined dict keyed by dnId:
            {
                "150453477": [ ... parent signals ... ],  # Max Charge Power (id=20001)
                "150468159": [ ... child signals ...  ],  # Working Mode (id=20002)
            }

        :param device_dn: Charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :return: Config signals keyed by dnId
        :rtype: dict
        """
        return charger_api.get_charger_config(self, device_dn)

    @logged_in
    def set_charger_max_charge_power(self, device_dn: str, max_power_kw: float) -> dict:
        """Sets the maximum charge power limit of the charger (signal id=20001).

        :param device_dn: Charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :param max_power_kw: Maximum charge power in kW, e.g. 11.0
        :type max_power_kw: float
        :return: API response
        :rtype: dict
        """
        return charger_api.set_charger_max_charge_power(self, device_dn, max_power_kw)

    @logged_in
    def set_charger_working_mode(self, device_dn: str, mode: str) -> dict:
        """Sets the working mode of the charger (signal id=20002).

        Uses the elementDn of the charging pile child device (e.g. NE=237145438),
        resolved dynamically via the device tree.

        :param device_dn: Parent charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :param mode: "0" = Normal charge, "1" = PV Power Preferred
        :type mode: str
        :return: API response
        :rtype: dict
        """
        return charger_api.set_charger_working_mode(self, device_dn, mode)

    @logged_in
    def charge_control(self, device_dn: str, action: str) -> dict:
        """Start or stop EV charging via the standard web API (port 443).

        Endpoint: POST /rest/neteco/web/homemgr/v1/charger/charge/{start-charge|stop-charge}
        start-charge returns an empty body on success; stop-charge returns {"serialNumber": ""}.

        :param device_dn: Charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :param action: "start" or "stop"
        :type action: str
        :return: API response
        :rtype: dict
        """
        return charger_api.charge_control(self, device_dn, action)

    # ── SmartAssistant / EMMA ──────────────────────────────────────────────────

    @logged_in
    def get_smart_assistant_config(self, device_dn: str) -> dict:
        """Retrieves configuration parameters for the SmartAssistant device.

        Includes PV Power Priority (signal id=230700180).

        :param device_dn: SmartAssistant device DN, e.g. "NE=237114668"
        :type device_dn: str
        :return: Config signals keyed by dnId
        :rtype: dict
        """
        return emma_api.get_smart_assistant_config(self, device_dn)

    @logged_in
    def set_smart_assistant_pv_priority(self, device_dn: str, priority: str) -> dict:
        """Sets the PV Power Priority of the SmartAssistant (signal id=230700180).

        :param device_dn: SmartAssistant device DN, e.g. "NE=237114668"
        :type device_dn: str
        :param priority: "0" = Battery first, "1" = Appliances first
        :type priority: str
        :return: API response
        :rtype: dict
        """
        return emma_api.set_smart_assistant_pv_priority(self, device_dn, priority)

    # ── Plant ──────────────────────────────────────────────────────────────────

    @logged_in
    def refresh_livedata(self, plant_dn: str) -> dict:
        """Triggers a livedata refresh for the plant.

        Forces all devices to report fresh data immediately.
        Response: {"success": true, "subscribeInfo": {"refreshPeriod": 2, "remainTime": 60}}

        :param plant_dn: Plant device DN, e.g. "NE=237114626"
        :type plant_dn: str
        :return: API response
        :rtype: dict
        """
        return plant_api.refresh_livedata(self, plant_dn)

    @logged_in
    def get_charger_config(self, device_dn: str) -> dict:
        """Retrieves configuration parameters for both the charger parent and its charging pile child.

        Returns a combined dict keyed by dnId:
            {
                "150453477": [ ... parent signals ... ],  # Max Charge Power (id=20001)
                "150468159": [ ... child signals ...  ],  # Working Mode (id=20002)
            }

        :param device_dn: Charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :return: Config signals keyed by dnId
        :rtype: dict
        """
        self.keep_alive()  # Keep session alive (same pattern as get_charger_data)

        # Resolve parent dnId from device DN
        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details",
            params=(("dn", device_dn), ("_", round(time.time() * 1000))),
        )
        r.raise_for_status()
        try:
            parent_dn_id = str(r.json().get("data", {}).get("mo", {}).get("dnId", ""))
        except Exception:
            raise FusionSolarException(
                f"Failed to parse mo-details response for {device_dn}. "
                "Session may have expired."
            )

        # Resolve child dnId (charging pile, mocId=60081) via the device tree
        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/dp/pvms/organization/v1/tree",
            json={
                "parentDn": device_dn,
                "treeDepth": "device",
                "pageParam": {"needPage": True},
                "filterCond": {"nameType": "device", "mocIdInclude": [60081]},
                "displayCond": {"self": False, "status": True},
            },
        )
        r.raise_for_status()
        children = r.json().get("childList", [])
        child_dn_id = str(children[0]["elementId"]) if children else None

        # Fetch config for both parent and child in a single request
        conditions = [{"dnId": parent_dn_id, "queryAll": True}]
        if child_dn_id:
            conditions.append({"dnId": child_dn_id, "queryAll": True})

        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/device/get-config-info",
            json={"conditions": conditions},
        )
        r.raise_for_status()
        return r.json()

    @logged_in
    def set_charger_max_charge_power(self, device_dn: str, max_power_kw: float) -> dict:
        """Sets the maximum charge power limit of the charger (signal id=20001).

        Uses the parent device DN directly.

        :param device_dn: Charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :param max_power_kw: Maximum charge power in kW, e.g. 11.0
        :type max_power_kw: float
        :return: API response
        :rtype: dict
        """
        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal",
            data={
                "dn": device_dn,
                "changeValues": f'[{{"id":"20001","value":"{max_power_kw}"}}]',
            },
        )
        r.raise_for_status()
        response = r.json()
        _LOGGER.debug("set_charger_max_charge_power response: %s", response)
        return response

    @logged_in
    def set_charger_working_mode(self, device_dn: str, mode: str) -> dict:
        """Sets the working mode of the charger (signal id=20002).

        Uses the elementDn of the charging pile child device (e.g. NE=237145438),
        which is different from the parent device DN (e.g. NE=237114670).

        :param device_dn: Parent charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :param mode: "0" = Normal charge, "1" = PV Power Preferred
        :type mode: str
        :return: API response
        :rtype: dict
        """
        mode = str(mode)
        if mode not in {"0", "1"}:
            raise ValueError(
                f"Invalid working mode '{mode}'. Valid values: 0=Normal charge, 1=PV Power Preferred"
            )

        # Resolve the elementDn of the charging pile child
        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/dp/pvms/organization/v1/tree",
            json={
                "parentDn": device_dn,
                "treeDepth": "device",
                "pageParam": {"needPage": True},
                "filterCond": {"nameType": "device", "mocIdInclude": [60081]},
                "displayCond": {"self": False, "status": True},
            },
        )
        r.raise_for_status()
        children = r.json().get("childList", [])
        if not children:
            raise FusionSolarException(
                f"No charging pile child found for {device_dn}"
            )
        child_element_dn = children[0]["elementDn"]  # e.g. "NE=237145438"

        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal",
            data={
                "dn": child_element_dn,
                "changeValues": f'[{{"id":"20002","value":"{mode}"}}]',
            },
        )
        r.raise_for_status()
        response = r.json()
        _LOGGER.debug("set_charger_working_mode response: %s", response)
        return response

    @logged_in
    def get_smart_assistant_config(self, device_dn: str) -> dict:
        """Retrieves configuration parameters for the SmartAssistant device.

        Returns a dict keyed by dnId containing config signals, including
        PV Power Priority (signal id=230700180).

        :param device_dn: SmartAssistant device DN, e.g. "NE=237114668"
        :type device_dn: str
        :return: Config signals keyed by dnId
        :rtype: dict
        """
        self.keep_alive()  # Keep session alive (same pattern as get_charger_data)

        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details",
            params=(("dn", device_dn), ("_", round(time.time() * 1000))),
        )
        r.raise_for_status()
        try:
            dn_id = str(r.json().get("data", {}).get("mo", {}).get("dnId", ""))
        except Exception:
            raise FusionSolarException(
                f"Failed to parse mo-details response for {device_dn}. "
                "Session may have expired."
            )

        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/web/homemgr/v1/device/get-config-info",
            json={"conditions": [{"dnId": dn_id, "queryAll": True}]},
        )
        r.raise_for_status()
        return r.json()

    @logged_in
    def set_smart_assistant_pv_priority(self, device_dn: str, priority: str) -> dict:
        """Sets the PV Power Priority of the SmartAssistant (signal id=230700180).

        :param device_dn: SmartAssistant device DN, e.g. "NE=237114668"
        :type device_dn: str
        :param priority: "0" = Battery first, "1" = Appliances first
        :type priority: str
        :return: API response
        :rtype: dict
        """
        priority = str(priority)
        if priority not in {"0", "1"}:
            raise ValueError(
                f"Invalid PV priority '{priority}'. Valid values: 0=Battery first, 1=Appliances first"
            )

        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/neteco/config/device/v1/config/set-signal",
            data={
                "dn": device_dn,
                "changeValues": f'[{{"id":"230700180","value":"{priority}"}}]',
            },
        )
        r.raise_for_status()
        response = r.json()
        _LOGGER.debug("set_smart_assistant_pv_priority response: %s", response)
        return response

    @logged_in
    def charge_control(self, device_dn: str, action: str) -> dict:
        """Start or stop EV charging

        Endpoint: POST /rest/neteco/web/homemgr/v1/charger/charge/{start-charge|stop-charge}

        :param device_dn: Charger device DN, e.g. "NE=237114670"
        :type device_dn: str
        :param action: "start" or "stop"
        :type action: str
        :return: API response, or {"success": True} when body is empty (start-charge)
        :rtype: dict
        """
        action = action.lower()
        if action not in {"start", "stop"}:
            raise ValueError(f"Invalid action '{action}'. Valid: 'start' or 'stop'")

        self.keep_alive()

        r = self._session.get(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com/rest/pvms/web/device/v1/mo-details",
            params=(("dn", device_dn), ("_", round(time.time() * 1000))),
        )
        r.raise_for_status()
        dn_id = int(r.json().get("data", {}).get("mo", {}).get("dnId", 0))

        endpoint = "start-charge" if action == "start" else "stop-charge"
        r = self._session.post(
            url=f"https://{self._huawei_subdomain}.fusionsolar.huawei.com"
                f"/rest/neteco/web/homemgr/v1/charger/charge/{endpoint}",
            json={
                "dnId": dn_id,
                "gunNumber": 1,
                "orderNumber": None,
                "serialNumber": None,
            },
        )
        r.raise_for_status()
        _LOGGER.debug("charge_control %s response: %s", action, r.text[:200])
        return r.json() if r.text.strip() else {"success": True}
        
    @logged_in
    def get_pv_info(
        self, device_dn: str = None
    ) -> dict:  # Doesn't generate the Power Entities for PV only Current & Volt
        return inverter_api.get_pv_info(self, device_dn)

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
        return battery_api.get_battery_ids(self, plant_id)

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
        return battery_api.get_battery_day_stats(self, battery_id, query_time)

    @logged_in
    def get_battery_module_stats(
        self, battery_id: str, module_id: str = "1", signal_ids: list = None
    ) -> dict:
        return battery_api.get_battery_module_stats(
            self, battery_id, module_id, signal_ids
        )

    @logged_in
    def get_battery_status(self, battery_id: str) -> dict:
        return battery_api.get_battery_status(self, battery_id)

    @logged_in
    def get_battery_data(self, battery_id: str) -> dict:
        return battery_api.get_battery_data(self, battery_id)

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
        return plant_api.get_plant_flow(self, plant_id)

    @logged_in
    def get_plant_stats(self, plant_id: str, query_time: int = None) -> dict:
        return plant_api.get_plant_stats(self, plant_id, query_time)

    def get_last_plant_data(self, plant_data: dict) -> dict:
        return plant_api.get_last_plant_data(self, plant_data)

    def _get_last_value(self, values: list, measurement_times: list):
        return plant_api.get_last_value(values, measurement_times)

    def _get_day_start_sec(self) -> int:
        return plant_api.get_day_start_sec()

    @logged_in
    def get_optimizer_stats(self, inverter_id: str):
        return inverter_api.get_optimizer_stats(self, inverter_id)

    @logged_in
    def get_powersensor_data(self, device_dn: str = None) -> dict:
        return powersensor_api.get_powersensor_data(self, device_dn)

    @logged_in
    def get_emma_data(self, device_dn: str = None) -> dict:
        return emma_api.get_emma_data(self, device_dn)

    @logged_in
    def get_backupbox_data(self, device_dn: str = None) -> dict:
        return backupbox_api.get_backupbox_data(self, device_dn)
