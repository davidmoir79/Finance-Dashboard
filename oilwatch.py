import streamlit as st
import pandas as pd
import csv
import os
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO, StringIO

st.set_page_config(page_title="Oilwatch Financial Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 1.5rem;}
    .hero {
        padding: 1rem 1.25rem;
        border-radius: 18px;
        background: linear-gradient(90deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 10px 28px rgba(0,0,0,0.18);
    }
    .hero h1 {margin: 0; font-size: 2.2rem; font-weight: 800;}
    .hero p {margin: 0.25rem 0 0 0; opacity: 0.9;}
    .section-title {
        font-size: 1.25rem;
        font-weight: 700;
        margin-top: 0.75rem;
        margin-bottom: 0.25rem;
        color: #0f172a;
    }
    div[data-testid="metric-container"] {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 0.75rem 0.85rem;
        border-radius: 14px;
        box-shadow: 0 2px 10px rgba(15,23,42,0.04);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="hero">
        <h1>🛢️ Oilwatch Financial Dashboard</h1>
        <p>Sales overview, monthly trends, and customer analysis.</p>
    </div>
    """,
    unsafe_allow_html=True
)

FILE_ID = "1KEbgg2u3FSMRIMcrEBTDeYW0qzTnpICH"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

COMPANY_MAP = {
    "Lube Oil Lab": ["TBY", "Lube Oil Lab", "Oilwatch Transformer Services"],
    "Transformer Oil Lab": ["TFM", "Transformer Oil Lab", "Oilwatch Lubricating Laboratory"]
}

MONTH_MAP = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

def fmt_rand(value):
    try:
        return f"R{float(value):,.2f}"
    except:
        return "R0.00"

def millions_formatter(x, pos):
    if pd.isna(x):
        return ""
    if abs(x) >= 1000000:
        return f"R{x/1000000:.1f}m"
    return f"R{x:,.0f}"

def clean_sales(value):
    if pd.isna(value):
        return 0.0
    s = str(value).strip().lower()
    if s == "":
        return 0.0
    s = s.replace("r", "").replace(" ", "").replace("\\u00a0", "")
    mult = 1.0
    if s.endswith("m"):
        mult = 1000000.0
        s = s[:-1]
    elif s.endswith("k"):
        mult = 1000.0
        s = s[:-1]
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = "".join(parts)
        else:
            s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = "".join(parts)
    try:
        return float(s) * mult
    except:
        return 0.0

@st.cache_data(ttl=600)
def load_data_from_drive():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=SCOPES,
    )
    service = build("drive", "v3", credentials=creds)
    request = service.files().get_media(fileId=FILE_ID)

    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    raw = fh.getvalue()
    encodings = ["utf-8", "cp1252", "latin1", "iso-8859-1"]

    for enc in encodings:
        try:
            text = raw.decode(enc)
            sample = "\n".join(text.splitlines()[:30])
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|"])
                sep = dialect.delimiter
            except Exception:
                sep = ";"
            df = pd.read_csv(StringIO(text), engine="python", sep=sep, on_bad_lines="skip")
            break
        except UnicodeDecodeError:
            df = None
            continue

    if df is None or df.empty:
        return pd.DataFrame(columns=["Date", "Montly Sales", "Company", "Customer Name"])

    df.columns = [c.strip() for c in df.columns]

    if "Montly Sales" not in df.columns:
        for c in df.columns:
            if "Montly Sales" in c:
                df = df.rename(columns={c: "Montly Sales"})
                break

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    else:
        df["Date"] = pd.NaT

    if "Montly Sales" in df.columns:
        df["Montly Sales"] = df["Montly Sales"].apply(clean_sales)
    else:
        df["Montly Sales"] = 0.0

    if "Company" not in df.columns:
        df["Company"] = ""
    if "Customer Name" not in df.columns:
        df["Customer Name"] = ""

    df = df[["Date", "Montly Sales", "Company", "Customer Name"]]
    return df.dropna(subset=["Date"])

def filter_company(df, choice):
    if choice == "Combined":
        return df[df["Company"].isin(sum(COMPANY_MAP.values(), []))].copy()
    if choice in COMPANY_MAP:
        return df[df["Company"].isin(COMPANY_MAP[choice])].copy()
    return df[df["Company"] == choice].copy()

def money_frame(df):
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_numeric_dtype(out[c]):
            if c not in ["Year", "Months_With_Data", "MonthNum", "Rank"]:
                out[c] = out[c].apply(fmt_rand)
    if "Growth %" in out.columns:
        out["Growth %"] = out["Growth %"].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    return out

def month_bounds(year, month):
    start = datetime(year, month, 1)
    if month == 12:
        end = datetime(year, 12, 31)
    else:
        end = datetime(year, month + 1, 1) - timedelta(days=1)
    return start, end

def last_month_bounds(now):
    first_this_month = datetime(now.year, now.month, 1)
    last_day_last_month = first_this_month - timedelta(days=1)
    return month_bounds(last_day_last_month.year, last_day_last_month.month)

def selected_range_label(start, end):
    return f"{start:%d %b %Y} to {end:%d %b %Y}"

def yearly_avg_frame(df):
    yearly_avg = (
        df.groupby("Year", as_index=False)
        .agg(Yearly_Total=("Montly Sales", "sum"), Months_With_Data=("MonthNum", "nunique"))
        .sort_values("Year")
    )
    yearly_avg["Average_Monthly_Sales"] = yearly_avg["Yearly_Total"] / yearly_avg["Months_With_Data"]
    return yearly_avg

def plot_yearly_growth(df):
    if df.empty:
        st.info("No data.")
        return
    yearly_avg = yearly_avg_frame(df)
    yearly_avg["Growth %"] = yearly_avg["Average_Monthly_Sales"].pct_change() * 100

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(yearly_avg["Year"], yearly_avg["Growth %"], marker="o", linewidth=2, color="#1f77b4")
    ax.axhline(0, color="gray", linewidth=1)
    ax.set_title("Yearly Growth Rate Based on Average Monthly Sales", fontsize=11)
    ax.set_xlabel("Year", fontsize=9)
    ax.set_ylabel("Growth %", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(True, alpha=0.25)

    for x, y in zip(yearly_avg["Year"], yearly_avg["Growth %"]):
        if pd.notna(y):
            ax.annotate(f"{y:.1f}%", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)

    st.pyplot(fig, clear_figure=True)

    display = yearly_avg.copy()
    display["Average_Monthly_Sales"] = display["Average_Monthly_Sales"].apply(fmt_rand)
    display["Growth %"] = display["Growth %"].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "")
    st.dataframe(display[["Year", "Average_Monthly_Sales", "Growth %"]], use_container_width=True, hide_index=True)

def plot_yearly_total_sales(df):
    if df.empty:
        st.info("No data.")
        return
    yearly_total = (
        df.groupby("Year", as_index=False)
        .agg(Yearly_Total_Sales=("Montly Sales", "sum"))
        .sort_values("Year")
    )

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(yearly_total["Year"], yearly_total["Yearly_Total_Sales"], marker="o", linewidth=2, color="#2ca02c")
    ax.set_title("Yearly Total Sales", fontsize=11)
    ax.set_xlabel("Year", fontsize=9)
    ax.set_ylabel("Rand (millions)", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(True, alpha=0.25)
    ax.yaxis.set_major_formatter(FuncFormatter(millions_formatter))
    ax.yaxis.offsetText.set_visible(False)

    for x, y in zip(yearly_total["Year"], yearly_total["Yearly_Total_Sales"]):
        label = f"R{y/1000000:.1f}m" if abs(y) >= 1000000 else f"R{y:,.0f}"
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)

    st.pyplot(fig, clear_figure=True)

    display = yearly_total.copy()
    display["Yearly_Total_Sales"] = display["Yearly_Total_Sales"].apply(fmt_rand)
    st.dataframe(display, use_container_width=True, hide_index=True)

def plot_yearly_average_monthly_sales(df):
    if df.empty:
        st.info("No data.")
        return
    yearly_avg = yearly_avg_frame(df)

    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.plot(yearly_avg["Year"], yearly_avg["Average_Monthly_Sales"], marker="o", linewidth=2, color="#ff7f0e")
    ax.set_title("Yearly Average Monthly Sales", fontsize=11)
    ax.set_xlabel("Year", fontsize=9)
    ax.set_ylabel("Rand (millions)", fontsize=9)
    ax.tick_params(axis="both", labelsize=8)
    ax.grid(True, alpha=0.25)
    ax.yaxis.set_major_formatter(FuncFormatter(millions_formatter))
    ax.yaxis.offsetText.set_visible(False)

    for x, y in zip(yearly_avg["Year"], yearly_avg["Average_Monthly_Sales"]):
        label = f"R{y/1000000:.1f}m" if abs(y) >= 1000000 else f"R{y:,.0f}"
        ax.annotate(label, (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=8)

    st.pyplot(fig, clear_figure=True)

    display = yearly_avg.copy()
    display["Yearly_Total"] = display["Yearly_Total"].apply(fmt_rand)
    display["Average_Monthly_Sales"] = display["Average_Monthly_Sales"].apply(fmt_rand)
    st.dataframe(display[["Year", "Yearly_Total", "Average_Monthly_Sales"]], use_container_width=True, hide_index=True)

def show_grouped_bar_last_3_years(comp_df, title):
    st.markdown(f"### {title}")
    if comp_df.empty:
        st.info("No data.")
        return
    latest_year = int(comp_df["Year"].max())
    last_3_years = [latest_year - 2, latest_year - 1, latest_year]
    filtered = comp_df[comp_df["Year"].isin(last_3_years)].copy()

    monthly = filtered.groupby(["MonthNum", "Year"], as_index=False)["Montly Sales"].sum()
    pivot = monthly.pivot(index="MonthNum", columns="Year", values="Montly Sales").reindex(range(1, 13))
    pivot.index = [MONTH_MAP[i] for i in pivot.index]

    fig, ax = plt.subplots(figsize=(11, 4))
    pivot.plot(kind="bar", ax=ax, width=0.85)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Month", fontsize=9)
    ax.set_ylabel("Sales (Rand)", fontsize=9)
    ax.set_title(title, fontsize=11)
    ax.tick_params(axis="x", labelsize=8)
    ax.tick_params(axis="y", labelsize=8)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.2)
    ax.yaxis.set_major_formatter(FuncFormatter(millions_formatter))
    ax.yaxis.offsetText.set_visible(False)
    st.pyplot(fig, clear_figure=True)

if "df" not in st.session_state:
    st.session_state.df = load_data_from_drive()

st.sidebar.success(f"Rows loaded: {len(st.session_state.df)}")
sidebar_company_choice = st.sidebar.selectbox("Company View", ["Combined", "Transformer Oil Lab", "Lube Oil Lab"])

tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🏆 Top Customers", "📁 Data"])

with tab1:
    st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)
    if st.session_state.df.empty:
        st.info("No data loaded.")
    else:
        df = st.session_state.df.copy()
        df["Year"] = df["Date"].dt.year
        df["MonthNum"] = df["Date"].dt.month
        df["Month"] = df["Date"].dt.strftime("%b")

        now = datetime.now()
        shifted_current = now.replace(day=1) - timedelta(days=1)
        shifted_last = shifted_current.replace(day=1) - timedelta(days=1)

        current_year = now.year
        cur_start, cur_end = month_bounds(shifted_current.year, shifted_current.month)
        last_start, last_end = month_bounds(shifted_last.year, shifted_last.month)
        year_start = datetime(current_year, 1, 1)
        year_end = datetime(current_year, 12, 31)

        company_choice = sidebar_company_choice

        view_df = filter_company(df, company_choice)
        view_current_month = view_df[(view_df["Date"] >= cur_start) & (view_df["Date"] <= cur_end)]
        view_last_month = view_df[(view_df["Date"] >= last_start) & (view_df["Date"] <= last_end)]
        view_current_year = view_df[(view_df["Date"] >= year_start) & (view_df["Date"] <= year_end)]
        view_total = view_df[(view_df["Date"].dt.year >= 2018) & (view_df["Date"].dt.year <= 2026)]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current Month Sales", fmt_rand(view_current_month["Montly Sales"].sum()), selected_range_label(cur_start, cur_end))
        m2.metric("Last Month Sales", fmt_rand(view_last_month["Montly Sales"].sum()), selected_range_label(last_start, last_end))
        m3.metric("Current Year Sales", fmt_rand(view_current_year["Montly Sales"].sum()), f"{year_start:%d %b %Y} to {year_end:%d %b %Y}")
        m4.metric("Sales 2018-2026", fmt_rand(view_total["Montly Sales"].sum()), "All included years")

        st.markdown('<div class="section-title">Yearly Growth Rate</div>', unsafe_allow_html=True)
        plot_yearly_growth(view_df)

        st.markdown('<div class="section-title">Yearly Total Sales</div>', unsafe_allow_html=True)
        plot_yearly_total_sales(view_df)

        st.markdown('<div class="section-title">Yearly Average Monthly Sales</div>', unsafe_allow_html=True)
        plot_yearly_average_monthly_sales(view_df)

        st.markdown('<div class="section-title">Monthly Sales by Year - Last 3 Years</div>', unsafe_allow_html=True)
        if company_choice == "Combined":
            cols = st.columns(2)
            with cols[0]:
                show_grouped_bar_last_3_years(view_df[view_df["Company"].isin(COMPANY_MAP["Lube Oil Lab"])], "Lube Oil Lab")
            with cols[1]:
                show_grouped_bar_last_3_years(view_df[view_df["Company"].isin(COMPANY_MAP["Transformer Oil Lab"])], "Transformer Oil Lab")
        else:
            show_grouped_bar_last_3_years(view_df, company_choice)

        st.markdown('<div class="section-title">Recent Records</div>', unsafe_allow_html=True)
        st.dataframe(money_frame(view_df.tail(20)), use_container_width=True, hide_index=True)

with tab2:
    st.markdown('<div class="section-title">Top Customers</div>', unsafe_allow_html=True)
    if st.session_state.df.empty:
        st.info("No data loaded.")
    else:
        top_choice = st.selectbox("View Customers For", ["Combined", "Lube Oil Lab", "Transformer Oil Lab", "All Companies"])

        if top_choice == "All Companies":
            view_df2 = st.session_state.df.copy()
        elif top_choice == "Combined":
            view_df2 = st.session_state.df[st.session_state.df["Company"].isin(sum(COMPANY_MAP.values(), []))].copy()
        else:
            view_df2 = st.session_state.df[st.session_state.df["Company"].isin(COMPANY_MAP[top_choice])].copy()

        today = pd.Timestamp.today().normalize()
        start_12 = today - pd.DateOffset(months=12)
        start_24 = today - pd.DateOffset(months=24)
        start_3 = today - pd.DateOffset(months=3)
        start_6 = today - pd.DateOffset(months=6)

        def top_customers_frame(dataframe):
            top = (
                dataframe.groupby("Customer Name", as_index=False)["Montly Sales"]
                .sum()
                .sort_values("Montly Sales", ascending=False)
                .head(30)
                .reset_index(drop=True)
            )
            top.insert(0, "Rank", range(1, len(top) + 1))
            top["Montly Sales"] = top["Montly Sales"].apply(fmt_rand)
            return top

        st.markdown("### All Time Top 30")
        top_all = top_customers_frame(view_df2)
        st.dataframe(top_all, use_container_width=True, hide_index=True)

        st.markdown("### Last 24 Months Top 30")
        view_24 = view_df2[(view_df2["Date"] >= start_24) & (view_df2["Date"] <= today)].copy()
        top_24 = top_customers_frame(view_24)
        st.dataframe(top_24, use_container_width=True, hide_index=True)

        st.markdown("### Last 12 Months Top 30")
        view_12 = view_df2[(view_df2["Date"] >= start_12) & (view_df2["Date"] <= today)].copy()
        top_12 = top_customers_frame(view_12)
        st.dataframe(top_12, use_container_width=True, hide_index=True)

        st.markdown("### Top 5 Customers With the Biggest Drop: Last 3 Months vs Previous 3 Months")
        last_3m = view_df2[(view_df2["Date"] > start_3) & (view_df2["Date"] <= today)].copy()
        prev_3m = view_df2[(view_df2["Date"] > start_6) & (view_df2["Date"] <= start_3)].copy()

        last_3m_sales = last_3m.groupby("Customer Name", as_index=False)["Montly Sales"].sum()
        prev_3m_sales = prev_3m.groupby("Customer Name", as_index=False)["Montly Sales"].sum()

        drop_df = last_3m_sales.merge(prev_3m_sales, on="Customer Name", how="outer", suffixes=("_Last3M", "_Prev3M")).fillna(0)
        drop_df["Drop Value"] = drop_df["Montly Sales_Prev3M"] - drop_df["Montly Sales_Last3M"]
        drop_df["Drop %"] = drop_df.apply(
            lambda r: (r["Drop Value"] / r["Montly Sales_Prev3M"] * 100) if r["Montly Sales_Prev3M"] > 0 else None,
            axis=1
        )

        drop_df = drop_df.sort_values("Drop Value", ascending=False).head(5).reset_index(drop=True)
        drop_df.insert(0, "Rank", range(1, len(drop_df) + 1))

        drop_df["Montly Sales_Last3M"] = drop_df["Montly Sales_Last3M"].apply(fmt_rand)
        drop_df["Montly Sales_Prev3M"] = drop_df["Montly Sales_Prev3M"].apply(fmt_rand)
        drop_df["Drop Value"] = drop_df["Drop Value"].apply(fmt_rand)
        drop_df["Drop %"] = drop_df["Drop %"].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "")

        st.dataframe(
            drop_df[[
                "Rank",
                "Customer Name",
                "Montly Sales_Prev3M",
                "Montly Sales_Last3M",
                "Drop Value",
                "Drop %"
            ]],
            use_container_width=True,
            hide_index=True
        )

        if not top_all.empty:
            plot_df = view_df2.groupby("Customer Name", as_index=False)["Montly Sales"].sum().sort_values("Montly Sales", ascending=True).tail(30)
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.barh(plot_df["Customer Name"], plot_df["Montly Sales"])
            ax.set_title("Top Customers")
            ax.set_xlabel("Rand")
            ax.tick_params(axis="y", labelsize=8)
            ax.tick_params(axis="x", labelsize=8)
            ax.grid(axis="x", alpha=0.25)
            ax.xaxis.set_major_formatter(FuncFormatter(millions_formatter))
            ax.xaxis.offsetText.set_visible(False)
            st.pyplot(fig, clear_figure=True)

with tab3:
    st.markdown('<div class="section-title">Data File</div>', unsafe_allow_html=True)
    st.write("Database file loaded from Google Drive.")
    st.dataframe(money_frame(st.session_state.df), use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("All amounts displayed in Rand.")
