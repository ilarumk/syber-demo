# app.py  – descriptive Streamlit walkthrough

import streamlit as st, qrcode, io, uuid, json, pathlib
from syber_core import SyberKey, Bank

st.set_page_config(page_title="SyberKey ↔︎ Bank End-to-End Demo",
                   layout="centered", initial_sidebar_state="collapsed")

# ── optional sidebar docs ───────────────────────────────────────────────
readme = pathlib.Path(__file__).with_name("README.md")
if readme.exists():
    with st.sidebar:
        st.title("Read-Me / Patent Notes")
        st.markdown(readme.read_text())

# ── initialise IdP and Bank once per session ────────────────────────────
if "sk" not in st.session_state:
    sk   = SyberKey()
    bank = Bank("XYZ_BANK", sk)

    # create a demo user with a random UUID
    uid = str(uuid.uuid4())
    first = sk.enroll(uid, "fingerprint-v1")          # QR version 1
    bank.store_qr(uid, first["blob"], first["version"])

    st.session_state.update(
        sk=sk, bank=bank, uid=uid,
        current_ver=first["version"],
        waiting_for_push=False,
        packet=None,
        result=None
    )

sk, bank, uid = st.session_state.sk, st.session_state.bank, st.session_state.uid

def qr_png(blob):
    buf = io.BytesIO(); qrcode.make(blob).save(buf)
    return buf.getvalue()

# ─────────────────────────────────── STEP 0 ──────────────────────────────────
st.header("Step 0 – Initial Registration")
st.markdown(
"""
* SyberKey captures the user’s biometric sample (simulated by the string `fingerprint-v1`).  
* SyberKey double-encrypts the sample (toy AES, then Base64) and embeds it into QR **version 1**.  
* The Bank stores that opaque QR blob; it never sees the raw biometric.  
""")
st.write(f"**User’s SyberKey-ID (UUID)**: `{uid}`")
st.image(qr_png(bank.db[uid]["blob"]),
         caption=f"QR credential • version {bank.db[uid]['version']}",
         width=140)

st.divider()

# ─────────────────────────────────── STEP 1 ──────────────────────────────────
st.header("Step 1 – User presents SyberKey-ID to the Bank kiosk")
user_id = st.text_input(
    "Operator types the SyberKey-ID shown above into the kiosk:",
    value=uid
)

# ─────────────────────────────────── STEP 2 ──────────────────────────────────
if st.button("Create and send signed login packet"):
    if user_id not in bank.db:
        st.error("The Bank has no record of that ID.")
    else:
        st.session_state.packet = bank.build_packet(user_id)
        st.session_state.waiting_for_push = True
        st.session_state.result = None

# show the packet content
if st.session_state.packet:
    st.subheader("Step 2 – Bank → SyberKey  •  Signed JSON payload")
    st.markdown(
        """
        * Bank retrieves the stored QR.  
        * Bank creates `timestamp` and `nonce` fields.  
        * Bank signs the entire `payload` with its HMAC key so SyberKey can verify authenticity.
        """
    )
    st.code(json.dumps(st.session_state.packet, indent=2), language="json")

# ────────────────────────────────── STEPS 3 & 4 ─────────────────────────────
if st.session_state.waiting_for_push:
    st.header("Step 3 – SyberKey validates the packet")

    st.markdown(
        """
        * Verifies HMAC signature using the shared secret issued during onboarding.  
        * Confirms the timestamp is within the acceptable window (30 s).  
        * Confirms the QR blob matches the **active** version stored for this user.  
        * If all checks succeed, SyberKey sends a push notification to the user’s phone/watch.
        """
    )

    choice = st.radio("Step 4 – User action on push notification:",
                      ("Approve login", "Deny login"), horizontal=True)
    if st.button("User responds"):
        approved = (choice == "Approve login")
        response = sk.handle_login(bank.id,
                                   st.session_state.packet,
                                   approved)
        st.session_state.result = response
        st.session_state.waiting_for_push = False

# ───────────────────────────────── STEPS 5 - 7 ──────────────────────────────
if st.session_state.result:
    res = st.session_state.result

    if res.get("status") == "success":
        st.header("Steps 5-6-7 – Decryption, biometric match, and success response")
        st.markdown(
            """
            * **Inner decryption** (toy AES) and **outer decryption** (Base64) expose the
              original biometric bytes.  
            * SHA-256 hash of decrypted bytes matches the stored template → user identity verified.  
            * SyberKey returns `{status: success, user_token: JWT-like value}`.  
            * Bank trusts this response and opens the user’s session.
            """
        )
        st.success(f"Session token: `{res['token']}`")

    elif res.get("status") == "qr_revoked":
        st.header("QR credential was rotated by SyberKey")
        st.warning(
            "SyberKey rejects the old QR (perhaps the user re-enrolled or a periodic "
            "rotation policy triggered). Bank now downloads the **new active QR**."
        )
        bank.store_qr(uid, res["blob"], res["version"])
        st.image(qr_png(res["blob"]), width=140,
                 caption=f"New QR credential • version {res['version']}")
        st.info("Repeat Step 1 → Step 2 to log in with the new QR.")

    else:
        st.header("Login failed")
        st.error(f"Failure reason reported by SyberKey: **{res['status']}**")

    st.session_state.result = None   # clear after display

st.write("---")
st.caption("All cryptography in this demo is illustrative. Replace toy functions with AES-GCM and RSA-OAEP in production.")
