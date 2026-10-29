import csv
import json
import pandas as pd
import requests
import streamlit as st
import urllib3

# Disable insecure HTTPS warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

st.set_page_config(
    page_title="NBO & ROP Lookup Tool", page_icon="📱", layout="wide"
)

# Initialize session state for history
if "lookup_results" not in st.session_state:
  st.session_state.lookup_results = []

st.title("🏦 NBO & ROP Live Lookup Tool")
st.write(
    "ID enter karein, live mobile number dekhein, aur CSV file mein save"
    " karein."
)

# Input Form
with st.form("lookup_form"):
  civil_id = st.text_input("Enter ID or Account Number:")
  submit_btn = st.form_submit_button("Lookup")

if submit_btn and civil_id:
  host = "5.37.58.147"
  url = f"https://{host}/nrsPhone"
  payload = {"civilId": civil_id.strip()}
  headers = {
      "host": host,
      "content-type": "application/json",
      "accept-encoding": "gzip",
      "user-agent": "Dart/3.9 (dart:io)",
  }

  try:
    session = requests.Session()
    session.verify = False
    resp = session.post(url, json=payload, headers=headers, timeout=10)
    data = json.loads(resp.text.strip())

    mobile_info = data.get("mobile", {})
    if mobile_info:
      mobile_str = ", ".join(list(mobile_info.keys()))
      st.success(f"Successfully processed ID: {civil_id}")
      st.markdown(f"### 📱 Live Mobile Number: `{mobile_str}`")

      # Add to session history if not already added
      entry = {"ID": civil_id.strip(), "Mobile": mobile_str}
      if entry not in st.session_state.lookup_results:
        st.session_state.lookup_results.append(entry)
    else:
      st.warning(f"No mobile number found for ID: {civil_id}")
  except Exception as e:
    st.error(f"Error fetching data: {str(e)}")

# Display History and CSV Export
if st.session_state.lookup_results:
  st.markdown("---")
  st.subheader("📊 Saved Records & CSV Export")

  df = pd.DataFrame(st.session_state.lookup_results)
  st.dataframe(df, use_container_width=True)

  # CSV Download Button
  csv_data = df.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Download CSV File",
      data=csv_data,
      file_name="lookup_results.csv",
      mime="text/csv",
  )

  if st.button("Clear History"):
    st.session_state.lookup_results = []
    st.rerun()
