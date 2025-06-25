# app.py — Full demo with detailed descriptions per step
import streamlit as st, qrcode, io, uuid, json
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo", layout="centered")

# ───────────── Sidebar tech components (render-safe emoji) ─────────────
with st.sidebar:
    st.title("🏗️ System Architecture")
    st.markdown("""
**🧠 SyberKey Service API**  
Handles validation, decryption, biometric match, and token issuance.

**☁️ Amazon Cognito**  
Stores:  
• Hashed biometric template  
• Active QR version  
• Device push tokens

**📱 SyberKey Mobile App**  
Receives push, shows *Approve / Deny*, confirms with server.

**🏦 Bank System**  
Stores encrypted QR blob, signs login packet, verifies SyberKey response.

**🔒 HTTPS Transport**  
All traffic over TLS 1.3 (end-to-end secure).
""")

# ───────────── Session init ─────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)
    uid  = str(uuid.uuid4())

    qr = sk.enroll(uid, "fingerprint-v1")
    bank.store_qr(uid, qr["blob"], qr["version"])

    st.session_state.update(sk=sk, bank=bank, uid=uid,
                            packet=None, waiting=False, result=None)

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

# ───────────── Helper ─────────────
def render_qr(blob): 
    buf = io.BytesIO()
    qrcode.make(blob).save(buf)
    return buf.getvalue()

# ───────────── Step 0 ─────────────
st.header("Step 0 – Registration")
st.markdown(f"""
**User Enrolls → SyberKey captures biometric**

- Simulated fingerprint (`fingerprint-v1`) is **double-encrypted**
- Inner layer = toy AES; outer = Base64
- SyberKey stores **only SHA-256 hash** in Cognito (not raw biometric)
- QR code (v1) is returned to Bank
- Bank stores only the encrypted QR blob + version

**Assigned SyberKey-ID (UUID):**
```{uid}```
""")
st.image(render_qr(bank.db[uid]["blob"]), width=140, caption="QR v1 – Double-encrypted")

st.divider()

# ───────────── Step 1 ─────────────
st.header("Step 1 – User presents SyberKey-ID")
st.markdown("""
At login time, user tells the bank agent their **SyberKey-ID** (UUID or short code).

Bank uses this ID to look up the stored QR code.
""")
entered = st.text_input("Enter SyberKey-ID at the Bank kiosk:", value=uid)

# ───────────── Step 2 ─────────────
st.header("Step 2 – Bank builds signed login packet")
st.markdown("""
Bank constructs a login packet with:

- User ID
- Stored QR blob
- Timestamp
- Nonce
- **HMAC signature** using its pre-shared key with SyberKey

This prevents tampering or spoofing.
""")
if st.button("Send login packet to SyberKey"):
    if entered not in bank.db:
        st.error("User not found in Bank database.")
    else:
        st.session_state.packet = bank.build_packet(entered)
        st.session_state.waiting = True
        st.session_state.result = None

if st.session_state.packet:
    st.code(json.dumps(st.session_state.packet, indent=2), language="json")

# ───────────── Step 3 ─────────────
if st.session_state.waiting:
    st.header("Step 3 – SyberKey validates request & sends push")
    st.markdown("""
SyberKey performs:

- Signature verification
- Timestamp freshness (≤ 30s)
- QR blob match with active version in Cognito

If valid, SyberKey sends a **push notification** to the mobile app:
> “Do you approve login to XYZ Bank?”
""")

    # ───────────── Step 4 ─────────────
    st.header("Step 4 – User responds via SyberKey app")
    user_action = st.radio("User taps:", ("Approve", "Deny"), horizontal=True)

    if st.button("User sends response"):
        approved = user_action == "Approve"
        result = sk.handle_login(bank.id, st.session_state.packet, approved)
        st.session_state.result = result
        st.session_state.waiting = False

# ───────────── Step 5–7 ─────────────
if st.session_state.result:
    result = st.session_state.result

    if result.get("status") == "success":
        st.header("Steps 5–6–7 – Biometric match → session success")
        st.markdown("""
**SyberKey decrypts QR:**

1. Outer Base64 decode  
2. Inner AES-like decrypt  
3. Resulting biometric is hashed (SHA-256) and compared to Cognito

If match succeeds:

- SyberKey issues a signed session token
- Bank accepts it and logs user in
        """)
        st.success("✅ Login successful!")
        st.code(result["token"], language="text")

    elif result.get("status") == "qr_revoked":
        st.header("QR Revoked – Bank receives new QR")
        st.warning("QR blob has been rotated to v2 by SyberKey")
        bank.store_qr(uid, result["blob"], result["version"])
        st.image(render_qr(result["blob"]), width=140, caption="New QR v2")
        st.info("Start login again with updated QR")

    else:
        st.header("Login failed")
        st.error(f"SyberKey rejected the request: {result['status']}")

    st.session_state.result = None

st.markdown("---")
st.caption("Note: This demo uses simplified crypto. Replace toy AES & Base64 with AES-256-GCM + RSA-OAEP in production.")
