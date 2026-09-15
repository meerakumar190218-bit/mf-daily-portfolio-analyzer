import io
import re
import datetime as dt

import numpy as np
import pandas as pd
import requests
import pdfplumber
import streamlit as st
import yfinance as yf


# =========================================================
# CONFIG
# =========================================================

st.set_page_config(
    page_title="MF Daily Portfolio Analyzer",
    page_icon="📊",
    layout="wide",
)

FUNDS = {
    "Motilal Oswal Active Momentum Fund - Direct Growth": {
        "key": "motilal",
        "official_portfolio": (
            "https://www.motilaloswalmf.com/"
            "content/dam/motilal-mf/sheets/fund-csvs/"
            "Month_End_Portfolio_August_2026/YO66.xlsx"
        ),
        "portfolio_date": "31-Aug-2026",
    },
    "HDFC Flexi Cap Fund - Direct Growth": {
        "key": "hdfc",
        "official_portfolio": (
            "https://files.hdfcfund.com/s3fs-public/2026-09/"
            "HDFC%20MF%20Factsheet%20-%20August%202026.pdf"
        ),
        "portfolio_date": "31-Aug-2026",
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


# =========================================================
# SYMBOL MAP
# =========================================================

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

    "LARSEN & TOUBRO": "LT.NS",
    "LARSEN AND TOUBRO": "LT.NS",

    "BHARTI AIRTEL": "BHARTIARTL.NS",
    "BHARTI AIRTEL LIMITED": "BHARTIARTL.NS",

    "ITC": "ITC.NS",
    "ITC LIMITED": "ITC.NS",

    "MARUTI SUZUKI": "MARUTI.NS",
    "MARUTI SUZUKI INDIA": "MARUTI.NS",

    "SUN PHARMACEUTICAL": "SUNPHARMA.NS",
    "SUN PHARMACEUTICAL INDUSTRIES": "SUNPHARMA.NS",

    "ADANI ENTERPRISES": "ADANIENT.NS",
    "ADANI ENTERPRISES LIMITED": "ADANIENT.NS",

    "ADANI PORTS": "ADANIPORTS.NS",
    "ADANI PORTS AND SPECIAL ECONOMIC ZONE": "ADANIPORTS.NS",

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

    "BAJAJ FINANCE": "BAJFINANCE.NS",
    "BAJAJ FINSERV": "BAJAJFINSV.NS",

    "EICHER MOTORS": "EICHERMOT.NS",

    "MAHINDRA & MAHINDRA": "M&M.NS",
    "M&M": "M&M.NS",

    "CIPLA": "CIPLA.NS",
    "DIVIS LABORATORIES": "DIVISLAB.NS",

    "TRENT": "TRENT.NS",

    "BHARAT ELECTRONICS": "BEL.NS",
    "BEL": "BEL.NS",

    "HINDUSTAN AERONAUTICS": "HAL.NS",
    "HAL": "HAL.NS",

    "PERSISTENT SYSTEMS": "PERSISTENT.NS",

    "DIXON TECHNOLOGIES": "DIXON.NS",

    "MAX HEALTHCARE": "MAXHEALTH.NS",

    "JIO FINANCIAL SERVICES": "JIOFIN.NS",

    "ONE 97 COMMUNICATIONS": "PAYTM.NS",
    "ONE 97 COMMUNICATIONS LIMITED": "PAYTM.NS",

    "PAYTM": "PAYTM.NS",

    "KALYAN JEWELLERS INDIA": "KALYANKJIL.NS",
    "KALYAN JEWELLERS INDIA LIMITED": "KALYANKJIL.NS",

    "MTAR TECHNOLOGIES": "MTARTECH.NS",

    "GARWARE HI-TECH FILMS": "GARFIBRES.NS",

    "STERLITE TECHNOLOGIES": "STLTECH.NS",

    "REDINGTON": "REDINGTON.NS",

    "OLA ELECTRIC MOBILITY": "OLAELEC.NS",

    "DATA PATTERNS": "DATAPATTNS.NS",

    "NAVIN FLUORINE INTERNATIONAL": "NAVINFLUOR.NS",

    "COFORGE": "COFORGE.NS",

    "TVS MOTOR COMPANY": "TVSMOTOR.NS",

    "SYRMA SGS TECHNOLOGY": "SYRMA.NS",

    "ONESOURCE SPECIALTY PHARMA": "ONESOURCE.NS",

    "DIAMOND POWER INFRASTRUCTURE": "DIACABS.NS",

    "DIAMOND POWER INFRASTRUCTURE LIMITED": "DIACABS.NS",
}


# =========================================================
# HELPERS
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value).strip()
    value = re.sub(r"\s+", " ", value)
    return value


