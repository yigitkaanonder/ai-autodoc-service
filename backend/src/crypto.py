import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import TypeDecorator, String

_KEY = os.getenv("TOKEN_ENCRYPTION_KEY")
_fernet = Fernet(_KEY.encode()) if _KEY else None


def _require_fernet() -> Fernet:
    if _fernet is None:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not set. Generate one with:\n"
            '  python -c "from cryptography.fernet import Fernet; '
            'print(Fernet.generate_key().decode())"'
        )
    return _fernet


class EncryptedString(TypeDecorator):
    """A String column that is encrypted at rest with Fernet (AES-128-CBC + HMAC).

    The value is ciphertext in the database and plaintext in Python, so every
    call site keeps working unchanged (e.g. ``user.access_token`` still returns
    the real token). If the DB is ever leaked, the tokens are useless without
    the key, which lives only in the environment.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        # Called on write: plaintext -> ciphertext
        if value is None:
            return None
        return _require_fernet().encrypt(value.encode()).decode()

    def process_result_value(self, value, dialect):
        # Called on read: ciphertext -> plaintext
        if value is None:
            return None
        try:
            return _require_fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            # Legacy plaintext or a wrong key: treat as no usable token.
            return None
