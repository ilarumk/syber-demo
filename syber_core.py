"""
SyberKey ↔︎ Bank demo core (toy crypto)

• SyberKey    – holds biometric templates, issues / rotates QR blobs,
                verifies signed packets, performs double-decryption & match
• Bank        – stores only opaque QR blobs (+ version) and signs packets
"""

import base64, hashlib, hmac, json, secrets, time, uuid
from typing import Dict, Any

# ── toy crypto helpers ───────────────────────────────────────────────────
def _toy_aes_enc(b: bytes) -> bytes: return b[::-1]      # reverse bytes
def _toy_aes_dec(b: bytes) -> bytes: return b[::-1]

def double_encrypt(data: bytes) -> str:
    inner = _toy_aes_enc(data)
    return base64.b64encode(inner).decode()

def double_decrypt(blob: str) -> bytes:
    return _toy_aes_dec(base64.b64decode(blob.encode()))

def hmac_sign(key: bytes, msg: bytes) -> str:
    return hmac.new(key, msg, hashlib.sha256).hexdigest()

def hmac_ok(key: bytes, msg: bytes, sig: str) -> bool:
    return hmac.new(key, msg, hashlib.sha256).hexdigest() == sig

# ── SyberKey (IdP) ───────────────────────────────────────────────────────
class SyberKey:
    def __init__(self):
        self._templates: Dict[str, str] = {}   # uid → sha256(bio)
        self._blobs: Dict[str, str]     = {}   # uid → active QR blob
        self._version: Dict[str, int]   = {}   # uid → int
        self._bank_keys: Dict[str, bytes] = {} # bank_id → HMAC key

    # enrol / rotate -------------------------------------------------------
    def _issue(self, biometric: str) -> str:
        return double_encrypt(biometric.encode())

    def enroll(self, uid: str, biometric: str) -> Dict[str, Any]:
        v = self._version.get(uid, 0) + 1
        self._version[uid] = v
        self._templates[uid] = hashlib.sha256(biometric.encode()).hexdigest()
        blob = self._issue(biometric)
        self._blobs[uid] = blob
        return {"blob": blob, "version": v}

    def rotate_qr(self, uid: str) -> Dict[str, Any]:
        new_bio = f"fingerprint-{uuid.uuid4().hex[:4]}"
        return self.enroll(uid, new_bio)

    # trust bank -----------------------------------------------------------
    def trust_bank(self, bank_id: str, key: bytes):
        self._bank_keys[bank_id] = key

    # login ----------------------------------------------------------------
    def handle_login(self, bank_id: str, packet: Dict[str, Any],
                     user_approved: bool):
        key = self._bank_keys.get(bank_id)
        if not key:
            return {"status": "unknown_bank"}

        payload, sig = packet["payload"], packet["signature"]
        if not hmac_ok(key, json.dumps(payload).encode(), sig):
            return {"status": "bad_sig"}
        if abs(time.time() - payload["ts"]) > 30:
            return {"status": "stale_ts"}

        uid, qr_blob = payload["uid"], payload["qr"]
        if qr_blob != self._blobs.get(uid):
            return {"status": "qr_revoked",
                    "blob": self._blobs[uid],
                    "version": self._version[uid]}

        if not user_approved:
            return {"status": "denied"}

        bio_hash = hashlib.sha256(double_decrypt(qr_blob)).hexdigest()
        if bio_hash != self._templates.get(uid):
            return {"status": "biometric_mismatch"}

        return {"status": "success", "token": f"TOKEN-{uuid.uuid4()}"}

# ── Bank (relying party) ─────────────────────────────────────────────────
class Bank:
    def __init__(self, bank_id: str, sk: SyberKey):
        self.id = bank_id
        self._hkey = secrets.token_bytes(32)
        self._db: Dict[str, Dict[str, Any]] = {}  # uid → {blob, version}
        self._sk = sk
        sk.trust_bank(bank_id, self._hkey)

    # expose read-only db property for Streamlit UI
    @property
    def db(self):       # <-- fix: Streamlit can call bank.db[…]
        return self._db

    def store_qr(self, uid: str, blob: str, version: int):
        self._db[uid] = {"blob": blob, "version": version}

    def build_packet(self, uid: str) -> Dict[str, Any]:
        qr = self._db[uid]
        payload = {"uid": uid, "qr": qr["blob"],
                   "ts": time.time(), "nonce": secrets.token_hex(6)}
        sig = hmac_sign(self._hkey, json.dumps(payload).encode())
        return {"payload": payload, "signature": sig}
