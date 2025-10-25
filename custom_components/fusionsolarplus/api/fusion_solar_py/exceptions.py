"""Collection of Exception classes used by the FusionSolar package"""


class FusionSolarException(Exception):
    """Base class for all exceptions."""

    pass


class AuthenticationException(FusionSolarException):
    """Issues with the supplied username or password"""

    pass


class CaptchaRequiredException(FusionSolarException):
    """A captcha is required for the login flow to proceed"""

    pass


class FusionSolarRateLimit(FusionSolarException):
    """Exception raised when the rate limit exceeded"""

    pass
