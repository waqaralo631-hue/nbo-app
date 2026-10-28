import streamlit as st
from curl_cffi import requests

st.title("NBO Bank Lookup Tool")

user_input = st.text_input("Enter ID or Account Number:")

if st.button("Lookup"):
    if user_input:
        with st.spinner("Searching..."):
            try:
                # Yahan apna curl_cffi request ka code lagayein
                st.success(f"Successfully processed: {user_input}")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Please enter a valid value.")
