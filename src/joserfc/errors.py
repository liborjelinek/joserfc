from typing import Optional


class JoseError(Exception):
    """Base Exception for all errors in joserfc."""

    #: short-string error code
    error = ""
    #: long-string to describe this error
    description = ""

    def __init__(self, description: Optional[str] = None, error: Optional[str] = None):
        if error is not None:
            self.error = error
        if description is not None:
            self.description = description

        message = "{}: {}".format(self.error, self.description)
        super(JoseError, self).__init__(message)

    def __repr__(self):
        return '<{} "{}">'.format(self.__class__.__name__, self.error)


class DecodeError(JoseError):
    error = "decode_error"


class InvalidKeyLengthError(JoseError):
    error = "invalid_key_length"


class InvalidKeyTypeError(JoseError):
    error = "invalid_key_type"


class InvalidEncryptedKeyError(JoseError):
    error = "invalid_encrypted_key"
    description = "JWE Encrypted Key value SHOULD be an empty octet sequence"


class MissingAlgorithmError(JoseError):
    error = "missing_algorithm"
    description = 'Missing "alg" value in header'


class MissingEncryptionError(JoseError):
    error = "missing_encryption"
    description = 'Missing "enc" value in header'


class BadSignatureError(JoseError):
    """This error is designed for JWS/JWT. It is raised when signature
    does not match.
    """
    error = "bad_signature"


class InvalidEncryptionAlgorithmError(JoseError):
    """This error is designed for JWE. It is raised when "enc" value
    does not work together with "alg" value.
    """
    error = 'invalid_encryption_algorithm'


class UnwrapError(JoseError):
    error = "unwrap_error"
    description = "Unwrap AES key failed"


class InvalidCEKLengthError(JoseError):
    error = "invalid_cek_length"
    description = 'Invalid "cek" length'


class InvalidClaimError(JoseError):
    error = "invalid_claim"

    def __init__(self, claim):
        description = f'Invalid claim: "{claim}"'
        super(InvalidClaimError, self).__init__(description=description)


class MissingClaimError(JoseError):
    error = "missing_claim"

    def __init__(self, claim):
        description = f'Missing claim: "{claim}"'
        super(MissingClaimError, self).__init__(description=description)


class InsecureClaimError(JoseError):
    error = "insecure_claim"

    def __init__(self, claim):
        description = f'Insecure claim "{claim}"'
        super(InsecureClaimError, self).__init__(description=description)


class ExpiredTokenError(JoseError):
    error = "expired_token"
    description = "The token is expired"


class InvalidTokenError(JoseError):
    error = "invalid_token"
    description = "The token is not valid yet"


class InvalidTypeError(JoseError):
    error = "invalid_type"
    description = 'The "typ" value in header is invalid'


class InvalidPayloadError(JoseError):
    error = "invalid_payload"
