import streamlit as st, qrcode, io, uuid, json
from syber_core import SyberKey, Bank
import pathlib

st.sidebar.title("📖 Docs")
with open(pathlib.Path(__file__).parent / "README.md") as f:
    st.sidebar.markdown(f.read())

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo",
                   layout="centered", initial_sidebar_state="collapsed")

# ---------- Initialise objects once ----------
if "sk" not in st.session_state:
    st.session_state.sk   = SyberKey()
    st.session_state.bank = Bank("XYZ_BANK", st.session_state.sk)

    # create demo user with UUID ID
    uid = str(uuid.uuid4())
    first = st.session_state.sk.enroll(uid, "fingerprint-v1")
    st.session_state.bank.store_qr(uid, first["blob"], first["version"])
    st.session_state.uid = uid
    st.session_state.current_ver = first["version"]
    st.session_state.push_pending = False
    st.session_state.last_packet  = None
    st.session_state.result       = None

sk, bank, uid = (st.session_state.sk, st.session_state.bank,
                 st.session_state.uid)

# ---------- helper ----------
def show_qr(blob, ver):
    buf = io.BytesIO(); qrcode.make(blob).save(buf)
    st.image(buf.getvalue(), width=160,
             caption=f"Active QR  •  v{ver}", output_format="PNG")

# ---------- 0️⃣ Registration banner ----------
with st.expander("0️⃣  Registered credentials", expanded=True):
    st.write(f"**SyberKey-ID**: `{uid}`")
    show_qr(bank.db[uid]["blob"], bank.db[uid]["version"])
    

# ---------- ① Kiosk input ----------
st.header("①  Bank kiosk")
user_input = st.text_input("Enter SyberKey-ID", placeholder="paste UUID above")

# ---------- ② Send packet ----------
if st.button("Send login request ➜"):
    if user_input not in bank._db:
        st.error("Unknown ID – not enrolled.")
    else:
        pkt = bank.build_packet(user_input)
        st.session_state.last_packet = pkt
        st.session_state.push_pending = True
        st.json(pkt)

# ---------- ④ Push prompt ----------
if st.session_state.get("push_pending"):
    st.header("④  User sees push notification")
    choice = st.radio("Approve login?", ("Approve", "Deny"), horizontal=True)
    if st.button("Respond"):
        approved = (choice == "Approve")
        res = sk.handle_login(bank.id,
                              st.session_state.last_packet,
                              user_approved=approved)
        st.session_state.result = res
        st.session_state.push_pending = False

# ---------- ⑦ Bank response ----------
if st.session_state.get("result"):
    res = st.session_state.result
    st.header("⑦  Bank receives response")

    # QR rotated?
    if res.get("status") == "qr_revoked":
        st.warning("QR revoked by SyberKey – rotating to latest version.")
        new_blob, new_ver = res["blob"], res["version"]
        bank.store_qr(uid, new_blob, new_ver)
        st.session_state.current_ver = new_ver
        show_qr(new_blob, new_ver)
        st.info("Retry the login with the new QR.")
        st.session_state.result = None  # clear
    elif res.get("status") == "success":
        st.success(f"Login success!\n\n`{res['token']}`")
        st.session_state.result = None
    else:
        st.error(f"Login failed: {res['status']}")
        st.session_state.result = None

st.write("---")
st.caption("Demo uses toy crypto for illustration only.")
