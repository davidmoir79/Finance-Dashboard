import streamlit as st
import pandas as pd
import csv
import os

from datetime import datetime, timedelta
from io import BytesIO, StringIO

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


# ==========================================================
# PAGE SETTINGS
# ==========================================================

st.set_page_config(
    page_title="Transformer Oil Lab Dashboard",
    layout="wide"
)

st.markdown("""
<style>

.main .block-container{
    padding-top:1.5rem;
    padding-bottom:1.5rem;
}

.hero{
    padding:1rem;
    border-radius:18px;
    background:linear-gradient(90deg,#0f172a,#1e3a8a,#2563eb);
    color:white;
    margin-bottom:1rem;
}

.hero h1{
    margin:0;
}

.section-title{
    font-size:1.25rem;
    font-weight:700;
    margin-top:1rem;
}

div[data-testid="metric-container"]{
    background:#f8fafc;
    border:1px solid #e2e8f0;
    border-radius:14px;
    padding:0.8rem;
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
<h1>🛢️ Transformer Oil Lab Dashboard</h1>
<p>Sales overview and customer analytics</p>
</div>
""", unsafe_allow_html=True)
# ==========================================================
# GOOGLE DRIVE SETTINGS
# ==========================================================

FILE_ID = "1KEbgg2u3FSMRIMcrEBTDeYW0qzTnpICH"

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly"
]


MONTH_MAP = {
    1:"Jan",
    2:"Feb",
    3:"Mar",
    4:"Apr",
    5:"May",
    6:"Jun",
    7:"Jul",
    8:"Aug",
    9:"Sep",
    10:"Oct",
    11:"Nov",
    12:"Dec"
}


TRANSFORMER_CODES = [
    "TFM",
    "Transformer Oil Lab",
    "Oilwatch Lubricating Laboratory"
]def fmt_rand(value):

    try:
        return f"R{float(value):,.2f}"

    except:
        return "R0.00"


def millions_formatter(x,pos):

    if abs(x)>=1000000:
        return f"R{x/1000000:.1f}m"

    return f"R{x:,.0f}"def clean_sales(value):

    if pd.isna(value):
        return 0

    s=str(value).lower().strip()

    negative=False

    if "-" in s or "(" in s:
        negative=True

    s=s.replace("(","")
    s=s.replace(")","")
    s=s.replace("-","")
    s=s.replace("r","")
    s=s.replace(" ","")

    multiplier=1

    if s.endswith("m"):
        multiplier=1000000
        s=s[:-1]

    elif s.endswith("k"):
        multiplier=1000
        s=s[:-1]

    if "," in s and "." in s:

        if s.rfind(".")>s.rfind(","):
            s=s.replace(",","")

        else:
            s=s.replace(".","")
            s=s.replace(",",".")
                try:
        value = float(s) * multiplier

        if negative:
            value = -value

        return value

    except:
        return 0


# ==========================================================
# GOOGLE DRIVE LOADER
# ==========================================================

@st.cache_data(ttl=600)

def load_data():

    try:

        service_account_info = dict(st.secrets["gcp_service_account"])

        service_account_info["private_key"] = (
            service_account_info["private_key"]
            .replace("\\n","\n")
        )

        creds = Credentials.from_service_account_info(
            service_account_info,
            scopes=SCOPES
        )

        service = build(
            "drive",
            "v3",
            credentials=creds
        )

        request = service.files().get_media(fileId=FILE_ID)

        fh = BytesIO()

        downloader = MediaIoBaseDownload(fh, request)

        done = False

        while not done:
            _, done = downloader.next_chunk()

        raw = fh.getvalue()

        text = raw.decode("utf-8", errors="ignore")

        sample = "\n".join(text.splitlines()[:30])

        try:
            dialect = csv.Sniffer().sniff(
                sample,
                delimiters=[",",";","\t","|"]
            )
            sep = dialect.delimiter

        except:
            sep=";"

        df = pd.read_csv(
            StringIO(text),
            sep=sep,
            engine="python",
            on_bad_lines="skip"
        )

    except Exception as e:

        st.error(e)

        return pd.DataFrame()

    df.columns = df.columns.str.strip()

    sales_col = next(
        (c for c in df.columns if "sale" in c.lower()),
        None
    )

    if sales_col:
        df.rename(
            columns={sales_col:"Monthly Sales"},
            inplace=True
        )

    df["Monthly Sales"] = (
        df["Monthly Sales"]
        .apply(clean_sales)
    )

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce"
    )

    df["Company"] = (
        df["Company"]
        .astype(str)
        .str.strip()
    )

    df["Customer Name"] = (
        df["Customer Name"]
        .astype(str)
        .str.strip()
    )

    df = df[
        df["Company"].isin(
            TRANSFORMER_CODES
        )
    ]

    df = df.dropna(subset=["Date"])

    return df.sort_values("Date")
    # ==========================================================
