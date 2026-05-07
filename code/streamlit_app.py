"""
AEC 2025 Narrative — Streamlit App
UTS MDSI Data Narrative Studio

A data narrative on the 2025 Australian federal election,
focused on the rise of independent candidates.

Narrative arc: Sparkline (the gap between "what is" and "what could be")
"""

import streamlit as st
import pandas as pd
import plotly.express as px


# ----------------------------------------------------------------------------
# Page configuration
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="AEC 2025 — The Independents Are Coming",
    page_icon="🗳️",
    layout="wide",
)


# ----------------------------------------------------------------------------
# Party colour palette
# Using consistent ABC-election-night-style party colours
# ----------------------------------------------------------------------------
PARTY_COLOURS = {
    "Australian Labor Party": "#DE3533",   # Labor red
    "Liberal Party":          "#1C4F9C",   # Liberal blue
    "LNP":                    "#1C4F9C",   # same as Liberal
    "National Party":         "#006644",   # National green
    "The Greens":             "#10C25B",   # Greens green
    "Independent":            "#7B3FA0",   # Purple — distinctive
    "Centre Alliance":        "#FF8C00",
    "Katter's Australian Party (KAP)": "#B8860B",
}


# ----------------------------------------------------------------------------
# Data loading + prep
# ----------------------------------------------------------------------------
@st.cache_data
def load_data():
    """Load the cleaned AEC dataset and build a per-division summary."""
    df = pd.read_csv("data/aec_cleaned.csv")

    # Drop informal vote rows (no party / candidate)
    candidates = df.dropna(subset=["PartyAb"]).copy()

    # One row per division: geography
    div_geo = (
        candidates[["DivisionNm", "StateAb", "Latitude", "Longitude"]]
        .drop_duplicates("DivisionNm")
    )

    # Winner per division
    winners = candidates[candidates["Elected"]].copy()
    winners = winners[
        ["DivisionNm", "PartyNm_clean", "CandidateName", "Swing", "TotalVotes"]
    ].rename(
        columns={
            "PartyNm_clean": "WinnerParty",
            "CandidateName": "Winner",
            "Swing": "WinnerSwing",
            "TotalVotes": "WinnerVotes",
        }
    )

    # Best-performing independent per division (winner OR runner-up)
    inds = candidates[candidates["PartyNm_clean"] == "Independent"].copy()
    best_ind = (
        inds.sort_values("TotalVotes", ascending=False)
        .groupby("DivisionNm")
        .first()
        .reset_index()[["DivisionNm", "CandidateName", "Swing", "TotalVotes", "Elected"]]
        .rename(
            columns={
                "CandidateName": "TopIndependent",
                "Swing": "IndSwing",
                "TotalVotes": "IndVotes",
                "Elected": "IndWon",
            }
        )
    )

    # Combine
    merged = div_geo.merge(winners, on="DivisionNm", how="left")
    merged = merged.merge(best_ind, on="DivisionNm", how="left")
    merged["IndSwing"] = merged["IndSwing"].fillna(0)
    merged["IndVotes"] = merged["IndVotes"].fillna(0).astype(int)
    merged["TopIndependent"] = merged["TopIndependent"].fillna("No independent ran")
    merged["IndWon"] = merged["IndWon"].fillna(False)

    return merged, candidates


# ----------------------------------------------------------------------------
# Visual 1 — National overview map
# ----------------------------------------------------------------------------
def visual_1_overview(div_summary: pd.DataFrame):
    """Map of all 150 divisions, coloured by winning party."""
    fig = px.scatter_map(
        div_summary,
        lat="Latitude",
        lon="Longitude",
        color="WinnerParty",
        color_discrete_map=PARTY_COLOURS,
        size="WinnerVotes",
        size_max=18,
        hover_name="DivisionNm",
        hover_data={
            "StateAb": True,
            "Winner": True,
            "WinnerParty": True,
            "WinnerVotes": ":,",
            "Latitude": False,
            "Longitude": False,
        },
        zoom=3.2,
        center={"lat": -27, "lon": 133},
        height=600,
    )
    fig.update_layout(
        map_style="carto-positron",
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            title="Winning party",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.85)",
        ),
    )
    return fig


