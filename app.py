import io
import re
import math
import requests
import datetime as dt

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


# ---------------------------------------------------------
# Page configuration
# ---------------------------------------------------------

st.set_page_config(
    page_title="Mutual Fund Portfolio Analyzer",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Mutual Fund Portfolio Analyzer")
st.caption(
    "Estimated portfolio movement based on latest disclosed holdings "
    "and market-price history. This is not the official live NAV."
)


# ---------------------------------------------------------
# Fund configuration
# ---------------------------------------------------------

FUNDS = {
    "Motilal Oswal Active Momentum Fund - Direct Growth": {
        "key": "motilal_oswal_active_momentum",
        "search_name": "Motilal Oswal Active Momentum Fund",
        "amc": "Motilal Oswal Mutual Fund",
    },
    "HDFC Flexi Cap Fund - Direct Growth": {
        "key": "hdfc_flexicap",
        "search_name": "HDFC Flexi Cap Fund",
        "amc": "HDFC Mutual Fund",
    },
}


PERIODS = {
    "Previous Trading Day": 1,
    "Previous Week": 7,
    "Previous Month": 30,
    "Previous 3 Months": 90,
    "Previous 6 Months": 180,
    "Previous 1 Year": 365,
}


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def clean_text(value):
    """Normalize text values."""
    if value is None:
        return ""

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_column_name(value):
    value = clean_text(value).lower()
    value = value.replace("%", "pct")
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def parse_weight(value):
    """Convert values such as '7.25%', '7.25', or 7.25 to percentage."""
    if pd.isna(value):
        return np.nan

    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()

    try:
        number = float(value)
    except Exception:
        return np.nan

    return number


def format_pct(value, decimals=2):
    if value is None or pd.isna(value):
        return "N/A"

    return f"{value:+.{decimals}f}%"


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return np.nan


# ---------------------------------------------------------
# Symbol mapping
# ---------------------------------------------------------

# This mapping can be expanded as more holdings are discovered.
# Yahoo Finance generally uses .NS for NSE-listed stocks and
# .BO for BSE-listed stocks.

SYMBOL_MAP = {
    "RELIANCE INDUSTRIES": "RELIANCE.NS",
    "RELIANCE INDUSTRIES LIMITED": "RELIANCE.NS",
    "HDFC BANK": "HDFCBANK.NS",
    "HDFC BANK LIMITED": "HDFCBANK.NS",
    "ICICI BANK": "ICICIBANK.NS",
    "ICICI BANK LIMITED": "ICICIBANK.NS",
    "STATE BANK OF INDIA": "SBIN.NS",
    "SBI": "SBIN.NS",
    "AXIS BANK": "AXISBANK.NS",
    "KOTAK MAHINDRA BANK": "KOTAKBANK.NS",
    "INFOSYS": "INFY.NS",
    "INFOSYS LIMITED": "INFY.NS",
    "TATA CONSULTANCY SERVICES": "TCS.NS",
    "TCS": "TCS.NS",
    "TATA MOTORS": "TATAMOTORS.NS",
    "TATA MOTORS LIMITED": "TATAMOTORS.NS",
    "TATA STEEL": "TATASTEEL.NS",
    "LARSEN AND TOUBRO": "LT.NS",
    "LARSEN & TOUBRO": "LT.NS",
    "BHARTI AIRTEL": "BHARTIARTL.NS",
    "BHARTI AIRTEL LIMITED": "BHARTIARTL.NS",
    "ITC": "ITC.NS",
    "ITC LIMITED": "ITC.NS",
    "MARUTI SUZUKI INDIA": "MARUTI.NS",
    "MARUTI SUZUKI": "MARUTI.NS",
    "SUN PHARMACEUTICAL": "SUNPHARMA.NS",
    "SUN PHARMACEUTICAL INDUSTRIES": "SUNPHARMA.NS",
    "ADANI ENTERPRISES": "ADANIENT.NS",
    "ADANI PORTS": "ADANIPORTS.NS",
    "NTPC": "NTPC.NS",
    "POWER GRID": "POWERGRID.NS",
    "POWER GRID CORPORATION": "POWERGRID.NS",
    "COAL INDIA": "COALINDIA.NS",
    "HINDUSTAN UNILEVER": "HINDUNILVR.NS",
    "HINDUSTAN UNILEVER LIMITED": "HINDUNILVR.NS",
    "ASIAN PAINTS": "ASIANPAINT.NS",
    "ULTRATECH CEMENT": "ULTRACEMCO.NS",
    "WIPRO": "WIPRO.NS",
    "TECH MAHINDRA": "TECHM.NS",
    "HCL TECHNOLOGIES": "HCLTECH.NS",
    "HCL TECH": "HCLTECH.NS",
    "BAJAJ FINANCE": "BAJFINANCE.NS",
    "BAJAJ FINSERV": "BAJAJFINSV.NS",
    "EICHER MOTORS": "EICHERMOT.NS",
    "M&M": "M&M.NS",
    "MAHINDRA & MAHINDRA": "M&M.NS",
    "DR REDDYS LABORATORIES": "DRREDDY.NS",
    "CIPLA": "CIPLA.NS",
    "DIVIS LABORATORIES": "DIVISLAB.NS",
    "APOLLO HOSPITALS": "APOLLOHOSP.NS",
    "TRENT": "TRENT.NS",
    "BEL": "BEL.NS",
    "BHARAT ELECTRONICS": "BEL.NS",
    "HAL": "HAL.NS",
    "HINDUSTAN AERONAUTICS": "HAL.NS",
    "ZOMATO": "ETERNAL.NS",
    "ETERNAL": "ETERNAL.NS",
    "PERSISTENT SYSTEMS": "PERSISTENT.NS",
    "DIXON TECHNOLOGIES": "DIXON.NS",
    "MAX HEALTHCARE": "MAXHEALTH.NS",
    "JIO FINANCIAL SERVICES": "JIOFIN.NS",
}


def guess_symbol(holding_name):
    """
    Try to map a holding name to a Yahoo Finance symbol.
    Returns None when no reliable mapping is available.
    """
    name = clean_text(holding_name).upper()

    # Exact mapping first
    if name in SYMBOL_MAP:
        return SYMBOL_MAP[name]

    # Remove common legal suffixes
    simplified = name
    for suffix in [
        " LIMITED",
        " LTD",
        " INDIA LIMITED",
        " INDUSTRIES LIMITED",
        " CORPORATION",
        " PLC",
    ]:
        simplified = simplified.replace(suffix, "")

    simplified = simplified.strip()

    if simplified in SYMBOL_MAP:
        return SYMBOL_MAP[simplified]

    # Try a few conservative heuristics
    if "RELIANCE" in simplified:
        return "RELIANCE.NS"

    if "HDFC BANK" in simplified:
        return "HDFCBANK.NS"

    if "ICICI BANK" in simplified:
        return "ICICIBANK.NS"

    if "BHARTI AIRTEL" in simplified:
        return "BHARTIARTL.NS"

    if "TATA CONSULTANCY" in simplified:
        return "TCS.NS"

    if "LARSEN" in simplified and "TOUBRO" in simplified:
        return "LT.NS"

    return None


# ---------------------------------------------------------
# Portfolio data loading
# ---------------------------------------------------------

def create_demo_holdings(fund_key):
    """
    Temporary fallback data.

    This is intentionally labelled as demo data. It is not used
    silently as real portfolio information.
    """
    if fund_key == "motilal_oswal_active_momentum":
        rows = [
            ["Demo holding 1", None, "Equity", 0.0],
        ]
    else:
        rows = [
            ["Demo holding 1", None, "Equity", 0.0],
        ]

    return pd.DataFrame(
        rows,
        columns=["holding_name", "symbol", "asset_type", "weight_pct"],
    )


@st.cache_data(ttl=3600, show_spinner=False)
def load_holdings(fund_key):
    """
    Load holdings.

    The current version uses a safe placeholder until the exact
    official AMC portfolio download URLs are configured.

    We deliberately do not fabricate current holdings or weights.
    """

    # Official portfolio download URLs should be inserted here
    # after confirming their current structure.
    #
    # Example structure:
    #
    # portfolio_urls = {
    #     "motilal_oswal_active_momentum": "...official AMC file...",
    #     "hdfc_flexicap": "...official AMC file...",
    # }
    #
    # The parser will then read the official file.

    holdings = create_demo_holdings(fund_key)

    return holdings


# ---------------------------------------------------------
# Market data
# ---------------------------------------------------------

@st.cache_data(ttl=900, show_spinner=False)
def download_price_history(symbol, period_days=400):
    """
    Download daily price history from Yahoo Finance.
    """
    if not symbol:
        return pd.DataFrame()

    try:
        end_date = dt.date.today() + dt.timedelta(days=1)
        start_date = dt.date.today() - dt.timedelta(days=period_days)

        data = yf.download(
            symbol,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if data is None or data.empty:
            return pd.DataFrame()

        # Handle multi-level columns returned by yfinance
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = [
                column[0] if isinstance(column, tuple) else column
                for column in data.columns
            ]

        data.columns = [str(column).lower() for column in data.columns]

        if "close" not in data.columns:
            return pd.DataFrame()

        result = data[["close"]].copy()
        result = result.dropna()
        result.index = pd.to_datetime(result.index).tz_localize(None)

        return result

    except Exception:
        return pd.DataFrame()


def find_price_on_or_before(price_data, target_date):
    """
    Find the latest available price on or before target_date.
    """
    if price_data is None or price_data.empty:
        return np.nan

    target_date = pd.Timestamp(target_date)

    eligible = price_data.loc[price_data.index <= target_date]

    if eligible.empty:
        return np.nan

    return safe_float(eligible.iloc[-1]["close"])


def calculate_holding_returns(symbol, latest_date=None):
    """
    Calculate historical returns for one holding.
    """
    prices = download_price_history(symbol)

    if prices.empty:
        return {
            period: np.nan
            for period in PERIODS
        }

    if latest_date is None:
        latest_date = prices.index.max()
    else:
        latest_date = pd.Timestamp(latest_date)

    latest_price = find_price_on_or_before(prices, latest_date)

    if pd.isna(latest_price) or latest_price == 0:
        return {
            period: np.nan
            for period in PERIODS
        }

    output = {}

    for period_name, days_back in PERIODS.items():
        target_date = latest_date - pd.Timedelta(days=days_back)
        old_price = find_price_on_or_before(prices, target_date)

        if pd.isna(old_price) or old_price == 0:
            output[period_name] = np.nan
        else:
            output[period_name] = ((latest_price / old_price) - 1) * 100

    return output


# ---------------------------------------------------------
# Portfolio calculations
# ---------------------------------------------------------

def classify_asset_type(row):
    text = " ".join(
        [
            clean_text(row.get("holding_name", "")),
            clean_text(row.get("asset_type", "")),
        ]
    ).lower()

    if any(word in text for word in ["cash", "cash balance", "net current asset"]):
        return "Cash"

    if any(
        word in text
        for word in [
            "bond",
            "debenture",
            "gilt",
            "treasury",
            "t-bill",
            "government security",
            "certificate of deposit",
            "commercial paper",
            "debt",
        ]
    ):
        return "Debt"

    if any(word in text for word in ["reit", "invit"]):
        return "REIT/InvIT"

    if any(word in text for word in ["etf", "mutual fund", "fund"]):
        return "Fund/ETF"

    return clean_text(row.get("asset_type", "")) or "Equity"


def calculate_analysis(holdings):
    """
    Calculate stock-level returns and weighted contributions.
    """
    if holdings is None or holdings.empty:
        return pd.DataFrame(), {}

    data = holdings.copy()

    required_columns = [
        "holding_name",
        "symbol",
        "asset_type",
        "weight_pct",
    ]

    for column in required_columns:
        if column not in data.columns:
            data[column] = None

    data["holding_name"] = data["holding_name"].apply(clean_text)
    data["asset_type"] = data.apply(classify_asset_type, axis=1)
    data["weight_pct"] = data["weight_pct"].apply(parse_weight)

    data["symbol"] = data.apply(
        lambda row: row["symbol"]
        if clean_text(row["symbol"])
        else guess_symbol(row["holding_name"]),
        axis=1,
    )

    data["mapped"] = data["symbol"].notna() & (
        data["symbol"].astype(str).str.len() > 0
    )

    for period in PERIODS:
        data[f"{period}_return_pct"] = np.nan
        data[f"{period}_contribution_pct"] = np.nan

    progress = st.progress(0, text="Preparing holding analysis...")

    total_rows = len(data)

    for index, (_, row) in enumerate(data.iterrows(), start=1):
        asset_type = row["asset_type"]
        symbol = row["symbol"]

        # Cash does not receive a stock-price return.
        # Debt and other assets are shown but not falsely priced.
        if asset_type in ["Cash", "Debt", "REIT/InvIT", "Fund/ETF"]:
            pass
        elif symbol:
            returns = calculate_holding_returns(symbol)

            for period in PERIODS:
                data.at[index - 1, f"{period}_return_pct"] = returns[period]

        for period in PERIODS:
            return_value = data.at[index - 1, f"{period}_return_pct"]
            weight = data.at[index - 1, "weight_pct"]

            if not pd.isna(return_value) and not pd.isna(weight):
                contribution = (weight / 100.0) * return_value
                data.at[
                    index - 1, f"{period}_contribution_pct"
                ] = contribution

        progress.progress(
            min(index / max(total_rows, 1), 1.0),
            text=f"Analyzing holding {index} of {total_rows}...",
        )

    progress.empty()

    summary = {}

    for period in PERIODS:
        contribution_column = f"{period}_contribution_pct"
        return_column = f"{period}_return_pct"

        known_contribution = data[contribution_column].sum(
            min_count=1
        )

        covered_weight = data.loc[
            data[return_column].notna(),
            "weight_pct",
        ].sum()

        total_weight = data["weight_pct"].sum(min_count=1)

        if pd.isna(known_contribution):
            known_contribution = np.nan

        summary[period] = {
            "estimated_movement_pct": known_contribution,
            "covered_weight_pct": covered_weight,
            "total_weight_pct": total_weight,
            "uncovered_weight_pct": (
                max(total_weight - covered_weight, 0)
                if not pd.isna(total_weight)
                else np.nan
            ),
        }

    return data, summary


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

st.sidebar.header("Fund Selection")

fund_name = st.sidebar.selectbox(
    "Select mutual fund",
    list(FUNDS.keys()),
)

selected_fund = FUNDS[fund_name]

st.sidebar.info(
    "The dashboard uses disclosed portfolio holdings. "
    "Fund holdings may be delayed compared with live market prices."
)

analyze_button = st.sidebar.button(
    "Analyze Portfolio",
    type="primary",
    use_container_width=True,
)


# ---------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------

if analyze_button:
    with st.spinner("Loading disclosed portfolio..."):
        holdings = load_holdings(selected_fund["key"])

    if holdings.empty:
        st.error("No portfolio holdings were returned.")
        st.stop()

    # Detect placeholder/demo data
    if (
        len(holdings) == 1
        and holdings.iloc[0]["holding_name"] == "Demo holding 1"
    ):
        st.warning(
            "The application is connected, but the official AMC portfolio "
            "download has not yet been configured. No real fund data is "
            "being displayed."
        )

        st.info(
            "The next development step is to connect the official portfolio "
            "files for Motilal Oswal and HDFC."
        )

        st.subheader("Expected dashboard structure")

        preview = pd.DataFrame(
            {
                "Holding": [
                    "Example stock",
                    "Cash",
                    "Debt security",
                ],
                "Asset Type": [
                    "Equity",
                    "Cash",
                    "Debt",
                ],
                "Portfolio Weight": [
                    "Example %",
                    "Example %",
                    "Example %",
                ],
                "Price Return": [
                    "Will be calculated",
                    "Not applicable",
                    "Not available from equity price feed",
                ],
            }
        )

        st.dataframe(
            preview,
            use_container_width=True,
            hide_index=True,
        )

        st.stop()

    with st.spinner("Calculating historical movements..."):
        analysis, summary = calculate_analysis(holdings)

    st.success("Portfolio analysis completed.")

    # -----------------------------------------------------
    # Summary metrics
    # -----------------------------------------------------

    st.subheader("Estimated Portfolio Movement")

    metric_columns = st.columns(6)

    for metric_column, period in zip(metric_columns, PERIODS):
        result = summary[period]
        movement = result["estimated_movement_pct"]
        coverage = result["covered_weight_pct"]

        with metric_column:
            st.metric(
                label=period,
                value=format_pct(movement),
                help=(
                    f"Estimated weighted movement using {coverage:.2f}% "
                    "of portfolio weight where available."
                    if not pd.isna(coverage)
                    else "No price coverage available."
                ),
            )

    st.divider()

    # -----------------------------------------------------
    # Data quality information
    # -----------------------------------------------------

    st.subheader("Data Quality and Coverage")

    total_weight = analysis["weight_pct"].sum(min_count=1)
    equity_weight = analysis.loc[
        analysis["asset_type"].eq("Equity"),
        "weight_pct",
    ].sum(min_count=1)

    mapped_weight = analysis.loc[
        analysis["mapped"],
        "weight_pct",
    ].sum(min_count=1)

    unmapped_weight = analysis.loc[
        ~analysis["mapped"],
        "weight_pct",
    ].sum(min_count=1)

    quality_columns = st.columns(4)

    with quality_columns[0]:
        st.metric(
            "Total disclosed weight",
            format_pct(total_weight),
        )

    with quality_columns[1]:
        st.metric(
            "Equity allocation",
            format_pct(equity_weight),
        )

    with quality_columns[2]:
        st.metric(
            "Mapped market symbols",
            format_pct(mapped_weight),
        )

    with quality_columns[3]:
        st.metric(
            "Unmapped allocation",
            format_pct(unmapped_weight),
        )

    st.warning(
        "The estimated movement is not the official mutual-fund NAV return. "
        "Cash, debt, and holdings without reliable price symbols are shown "
        "separately and are not assigned invented equity-price returns."
    )

    # -----------------------------------------------------
    # Asset allocation
    # -----------------------------------------------------

    st.subheader("Asset Allocation")

    allocation = (
        analysis.groupby("asset_type", dropna=False)["weight_pct"]
        .sum()
        .reset_index()
        .sort_values("weight_pct", ascending=False)
    )

    allocation.columns = ["Asset Type", "Weight (%)"]

    st.dataframe(
        allocation,
        use_container_width=True,
        hide_index=True,
    )

    # -----------------------------------------------------
    # Holding-level analysis
    # -----------------------------------------------------

    st.subheader("Individual Holding Analysis")

    display_data = analysis.copy()

    display_data["Weight (%)"] = display_data["weight_pct"].round(4)
    display_data["Symbol"] = display_data["symbol"].fillna("Not mapped")
    display_data["Asset Type"] = display_data["asset_type"]
    display_data["Holding"] = display_data["holding_name"]

    display_data["Mapped"] = np.where(
        display_data["mapped"],
        "Yes",
        "No",
    )

    selected_period = st.selectbox(
        "Select period for holding-level details",
        list(PERIODS.keys()),
    )

    return_column = f"{selected_period}_return_pct"
    contribution_column = f"{selected_period}_contribution_pct"

    display_data["Return (%)"] = display_data[return_column].round(4)
    display_data["Contribution (%)"] = display_data[
        contribution_column
    ].round(4)

    final_columns = [
        "Holding",
        "Symbol",
        "Asset Type",
        "Weight (%)",
        "Return (%)",
        "Contribution (%)",
        "Mapped",
    ]

    display_data = display_data[final_columns].sort_values(
        "Weight (%)",
        ascending=False,
    )

    st.dataframe(
        display_data,
        use_container_width=True,
        hide_index=True,
    )

    # -----------------------------------------------------
    # Unmapped holdings
    # -----------------------------------------------------

    unmapped = analysis.loc[
        ~analysis["mapped"],
        [
            "holding_name",
            "asset_type",
            "weight_pct",
        ],
    ].copy()

    if not unmapped.empty:
        with st.expander("View unmapped or non-price holdings"):
            unmapped.columns = [
                "Holding",
                "Asset Type",
                "Weight (%)",
            ]

            st.dataframe(
                unmapped,
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "These holdings require manual symbol mapping or a separate "
                "debt/cash valuation method."
            )

else:
    st.info(
        "Choose a fund from the sidebar and tap 'Analyze Portfolio' "
        "to begin."
    )

    st.markdown(
        """
### Current development status

- Streamlit interface: connected
- Fund selector: available
- Historical calculation engine: prepared
- Official AMC portfolio connection: next step
- Live NAV: not yet available
        """
    )
