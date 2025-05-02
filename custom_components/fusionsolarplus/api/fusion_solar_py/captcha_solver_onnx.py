from .exceptions import FusionSolarException

try:
    from gradio_client import Client, handle_file
    from PIL import Image
    from io import BytesIO
except ImportError:
    print(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha].")
    raise FusionSolarException(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha].")

from fusion_solar_py.interfaces import GenericSolver


class Solver(GenericSolver):
    def _init_model(self):
        self.hass = self.model_path     # Using modelpath to pass self.hass
        if not self.hass:
            raise FusionSolarException("hass instance not provided as model_path")

    def save_image_to_disk(self, img_bytes, filename):
        img = Image.open(BytesIO(img_bytes))

        # Save in Home Assistant's .storage directory
        save_path = self.hass.config.path(".storage", filename)
        img.save(save_path)

        return save_path

    def solve_captcha(self, img_bytes):
        # Save image and get path
        image_path = self.save_image_to_disk(img_bytes, 'captcha_input.png')

        # Send to Hugging Face Gradio client
        client = Client("docparser/Text_Captcha_breaker")
        result = client.predict(
            img_org=handle_file(image_path),
            api_name="/predict"
        )
        return result

    def decode_batch_predictions(self):
        pass

    def preprocess_image(self, img_bytes):
        pass