# FILTERS
# ==========================================================

def month_bounds(year, month):

    start = datetime(year, month, 1)

    if month == 12:

        end = datetime(
            year,
            12,
            31,
            23,
            59,
            59
        )

    else:

        end = (
            datetime(year, month + 1, 1)
            - timedelta(seconds=1)
        )

    return start, end


def last_month_bounds(now):

    first_this_month = datetime(
        now.year,
        now.month,
        1
    )

    last_day = first_this_month - timedelta(days=1)

    return month_bounds(
        last_day.year,
        last_day.month
    )


def selected_range_label(start,end):

    return (
        f"{start:%d %b %Y}"
        f" to "
        f"{end:%d %b %Y}"
    )def yearly_average(df):

    out = (
        df.groupby("Year",as_index=False)
        .agg(
            Yearly_Total=("Monthly Sales","sum"),
            Months=("MonthNum","nunique")
        )
        .sort_values("Year")
    )

    out["Average Monthly"] = (
        out["Yearly_Total"] /
        out["Months"]
    )

    return out
    # ==========================================================
# LOAD DATA
# ==========================================================

if "df" not in st.session_state:
    st.session_state.df = load_data()

df = st.session_state.df.copy()

if df.empty:
    st.error("No data could be loaded.")
    st.stop()

# ==========================================================
# PREPARE DATA
# ==========================================================

df["Year"] = df["Date"].dt.year
df["MonthNum"] = df["Date"].dt.month
df["Month"] = df["Date"].dt.strftime("%b")

# ==========================================================
# REPORTING MONTH
# Current Month = Previous Completed Month
# ==========================================================

today = datetime.today()

first_this_month = datetime(
    today.year,
    today.month,
    1
)

report_month = first_this_month - timedelta(days=1)

cur_start, cur_end = month_bounds(
    report_month.year,
    report_month.month
)

last_start, last_end = last_month_bounds(
    report_month
)

current_year = report_month.year

year_start = datetime(
    current_year,
    1,
    1
)

year_end = datetime(
    current_year,
    12,
    31,
    23,
    59,
    59
)

# ==========================================================
# FILTERS
# ==========================================================

current_month = df[
    (df["Date"] >= cur_start) &
    (df["Date"] <= cur_end)
]

last_month = df[
    (df["Date"] >= last_start) &
    (df["Date"] <= last_end)
]

current_year_df = df[
    (df["Date"] >= year_start) &
    (df["Date"] <= year_end)
]

all_sales = df[
    df["Date"].dt.year <= current_year
]

# ==========================================================
# TABS
# ==========================================================

