"""
Core logic for SyberKey ↔︎ Bank demo
• Toy crypto (reverse-bytes “AES”, base64, HMAC-SHA256)
• Tracks QR version so rotation revokes older blobs
"""

import base64, hashlib, hmac, json, secrets, time, uuid
from typing import Dict, Any

# ── trivial “AES” placeholders ────────────────────────────────────────────
def _toy_aes_enc(b: bytes) -> bytes: return b[::-1]          # reverse
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

# ── SyberKey IdP ──────────────────────────────────────────────────────────
class SyberKey:
    def __init__(self):
        self._templates: Dict[str, str] = {}    # uid → sha256(bio)
        self._blobs: Dict[str, str]     = {}    # uid → active QR blob
        self._version: Dict[str, int]   = {}    # uid → int
        self._bank_keys: Dict[str, bytes] = {}  # bank_id → HMAC key

    # ----- enrol / rotate -------------------------------------------------
    def _issue_blob(self, biometric: str) -> str:
        return double_encrypt(biometric.encode())

    def enroll(self, uid: str, biometric: str) -> Dict[str, Any]:
        v = self._version.get(uid, 0) + 1
        self._version[uid] = v
        self._templates[uid] = hashlib.sha256(biometric.encode()).hexdigest()
        blob = self._issue_blob(biometric)
        self._blobs[uid] = blob
        return {"blob": blob, "version": v}

    def rotate_qr(self, uid: str) -> Dict[str, Any]:
        new_bio = f"fingerprint-{uuid.uuid4().hex[:4]}"
        return self.enroll(uid, new_bio)

    # ----- trust relationship with bank ----------------------------------
    def trust_bank(self, bank_id: str, hmac_key: bytes):
        self._bank_keys[bank_id] = hmac_key

    # ----- login flow -----------------------------------------------------
    def handle_login(self, bank_id: str, packet: Dict[str, Any],
                     user_approved: bool):
        key = self._bank_keys.get(bank_id)
        if not key:
            return {"status": "unknown_bank"}

        payload = packet["payload"]
        if not hmac_ok(key, json.dumps(payload).encode(), packet["signature"]):
            return {"status": "bad_sig"}

        if abs(time.time() - payload["ts"]) > 30:
            return {"status": "stale_ts"}

        uid, qr_blob = payload["uid"], payload["qr"]
        if qr_blob != self._blobs.get(uid):
            # tell bank the fresh blob + version
            return {"status": "qr_revoked",
                    "blob": self._blobs[uid],
                    "version": self._version[uid]}

        if not user_approved:
            return {"status": "denied"}

        bio_hash = hashlib.sha256(double_decrypt(qr_blob)).hexdigest()
        if bio_hash != self._templates.get(uid):
            return {"status": "biometric_mismatch"}

        return {"status": "success", "token": f"TOKEN-{uuid.uuid4()}"}

# ── Bank RP ───────────────────────────────────────────────────────────────
class Bank:
    def __init__(self, bank_id: str, sk: SyberKey):
        self.id = bank_id
        self._hkey = secrets.token_bytes(32)
        self._db: Dict[str, Dict[str, Any]] = {}   # uid → {blob, version}
        self._sk = sk
        sk.trust_bank(bank_id, self._hkey)

    def store_qr(self, uid: str, blob: str, version: int):
        self._db[uid] = {"blob": blob, "version": version}

    def build_packet(self, uid: str) -> Dict[str, Any]:
        qr = self._db[uid]
        payload = {"uid": uid, "qr": qr["blob"],
                   "ts": time.time(), "nonce": secrets.token_hex(6)}
        sig = hmac_sign(self._hkey, json.dumps(payload).encode())
        return {"payload": payload, "signature": sig}
