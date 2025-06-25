import streamlit as st, qrcode, io, uuid, json, pathlib
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo",
                   layout="centered", initial_sidebar_state="collapsed")

# ── sidebar docs (optional) ──────────────────────────────────────────────
sidebar_md = pathlib.Path(__file__).with_name("README.md")
if sidebar_md.exists():
    st.sidebar.title("📖 Docs")
    st.sidebar.markdown(sidebar_md.read_text())

# ── initialise objects once ─────────────────────────────────────────────
if "sk" not in st.session_state:
    st.session_state.sk   = SyberKey()
    st.session_state.bank = Bank("XYZ_BANK", st.session_state.sk)

    uid = str(uuid.uuid4())
    first = st.session_state.sk.enroll(uid, "fingerprint-v1")
    st.session_state.bank.store_qr(uid, first["blob"], first["version"])

    st.session_state.uid          = uid
    st.session_state.current_ver  = first["version"]
    st.session_state.push_pending = False
    st.session_state.last_packet  = None
    st.session_state.result       = None

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

# ── helper to render QR ─────────────────────────────────────────────────
def show_qr(blob, ver):
    buf = io.BytesIO(); qrcode.make(blob).save(buf)
    st.image(buf.getvalue(), width=160,
             caption=f"Active QR  •  v{ver}", output_format="PNG")

# 0️⃣ Registered credentials ------------------------------------------------
with st.expander("0️⃣  Registered credentials", expanded=True):
    st.write(f"**SyberKey-ID**: `{uid}`")
    show_qr(bank.db[uid]["blob"], bank.db[uid]["version"])

# ① Bank kiosk -------------------------------------------------------------
st.header("①  Bank kiosk")
user_id = st.text_input("Enter SyberKey-ID", placeholder="paste UUID above")

# ② Send packet ------------------------------------------------------------
if st.button("Send login request ➜"):
    if user_id not in bank.db:
        st.error("Unknown ID – not enrolled.")
    else:
        pkt = bank.build_packet(user_id)
        st.session_state.last_packet = pkt
        st.session_state.push_pending = True
        st.json(pkt)

# ④ Push prompt ------------------------------------------------------------
if st.session_state.get("push_pending"):
    st.header("④  User push approval")
    approve = st.radio("Approve login?", ("Approve", "Deny"), horizontal=True)
    if st.button("Respond"):
        res = sk.handle_login(bank.id,
                              st.session_state.last_packet,
                              user_approved=(approve == "Approve"))
        st.session_state.result = res
        st.session_state.push_pending = False

# ⑦ Bank response ----------------------------------------------------------
if st.session_state.get("result"):
    res = st.session_state.result
    st.header("⑦  Bank receives response")

    if res.get("status") == "success":
        st.success(f"Login success!\n\n`{res['token']}`")
    elif res.get("status") == "qr_revoked":
        st.warning("QR revoked – updating to new version.")
        bank.store_qr(uid, res["blob"], res["version"])
        st.session_state.current_ver = res["version"]
        show_qr(res["blob"], res["version"])
        st.info("Retry the login with the new QR.")
    else:
        st.error(f"Login failed: {res['status']}")

    st.session_state.result = None  # clear after display

st.write("---")
st.caption("Demo uses toy crypto for illustration only.")
