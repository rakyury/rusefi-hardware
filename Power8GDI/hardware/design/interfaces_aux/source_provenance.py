"""Hash reviewed repository text independently of checkout line endings.

Only CRLF is normalized. Whitespace, encoding, lone CR, and a missing final
newline remain significant. Manufacturer PDF hashes are always raw bytes.
"""
import hashlib


def text_fingerprints(raw: bytes) -> tuple[str, str]:
    canonical = raw.replace(b"\r\n", b"\n")
    header = b"blob " + str(len(canonical)).encode("ascii") + b"\0"
    return (hashlib.sha256(canonical).hexdigest(),
            hashlib.sha1(header + canonical).hexdigest())
