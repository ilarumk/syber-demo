# syber_core.py
import base64, hashlib, hmac, json, secrets, time, uuid

def _aes_like_encrypt(b):     return b[::-1]        # toy
def _aes_like_decrypt(b):     return b[::-1]
def double_encrypt(b):
    return base64.b64encode(_aes_like_encrypt(b)).decode()
def double_decrypt(s):
    return _aes_like_decrypt(base64.b64decode(s.encode()))
def hmac_sign(k, m):          return hmac.new(k, m, hashlib.sha256).hexdigest()
def hmac_ok(k, m, s):         return hmac.new(k, m, hashlib.sha256).hexdigest() == s

class SyberKey:
    def __init__(self):
        self.templates = {}         # uid → sha256(bio)
        self.qr_store  = {}         # uid → blob (active)
        self.bank_keys = {}         # bank_id → hmac_key

    # ----- enrol / rotation -----
    def enroll(self, uid, biometric):
        self.templates[uid] = hashlib.sha256(biometric.encode()).hexdigest()
        blob = double_encrypt(biometric.encode())
        self.qr_store[uid] = blob
        return blob

    def rotate_qr(self, uid):
        biom = f"fingerprint-{uuid.uuid4().hex[:4]}"
        return self.enroll(uid, biom)            # overwrite + return new blob

    def trust_bank(self, bank, key):  self.bank_keys[bank] = key

    # ----- login -----
    def handle_login(self, bank_id, packet, user_approved):
        key = self.bank_keys.get(bank_id)
        if not key:                                  return "unknown_bank"
        payload, sig = packet["payload"], packet["signature"]
        if not hmac_ok(key, json.dumps(payload).encode(), sig):
            return "bad_sig"
        if abs(time.time() - payload["ts"]) > 30:    return "stale"
        if payload["qr"] != self.qr_store.get(payload["uid"]):
            return "qr_revoked"
        if not user_approved:                        return "denied"
        bio_hash = hashlib.sha256(double_decrypt(payload["qr"])).hexdigest()
        if bio_hash != self.templates[payload["uid"]]:
            return "biometric_mismatch"
        return {"token": f"TOKEN-{uuid.uuid4()}"}

class Bank:
    def __init__(self, bank_id, sk: SyberKey):
        self.id  = bank_id
        self.key = secrets.token_bytes(32)
        self.db  = {}               # uid → qr_blob
        sk.trust_bank(bank_id, self.key)
        self.sk = sk

    def store_qr(self, uid, blob):   self.db[uid] = blob

    def build_packet(self, uid):
        qr = self.db[uid]
        payload = {"uid": uid, "qr": qr, "ts": time.time(),
                   "nonce": secrets.token_hex(6)}
        sig = hmac_sign(self.key, json.dumps(payload).encode())
        return {"payload": payload, "signature": sig}

