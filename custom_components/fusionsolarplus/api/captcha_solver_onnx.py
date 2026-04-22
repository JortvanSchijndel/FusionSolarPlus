import time
import logging

from .exceptions import FusionSolarException, FusionSolarRateLimit

_LOGGER = logging.getLogger(__name__)


class Solver(object):
    def __init__(self, hass):
        self.hass = hass
        self.last_rate_limit = 0

    RATE_LIMIT_COOLDOWN = 6 * 60 * 60  # 6-hour cooldown

    def solve_captcha_rest(self, img_bytes: bytes) -> str:
        """Send captcha image bytes to Nischay103/captcha_recognition via gradio_client."""
        try:
            from gradio_client import Client, handle_file
        except ImportError:
            raise FusionSolarException(
                "gradio_client is not installed. Run: pip install gradio_client"
            )

        import tempfile
        import os

        # Write bytes to a temp file since handle_file expects a path or URL
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(img_bytes)
            tmp_path = tmp.name

        try:
            client = Client("Nischay103/captcha_recognition")
            result = client.predict(
                input=handle_file(tmp_path),
                api_name="/predict",
            )
            _LOGGER.debug("Captcha solved: %s", result)
            return str(result).strip().upper()
        finally:
            os.remove(tmp_path)

    def solve_captcha(self, img_bytes: bytes) -> str:
        if time.time() - self.last_rate_limit < self.RATE_LIMIT_COOLDOWN:
            raise FusionSolarRateLimit(
                "Captcha solving temporarily disabled due to rate limiting. Try again later."
            )

        try:
            return self.solve_captcha_rest(img_bytes)
        except FusionSolarRateLimit:
            raise
        except Exception as e:
            _LOGGER.error("Captcha solving failed: %s", e)
            self.last_rate_limit = time.time()
            raise FusionSolarRateLimit(
                f"Captcha API failed, please try again in 6 hours: {e}"
            )
