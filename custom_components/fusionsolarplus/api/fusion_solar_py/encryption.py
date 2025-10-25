"""
These functions take care of the RSA encryption of the user password
"""

import logging
import base64
import urllib
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes

from .exceptions import FusionSolarException


_LOGGER = logging.getLogger(__name__)


def get_secure_random() -> str:
    """This function replicates the random value
       generation found in the fusion solar code

    :return: A random 16-bit random value as a hex string.
    :rtype: str
    """
    random_data = os.urandom(16)

    return random_data.hex()


def encrypt_password(key_data: dict, password: str) -> str:
    """Encrypt's the password using the FusionSolar public key.

    :param key_data: The complete key data as a dict as returned by the pubkey endpoint.
    :type key_data: dict
    :param password: The password to encrypt.
    :type password: str
    :return: The encrypted password
    :rtype: str
    """
    # make sure password encryption is enabled
    if (
        "enableEncrypt" not in key_data
        or "pubKey" not in key_data
        or "version" not in key_data
    ):
        _LOGGER.error(
            "Invalid key_data passed. Dict must contain the 'enableEncrypt', 'pubKey', and 'version' fields."
        )
        raise FusionSolarException("Invalid 'key_data' parameter passed.")

    # make sure the encryption was enabled, if not, simply return the non-encrypted password
    if not key_data["enableEncrypt"]:
        _LOGGER.warn(
            "Password encryption called even though encryption is not enabled. Returning non-encrypted password"
        )
        return password

    # load the public key
    try:
        public_key = serialization.load_pem_public_key(
            key_data["pubKey"].encode(), backend=default_backend()
        )
    except Exception as e:
        _LOGGER.error("Failed to load public key.")
        _LOGGER.exception(e)
        raise FusionSolarException("Failed to load public key for encryption.")

    # iteratively encrypt the password phrase
    try:
        value_encode = urllib.parse.quote(password)
        encrypt_value = ""

        for i in range(0, len(value_encode) // 270 + 1):
            current_value = value_encode[i * 270 : (i + 1) * 270]
            encrypt_value_current = public_key.encrypt(
                current_value.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA384()),
                    algorithm=hashes.SHA384(),
                    label=None,
                ),
            )

            if encrypt_value != "":
                encrypt_value += "00000001"

            encrypt_value += to_base64_str(encrypt_value_current)

        return encrypt_value + key_data["version"]
    except Exception as e:
        _LOGGER.error("Failed to encrypt password.")
        _LOGGER.exception(e)
        raise FusionSolarException("Failed to encrypt password.")


def to_base64_str(value) -> str:
    """Encode the passed value in base64 and
       return it as a string

    :param value: The value to encode
    :type value: any
    :return: The base64 encoded value as a string.
    :rtype: str
    """
    return base64.b64encode(value).decode("utf-8")
