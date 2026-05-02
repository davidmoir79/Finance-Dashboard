import streamlit as st
import pandas as pd
import csv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO, StringIO

FILE_ID = "1KEbgg2u3FSMRIMcrEBTDeYW0qzTnpICH"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

st.set_page_config(page_title="Finance Dashboard", layout="wide")
st.title("Finance Dashboard")

@st.cache_data(ttl=600)
def load_csv_from_drive(file_id: str) -> pd.DataFrame:
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )

    service = build("drive", "v3", credentials=creds)
    request = service.files().get_media(fileId=file_id)

    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    raw = fh.getvalue()
    encodings = ["utf-8", "cp1252", "latin1"]

    for enc in encodings:
        try:
            text = raw.decode(enc)
            sample = "\n".join(text.splitlines()[:30])
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
                sep = dialect.delimiter
            except Exception:
                sep = None

            if sep is None:
                return pd.read_csv(StringIO(text), engine="python", sep=None, on_bad_lines="skip")
            else:
                return pd.read_csv(StringIO(text), engine="python", sep=sep, on_bad_lines="skip")
        except UnicodeDecodeError:
            continue

    text = raw.decode("latin1", errors="replace")
    return pd.read_csv(StringIO(text), engine="python", sep=None, on_bad_lines="skip")


st.write("Loading financial data from Google Drive...")

try:
    df = load_csv_from_drive(FILE_ID)
    st.success(f"CSV loaded successfully. Rows: {len(df):,} | Columns: {len(df.columns):,}")
    st.dataframe(df, use_container_width=True)

except KeyError:
    st.error(
        'Missing secret: add your `[gcp_service_account]` block to Streamlit Cloud → App settings → Secrets.'
    )

except Exception as e:
    st.error("Could not load the CSV from Google Drive.")
    st.exception(e)
