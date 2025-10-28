import time
import base64
import requests
import uuid
import os

from .exceptions import FusionSolarException, FusionSolarRateLimit

try:
    from PIL import Image
    from io import BytesIO
except ImportError:
    print(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
    )
    raise FusionSolarException(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
    )


class Solver(object):
    def __init__(self, hass):
        self.hass = hass
        self.last_rate_limit = 0

    RATE_LIMIT_COOLDOWN = 6 * 60 * 60  # 6-Hour cooldown

    def _init_model(self):
        self.hass = self.model_path  # Using model-path to pass self.hass
        if not self.hass:
            raise FusionSolarException("hass instance not provided as model_path")

    def save_image_to_disk(self, img_bytes, prefix="captcha"):
        filename = f"{prefix}_{uuid.uuid4().hex}.png"
        save_path = self.hass.config.path(".storage", filename)
        img = Image.open(BytesIO(img_bytes))
        img.save(save_path)
        return save_path

    def solve_captcha_rest(self, img_path):
        """Send captcha image to Hugging Face REST API and return result."""
        with open(img_path, "rb") as f:
            img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        response = requests.post(
            "https://bready11-captchabreakerr.hf.space/run/predict",
            json={"data": [f"data:image/png;base64,{img_b64}"]},
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        predicted_code = data["data"][0]
        return predicted_code

    def solve_captcha(self, img_bytes):
        if time.time() - self.last_rate_limit < self.RATE_LIMIT_COOLDOWN:
            raise FusionSolarRateLimit(
                "Captcha solving temporarily disabled due to rate limiting. Try again later."
            )

        image_path = None
        try:
            # Save captcha to disk
            image_path = self.save_image_to_disk(img_bytes, "captcha_input.png")
            # Solve captcha via REST API
            result = self.solve_captcha_rest(image_path)
            return str(result)
        except Exception as e:
            print(e)
            raise FusionSolarRateLimit(
                "Captcha API rate limited, please try again in 6 hours."
            )
        finally:
            # Delete captcha image after processing
            if image_path and os.path.exists(image_path):
                try:
                    os.remove(image_path)
                except Exception as e:
                    print(f"Failed to delete captcha image {image_path}: {e}")
