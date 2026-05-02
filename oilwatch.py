import streamlit as st
st.set_page_config(page_title="Finance Dashboard", layout="wide")

import pandas as pd
from io import BytesIO
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

FILE_ID = "1GkqTgjGceWKS7xAo8uA3hcROwj3o_OCy"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

@st.cache_data(ttl=600)
def load_csv_from_drive(file_id):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    request = service.files().get_media(fileId=file_id)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_csv(fh)

st.title("Finance Dashboard")
st.write("Loading financial data from Google Drive...")

try:
    df = load_csv_from_drive(FILE_ID)
    st.success("CSV loaded from Google Drive.")
    st.dataframe(df, use_container_width=True)
except Exception as e:
    st.error("Could not load the CSV from Google Drive.")
    st.exception(e)
