import streamlit as st
import pandas as pd
import csv
import plotly.express as px
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

    st.divider()
    st.header("Graphics")

    all_cols = df.columns.tolist()
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    text_cols = df.select_dtypes(exclude="number").columns.tolist()

    left, right = st.columns(2)

    with left:
        st.subheader("Bar / Line / Area")
        chart_type = st.selectbox("Chart type", ["Bar", "Line", "Area"], key="chart_type")
        x_col = st.selectbox("X axis", all_cols, key="x_col")

        y_candidates = numeric_cols if numeric_cols else all_cols
        y_col = st.selectbox("Y axis", y_candidates, key="y_col")

        chart_df = df[[x_col, y_col]].dropna().copy()

        if chart_type == "Bar":
            fig = px.bar(chart_df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
        elif chart_type == "Line":
            fig = px.line(chart_df, x=x_col, y=y_col, title=f"{y_col} over {x_col}")
        else:
            fig = px.area(chart_df, x=x_col, y=y_col, title=f"{y_col} over {x_col}")

        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Scatter Plot")
        if len(numeric_cols) >= 2:
            x_scatter = st.selectbox("Scatter X", numeric_cols, index=0, key="scatter_x")
            y_scatter = st.selectbox("Scatter Y", numeric_cols, index=1, key="scatter_y")
            color_col = st.selectbox(
                "Color by",
                ["(none)"] + text_cols,
                key="scatter_color"
            )

            scatter_df = df[[x_scatter, y_scatter] + ([color_col] if color_col != "(none)" else [])].dropna()

            if color_col == "(none)":
                fig2 = px.scatter(scatter_df, x=x_scatter, y=y_scatter, title=f"{x_scatter} vs {y_scatter}")
            else:
                fig2 = px.scatter(
                    scatter_df,
                    x=x_scatter,
                    y=y_scatter,
                    color=color_col,
                    title=f"{x_scatter} vs {y_scatter}"
                )

            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Need at least two numeric columns for a scatter plot.")

    st.divider()
    st.header("Summary Charts")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Column Counts")
        count_col = st.selectbox(
            "Choose a category column",
            text_cols if text_cols else all_cols,
            key="count_col"
        )
        counts = df[count_col].astype(str).value_counts().head(20).reset_index()
        counts.columns = [count_col, "Count"]
        fig3 = px.bar(counts, x=count_col, y="Count", title=f"Top 20 values in {count_col}")
        st.plotly_chart(fig3, use_container_width=True)

    with c2:
        st.subheader("Numeric Summary")
        if numeric_cols:
            summary_col = st.selectbox("Choose numeric column", numeric_cols, key="summary_col")
            fig4 = px.histogram(df, x=summary_col, nbins=30, title=f"Distribution of {summary_col}")
            st.plotly_chart(fig4, use_container_width=True)
        else:
            st.info("No numeric columns found for histogram.")

except KeyError:
    st.error(
        'Missing secret: add your `[gcp_service_account]` block to Streamlit Cloud → App settings → Secrets.'
    )

except Exception as e:
    st.error("Could not load the CSV from Google Drive.")
    st.exception(e)
