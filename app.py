# app.py – SyberKey ↔︎ Bank demo with inline component descriptions
import streamlit as st, qrcode, io, uuid, json
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank Demo", layout="centered")

# ─────────────────  architecture explainer  ─────────────────────────────
with st.expander("System Architecture (tech components)", expanded=True):
    st.markdown("""
| Component | Purpose |
|-----------|---------|
| **SyberKey Service API** :gear: | Validates signed packets, decrypts QR, queries Cognito, issues JWT. |
| **Amazon Cognito** :cloud: | Stores:<br/>• SHA-256(biometric)<br/>• device push tokens<br/>• active QR version. |
| **SyberKey Mobile App** :iphone: | Receives FCM / APNs push, shows *Approve / Deny*, sends result to API. |
| **Bank Backend & DB** :office: | Holds opaque `qr_blob` + version; signs login packets with its secret key. |
| **Transport** :lock: | All traffic over HTTPS (TLS 1.3). |
""")

# ─────────────────  one-time session init  ──────────────────────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)

    uid  = str(uuid.uuid4())
    first = sk.enroll(uid, "fingerprint-v1")
    bank.store_qr(uid, first["blob"], first["version"])

    st.session_state.update(
        sk=sk, bank=bank, uid=uid,
        waiting=False, packet=None, response=None
    )

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

def png_from_blob(blob):
    buf = io.BytesIO(); qrcode.make(blob).save(buf); return buf.getvalue()

# ───────────────────────── Step 0 ───────────────────────────────────────
st.header("Step 0 – Registration")
st.markdown("""
* SyberKey captures user biometric (`fingerprint-v1`).  
* Encrypts **inner layer** (toy AES) → **outer layer** (Base64) → QR v1.  
* Stores SHA-256 template in Cognito.  
* Sends QR blob to Bank; Bank stores it **cipher-only**.
""")
st.write(f"SyberKey-ID (UUID): `{uid}`")
st.image(png_from_blob(bank.db[uid]["blob"]), width=140,
         caption=f"QR credential v{bank.db[uid]['version']}")

st.divider()

# ───────────────────────── Step 1 ───────────────────────────────────────
st.header("Step 1 – User presents ID at kiosk")
entered = st.text_input("Enter SyberKey-ID:", value=uid)

# ───────────────────────── Step 2 ───────────────────────────────────────
if st.button("Build & send signed login packet"):
    if entered not in bank.db:
        st.error("Bank DB has no record for that ID.")
    else:
        pkt = bank.build_packet(entered)
        st.session_state.packet = pkt
        st.session_state.waiting = True
        st.session_state.response = None

if st.session_state.packet:
    st.subheader("Step 2 – Payload sent to SyberKey")
    st.code(json.dumps(st.session_state.packet, indent=2), language="json")

# ───────────────────────── Steps 3-4 ────────────────────────────────────
if st.session_state.waiting:
    st.header("Step 3 – SyberKey validates")
    st.markdown("""
* HMAC signature ✓, timestamp window ✓, QR hash matches active version.  
* Sends push to **SyberKey Mobile App** on user’s device.
""")
    action = st.radio("Step 4 – User action on phone:", ("Approve", "Deny"),
                      horizontal=True)
    if st.button("User responds"):
        ok = (action == "Approve")
        res = sk.handle_login(bank.id, st.session_state.packet, ok)
        st.session_state.response = res
        st.session_state.waiting = False

# ───────────────────────── Steps 5-7 ────────────────────────────────────
if st.session_state.response:
    res = st.session_state.response

    if res.get("status") == "success":
        st.header("Steps 5-6-7 – Decrypt, match, success")
        st.markdown("""
* **Inner decrypt** + **outer decrypt** expose original biometric bytes.  
* SHA-256 hash matches template in Cognito → identity verified.  
* SyberKey returns signed JWT; Bank trusts response & opens session.
""")
        st.success(f"Session token:\n\n`{res['token']}`")

    elif res.get("status") == "qr_revoked":
        st.header("QR credential rotated by SyberKey")
        st.warning("Old QR invalid; Bank auto-updates to new version.")
        bank.store_qr(uid, res["blob"], res["version"])
        st.image(png_from_blob(res["blob"]), width=140,
                 caption=f"New QR credential v{res['version']}")
        st.info("Repeat Step 1 & Step 2 to log in with fresh credential.")

    else:
        st.header("Login failed")
        st.error(f"SyberKey error: {res['status']}")

    st.session_state.response = None

st.write("---")
st.caption("All crypto is illustrative. Replace toy AES/Base64 with AES-GCM & RSA-OAEP for production.")
