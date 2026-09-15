import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

st.set_page_config(
    page_title="MF Daily Portfolio Analyzer",
    page_icon="📊",
    layout="wide",
)

# ---------------------------------------------------------
# Page styling
# ---------------------------------------------------------
st.markdown("""
<style>
    .main-title {
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #666;
        margin-bottom: 1.5rem;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666;
    }
    .warning-box {
        padding: 1rem;
        border-radius: 8px;
        background-color: #fff4d6;
        border: 1px solid #e5c46b;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Fund configuration
# ---------------------------------------------------------
FUNDS = {
    "Motilal Oswal Active Momentum Fund - Direct Growth":
        "motilal_oswal_active_momentum",
    "HDFC Flexi Cap Fund - Direct Growth":
        "hdfc_flexicap",
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
def calculate_return(current_price, historical_price):
    """Calculate percentage return."""
    if pd.isna(current_price) or pd.isna(historical_price):
        return np.nan

    if historical_price == 0:
        return np.nan

    return ((current_price / historical_price) - 1) * 100


def calculate_weighted_contribution(weight, return_pct):
    """Weight is a percentage of NAV; return_pct is a percentage."""
    if pd.isna(weight) or pd.isna(return_pct):
        return np.nan

    return (weight / 100) * return_pct


def format_pct(value):
    """Format a percentage for display."""
    if pd.isna(value):
        return "—"

    return f"{value:+.2f}%"


def load_holdings(fund_key):
    """
    Load verified holdings.

    The actual holdings connector will be added next.
    We intentionally return an empty DataFrame until
    verified fund data is connected.
    """
    columns = [
        "holding_name",
        "symbol",
        "asset_type",
        "weight_pct",
    ]

    # No fabricated holdings.
    return pd.DataFrame(columns=columns)


def calculate_analysis(holdings):
    """
    Placeholder for the market-data calculation engine.

    This will:
    1. Fetch current/latest prices.
    2. Fetch historical prices.
    3. Calculate period returns.
    4. Calculate weighted contributions.
    5. Aggregate the portfolio.
    """
    if holdings.empty:
        return holdings.copy(), {}

    return holdings.copy(), {}


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------
st.markdown(
    '<div class="main-title">📊 MF Daily Portfolio Analyzer</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    'Estimate mutual fund portfolio movement using disclosed holdings '
    'and market prices.'
    '</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
with st.sidebar:
    st.header("Fund Selection")

    selected_fund = st.selectbox(
        "Select Mutual Fund",
        list(FUNDS.keys()),
    )

    analyze_button = st.button(
        "🔄 Analyze Fund",
        type="primary",
        use_container_width=True,
    )

    st.divider()

    st.caption("Supported funds")
    st.caption("• Motilal Oswal Active Momentum Fund")
    st.caption("• HDFC Flexi Cap Fund")

    st.divider()

    st.caption(
        "Version 1 uses the latest available disclosed holdings. "
        "Estimated weighted movement is not the official live NAV."
    )

# ---------------------------------------------------------
# Main dashboard
# ---------------------------------------------------------
fund_key = FUNDS[selected_fund]

st.subheader(selected_fund)

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Holdings Disclosure Date", "Not connected")

with col2:
    st.metric("Price Data Updated", "Not connected")

with col3:
    st.metric("Holdings Loaded", "0")

st.markdown("---")

holdings = load_holdings(fund_key)

if analyze_button:
    st.session_state["analyze_requested"] = True

if holdings.empty:
    st.markdown(
        '<div class="warning-box">'
        '<b>Data connection pending</b><br><br>'
        'The dashboard interface is ready, but verified mutual fund '
        'holdings and historical market-price data have not yet been '
        'connected. No estimated returns are shown until real data '
        'is available.'
        '</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "Next step: connect the official portfolio disclosures for "
        "the two selected funds, then connect historical stock prices."
    )

else:
    analyzed_holdings, overall_results = calculate_analysis(holdings)

    st.subheader("Estimated Weighted Portfolio Movement")

    metric_columns = st.columns(6)

    for index, (period_name, _) in enumerate(PERIODS.items()):
        with metric_columns[index]:
            value = overall_results.get(period_name, np.nan)
            st.metric(period_name, format_pct(value))

    st.caption(
        "Estimated movement is calculated from holding weights and "
        "available market-price returns."
    )

    st.markdown("---")

    st.subheader("Individual Holdings")

    display_columns = [
        "holding_name",
        "asset_type",
        "weight_pct",
    ]

    st.dataframe(
        analyzed_holdings[display_columns],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Portfolio Contribution")

    st.info(
        "The contribution view will show which holdings are adding "
        "to or reducing the estimated overall portfolio movement."
    )
