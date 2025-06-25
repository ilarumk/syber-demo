import streamlit as st, qrcode, io, uuid, json, pathlib, datetime as dt
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo",
                   layout="centered", initial_sidebar_state="collapsed")

# ── sidebar docs (optional) ────────────────────────────────────────────
readme_path = pathlib.Path(__file__).with_name("README.md")
if readme_path.exists():
    st.sidebar.title("📖 Docs")
    st.sidebar.markdown(readme_path.read_text())

# ── global session init ────────────────────────────────────────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)

    uid  = str(uuid.uuid4())
    qr0  = sk.enroll(uid, "fingerprint-v1")
    bank.store_qr(uid, qr0["blob"], qr0["version"])

    st.session_state.update(
        sk=sk, bank=bank, uid=uid,
        current_ver=qr0["version"],
        push_pending=False,
        last_packet=None,
        flow_log=[]
    )

# handy refs
sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

# ── helpers ────────────────────────────────────────────────────────────
def show_qr(blob, ver):
    buf = io.BytesIO(); qrcode.make(blob).save(buf)
    st.image(buf.getvalue(), width=160,
             caption=f"Active QR • v{ver}", output_format="PNG")

def log(msg):
    ts = dt.datetime.now().strftime("%H:%M:%S")
    st.session_state.flow_log.append(f"**{ts}** — {msg}")

def render_log():
    if st.session_state.flow_log:
        st.markdown("### Flow Log")
        st.markdown("\n\n".join(st.session_state.flow_log[-15:]))  # last N lines

# ── 0️⃣ Registration banner ────────────────────────────────────────────
with st.expander("0️⃣  Registered credentials", expanded=True):
    st.write(f"**SyberKey-ID**: `{uid}`")
    show_qr(bank.db[uid]["blob"], bank.db[uid]["version"])

# ── ① Bank kiosk input ────────────────────────────────────────────────
st.header("①  Bank kiosk")
user_id = st.text_input("Enter SyberKey-ID", placeholder="paste UUID above")

# ── ② Send packet (steps 1-2) ─────────────────────────────────────────
if st.button("Send login request ➜"):
    if user_id not in bank.db:
        st.error("Unknown ID – not enrolled.")
    else:
        qr_meta = bank.db[user_id]
        log(f"1 · User provides ID **{user_id}** to Bank; Bank fetches QR v{qr_meta['version']}.")
        packet = bank.build_packet(user_id)
        log("2 · Bank builds signed packet and sends to SyberKey:")
        log(f"`{json.dumps(packet, indent=2)}`")
        st.session_state.last_packet  = packet
        st.session_state.push_pending = True

# ── ④ Push prompt ─────────────────────────────────────────────────────
if st.session_state.get("push_pending"):
    st.header("③➜④  SyberKey verifies → pushes approval")
    st.info("SyberKey validated HMAC & timestamp, now needs user approval.")
    choice = st.radio("Approve login?", ("Approve", "Deny"), horizontal=True)
    if st.button("Respond"):
        approved = (choice == "Approve")
        if approved:
            log("3 · SyberKey signature & freshness checks ✓; push sent.")
            log("4 · User taps **Approve** in SyberKey app.")
        else:
            log("User tapped **Deny**.")
        res = sk.handle_login(bank.id, st.session_state.last_packet, approved)
        st.session_state.result = res
        st.session_state.push_pending = False

# ── ⑤-⑦ results ───────────────────────────────────────────────────────
if st.session_state.get("result"):
    res = st.session_state.result
    if res.get("status") == "success":
        log("5 · SyberKey decrypted both layers, biometric match ✓.")
        log("6 · SyberKey returns `{status: success, user_token: …}`.")
        log("7 · Bank accepts response and logs user in.")
        st.success(f"Login success!\n\n`{res['token']}`")
    elif res.get("status") == "qr_revoked":
        log("SyberKey says QR **revoked**. Bank retrieves new blob v"
            f"{res['version']} and retries.")
        bank.store_qr(uid, res["blob"], res["version"])
        st.info("Bank updated to latest QR. Try login again.")
        show_qr(res["blob"], res["version"])
    else:
        log(f"Login failed – {res['status']}")
        st.error(f"Login failed: {res['status']}")

    st.session_state.result = None  # clear

# ──  flow log at bottom ───────────────────────────────────────────────
render_log()

st.write("---")
st.caption("Demo uses toy crypto for illustration only – replace with AES-GCM & RSA-OAEP in production.")
