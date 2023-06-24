import os
import typing as t
from abc import ABCMeta, abstractmethod
from ..rfc7517.models import Key, CurveKey
from ..registry import Header, HeaderRegistryDict
from ..errors import InvalidKeyTypeError


class Recipient:
    def __init__(
            self,
            parent: t.Union["CompactEncryption", "JSONEncryption"],
            header: t.Optional[Header] = None,
            recipient_key: t.Optional[Key]=None):
        self.__parent = parent
        self.header = header
        self.recipient_key = recipient_key
        self.sender_key: t.Optional[Key] = None
        self.encrypted_key: t.Optional[bytes] = None
        self.ephemeral_key: t.Optional[CurveKey] = None
        self.segments = {}  # store temporary segments

    def headers(self) -> Header:
        rv = {}
        rv.update(self.__parent.protected)
        if isinstance(self.__parent, JSONEncryption) and self.__parent.unprotected:
            rv.update(self.__parent.unprotected)
        if self.header:
            rv.update(self.header)
        return rv

    def add_header(self, k: str, v: t.Any):
        if isinstance(self.__parent, CompactEncryption):
            self.__parent.protected.update({k: v})
        else:
            self.header.update({k: v})

    def set_kid(self, kid: str):
        self.add_header("kid", kid)


class CompactEncryption:
    def __init__(self, protected: Header, plaintext: t.Optional[bytes] = None):
        self.protected = protected
        self.plaintext = plaintext
        self.recipient: t.Optional[Recipient] = None
        self.bytes_segments: t.Dict[str, bytes] = {}  # store the decoded segments
        self.base64_segments: t.Dict[str, bytes] = {}  # store the encoded segments

    def add_recipient(self, key: Key, header: t.Optional[Header] = None):
        recipient = Recipient(self, header, key)
        self.recipient = recipient

    @property
    def recipients(self) -> t.List[Recipient]:
        return [self.recipient]


class JSONEncryption:
    def __init__(
            self,
            protected: Header,
            plaintext: t.Optional[bytes] = None,
            unprotected: t.Optional[Header] = None,
            aad: t.Optional[bytes] = None,
            flatten: bool=False):
        self.protected = protected
        self.plaintext = plaintext
        self.unprotected = unprotected
        self.aad: t.Optional[bytes] = aad
        self.flatten = flatten
        self.recipients: t.List[Recipient] = []
        self.bytes_segments: t.Dict[str, bytes] = {}  # store the decoded segments
        self.base64_segments: t.Dict[str, bytes] = {}  # store the encoded segments

    def add_recipient(self, key: Key, header: t.Optional[Header] = None):
        recipient = Recipient(self, header, key)
        self.recipients.append(recipient)


class JWEEncModel(object, metaclass=ABCMeta):
    name: str
    description: str
    recommended: bool = True
    algorithm_type = "JWE"
    algorithm_location = "enc"

    iv_size: int
    cek_size: int

    def generate_cek(self) -> bytes:
        return os.urandom(self.cek_size // 8)

    def generate_iv(self) -> bytes:
        return os.urandom(self.iv_size // 8)

    def check_iv(self, iv: bytes) -> bytes:
        if len(iv) * 8 != self.iv_size:
            raise ValueError('Invalid "iv" size')
        return iv

    @abstractmethod
    def encrypt(self, plaintext: bytes, cek: bytes, iv: bytes, aad: bytes) -> (bytes, bytes):
        pass

    @abstractmethod
    def decrypt(self, ciphertext: bytes, tag: bytes, cek: bytes, iv: bytes, aad: bytes) -> bytes:
        pass


class JWEZipModel(object, metaclass=ABCMeta):
    name: str
    description: str
    recommended: bool = True
    algorithm_type = "JWE"
    algorithm_location = "zip"

    @abstractmethod
    def compress(self, s: bytes) -> bytes:
        pass

    @abstractmethod
    def decompress(self, s: bytes) -> bytes:
        pass


class KeyManagement:
    name: str
    description: str
    recommended: bool = False
    key_size: t.Optional[int] = None
    algorithm_type = "JWE"
    algorithm_location = "alg"
    more_header_registry: HeaderRegistryDict = {}
    key_agreement: bool = False

    @property
    def direct_mode(self) -> bool:
        return self.key_size is None

    @staticmethod
    def check_recipient_key(key) -> Key:
        raise NotImplementedError()

    def prepare_recipient_header(self, recipient: Recipient):
        raise NotImplementedError()


class JWEDirectEncryption(KeyManagement, metaclass=ABCMeta):
    @abstractmethod
    def compute_cek(self, size: int, recipient: Recipient) -> bytes:
        pass


class JWEKeyEncryption(KeyManagement, metaclass=ABCMeta):
    @abstractmethod
    def encrypt_cek(self, cek: bytes, recipient: Recipient) -> bytes:
        pass

    @abstractmethod
    def decrypt_cek(self, recipient: Recipient) -> bytes:
        pass


class JWEKeyWrapping(KeyManagement, metaclass=ABCMeta):
    @abstractmethod
    def wrap_cek(self, cek: bytes, key: bytes) -> bytes:
        pass

    @abstractmethod
    def unwrap_cek(self, ek: bytes, key: bytes) -> bytes:
        pass

    @abstractmethod
    def encrypt_cek(self, cek: bytes, recipient: Recipient) -> bytes:
        pass

    @abstractmethod
    def decrypt_cek(self, recipient: Recipient) -> bytes:
        pass


class JWEKeyAgreement(KeyManagement, metaclass=ABCMeta):
    tag_aware = False
    key_agreement = True
    key_wrapping: JWEKeyWrapping

    @staticmethod
    def check_recipient_key(key) -> CurveKey:
        if isinstance(key, CurveKey):
            return key
        raise InvalidKeyTypeError()

    def prepare_ephemeral_key(self, recipient: Recipient):
        recipient_key = self.check_recipient_key(recipient.recipient_key)
        if recipient.ephemeral_key is None:
            recipient.ephemeral_key = recipient_key.generate_key(recipient_key.curve_name, private=True)
        recipient.add_header("epk", recipient.ephemeral_key.as_dict(private=False))

    @abstractmethod
    def encrypt_agreed_upon_key(self, enc: JWEEncModel, recipient: Recipient) -> bytes:
        pass

    @abstractmethod
    def decrypt_agreed_upon_key(self, enc: JWEEncModel, recipient: Recipient) -> bytes:
        pass

    def wrap_cek_with_auk(self, cek: bytes, key: bytes) -> bytes:
        return self.key_wrapping.wrap_cek(cek, key)

    def unwrap_cek_with_auk(self, ek: bytes, key: bytes) -> bytes:
        return self.key_wrapping.unwrap_cek(ek, key)

    def encrypt_agreed_upon_key_with_tag(self, enc: JWEEncModel, recipient: Recipient, tag: bytes) -> bytes:
        raise NotImplementedError()

    def decrypt_agreed_upon_key_with_tag(self, enc: JWEEncModel, recipient: Recipient, tag: bytes) -> bytes:
        raise NotImplementedError()


JWEAlgModel = t.Union[JWEKeyEncryption, JWEKeyWrapping, JWEKeyAgreement, JWEDirectEncryption]
