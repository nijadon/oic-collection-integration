import base64
import random
import re
import string


def encode(pwd: str, salt_length: int = 5):
    pwd_in_bytes = pwd.encode()
    salt = "".join(
        [random.choice(string.ascii_letters) for _ in range(salt_length)]
    ).encode()
    return "{pwd_encoded}:{salt}:46b".format(
        pwd_encoded=base64.b64encode(pwd_in_bytes + salt).decode(), salt=salt.decode()
    )


def decode(pwd: str):
    pwd_salt_encoded, salt, enc_type = pwd.split(":")
    pwd_salt_decoded = base64.b64decode(pwd_salt_encoded).decode()

    return re.sub(re.escape(salt) + "$", "", pwd_salt_decoded)


def is_b64_encoded(pwd: str):
    if pwd.count(":") == 2 and pwd.endswith("46b"):
        return True
    return False