def parse_number(value):
    if value is None:
        return np.nan

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    text = clean_text(value)
    text = text.replace(",", "")
    text = text.replace("%", "")

    try:
        return float(text)
    except Exception:
        return np.nan


def find_symbol(name):
    name = clean_text(name).upper()

    if name in SYMBOL_MAP:
        return SYMBOL_MAP[name]

    simplified = name

    for suffix in [
        " LIMITED",
        " LTD.",
        " LTD",
        " PVT LTD",
        " PRIVATE LIMITED",
    ]:
        simplified = simplified.replace(suffix, "")

    simplified = simplified.strip()

    if simplified in SYMBOL_MAP:
        return SYMBOL_MAP[simplified]

    # Conservative pattern matching
    patterns = [
        ("HDFC BANK", "HDFCBANK.NS"),
        ("ICICI BANK", "ICICIBANK.NS"),
        ("STATE BANK OF INDIA", "SBIN.NS"),
        ("AXIS BANK", "AXISBANK.NS"),
        ("RELIANCE", "RELIANCE.NS"),
        ("BHARTI AIRTEL", "BHARTIARTL.NS"),
        ("TATA CONSULTANCY", "TCS.NS"),
        ("LARSEN", "LT.NS"),
        ("INFOSYS", "INFY.NS"),
    ]

    for pattern, symbol in patterns:
        if pattern in simplified:
            return symbol

    return None


def classify_asset(name, asset_type=""):
    text = (
        clean_text(name) + " " + clean_text(asset_type)
    ).lower()

    if any(
        x in text
        for x in [
            "cash",
            "net current asset",
            "bank balance",
            "cash & cash",
        ]
    ):
        return "Cash"

    if any(
        x in text
        for x in [
            "repo",
            "triparty repo",
            "g-sec",
            "government security",
            "treasury",
            "bond",
            "debenture",
            "commercial paper",
            "certificate of deposit",
            "debt",
            "t-bill",
        ]
    ):
        return "Debt / Money Market"

    if any(
        x in text
        for x in [
            "reit",
            "real estate investment trust",
            "invit",
        ]
    ):
        return "REIT / InvIT"

    if any(
        x in text
        for x in [
            "etf",
            "mutual fund",
            "units of",
        ]
    ):
        return "Fund / ETF"

    return "Equity"


# =========================================================
# DOWNLOAD OFFICIAL FILE
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def download_file(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/131 Safari/537.36"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
    )

    response.raise_for_status()

    return response.content


# =========================================================
# MOTILAL OSWAL PORTFOLIO
# =========================================================

