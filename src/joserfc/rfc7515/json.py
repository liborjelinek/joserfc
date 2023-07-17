import typing as t
import binascii
from .model import (
    HeaderMember,
    GeneralJSONSignature,
    FlattenedJSONSignature,
)
from .types import (
    HeaderDict,
    JSONSignatureDict,
    GeneralJSONSerialization,
    FlattenedJSONSerialization,
)
from .registry import JWSRegistry
from ..util import (
    json_b64encode,
    json_b64decode,
    urlsafe_b64encode,
    urlsafe_b64decode,
)
from ..errors import DecodeError
from ..rfc7517.models import BaseKey


FindKey = t.Callable[[HeaderMember], BaseKey]


def sign_general_json(
        members: t.List[HeaderDict],
        payload: t.AnyStr,
        registry: JWSRegistry,
        find_key: FindKey) -> GeneralJSONSerialization:

    payload_segment = urlsafe_b64encode(payload)
    signatures: t.List[JSONSignatureDict] = [
        __sign_member(payload_segment, HeaderMember(**member), registry, find_key)
        for member in members
    ]
    payload = payload_segment.decode("utf-8")
    return {"payload": payload, "signatures": signatures}


def sign_flattened_json(
        member: HeaderDict,
        payload: t.AnyStr,
        registry: JWSRegistry,
        find_key: FindKey) -> FlattenedJSONSerialization:
    payload_segment = urlsafe_b64encode(payload)
    signature = __sign_member(payload_segment, HeaderMember(**member), registry, find_key)
    payload = payload_segment.decode("utf-8")
    return {"payload": payload, **signature}


def __sign_member(
        payload_segment: bytes,
        member: HeaderMember,
        registry: JWSRegistry,
        find_key: FindKey) -> JSONSignatureDict:
    headers = member.headers()
    registry.check_header(headers)
    alg = registry.get_alg(headers["alg"])
    key = find_key(member)
    key.check_use("sig")
    alg.check_key_type(key)
    if member.protected:
        protected_segment = json_b64encode(member.protected)
    else:
        protected_segment = b""
    signing_input = b".".join([protected_segment, payload_segment])
    signature = urlsafe_b64encode(alg.sign(signing_input, key))
    rv: JSONSignatureDict = {"signature": signature.decode("utf-8")}
    if member.protected:
        rv["protected"] = protected_segment.decode("utf-8")
    if member.header:
        rv["header"] = member.header
    return rv


def extract_general_json(value: GeneralJSONSerialization) -> GeneralJSONSignature:
    payload_segment: bytes = value["payload"].encode("utf-8")
    try:
        payload = urlsafe_b64decode(payload_segment)
    except (TypeError, ValueError, binascii.Error):
        raise DecodeError("Invalid payload")

    signatures: t.List[JSONSignatureDict] = value["signatures"]
    members = [__signature_to_member(sig) for sig in signatures]
    obj = GeneralJSONSignature(members, payload)
    obj.signatures = signatures
    obj.segments.update({"payload": payload_segment})
    return obj


def extract_flattened_json(value: FlattenedJSONSerialization) -> FlattenedJSONSignature:
    payload_segment: bytes = value["payload"].encode("utf-8")
    try:
        payload = urlsafe_b64decode(payload_segment)
    except (TypeError, ValueError, binascii.Error):
        raise DecodeError("Invalid payload")
    _sig: JSONSignatureDict = {
        "protected": value["protected"],
        "signature": value["signature"],
    }
    if "header" in value:
        _sig["header"] = value["header"]

    member = __signature_to_member(_sig)
    obj = FlattenedJSONSignature(member, payload)
    obj.signature = _sig
    obj.segments.update({"payload": payload_segment})
    return obj


def __signature_to_member(sig: JSONSignatureDict) -> HeaderMember:
    member = HeaderMember()
    if "protected" in sig:
        protected_segment = sig["protected"]
        member.protected = json_b64decode(protected_segment)
    if "header" in sig:
        member.header = sig["header"]
    return member


def verify_general_json(
        obj: GeneralJSONSignature,
        registry: JWSRegistry,
        find_key: FindKey) -> bool:
    payload_segment = obj.segments["payload"]
    for index, signature in enumerate(obj.signatures):
        member = obj.members[index]
        if not __verify_signature(member, signature, payload_segment, registry, find_key):
            return False
    return True


def verify_flattened_json(
        obj: FlattenedJSONSignature,
        registry: JWSRegistry,
        find_key: FindKey) -> bool:
    payload_segment = obj.segments["payload"]
    return __verify_signature(obj.member, obj.signature, payload_segment, registry, find_key)


def __verify_signature(
        member: HeaderMember,
        signature: JSONSignatureDict,
        payload_segment: bytes,
        registry: JWSRegistry,
        find_key: FindKey) -> bool:
    headers = member.headers()
    registry.check_header(headers)
    alg = registry.get_alg(headers["alg"])
    key = find_key(member)
    key.check_use("sig")
    alg.check_key_type(key)
    if "protected" in signature:
        protected_segment = signature["protected"].encode("utf-8")
    else:
        protected_segment = b""
    sig = urlsafe_b64decode(signature["signature"].encode("utf-8"))
    signing_input = b".".join([protected_segment, payload_segment])
    return alg.verify(signing_input, sig, key)


def detach_json_content(value):
    # https://www.rfc-editor.org/rfc/rfc7515#appendix-F
    rv = value.copy()  # don't alter original value
    if "payload" in rv:
        del rv["payload"]
    return rv