# ----------------------------------------------------------------------------
# Visual 2 — The independent surge
# ----------------------------------------------------------------------------
def visual_2_independents(div_summary: pd.DataFrame):
    """Map of where independents won + where they almost won.

    Categorises every division into 4 groups based on how the
    top independent performed.
    """
    df = div_summary.copy()

    def categorise(row):
        if row["IndWon"]:
            return "Won"
        if row["IndSwing"] >= 15:
            return "Near miss (swing 15%+)"
        if row["IndSwing"] >= 5:
            return "Building (swing 5–15%)"
        if row["TopIndependent"] == "No independent ran":
            return "No independent ran"
        return "No traction"

    df["IndStatus"] = df.apply(categorise, axis=1)

    status_colours = {
        "Won":                     "#7B3FA0",   # purple
        "Near miss (swing 15%+)":  "#E94BCB",   # bright pink-purple
        "Building (swing 5–15%)":  "#FFB347",   # warm orange
        "No traction":             "#BBBBBB",   # grey
        "No independent ran":      "#E5E5E5",   # very light grey
    }
    status_order = [
        "Won",
        "Near miss (swing 15%+)",
        "Building (swing 5–15%)",
        "No traction",
        "No independent ran",
    ]

    # Bubble size: independents' vote count, with a minimum so dots are visible
    df["BubbleSize"] = df["IndVotes"].clip(lower=2000)

    fig = px.scatter_map(
        df,
        lat="Latitude",
        lon="Longitude",
        color="IndStatus",
        category_orders={"IndStatus": status_order},
        color_discrete_map=status_colours,
        size="BubbleSize",
        size_max=22,
        hover_name="DivisionNm",
        hover_data={
            "StateAb": True,
            "TopIndependent": True,
            "IndSwing": ":+.2f",
            "IndVotes": ":,",
            "WinnerParty": True,
            "Winner": True,
            "BubbleSize": False,
            "IndStatus": False,
            "Latitude": False,
            "Longitude": False,
        },
        zoom=3.2,
        center={"lat": -27, "lon": 133},
        height=600,
    )
    fig.update_layout(
        map_style="carto-positron",
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            title="Top independent's result",
            orientation="v",
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.85)",
        ),
    )
    return fig


# ----------------------------------------------------------------------------
# App
# ----------------------------------------------------------------------------
def main():
    div_summary, candidates = load_data()

    # ---- Header
    st.title("🗳️ The Independents Are Coming")
    st.markdown(
        "##### A data narrative on the 2025 Australian federal election"
    )
    st.caption(
        "UTS MDSI · Data Narrative Studio · Group project"
    )
    st.divider()

    # ---- Visual 1
    st.header("1. The headline result")
    st.markdown(
        """
        On 3 May 2025, Australians elected a Labor government with a thumping
        majority — **94 of 150 House seats**. The Coalition (Liberal + LNP +
        Nationals combined) was reduced to just 43 seats, its worst result
        on record.

        Below is the map of who won every electorate. Each dot is one of
        Australia's 150 federal divisions, sized by total first-preference votes.
        """
    )

    st.plotly_chart(
        visual_1_overview(div_summary),
        use_container_width=True,
    )

    # Quick summary stats
    seat_counts = (
        div_summary.groupby("WinnerParty")
        .size()
        .sort_values(ascending=False)
        .reset_index(name="Seats")
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Labor seats", int(seat_counts.loc[seat_counts["WinnerParty"] == "Australian Labor Party", "Seats"].values[0]))
    coalition_seats = int(
        seat_counts.loc[seat_counts["WinnerParty"].isin(
            ["Liberal Party", "LNP", "National Party"]
        ), "Seats"].sum()
    )
    col2.metric("Coalition seats", coalition_seats)
    col3.metric("Independent seats", int(seat_counts.loc[seat_counts["WinnerParty"] == "Independent", "Seats"].values[0]))
    col4.metric("Greens seats", int(seat_counts.loc[seat_counts["WinnerParty"] == "The Greens", "Seats"].values[0]))

    st.divider()

    # ---- Visual 2
    st.header("2. The story underneath")
    st.markdown(
        """
        That headline obscures something more interesting.

        **10 independents won.** But look at where they *almost* won. The map
        below shows every electorate categorised by how the leading
        independent candidate performed — whether they won, came agonisingly
        close, or are building support for next time.
        """
    )

    st.plotly_chart(
        visual_2_independents(div_summary),
        use_container_width=True,
    )

    # Pull out the near-miss numbers for the takeaway
    df = div_summary.copy()
    won = df[df["IndWon"]]
    near_miss = df[(~df["IndWon"]) & (df["IndSwing"] >= 15)]
    building = df[(~df["IndWon"]) & (df["IndSwing"] >= 5) & (df["IndSwing"] < 15)]

    col1, col2, col3 = st.columns(3)
    col1.metric("Independents who won", len(won))
    col2.metric("Near misses (15%+ swing)", len(near_miss))
    col3.metric("Building support (5–15% swing)", len(building))

    st.markdown(
        f"""
        **In 2022 the teals shocked Australia by winning 6 wealthy Liberal seats.
        In 2025 they held them — but {len(near_miss)} more independents picked
        up swings of 15 percentage points or more without winning.**

        These weren't the inner-city seats people associate with the teals.
        They were outer suburbs, regional towns, and overlooked corners of
        the country. Hover any pink dot above to see who came close, where,
        and by how much.
        """
    )

    if len(near_miss) > 0:
        st.markdown("##### The closest 'near misses'")
        near_miss_table = near_miss.nlargest(10, "IndSwing")[
            ["DivisionNm", "StateAb", "TopIndependent", "IndSwing", "IndVotes", "WinnerParty"]
        ].rename(columns={
            "DivisionNm": "Division",
            "StateAb": "State",
            "TopIndependent": "Independent candidate",
            "IndSwing": "Swing (pp)",
            "IndVotes": "Votes",
            "WinnerParty": "Seat held by",
        })
        st.dataframe(near_miss_table, hide_index=True, use_container_width=True)

    st.divider()
    st.caption(
        "Data source: Australian Electoral Commission, House First Preferences "
        "by Candidate by Vote Type, 2025 Federal Election."
    )


if __name__ == "__main__":
    main()

