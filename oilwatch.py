import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO

# Google Drive file ID from:
# https://drive.google.com/file/d/1KEbgg2u3FSMRIMcrEBTDeYW0qzTnpICH/view
FILE_ID = "1KEbgg2u3FSMRIMcrEBTDeYW0qzTnpICH"

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("Finance Dashboard")

@st.cache_data(ttl=600)
def load_csv_from_drive(file_id: str) -> pd.DataFrame:
    # Build credentials from Streamlit secrets
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )

    # Build Drive service
    service = build("drive", "v3", credentials=creds)

    # Download file content
    request = service.files().get_media(fileId=file_id)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    # Go back to start of buffer
    fh.seek(0)

    # Try UTF‑8 first, then fall back to latin1 for Windows/Excel CSVs
    try:
        return pd.read_csv(fh)
    except UnicodeDecodeError:
        fh.seek(0)
        return pd.read_csv(fh, encoding="latin1")


st.write("Loading financial data from Google Drive...")

try:
    df = load_csv_from_drive(FILE_ID)
    st.success("CSV loaded successfully.")
    st.dataframe(df, use_container_width=True)

except KeyError:
    st.error(
        'Missing secret: add your `[gcp_service_account]` block to Streamlit Cloud → '
        'App settings → Secrets.'
    )

except Exception as e:
    st.error("Could not load the CSV from Google Drive.")
    st.exception(e)
