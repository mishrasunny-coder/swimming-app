#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Swimming Results Database (Streamlit)
- Loads event CSVs (25/50/100 Yard_*.csv) from the working directory
- Filters by swimmer, event, team, and date range
- Handles DQ/NT/invalid times gracefully for charts, "Best", and stats
"""

from pathlib import Path
from datetime import datetime
import re

import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# -----------------------------
# Globals / helpers
# -----------------------------

DATA_PATTERNS = ("25_Yard_*.csv", "50_Yard_*.csv", "100_Yard_*.csv")
DQ_LIKE = {"DQ", "DSQ", "DNF", "DNS", "NS", "SCR", "NT", ""}

st.set_page_config(page_title="Swimming Results", layout="wide")


def parse_time_to_seconds(x) -> float:
    """
    Convert time strings to seconds (float).
    Accepts: "28.43", "59.1", "1:02.34", "2:03", etc.
    Returns np.nan for DQ/NT/invalid values.
    """
    if pd.isna(x):
        return np.nan
    s = str(x).strip().upper()
    if s in DQ_LIKE:
        return np.nan
    try:
        if ":" in s:
            mm, ss = s.split(":", 1)
            return int(mm) * 60 + float(ss)
        return float(s)
    except Exception:
        return np.nan


def format_time(x) -> str:
    """
    Pretty formatting for display.
    If x is numeric seconds -> "M:SS.xx" or "SS.xx"
    If x is already a string like "1:02.34", return as-is.
    Preserve DQ/NT/N/A strings.
    """
    if pd.isna(x):
        return "N/A"
    s = str(x).strip()
    u = s.upper()
    if u in DQ_LIKE or u == "N/A":
        return s

    # If it's already mm:ss(.xx), keep as-is
    if ":" in s:
        return s

    # Otherwise, assume seconds float
    try:
        sec = float(s)
        if sec >= 60:
            m = int(sec // 60)
            rem = sec - m * 60
            return f"{m}:{rem:05.2f}"
        else:
            return f"{sec:.2f}"
    except Exception:
        return s


# -----------------------------
# Data loading
# -----------------------------

@st.cache_data
def load_all_swimming_data() -> pd.DataFrame:
    """
    Load CSVs for 25/50/100 Yard events in the current working directory.
    Adds Event_Type from filename "<stem>.csv" with underscores replaced by spaces.
    Converts Meet_Date to datetime (coerce errors).
    """
    data_dir = Path(".")
    csv_files = []
    for pattern in DATA_PATTERNS:
        csv_files.extend(sorted(data_dir.glob(pattern)))

    if not csv_files:
        return pd.DataFrame()

    all_data = []
    for file in csv_files:
        try:
            # Read as strings to avoid mixed-type headaches, then cast as needed
            df = pd.read_csv(file, dtype=str).dropna(how="all")

            # Ensure expected columns exist (create if missing)
            for col in ["Meet_Name", "Meet_Date", "Name", "Age", "No_of_Participants",
                        "Rank", "Time", "Team", "Notes", "DQ", "DQ_Reason"]:
                if col not in df.columns:
                    df[col] = np.nan

            # Event type from filename
            df["Event_Type"] = file.stem.replace("_", " ")

            all_data.append(df)
        except Exception as e:
            st.warning(f"Could not load {file.name}: {e}")

    if not all_data:
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)

    # Types / cleaning
    combined["Name"] = combined["Name"].astype(str).str.strip()
    combined = combined[combined["Name"].astype(str).str.len() > 0]

    # You normalized CSV dates already; coerce for safety
    combined["Meet_Date"] = pd.to_datetime(combined["Meet_Date"], errors="coerce")

    # Numeric helper for times
    combined["Time_s"] = combined["Time"].apply(parse_time_to_seconds)

    # Drop duplicates
    combined = combined.drop_duplicates()

    return combined


@st.cache_data
def get_available_events() -> list[str]:
    df = load_all_swimming_data()
    if df.empty:
        return []
    return sorted(df["Event_Type"].dropna().unique().tolist())


@st.cache_data
def get_available_swimmers() -> list[str]:
    df = load_all_swimming_data()
    if df.empty:
        return []
    names = df["Name"].dropna().astype(str)
    names = [n for n in names if n.strip()]
    return sorted(pd.unique(names).tolist())


# -----------------------------
# Charting
# -----------------------------

def create_performance_chart(df: pd.DataFrame, swimmer_name: str, event_type: str):
    """
    Performance trend chart for a single swimmer + event.
    Uses Time_s; rows with NaN Time_s (DQ/NT) are excluded from the line,
    but you can still display them in the table.
    """
    if df.empty:
        return None

    # Keep only rows with valid numeric time
    df_chart = df.dropna(subset=["Time_s"]).copy()
    if df_chart.empty:
        return None

    # Sort by Meet_Date for a proper line chart
    df_chart = df_chart.sort_values("Meet_Date")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df_chart["Meet_Date"],
            y=df_chart["Time_s"],
            mode="lines+markers",
            name="Time (s)",
            marker=dict(size=8),
            hovertemplate="<b>%{x}</b><br>Time: %{customdata[0]}<br>Rank: %{customdata[1]}<extra></extra>",
            customdata=list(zip(df_chart["Time"], df_chart["Rank"])),
        )
    )
    fig.update_layout(
        title=f"{swimmer_name} — {event_type} Performance Trend",
        xaxis_title="Meet Date",
        yaxis_title="Time (seconds)",
        hovermode="closest",
        template="plotly_white",
    )
    return fig


# -----------------------------
# App
# -----------------------------

def main():
    st.markdown('<h1 class="main-header">🏊‍♀️ Swimming Results Database</h1>', unsafe_allow_html=True)

    with st.spinner("Loading swimming data..."):
        df = load_all_swimming_data()
        available_events = get_available_events()
        available_swimmers = get_available_swimmers()

    if df.empty:
        st.error("No swimming data found! Ensure CSVs (25/50/100_Yard_*.csv) are in the working directory.")
        return

    # Quick diagnostics (collapsible)
    with st.expander("🔎 Loaded CSV diagnostics", expanded=False):
        st.caption("Events found:")
        st.write(", ".join(sorted(df["Event_Type"].unique())))
        st.caption(f"Rows loaded: {len(df)}; date coverage: "
                   f"{df['Meet_Date'].min()} → {df['Meet_Date'].max()}")

    # Sidebar filters
    st.sidebar.header("🔍 Search Filters")

    swimmer_name = st.sidebar.selectbox(
        "Select Swimmer:",
        options=["All Swimmers"] + available_swimmers,
        index=0,
    )

    event_type = st.sidebar.selectbox(
        "Select Event:",
        options=["All Events"] + available_events,
        index=0,
    )

    teams = ["All Teams"] + sorted(df["Team"].dropna().astype(str).unique().tolist())
    selected_team = st.sidebar.selectbox("Select Team:", options=teams, index=0)

    # Date range filter (only if any valid dates exist)
    if not df["Meet_Date"].isna().all():
        min_date = df["Meet_Date"].min().date()
        max_date = df["Meet_Date"].max().date()
        date_range = st.sidebar.date_input(
            "Date Range:",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )
    else:
        date_range = None

    # Apply filters
    filtered = df.copy()

    if swimmer_name != "All Swimmers":
        # Case-insensitive matching that handles name order variations
        # Normalize both search term and CSV names for comparison
        search_normalized = " ".join(sorted(swimmer_name.lower().split()))
        filtered = filtered.loc[
            filtered["Name"].apply(
                lambda x: " ".join(sorted(str(x).lower().split())) == search_normalized
            )
        ]

    if event_type != "All Events":
        filtered = filtered.loc[filtered["Event_Type"] == event_type]

    if selected_team != "All Teams":
        filtered = filtered.loc[filtered["Team"] == selected_team]

    if date_range and len(date_range) == 2 and not filtered["Meet_Date"].isna().all():
        start_date = pd.to_datetime(date_range[0])
        end_date = pd.to_datetime(date_range[1])
        filtered = filtered.loc[
            (filtered["Meet_Date"] >= start_date) &
            (filtered["Meet_Date"] <= end_date)
        ]

    # Main content
    if filtered.empty:
        st.warning("No results found for the selected filters.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Results", len(filtered))
    with col2:
        st.metric("Unique Swimmers", filtered["Name"].nunique())
    with col3:
        st.metric("Event Types", filtered["Event_Type"].nunique())
    with col4:
        st.metric("Total Meets", filtered["Meet_Name"].nunique())

    st.markdown("---")

    # Results table
    st.header("📊 Results Table")
    display_df = filtered.copy()
    # show human-friendly time next to original
    display_df["Time_Formatted"] = display_df["Time"].apply(format_time)

    display_columns = [
        "Meet_Name", "Meet_Date", "Name", "Age", "No_of_Participants",
        "Rank", "Time_Formatted", "Team", "Notes", "Event_Type"
    ]
    # Only keep those that exist
    display_columns = [c for c in display_columns if c in display_df.columns]

    st.dataframe(
        display_df[display_columns].sort_values(["Meet_Date"], ascending=True),
        use_container_width=True,
        hide_index=True,
    )

    # Performance analysis for a single swimmer + single event
    if swimmer_name != "All Swimmers" and event_type != "All Events":
        st.markdown("---")
        st.header("📈 Performance Analysis")

        chart_data = filtered.copy()
        if not chart_data.empty:
            fig = create_performance_chart(chart_data, swimmer_name, event_type)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("All selected rows are DQ/No-Time for charting. Showing table only.")

        col1, col2 = st.columns(2)

        # Best Performance (DQ-safe)
        with col1:
            st.subheader("🏆 Best Performance")
            valid = chart_data.loc[chart_data["Time_s"].notna()]
            if valid.empty:
                st.info("All results are DQ / no-time. Best performance skipped.")
            else:
                best_row = valid.loc[valid["Time_s"].idxmin()]
                st.success(
                    f"**Best Time:** {format_time(best_row['Time'])}  \n"
                    f"**Meet:** {best_row['Meet_Name']}  \n"
                    f"**Date:** {best_row['Meet_Date'].strftime('%Y-%m-%d')}  \n"
                    f"**Rank:** {best_row['Rank']}"
                )

        # Statistics (DQ-safe)
        with col2:
            st.subheader("📊 Statistics")
            valid = chart_data.loc[chart_data["Time_s"].notna(), "Time_s"]
            if len(valid) > 1:
                time_range = (valid.min(), valid.max())
                improvement = valid.max() - valid.min()
                avg = valid.mean()
                st.info(
                    f"**Time Range:** {format_time(time_range[0])} - {format_time(time_range[1])}  \n"
                    f"**Total Improvement:** {improvement:.2f} seconds  \n"
                    f"**Average Time:** {format_time(avg)}  \n"
                    f"**Total Events:** {len(chart_data)}"
                )
            else:
                st.info(f"**Total Events:** {len(chart_data)}")

    # Event comparison for a swimmer across all events
    if swimmer_name != "All Swimmers" and event_type == "All Events":
        st.markdown("---")
        st.header("🏊‍♀️ Event Comparison")

        # Compute best per Event_Type using Time_s to avoid picking DQ
        comp = (
            filtered.assign(_valid=filtered["Time_s"].notna())
            .groupby("Event_Type", as_index=False)
            .agg(Best_Time_s=("Time_s", "min"), Event_Count=("Time", "count"))
        )

        # Best rank (ignores DQ), fall back to string min if needed
        if "Rank" in filtered.columns:
            # Try numeric rank if possible
            def _rank_to_num(x):
                try:
                    return float(x)
                except Exception:
                    return np.nan

            tmp = filtered.copy()
            tmp["Rank_num"] = tmp["Rank"].apply(_rank_to_num)
            rank_comp = (
                tmp.groupby("Event_Type", as_index=False)
                .agg(Best_Rank=("Rank_num", "min"))
            )
            comp = comp.merge(rank_comp, on="Event_Type", how="left")
        else:
            comp["Best_Rank"] = np.nan

        comp["Best_Time_Formatted"] = comp["Best_Time_s"].apply(format_time)

        st.dataframe(
            comp[["Event_Type", "Best_Time_Formatted", "Best_Rank", "Event_Count"]]
            .sort_values("Event_Type"),
            use_container_width=True,
            hide_index=True,
        )

    # Downloads / Reset
    st.markdown("---")
    st.header("💾 Download Data")

    c1, c2 = st.columns(2)
    with c1:
        csv_data = filtered.drop(columns=["Time_s"], errors="ignore").to_csv(index=False)
        st.download_button(
            label="📥 Download Filtered Results (CSV)",
            data=csv_data,
            file_name=f"swimming_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )
    with c2:
        if st.button("🔄 Reset Filters"):
            st.rerun()


if __name__ == "__main__":
    main()
