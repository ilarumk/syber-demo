# app.py — SyberKey ↔︎ Bank demo with sidebar tech-component table (no HTML)
import streamlit as st, qrcode, io, uuid, json, pathlib
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo", layout="centered")

# ─────────────── Sidebar: Architecture overview ────────────────────────
with st.sidebar:
    st.title("🏗️  System Architecture")
    st.markdown("""
| Component | Emoji | Purpose |
|-----------|-------|---------|
| SyberKey Service API | ⚙️ | Validates packets, decrypts QR, queries Cognito, issues JWT. |
| Amazon Cognito | ☁️ | Stores SHA-256(biometric), device tokens, active QR version. |
| SyberKey Mobile App | 📱 | Receives push, shows *Approve / Deny*. |
| Bank Backend & DB | 🏦 | Keeps encrypted `qr_blob` + version; signs login packets. |
| Transport (HTTPS) | 🔒 | All data in transit over TLS 1.3. |
""")

# ─────────────── Initialise objects once ───────────────────────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)

    uid  = str(uuid.uuid4())
    qr0  = sk.enroll(uid, "fingerprint-v1")
    bank.store_qr(uid, qr0["blob"], qr0["version"])

    st.session_state.update(
        sk=sk, bank=bank, uid=uid,
        waiting=False, packet=None, result=None
    )

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid
png = lambda blob: qrcode.make(blob).get_image()

# ─────────────── Step 0 — Registration ─────────────────────────────────
st.header("Step 0 – Registration (SyberKey issues QR)")
st.write(f"**SyberKey-ID (UUID)**: `{uid}`")
st.image(png(bank.db[uid]["blob"]), width=140,
         caption=f"Encrypted QR – version {bank.db[uid]['version']}")

# ─────────────── Step 1 — User presents ID ─────────────────────────────
st.header("Step 1 – User provides SyberKey-ID at the Bank kiosk")
syber_id = st.text_input("Operator enters SyberKey-ID:", value=uid)

# ─────────────── Step 2 — Build & send packet ──────────────────────────
if st.button("Build & send signed login packet"):
    if syber_id not in bank.db:
        st.error("ID not in Bank database.")
    else:
        st.session_state.packet = bank.build_packet(syber_id)
        st.session_state.waiting = True
        st.session_state.result  = None

if st.session_state.packet:
    st.subheader("Step 2 – Payload sent to SyberKey")
    st.code(json.dumps(st.session_state.packet, indent=2), language="json")

# ─────────────── Steps 3–4 — Push approval ────────────────────────────
if st.session_state.waiting:
    st.header("Step 3 – SyberKey validates packet & sends push")
    action = st.radio("Step 4 – User action on phone:", ("Approve", "Deny"),
                      horizontal=True)
    if st.button("User responds"):
        ok = (action == "Approve")
        res = sk.handle_login(bank.id, st.session_state.packet, ok)
        st.session_state.result = res
        st.session_state.waiting = False

# ─────────────── Steps 5–7 — Outcome ──────────────────────────────────
if st.session_state.result:
    res = st.session_state.result
    if res.get("status") == "success":
        st.header("Steps 5-6-7 — Decrypt, match, success")
        st.success(f"🚀 Login succeeded – token:\n\n`{res['token']}`")
    elif res.get("status") == "qr_revoked":
        st.header("QR rotated by SyberKey")
        st.warning("Bank fetches the new QR.")
        bank.store_qr(uid, res["blob"], res["version"])
        st.image(png(res["blob"]), width=140,
                 caption=f"New QR – version {res['version']}")
        st.info("Re-run Step 1 → Step 2 to authenticate with the new QR.")
    else:
        st.header("Login failed")
        st.error(f"Reason: {res['status']}")

    st.session_state.result = None  # clear after display

st.write("---")
st.caption("Crypto is illustrative only. Replace toy AES/Base64 with AES-GCM & RSA-OAEP in production.")