def parse_motilal_excel(content):
    workbook = pd.ExcelFile(
        io.BytesIO(content),
        engine="openpyxl",
    )

    candidates = []

    for sheet in workbook.sheet_names:
        try:
            raw = pd.read_excel(
                io.BytesIO(content),
                sheet_name=sheet,
                header=None,
                engine="openpyxl",
            )

            candidates.append(raw)

        except Exception:
            continue

    best = None
    best_score = -1

    for raw in candidates:
        score = 0

        for _, row in raw.iterrows():
            text = " ".join(
                clean_text(x).lower()
                for x in row.tolist()
                if clean_text(x)
            )

            if "security" in text:
                score += 3

            if "nav" in text:
                score += 2

            if "market value" in text:
                score += 2

            if "percentage" in text:
                score += 2

            if "% to nav" in text:
                score += 3

        if score > best_score:
            best_score = score
            best = raw

    if best is None:
        raise ValueError(
            "Could not identify the portfolio table in the Motilal file."
        )

    header_row = None

    for i, row in best.iterrows():
        text = " ".join(
            clean_text(x).lower()
            for x in row.tolist()
            if clean_text(x)
        )

        if (
            "security" in text
            and (
                "nav" in text
                or "market value" in text
                or "percentage" in text
            )
        ):
            header_row = i
            break

    if header_row is None:
        raise ValueError(
            "Could not identify column headers in Motilal portfolio."
        )

    data = best.iloc[header_row + 1:].copy()

    headers = [
        clean_text(x) or f"column_{i}"
        for i, x in enumerate(best.iloc[header_row].tolist())
    ]

    data.columns = headers

    name_column = None
    weight_column = None
    asset_column = None

    for column in data.columns:
        text = clean_text(column).lower()

        if (
            name_column is None
            and (
                "security" in text
                or "name" in text
                or "instrument" in text
            )
        ):
            name_column = column

        if (
            weight_column is None
            and (
                "% to nav" in text
                or "percent to nav" in text
                or "percentage" in text
                or "weight" in text
            )
        ):
            weight_column = column

        if asset_column is None and (
            "asset" in text
            or "type" in text
            or "instrument" in text
        ):
            asset_column = column

    if name_column is None or weight_column is None:
        raise ValueError(
            "Could not identify holding name and portfolio weight columns."
        )

    output = pd.DataFrame()

    output["holding_name"] = data[name_column].apply(clean_text)
    output["weight_pct"] = data[weight_column].apply(parse_number)

    if asset_column:
        output["asset_type"] = data[asset_column].apply(clean_text)
    else:
        output["asset_type"] = ""

    output = output[
        (output["holding_name"] != "")
        & output["weight_pct"].notna()
        & (output["weight_pct"] > 0)
    ]

    output["asset_type"] = output.apply(
        lambda row: classify_asset(
            row["holding_name"],
            row["asset_type"],
        ),
        axis=1,
    )

    output["symbol"] = output["holding_name"].apply(
        find_symbol
    )

    return output[
        [
            "holding_name",
            "symbol",
            "asset_type",
            "weight_pct",
        ]
    ].reset_index(drop=True)


# =========================================================
# HDFC PORTFOLIO
# =========================================================

def parse_hdfc_pdf(content):
    rows = []

    with pdfplumber.open(io.BytesIO(content)) as pdf:

        for page in pdf.pages:

            try:
                tables = page.extract_tables()
            except Exception:
                tables = []

            for table in tables:

                if not table:
                    continue

                for row in table:
                    if not row:
                        continue

                    cleaned = [
                        clean_text(cell)
                        for cell in row
                    ]

                    text = " ".join(cleaned).lower()

                    # Need a company/instrument and a percentage.
                    if (
                        not any(
                            keyword in text
                            for keyword in [
                                "bank",
                                "limited",
                                "ltd",
                                "industries",
                                "corporation",
                                "trust",
                                "repo",
                                "government",
                                "securities",
                                "bond",
                            ]
                        )
                    ):
                        continue

                    percentage_values = []

                    for cell in cleaned:
                        match = re.search(
                            r"(-?\d+(?:\.\d+)?)\s*%?",
                            cell,
                        )

                        if match:
                            try:
                                number = float(match.group(1))

                                if 0 <= number <= 100:
                                    percentage_values.append(number)
                            except Exception:
                                pass

                    if not percentage_values:
                        continue

                    # In HDFC's table the first relevant percentage
                    # is generally % of NAV.
                    weight = percentage_values[0]

                    name = cleaned[0]

                    if not name:
                        continue

                    # Avoid header rows.
                    if any(
                        x in name.lower()
                        for x in [
                            "company/instrument",
                            "% to nav",
                            "industry",
                            "rating",
                        ]
                    ):
                        continue

                    rows.append(
                        {
                            "holding_name": name,
                            "weight_pct": weight,
                        }
                    )

    if not rows:
        raise ValueError(
            "Could not extract HDFC portfolio holdings from the PDF."
        )

    output = pd.DataFrame(rows)

    # Remove obvious duplicates created by PDF table repetition.
    output = (
        output.groupby(
            "holding_name",
            as_index=False,
        )["weight_pct"]
        .max()
    )

    output["asset_type"] = output["holding_name"].apply(
        classify_asset
    )

    output["symbol"] = output["holding_name"].apply(
        find_symbol
    )

    return output[
        [
            "holding_name",
            "symbol",
            "asset_type",
            "weight_pct",
        ]
    ].reset_index(drop=True)


