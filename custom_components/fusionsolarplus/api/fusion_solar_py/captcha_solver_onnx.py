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
        pass

    def save_image_to_disk(self, img_bytes, filename):
        img = Image.open(BytesIO(img_bytes))

        # Save relative to this file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        save_path = os.path.join(base_dir, filename)

        img.save(save_path)

    def solve_captcha(self, img_bytes):
        # Save image to disk before processing
        self.save_image_to_disk(img_bytes, 'output_image.png')

        # Use the Gradio Client to process the image with the external model
        client = Client("docparser/Text_Captcha_breaker")
        result = client.predict(
            img_org=handle_file('./output_image.png'),
            api_name="/predict"
        )
        return result

    def decode_batch_predictions(self):
        pass

    def preprocess_image(self, img_bytes):
        pass