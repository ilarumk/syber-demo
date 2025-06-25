# app.py — Streamlit demo with in-app architecture section
import streamlit as st, qrcode, io, uuid, json, pathlib
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank End-to-End Demo",
                   layout="centered", initial_sidebar_state="expanded")

# ───────────────────── “System Architecture” panel ──────────────────────
with st.sidebar.expander("▶ System Architecture (tech components)", expanded=True):
    st.markdown("""
| Component | Icon | Purpose |
|-----------|------|---------|
| SyberKey Service API | <img width="20" src="https://cdn.simpleicons.org/fastapi"> | Owns encryption keys, validates packets, decrypts QR, hits Cognito. |
| Amazon Cognito | <img width="20" src="https://cdn.simpleicons.org/amazonaws"> | Stores SHA-256(biometric), device push tokens, QR version pointer. |
| SyberKey Mobile App | <img width="18" src="https://cdn.simpleicons.org/apple"> <img width="18" src="https://cdn.simpleicons.org/android"> | Receives FCM / APNs push, shows Approve / Deny. |
| Bank Backend & DB | <img width="20" src="https://cdn.simpleicons.org/postgresql"> | Holds **only** encrypted `qr_blob` + version; signs login packets. |
| Transport | <img width="20" src="https://cdn.simpleicons.org/ssl"> | All traffic HTTPS (TLS 1.3). |
""", unsafe_allow_html=True)

# ───────────────────── demo initialisation ──────────────────────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)

    # create demo user
    uid = str(uuid.uuid4())
    qr0 = sk.enroll(uid, "fingerprint-v1")  # QR version 1
    bank.store_qr(uid, qr0["blob"], qr0["version"])

    st.session_state.update(
        sk=sk, bank=bank, uid=uid,
        current_ver=qr0["version"],
        waiting_for_push=False,
        packet=None,
        result=None
    )

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

def qr_png(blob):
    buf = io.BytesIO(); qrcode.make(blob).save(buf); return buf.getvalue()

# ───────────────────── STEP 0  Registration ────────────────────────────
st.header("Step 0 – Registration (biometric capture & QR issuance)")
st.markdown("""
* SyberKey encrypts the user’s fingerprint twice, embeds it in **QR version 1**  
  (inner AES-like, outer Base64) and stores only a **hash** of the biometric in Cognito.  
* Bank stores the opaque QR blob along with its version number.
""")
st.write(f"**SyberKey-ID (UUID)**: `{uid}`")
st.image(qr_png(bank.db[uid]["blob"]), width=140,
         caption=f"QR credential • v{bank.db[uid]['version']}")

st.divider()

# ───────────────────── STEP 1  User presents ID ─────────────────────────
st.header("Step 1 – User presents SyberKey-ID to the Bank kiosk/agent")
user_input = st.text_input("Operator types the SyberKey-ID:", value=uid)

# ───────────────────── STEP 2  Bank sends packet ───────────────────────
if st.button("Create & send signed login packet"):
    if user_input not in bank.db:
        st.error("Bank has no record of that ID.")
    else:
        st.session_state.packet = bank.build_packet(user_input)
        st.session_state.waiting_for_push = True
        st.session_state.result = None

if st.session_state.packet:
    st.subheader("Step 2 – JSON packet from Bank to SyberKey")
    st.markdown("*Bank fetches the stored QR, adds timestamp & nonce, signs with its HMAC key.*")
    st.code(json.dumps(st.session_state.packet, indent=2), language="json")

# ───────────────────── STEP 3 & 4  Push approval ───────────────────────
if st.session_state.waiting_for_push:
    st.subheader("Step 3 – SyberKey validates packet & sends push")
    st.markdown("""
* **HMAC signature** verified using bank’s secret key  
* **Timestamp** checked (≤ 30 s)  
* **QR hash** compared with active version in Cognito  
* Push notification sent to SyberKey Mobile App
""")
    decision = st.radio("Step 4 – User action on the phone:", ("Approve", "Deny"), horizontal=True)
    if st.button("User responds"):
        res = sk.handle_login(
            bank.id,
            st.session_state.packet,
            user_approved=(decision == "Approve")
        )
        st.session_state.result = res
        st.session_state.waiting_for_push = False

# ───────────────────── STEP 5-6-7  Results ─────────────────────────────
if st.session_state.result:
    res = st.session_state.result
    if res.get("status") == "success":
        st.subheader("Step 5 – Decrypt QR & match biometric ✔")
        st.markdown("*Inner AES + outer Base64 decrypt → hash matches template in Cognito.*")
        st.subheader("Step 6 – SyberKey returns success + signed token")
        st.code(json.dumps(res, indent=2), language="json")
        st.subheader("Step 7 – Bank accepts token, opens session ✅")
        st.success("User logged in.")
    elif res.get("status") == "qr_revoked":
        st.subheader("QR credential rotated by SyberKey")
        st.warning("Old QR is obsolete. Bank downloads the new blob and version.")
        bank.store_qr(uid, res["blob"], res["version"])
        st.image(qr_png(res["blob"]), width=140,
                 caption=f"New QR credential • v{res['version']}")
        st.info("Repeat Step 1 → Step 2 with the updated credential.")
    else:
        st.subheader("Login failed")
        st.error(f"SyberKey response: {res['status']}")

    st.session_state.result = None   # reset
