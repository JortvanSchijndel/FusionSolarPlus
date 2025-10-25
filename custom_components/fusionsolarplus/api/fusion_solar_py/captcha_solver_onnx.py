import time
from abc import ABC

from .exceptions import FusionSolarException, FusionSolarRateLimit

try:
    from gradio_client import Client
    from PIL import Image
    from io import BytesIO
except ImportError:
    print(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
    )
    raise FusionSolarException(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
    )

from fusion_solar_py.interfaces import GenericSolver


class Solver(GenericSolver, ABC):
    RATE_LIMIT_COOLDOWN = 6 * 60 * 60  # 6-Hour cooldown
    last_rate_limit = 0

    def _init_model(self):
        self.hass = self.model_path  # Using model-path to pass self.hass
        if not self.hass:
            raise FusionSolarException("hass instance not provided as model_path")

    def save_image_to_disk(self, img_bytes, filename):
        img = Image.open(BytesIO(img_bytes))

        # Save in .storage directory
        save_path = self.hass.config.path(".storage", filename)
        img.save(save_path)

        return save_path

    def solve_captcha(self, img_bytes):
        # Check cooldown before making an API request
        if time.time() - self.last_rate_limit < self.RATE_LIMIT_COOLDOWN:
            raise FusionSolarRateLimit(
                "Captcha solving temporarily disabled due to rate limiting. Try again later."
            )

        try:
            image_path = self.save_image_to_disk(img_bytes, "captcha_input.png")
            client = Client("https://bready11-captchabreakerr.hf.space/")

            result = client.predict(image_path, api_name="/predict")
            return result
        except Exception:
            self.last_rate_limit = time.time()
            raise FusionSolarRateLimit(
                "Captcha API rate limited, please try again in 6 hours."
            )
