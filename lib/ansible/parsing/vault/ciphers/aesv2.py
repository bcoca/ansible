# (c) The Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt

from __future__ import annotations

import base64
import dataclasses
import hashlib
import json
import typing as t

from cryptography.fernet import Fernet, InvalidToken

from .. import VaultSecret
from . import VaultCipherBase, VaultSecretError


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class NoParams:
    ''' This VaultCipher takes no options, this class will make any passed in into an error '''
    pass


@dataclasses.dataclass(frozen=True, kw_only=True, slots=True)
class Params:
    ''' Default options for this VaultCipher'''
    salt: str = 'Xr95MRI1ljY1NZrFcirBgKVPo3BdoHpPqw9WH8kOUeE='  # generated by base64.b64encode(os.urandom(32)).decode()
    length: int = 32
    n: int = 2**14
    r: int = 8
    p: int = 1


class VaultCipher(VaultCipherBase):

    @classmethod
    @VaultCipherBase.lru_cache()
    def _derive_key_encryption_key_from_secret(cls, secret: bytes, params: Params, /) -> bytes:
        if len(secret) < 10:
            raise VaultSecretError(f"The vault secret must be at least 10 bytes (received {len(secret)}).")

        derived_key = hashlib.scrypt(secret, salt=params.salt.encode(), n=params.n, r=params.r, p=params.p, dklen=params.length)

        return base64.urlsafe_b64encode(derived_key)

    @classmethod
    def encrypt(cls, plaintext: bytes, secret: VaultSecret, options: dict[str, t.Any]) -> str:

        NoParams(**options)  # no options accepted
        params = Params()

        key_encryption_key = cls._derive_key_encryption_key_from_secret(secret.bytes, params)
        key_encryption_cipher = Fernet(key_encryption_key)

        data_encryption_key = Fernet.generate_key()
        data_encryption_cipher = Fernet(data_encryption_key)

        encrypted_data_encryption_key = key_encryption_cipher.encrypt(data_encryption_key)
        encrypted_plaintext = data_encryption_cipher.encrypt(plaintext)

        payload = dict(
            key=encrypted_data_encryption_key.decode(),
            ciphertext=encrypted_plaintext.decode(),
        )

        return base64.b64encode(json.dumps(payload).encode()).decode()

    @classmethod
    def decrypt(cls, vaulttext: str, secret: VaultSecret) -> bytes:
        payload = json.loads(base64.b64decode(vaulttext.encode()).decode())
        params = Params()

        key_encryption_key = cls._derive_key_encryption_key_from_secret(secret.bytes, params)
        key_encryption_cipher = Fernet(key_encryption_key)

        try:
            data_encryption_key = key_encryption_cipher.decrypt(payload['key'])
        except InvalidToken as ex:
            raise VaultSecretError() from ex

        data_encryption_cipher = Fernet(data_encryption_key)

        return data_encryption_cipher.decrypt(payload['ciphertext'])
