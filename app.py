import streamlit as st, qrcode, io, uuid, json, pathlib
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo",
                   layout="centered", initial_sidebar_state="collapsed")

# ── optional sidebar docs ──────────────────────────────────────────────
readme = pathlib.Path(__file__).with_name("README.md")
if readme.exists():
    with st.sidebar:
        st.title("📖 Docs")
        st.markdown(readme.read_text())

# ── one-time init ──────────────────────────────────────────────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)

    uid  = str(uuid.uuid4())
    qr0  = sk.enroll(uid, "fingerprint-v1")
    bank.store_qr(uid, qr0["blob"], qr0["version"])

    st.session_state.update(
        sk=sk, bank=bank, uid=uid,
        current_ver=qr0["version"],
        step2_packet=None,
        step3_waiting=False,
        step7_result=None
    )

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

def qr_png(blob):
    buf = io.BytesIO(); qrcode.make(blob).save(buf)
    return buf.getvalue()

# ───────────────────────────────── 0️⃣ Registration ─────────────────────────
st.header("0️⃣  Registered credentials")
cols = st.columns([2,1])
cols[0].write(f"**SyberKey-ID (UUID)**: `{uid}`")
cols[1].image(qr_png(bank.db[uid]["blob"]), width=120,
              caption=f"QR v{bank.db[uid]['version']}")

st.divider()

# ───────────────────────────────── 1️⃣ User provides ID ──────────────────────
st.subheader("1️⃣  User tells Bank: “I want to log in”")
syber_id = st.text_input("SyberKey-ID received at kiosk", value=uid)

# ───────────────────────────────── 2️⃣ Bank builds packet ────────────────────
if st.button("Send login request ➜"):
    if syber_id not in bank.db:
        st.error("Unknown ID – not enrolled.")
    else:
        st.session_state.step2_packet = bank.build_packet(syber_id)
        st.session_state.step3_waiting = True
        st.session_state.step7_result  = None

# Show step 2 packet if ready
if st.session_state.step2_packet:
    st.subheader("2️⃣  Bank → SyberKey payload")
    st.code(json.dumps(st.session_state.step2_packet, indent=2), language="json")

# ───────────────────────────────── 3️⃣ & 4️⃣ Push approval ──────────────────
if st.session_state.get("step3_waiting"):
    st.subheader("3️⃣  SyberKey validates & sends push")
    st.info("Signature ✅  Timestamp ✅ — push sent to user device.")

    choice = st.radio("4️⃣  User sees push → choose:", ("Approve", "Deny"),
                      horizontal=True)
    if st.button("Respond"):
        approved = (choice == "Approve")
        result = sk.handle_login(
            bank.id, st.session_state.step2_packet, approved
        )
        st.session_state.step3_waiting = False
        st.session_state.step7_result  = result

# ───────────────────────────────── 5-7  Results & rotation ──────────────────
if st.session_state.step7_result:
    res = st.session_state.step7_result
    if res.get("status") == "success":
        st.subheader("5-6-7 ✅  Decrypt ✔  Match ✔  Login success")
        st.success(f"Session token: `{res['token']}`")
    elif res.get("status") == "qr_revoked":
        st.subheader("⟳  QR rotated")
        st.warning("Old QR rejected. Bank fetches the new active blob.")
        bank.store_qr(uid, res["blob"], res["version"])
        st.image(qr_png(res["blob"]), width=120,
                 caption=f"New QR v{res['version']}")
        st.info("Now press **Send login request** again.")
    else:
        st.subheader("❌  Login failed")
        st.error(f"Reason: {res['status']}")

    st.session_state.step7_result = None   # clear after showing

st.write("---")
st.caption("All cryptography is illustrative. Replace toy functions with AES-GCM and RSA-OAEP in production.")
