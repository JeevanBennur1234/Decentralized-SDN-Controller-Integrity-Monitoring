"""
integrity/signer.py
ECDSA P-256 key lifecycle: generate → persist to disk → sign → verify
Keys are NEVER regenerated on import. They are created once and reloaded.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature
from shared.config import KEYS_DIR
from shared.logger import get_logger

log = get_logger("integrity.signer")

def _paths(cid):
    os.makedirs(KEYS_DIR, exist_ok=True)
    return (os.path.join(KEYS_DIR, f"{cid}_priv.pem"),
            os.path.join(KEYS_DIR, f"{cid}_pub.pem"))

def generate_keys(cid: str):
    p, q = _paths(cid)
    k = ec.generate_private_key(ec.SECP256R1())
    open(p,"wb").write(k.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    open(q,"wb").write(k.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    log.info(f"Keys generated for {cid}")

def ensure_keys(cid: str):
    p, _ = _paths(cid)
    if not os.path.exists(p):
        generate_keys(cid)

def load_priv(cid: str):
    p, _ = _paths(cid)
    return serialization.load_pem_private_key(open(p,"rb").read(), password=None)

def load_pub(cid: str):
    _, q = _paths(cid)
    return serialization.load_pem_public_key(open(q,"rb").read())

def sign(data: bytes, cid: str) -> str:
    return load_priv(cid).sign(data, ec.ECDSA(hashes.SHA256())).hex()

def verify(data: bytes, sig_hex: str, cid: str) -> bool:
    try:
        load_pub(cid).verify(bytes.fromhex(sig_hex), data, ec.ECDSA(hashes.SHA256()))
        return True
    except (InvalidSignature, Exception):
        return False