tab1, tab2, tab3 = st.tabs(
    [
        "📊 Dashboard",
        "🏆 Top Customers",
        "📁 Data"
    ]
)with tab1:

    st.markdown(
        '<div class="section-title">Dashboard</div>',
        unsafe_allow_html=True
    )

    c1,c2,c3,c4 = st.columns(4)

    c1.metric(
        "Current Month Sales",
        fmt_rand(
            current_month["Monthly Sales"].sum()
        ),
        selected_range_label(
            cur_start,
            cur_end
        )
    )

    c2.metric(
        "Previous Month Sales",
        fmt_rand(
            last_month["Monthly Sales"].sum()
        ),
        selected_range_label(
            last_start,
            last_end
        )
    )

    c3.metric(
        "Current Year Sales",
        fmt_rand(
            current_year_df["Monthly Sales"].sum()
        ),
        str(current_year)
    )

    c4.metric(
        "Total Sales",
        fmt_rand(
            all_sales["Monthly Sales"].sum()
        ),
        "All Years"
    )    yearly = (
        df.groupby("Year",as_index=False)
        .agg(
            Sales=("Monthly Sales","sum")
        )
        .sort_values("Year")
    )

    st.markdown(
        "### Yearly Sales"
    )

    fig,ax = plt.subplots(
        figsize=(10,4)
    )

    ax.plot(
        yearly["Year"],
        yearly["Sales"],
        marker="o",
        linewidth=2
    )

    ax.grid(True)

    ax.set_xlabel("Year")
    ax.set_ylabel("Sales")

    ax.yaxis.set_major_formatter(
        FuncFormatter(
            millions_formatter
        )
    )

    st.pyplot(fig)

    plt.close(fig)
        avg = yearly_average(df)

    st.markdown(
        "### Average Monthly Sales"
    )

    fig,ax = plt.subplots(
        figsize=(10,4)
    )

    ax.plot(
        avg["Year"],
        avg["Average Monthly"],
        marker="o",
        linewidth=2,
        color="orange"
    )

    ax.grid(True)

    ax.yaxis.set_major_formatter(
        FuncFormatter(
            millions_formatter
        )
    )

    st.pyplot(fig)

    plt.close(fig)
    st.markdown(
        "### Recent Records"
    )

    recent = (
        df.sort_values(
            "Date",
            ascending=False
        )
        .head(20)
    )

    st.dataframe(
        recent,
        use_container_width=True,
        hide_index=True
    )
# ==========================================================
# TOP CUSTOMERS
# ==========================================================