# =========================================================
# LOAD FUND
# =========================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_holdings(fund_key):

    fund = FUNDS[fund_key]

    content = download_file(
        fund["official_portfolio"]
    )

    if fund_key == "motilal":
        holdings = parse_motilal_excel(content)

    elif fund_key == "hdfc":
        holdings = parse_hdfc_pdf(content)

    else:
        raise ValueError("Unknown fund.")

    holdings = holdings[
        holdings["weight_pct"].notna()
        & (holdings["weight_pct"] > 0)
    ].copy()

    return holdings


# =========================================================
# MARKET DATA
# =========================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_price_history(symbol):

    if not symbol:
        return pd.DataFrame()

    try:

        end = dt.date.today() + dt.timedelta(days=1)

        start = (
            dt.date.today()
            - dt.timedelta(days=400)
        )

        data = yf.download(
            symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval="1d",
            auto_adjust=True,
            progress=False,
            threads=False,
        )

        if data.empty:
            return pd.DataFrame()

        if isinstance(
            data.columns,
            pd.MultiIndex,
        ):
            data.columns = [
                column[0]
                for column in data.columns
            ]

        data.columns = [
            str(column).lower()
            for column in data.columns
        ]

        if "close" not in data.columns:
            return pd.DataFrame()

        data = data[["close"]].dropna()

        data.index = pd.to_datetime(
            data.index
        ).tz_localize(None)

        return data

    except Exception:
        return pd.DataFrame()


def price_on_or_before(
    prices,
    date,
):
    if prices.empty:
        return np.nan

    date = pd.Timestamp(date)

    eligible = prices[
        prices.index <= date
    ]

    if eligible.empty:
        return np.nan

    return float(
        eligible.iloc[-1]["close"]
    )


def calculate_returns(symbol):

    prices = get_price_history(symbol)

    if prices.empty:
        return {
            period: np.nan
            for period in PERIODS
        }

    latest_date = prices.index.max()

    latest_price = price_on_or_before(
        prices,
        latest_date,
    )

    if pd.isna(latest_price):
        return {
            period: np.nan
            for period in PERIODS
        }

    result = {}

    for period, days in PERIODS.items():

        target = (
            latest_date
            - pd.Timedelta(days=days)
        )

        old_price = price_on_or_before(
            prices,
            target,
        )

        if (
            pd.isna(old_price)
            or old_price == 0
        ):
            result[period] = np.nan

        else:
            result[period] = (
                (latest_price / old_price) - 1
            ) * 100

    return result


# =========================================================
# ANALYSIS
# =========================================================

