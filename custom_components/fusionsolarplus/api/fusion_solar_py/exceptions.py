"""Collection of Exception classes used by the FusionSolar package"""


class FusionSolarException(Exception):
    """Base class for all exceptions.

    :param Exception: _description_
    :type Exception: _type_
    """

    pass


class AuthenticationException(FusionSolarException):
    """Issues with the supplied username or password

    :param FusionSolarException: _description_
    :type FusionSolarException: _type_
    """

    pass


class CaptchaRequiredException(FusionSolarException):
    """A captcha is required for the login flow to proceed

    :param FusionSolarException: _description_
    :type FusionSolarException: _type_
    """

    pass


class FusionSolarRateLimit(FusionSolarException):
    """Exception raised when rate limit exceeded"""

    pass