with tab2:

    st.markdown(
        '<div class="section-title">Top Customers</div>',
        unsafe_allow_html=True
    )

    report_date = pd.Timestamp(report_month)

    start_24 = report_date - pd.DateOffset(months=24)
    start_12 = report_date - pd.DateOffset(months=12)
    start_6  = report_date - pd.DateOffset(months=6)
    start_3  = report_date - pd.DateOffset(months=3)

    # ------------------------------------------------------
    # Helper
    # ------------------------------------------------------

    def top_customers_frame(data):

        top = (
            data.groupby("Customer Name", as_index=False)
            ["Monthly Sales"]
            .sum()
            .sort_values(
                "Monthly Sales",
                ascending=False
            )
            .head(30)
            .reset_index(drop=True)
        )

        top.insert(
            0,
            "Rank",
            range(1, len(top)+1)
        )

        return top


    # ------------------------------------------------------
    # All Time
    # ------------------------------------------------------

    st.subheader("Top 30 Customers - All Time")

    top_all = top_customers_frame(df)

    display = top_all.copy()
    display["Monthly Sales"] = display["Monthly Sales"].apply(fmt_rand)

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )


    # ------------------------------------------------------
    # Last 24 Months
    # ------------------------------------------------------

    st.subheader("Top 30 Customers - Last 24 Months")

    last24 = df[
        (df["Date"] >= start_24) &
        (df["Date"] <= report_date)
    ]

    display = top_customers_frame(last24)

    display["Monthly Sales"] = (
        display["Monthly Sales"]
        .apply(fmt_rand)
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )


    # ------------------------------------------------------
    # Last 12 Months
    # ------------------------------------------------------

    st.subheader("Top 30 Customers - Last 12 Months")

    last12 = df[
        (df["Date"] >= start_12) &
        (df["Date"] <= report_date)
    ]

    display = top_customers_frame(last12)

    display["Monthly Sales"] = (
        display["Monthly Sales"]
        .apply(fmt_rand)
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )


    # ------------------------------------------------------
    # Biggest Customer Drops
    # ------------------------------------------------------

    st.subheader(
        "Top 5 Customer Sales Drops"
    )

    current3 = df[
        (df["Date"] > start_3) &
        (df["Date"] <= report_date)
    ]

    previous3 = df[
        (df["Date"] > start_6) &
        (df["Date"] <= start_3)
    ]

    cur = (
        current3
        .groupby(
            "Customer Name",
            as_index=False
        )
        ["Monthly Sales"]
        .sum()
    )

    prev = (
        previous3
        .groupby(
            "Customer Name",
            as_index=False
        )
        ["Monthly Sales"]
        .sum()
    )

    drop = cur.merge(
        prev,
        on="Customer Name",
        how="outer",
        suffixes=(
            "_Current",
            "_Previous"
        )
    ).fillna(0)

    drop["Drop Value"] = (
        drop["Monthly Sales_Previous"]
        -
        drop["Monthly Sales_Current"]
    )

    drop["Drop %"] = drop.apply(
        lambda r:
        (
            r["Drop Value"]
            /
            r["Monthly Sales_Previous"]
            *100
        )
        if r["Monthly Sales_Previous"]>0
        else None,
        axis=1
    )

    drop = (
        drop
        .sort_values(
            "Drop Value",
            ascending=False
        )
        .head(5)
        .reset_index(drop=True)
    )

    drop.insert(
        0,
        "Rank",
        range(1,len(drop)+1)
    )

    display = drop.copy()

    display["Monthly Sales_Current"] = (
        display["Monthly Sales_Current"]
        .apply(fmt_rand)
    )

    display["Monthly Sales_Previous"] = (
        display["Monthly Sales_Previous"]
        .apply(fmt_rand)
    )

    display["Drop Value"] = (
        display["Drop Value"]
        .apply(fmt_rand)
    )

    display["Drop %"] = (
        display["Drop %"]
        .map(
            lambda x:
            f"{x:.1f}%"
            if pd.notna(x)
            else ""
        )
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )


    # ------------------------------------------------------
    # Bar Chart
    # ------------------------------------------------------

    st.subheader("Top Customers Chart")

    chart = (
        top_all
        .sort_values(
            "Monthly Sales",
            ascending=True
        )
    )

    fig, ax = plt.subplots(
        figsize=(10,7)
    )

    ax.barh(
        chart["Customer Name"],
        chart["Monthly Sales"]
    )

    ax.grid(
        axis="x",
        alpha=0.3
    )

    ax.set_xlabel("Sales")

    ax.xaxis.set_major_formatter(
        FuncFormatter(
            millions_formatter
        )
    )

    st.pyplot(fig)

    plt.close(fig)
# ==========================================================
# DATA TAB
# ==========================================================

with tab3:

    st.markdown(
        '<div class="section-title">Transformer Oil Lab Data</div>',
        unsafe_allow_html=True
    )

    st.caption(
        "Live data loaded from Google Drive"
    )

    display = df.copy()

    display["Monthly Sales"] = (
        display["Monthly Sales"]
        .apply(fmt_rand)
    )

    display = display.sort_values(
        "Date",
        ascending=False
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )


# ==========================================================
# DASHBOARD SUMMARY
# ==========================================================

st.markdown("---")

left,right = st.columns(2)

with left:

    st.metric(
        "Records Loaded",
        f"{len(df):,}"
    )

with right:

    st.metric(
        "Customers",
        f"{df['Customer Name'].nunique():,}"
    )


# ==========================================================
# FOOTER
# ==========================================================

st.markdown("---")

st.caption(
    f"""
Transformer Oil Lab Financial Dashboard

Reporting Month:
{report_month.strftime('%B %Y')}

Generated:
{datetime.now().strftime('%d %B %Y %H:%M')}
"""
)