def analyse_portfolio(holdings):

    data = holdings.copy()

    for period in PERIODS:
        data[
            f"{period}_return"
        ] = np.nan

        data[
            f"{period}_contribution"
        ] = np.nan

    equity_rows = data[
        data["asset_type"] == "Equity"
    ]

    progress = st.progress(
        0,
        text="Calculating stock-level movements...",
    )

    total = len(equity_rows)

    for counter, index in enumerate(
        equity_rows.index,
        start=1,
    ):

        symbol = data.loc[
            index,
            "symbol",
        ]

        if symbol:

            returns = calculate_returns(
                symbol
            )

            for period in PERIODS:

                data.loc[
                    index,
                    f"{period}_return",
                ] = returns[period]

                weight = data.loc[
                    index,
                    "weight_pct",
                ]

                if not pd.isna(
                    returns[period]
                ):
                    data.loc[
                        index,
                        f"{period}_contribution",
                    ] = (
                        weight / 100
                    ) * returns[period]

        progress.progress(
            counter / max(total, 1),
            text=(
                f"Analyzing {counter} "
                f"of {total} equity holdings..."
            ),
        )

    progress.empty()

    summary = {}

    for period in PERIODS:

        contribution_column = (
            f"{period}_contribution"
        )

        return_column = (
            f"{period}_return"
        )

        movement = data[
            contribution_column
        ].sum(min_count=1)

        covered_weight = data.loc[
            data[return_column].notna(),
            "weight_pct",
        ].sum()

        total_equity_weight = data.loc[
            data["asset_type"] == "Equity",
            "weight_pct",
        ].sum()

        summary[period] = {
            "movement": movement,
            "covered": covered_weight,
            "equity_weight": total_equity_weight,
        }

    return data, summary


# =========================================================
# UI
# =========================================================

st.title(
    "📊 Mutual Fund Daily Portfolio Analyzer"
)

st.caption(
    "Latest disclosed holdings × market-price movement"
)

st.sidebar.header("Fund")

fund_name = st.sidebar.selectbox(
    "Select fund",
    list(FUNDS.keys()),
)

fund = FUNDS[fund_name]

st.sidebar.caption(
    f"Latest portfolio disclosure: "
    f"{fund['portfolio_date']}"
)

run = st.sidebar.button(
    "🔄 Analyze Now",
    type="primary",
    use_container_width=True,
)


