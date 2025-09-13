from .exceptions import FusionSolarException

try:
    from PIL import Image
    import numpy as np
    import torch
    import torch.nn.functional as F
    import torch.nn as nn
    import io
except ImportError:
    print(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
    )
    raise FusionSolarException(
        "Required libraries for CAPTCHA solving are not available. Please install the package using pip install fusion_solar_py[captcha]."
    )

from fusion_solar_py.interfaces import GenericSolver
from .ctc_decoder import decode

alphabet = [
    "2",
    "3",
    "4",
    "5",
    "6",
    "8",
    "9",
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "l",
    "r",
    "t",
    "y",
]
blank_idx = 20


class CaptchaNet(nn.Module):
    def __init__(self, num_classes, input_height=50, input_width=200):
        super(CaptchaNet, self).__init__()
        self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)

        # compute feature size after conv + pooling
        conv_out_height = input_height // 4
        conv_out_width = input_width // 4
        conv_out_features = 64 * conv_out_height * conv_out_width

        # first dense
        self.fc1 = nn.Linear(conv_out_features, 128)

        # bidirectional LSTM (2 layers)
        self.lstm = nn.LSTM(
            input_size=128,
            hidden_size=128,
            num_layers=2,
            bidirectional=True,
            batch_first=True,
        )

        # final dense (to num_classes)
        self.fc2 = nn.Linear(256, num_classes)

    def forward(self, x):
        # input: (batch, H, W, 1)
        x = x.permute(0, 3, 1, 2)  # to (batch, 1, H, W)
        x = F.relu(self.conv1(x))
        x = self.pool(x)
        x = F.relu(self.conv2(x))
        x = self.pool(x)

        # reshape for LSTM
        x = x.permute(0, 2, 1, 3)  # (batch, H, C, W)
        B, H, C, W = x.size()
        x = x.contiguous().view(B, H, C * W)

        x = F.relu(self.fc1(x))
        x, _ = self.lstm(x)
        x = self.fc2(x)
        return x


class Solver(GenericSolver):
    def _init_model(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = CaptchaNet(
            num_classes=len(alphabet), input_height=50, input_width=200
        )
        self.model.load_state_dict(
            torch.load("captcha_model_weights.pt", map_location=self.device)
        )
        self.model.eval()

    def solve_captcha(self, img):
        if not isinstance(img, np.ndarray):
            image = Image.open(io.BytesIO(img)).convert("L")
            img = np.array(image)

        img = self.preprocess_image(img)
        img_tensor = torch.tensor(img, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            out = self.model(img_tensor)
            if out.shape[-1] != len(alphabet):
                out = F.log_softmax(out, dim=-1)
            pred = out.cpu().numpy()

        return self.decode_batch_predictions(pred)

    def decode_batch_predictions(self, pred):
        results = decode(pred[0], beam_size=10, blank=blank_idx)
        output_text = list(map(lambda n: alphabet[n - 1], results[0]))
        return "".join(output_text)

    def preprocess_image(self, img):
        if len(img.shape) == 3:
            img = img[..., 0]
        img = img / 255.0
        img = np.swapaxes(img, 0, 1)
        img = np.expand_dims(img, axis=2)
        return img
