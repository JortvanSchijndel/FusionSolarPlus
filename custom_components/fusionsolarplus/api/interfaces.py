from abc import ABC, abstractmethod

class GenericSolver(ABC):
    def __init__(self, model_path, device=None):
        """Instantiates a new captcha solver
        """
        self.model_path = model_path
        self.device = device
        self._init_model()

    @abstractmethod
    def _init_model(self):
        pass

    @abstractmethod
    def solve_captcha(self, img):
        pass

    @abstractmethod
    def decode_batch_predictions(self, pred):
        pass

    @abstractmethod
    def preprocess_image(self, img):
        pass
