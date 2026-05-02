import streamlit as st
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO

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

    fh.seek(0)
    raw = fh.getvalue()

    encodings = ["utf-8", "cp1252", "latin1"]
    seps = [",", ";", "\t", "|"]

    for enc in encodings:
        for sep in seps:
            try:
                text = raw.decode(enc)
                return pd.read_csv(
                    BytesIO(text.encode("utf-8")),
                    sep=sep,
                    engine="python",
                    on_bad_lines="skip",
                )
            except (UnicodeDecodeError, pd.errors.ParserError):
                pass

    text = raw.decode("latin1", errors="replace")
    return pd.read_csv(
        BytesIO(text.encode("utf-8")),
        sep=",",
        engine="python",
        on_bad_lines="skip",
    )

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