if run:

    try:

        with st.spinner(
            "Downloading official portfolio disclosure..."
        ):
            holdings = load_holdings(
                fund["key"]
            )

        st.success(
            f"Loaded {len(holdings)} disclosed holdings."
        )

    except Exception as error:

        st.error(
            "The official portfolio file could not be "
            "processed."
        )

        st.code(
            str(error)
        )

        st.stop()

    with st.spinner(
        "Calculating portfolio movement..."
    ):
        analysis, summary = analyse_portfolio(
            holdings
        )

    # =====================================================
    # SUMMARY
    # =====================================================

    st.subheader(
        "Estimated Portfolio Movement"
    )

    columns = st.columns(6)

    for column, period in zip(
        columns,
        PERIODS,
    ):

        movement = summary[
            period
        ]["movement"]

        coverage = summary[
            period
        ]["covered"]

        if pd.isna(movement):
            movement_text = "N/A"
        else:
            movement_text = (
                f"{movement:+.2f}%"
            )

        with column:

            st.metric(
                period,
                movement_text,
            )

            if not pd.isna(coverage):
                st.caption(
                    f"Coverage: {coverage:.1f}%"
                )

    st.divider()

    # =====================================================
    # ALLOCATION
    # =====================================================

    st.subheader(
        "Portfolio Allocation"
    )

    allocation = (
        analysis.groupby(
            "asset_type"
        )["weight_pct"]
        .sum()
        .sort_values(
            ascending=False
        )
        .reset_index()
    )

    allocation.columns = [
        "Asset Type",
        "Weight (%)",
    ]

    st.dataframe(
        allocation,
        use_container_width=True,
        hide_index=True,
    )

    # =====================================================
    # DATA QUALITY
    # =====================================================

    total_weight = (
        analysis["weight_pct"].sum()
    )

    mapped_weight = (
        analysis.loc[
            analysis["symbol"].notna(),
            "weight_pct",
        ].sum()
    )

    equity_weight = (
        analysis.loc[
            analysis["asset_type"]
            == "Equity",
            "weight_pct",
        ].sum()
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Total disclosed weight",
        f"{total_weight:.2f}%",
    )

    c2.metric(
        "Equity weight",
        f"{equity_weight:.2f}%",
    )

    c3.metric(
        "Mapped securities",
        f"{mapped_weight:.2f}%",
    )

    c4.metric(
        "Unmapped / non-price",
        f"{max(total_weight - mapped_weight, 0):.2f}%",
    )

    st.warning(
        "This is an estimated holdings-based movement, "
        "not the official live NAV. Holdings are based on "
        "the latest disclosed portfolio and may be stale. "
        "Market prices may be more recent."
    )

    # =====================================================
    # HOLDING DETAILS
    # =====================================================

    st.subheader(
        "Individual Holding Movement"
    )

    selected_period = st.selectbox(
        "Period",
        list(PERIODS.keys()),
    )

    return_column = (
        f"{selected_period}_return"
    )

    contribution_column = (
        f"{selected_period}_contribution"
    )

    table = analysis.copy()

    table["Return (%)"] = table[
        return_column
    ].round(2)

    table["Contribution (%)"] = table[
        contribution_column
    ].round(3)

    table["Weight (%)"] = table[
        "weight_pct"
    ].round(2)

    table["Symbol"] = table[
        "symbol"
    ].fillna("Not mapped")

    table = table[
        [
            "holding_name",
            "Symbol",
            "asset_type",
            "Weight (%)",
            "Return (%)",
            "Contribution (%)",
        ]
    ]

    table.columns = [
        "Holding",
        "Symbol",
        "Asset Type",
        "Weight (%)",
        "Return (%)",
        "Contribution (%)",
    ]

    table = table.sort_values(
        "Weight (%)",
        ascending=False,
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

    # =====================================================
    # TOP CONTRIBUTORS
    # =====================================================

    st.subheader(
        "Biggest Contributors"
    )

    contributors = analysis[
        [
            "holding_name",
            "weight_pct",
            return_column,
            contribution_column,
        ]
    ].dropna(
        subset=[contribution_column]
    )

    if not contributors.empty:

        positive = contributors.sort_values(
            contribution_column,
            ascending=False,
        ).head(10)

        negative = contributors.sort_values(
            contribution_column,
            ascending=True,
        ).head(10)

        left, right = st.columns(2)

        with left:

            st.markdown(
                "### 📈 Positive contributors"
            )

            positive = positive.rename(
                columns={
                    "holding_name": "Holding",
                    "weight_pct": "Weight (%)",
                    return_column: "Return (%)",
                    contribution_column: "Contribution (%)",
                }
            )

            st.dataframe(
                positive[
                    [
                        "Holding",
                        "Weight (%)",
                        "Return (%)",
                        "Contribution (%)",
                    ]
                ].round(3),
                use_container_width=True,
                hide_index=True,
            )

        with right:

            st.markdown(
                "### 📉 Negative contributors"
            )

            negative = negative.rename(
                columns={
                    "holding_name": "Holding",
                    "weight_pct": "Weight (%)",
                    return_column: "Return (%)",
                    contribution_column: "Contribution (%)",
                }
            )

            st.dataframe(
                negative[
                    [
                        "Holding",
                        "Weight (%)",
                        "Return (%)",
                        "Contribution (%)",
                    ]
                ].round(3),
                use_container_width=True,
                hide_index=True,
            )

    # =====================================================
    # UNMAPPED
    # =====================================================

    unmapped = analysis[
        analysis["symbol"].isna()
    ]

    if not unmapped.empty:

        with st.expander(
            "⚠️ Holdings without reliable market-price mapping"
        ):

            st.dataframe(
                unmapped[
                    [
                        "holding_name",
                        "asset_type",
                        "weight_pct",
                    ]
                ].rename(
                    columns={
                        "holding_name": "Holding",
                        "asset_type": "Asset Type",
                        "weight_pct": "Weight (%)",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "These securities are not given an invented "
                "stock return. This prevents the dashboard "
                "from falsely claiming greater accuracy."
            )

else:

    st.info(
        "Select a fund and tap 'Analyze Now'."
    )

    st.markdown(
        """
### What this dashboard calculates

**Portfolio movement ≈ Σ (holding weight × holding price return)**

It provides separate views for:

- Previous trading day
- Previous week
- Previous month
- Previous 3 months
- Previous 6 months
- Previous 1 year

The individual holding table shows exactly which stocks
are helping or hurting the estimated portfolio movement.
"""
    )
