# app.py
import streamlit as st, qrcode, io, uuid, json
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo",
                   layout="centered", initial_sidebar_state="collapsed")

# ---------- one-time globals ----------
if "sk" not in st.session_state:
    sk = SyberKey()
    bank = Bank("XYZ_BANK", sk)
    uid  = str(uuid.uuid4())               # random SyberKey-ID
    qr   = sk.enroll(uid, "fingerprint-v1")
    bank.store_qr(uid, qr)
    st.session_state.update(dict(sk=sk, bank=bank, uid=uid,
                                 last_packet=None, push_pending=False))

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

st.title("SyberKey ↔︎ Bank login flow")

# ========== 0️⃣  Registration ==========
with st.expander("0️⃣  Registered user info", expanded=True):
    st.markdown(f"**SyberKey-ID (UUID)**: `{uid}`")
    buf = io.BytesIO(); qrcode.make(bank.db[uid]).save(buf)
    st.image(buf.getvalue(), width=140, caption="QR v1 (encrypted)")

# ========== ①-②  Bank kiosk input & packet ==========
st.header("①  Bank kiosk")
input_id = st.text_input("Enter SyberKey-ID", placeholder="paste UUID above")

if st.button("Send login request ➜"):
    if input_id not in bank.db:
        st.error("Unknown ID – not enrolled.")
    else:
        packet = bank.build_packet(input_id)
        st.session_state.last_packet = packet
        st.session_state.push_pending = True
        st.success("Packet sent to SyberKey.")
        st.json(packet)

# ========== ③-④  SyberKey verification & push ==========
if st.session_state.push_pending:
    st.header("④  User sees push notification")
    approve = st.radio("Approve login?", ("Approve", "Deny"), horizontal=True)
    if st.button("Respond"):
        user_ok = (approve == "Approve")
        result = sk.handle_login(bank.id,
                                 st.session_state.last_packet,
                                 user_approved=user_ok)
        st.session_state.push_pending = False
        st.session_state.login_result = result

# ========== ⑤-⑦  Results at Bank side ==========
if "login_result" in st.session_state:
    st.header("⑦  Bank receives response")
    res = st.session_state.login_result
    if isinstance(res, dict):
        st.success(f"Login success!  \nJWT/Token: `{res['token']}`")
    else:
        if res == "qr_revoked":
            st.warning("QR revoked – rotating …")
            new_blob = sk.rotate_qr(uid)
            bank.store_qr(uid, new_blob)
            st.info("New QR stored. Retry the login.")
        else:
            st.error(f"Login failed: {res}")

# ---------- footer ----------
st.write("---")
st.caption("Demo backend is toy-crypto for illustration only.")

