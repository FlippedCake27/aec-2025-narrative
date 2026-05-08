import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json

st.set_page_config(
    page_title="AEC 2025 — Beyond the Headlines",
    page_icon="🗳️",
    layout="wide"
)

st.title("🗳️ Beyond the Headlines")
st.markdown("##### A data narrative on the 2025 Australian federal election")
st.caption("UTS 36104 · Data Visualisation and Narratives · Group project")
st.divider()

possible_paths = [Path("data/aec_cleaned.csv"), Path("aec_cleaned.csv")]
csv_path = next((p for p in possible_paths if p.exists()), None)

if csv_path is None:
    st.error("Could not find aec_cleaned.csv. Put it in the same folder as this file, or inside a data folder.")
    st.stop()

df = pd.read_csv(csv_path)

df = df.dropna(subset=["PartyAb"]).copy()

elected_map = {
    "TRUE": True,
    "FALSE": False,
    "Y": True,
    "N": False,
    "1": True,
    "0": False
}
df["ElectedBool"] = df["Elected"].astype(str).str.upper().map(elected_map).fillna(False)

for col in ["TotalVotes", "Swing", "PrePollShare"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

def party_group(party_name):
    if pd.isna(party_name):
        return "Other"

    party_name = str(party_name).strip()
    lower_name = party_name.lower()

    if party_name in ["Australian Labor Party", "ALP"]:
        return "Labor"
    elif party_name in [
        "Liberal Party",
        "LNP",
        "Liberal National Party of Queensland",
        "National Party",
        "The Nationals"
    ]:
        return "Coalition"
    elif party_name == "The Greens" or "greens" in lower_name:
        return "Greens"
    elif "independent" in lower_name or "teal" in lower_name:
        return "Independent"
    else:
        return "Other"

df["PartyGroup"] = df["PartyNm_clean"].apply(party_group)

PARTY_COLOURS = {
    "Labor": "#DE3533",
    "Coalition": "#1C4F9C",
    "Greens": "#10C25B",
    "Independent": "#7B3FA0",
    "Other": "#999999",
}

PARTY_ORDER = ["Labor", "Coalition", "Greens", "Independent", "Other"]

winners = df[df["ElectedBool"] == True].copy()

if winners.empty:
    winners = (
        df.sort_values(["DivisionID", "TotalVotes"], ascending=[True, False])
        .groupby("DivisionID", as_index=False)
        .first()
    )

seat_counts = (
    winners.groupby(["StateAb", "PartyGroup"])
    .size()
    .reset_index(name="Seats")
)

state_data = (
    seat_counts.pivot(index="StateAb", columns="PartyGroup", values="Seats")
    .fillna(0)
    .reset_index()
)

for col in PARTY_ORDER:
    if col not in state_data.columns:
        state_data[col] = 0

state_data["TotalSeats"] = state_data[PARTY_ORDER].sum(axis=1)
state_data["DominantBloc"] = state_data[PARTY_ORDER].idxmax(axis=1)

state_name_map = {
    "NSW": "New South Wales",
    "VIC": "Victoria",
    "QLD": "Queensland",
    "WA": "Western Australia",
    "SA": "South Australia",
    "TAS": "Tasmania",
    "ACT": "Australian Capital Territory",
    "NT": "Northern Territory"
}

state_data["StateName"] = state_data["StateAb"].map(state_name_map)
state_data["StateLabel"] = state_data["StateAb"]

state_coords = {
    "NSW": {"lat": -32.5, "lon": 147.0},
    "VIC": {"lat": -37.0, "lon": 144.5},
    "QLD": {"lat": -22.5, "lon": 144.5},
    "WA": {"lat": -25.5, "lon": 122.0},
    "SA": {"lat": -30.0, "lon": 135.5},
    "TAS": {"lat": -42.0, "lon": 146.5},
    "ACT": {"lat": -35.5, "lon": 149.0},
    "NT": {"lat": -19.0, "lon": 133.0}
}

state_data["lat"] = state_data["StateAb"].map(lambda x: state_coords[x]["lat"])
state_data["lon"] = state_data["StateAb"].map(lambda x: state_coords[x]["lon"])

state_data["BubbleSize"] = (state_data["TotalSeats"]) + 25

state_data["Tooltip"] = state_data.apply(
    lambda row: (
        f"<b>{row['StateName']}</b><br>"
        f"Dominant bloc: <b>{row['DominantBloc']}</b><br>"
        f"Total seats: {int(row['TotalSeats'])}<br>"
        f"Labor: {int(row['Labor'])}<br>"
        f"Coalition: {int(row['Coalition'])}<br>"
        f"Greens: {int(row['Greens'])}<br>"
        f"Independent: {int(row['Independent'])}<br>"
        f"Other: {int(row['Other'])}"
    ),
    axis=1
)

st.markdown("## 1. Australia’s current electoral map")
st.markdown(
    """
    Insert Explanations Here
    """
)

total_independent_seats = int((winners["PartyGroup"] == "Independent").sum())
states_with_independent_winners = int(
    winners.loc[winners["PartyGroup"] == "Independent", "StateAb"].nunique()
)
total_states = int(state_data["StateAb"].nunique())

k1, k2, k3 = st.columns(3)
k1.metric("Independent-held seats", total_independent_seats)
k2.metric("States with independent wins", states_with_independent_winners)
k3.metric("States in this overview", total_states)

left, right = st.columns([1.25, 1])

with left:
    geojson_path = Path("data/australian-states.json")

    with open(geojson_path, "r", encoding="utf-8") as f:
        australia_geojson = json.load(f)

    fig_map = go.Figure()

    fig_map.add_trace(
        go.Choropleth(
            geojson=australia_geojson,
            locations=state_data["StateName"],
            z=[1] * len(state_data),
            featureidkey="properties.STATE_NAME",
            colorscale=[[0, "#f5f5f5"], [1, "#f5f5f5"]],
            showscale=False,
            marker_line_color="white",
            marker_line_width=2,
            hoverinfo="skip"
        )
    )

    fig_map.add_trace(
        go.Scattergeo(
            lon=state_data["lon"],
            lat=state_data["lat"],
            mode="markers",
            marker=dict(
                size=state_data["BubbleSize"],
                color=state_data["DominantBloc"].map(PARTY_COLOURS),
                opacity=0.95,
                line=dict(width=1.5, color="white")
            ),
            text=state_data["Tooltip"],
            hovertemplate="%{text}<extra></extra>",
            showlegend=False
        )
    )

    fig_map.add_trace(
        go.Scattergeo(
            lon=state_data["lon"],
            lat=state_data["lat"],
            text=state_data["StateLabel"],
            mode="text",
            textfont=dict(
                size=12,
                color="white",
                family="Arial Black"
            ),
            showlegend=False,
            hoverinfo="skip"
        )
    )

    fig_map.update_geos(
        fitbounds="locations",
        visible=False,
        showcountries=False,
        showcoastlines=True,
        coastlinecolor="LightGray",
        projection_type="equirectangular"
    )

    fig_map.update_layout(
        title="Which bloc dominates each state?",
        height=560,
        margin=dict(l=10, r=10, t=60, b=10),
        font=dict(size=13)
    )

    st.plotly_chart(fig_map, use_container_width=True)

with right:
    state_long = state_data[["StateAb"] + PARTY_ORDER].melt(
        id_vars="StateAb",
        var_name="PartyGroup",
        value_name="Seats"
    )

    fig_bar = px.bar(
        state_long,
        x="StateAb",
        y="Seats",
        color="PartyGroup",
        category_orders={"PartyGroup": PARTY_ORDER},
        color_discrete_map=PARTY_COLOURS,
        title="How seats are distributed across states"
    )

    fig_bar.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis_title="State",
        yaxis_title="Seats",
        legend_title_text="Bloc",
        barmode="stack"
    )

    st.plotly_chart(fig_bar, use_container_width=True)

strongest_ind_state_row = state_data.sort_values("Independent", ascending=False).iloc[0]
strongest_ind_state = strongest_ind_state_row["StateAb"]
strongest_ind_count = int(strongest_ind_state_row["Independent"])

st.info(
    f"Insert Explanations Here")

st.caption(
    "This overview is intentionally shown at the state level to keep the first scene simple and readable. "
    "Later sections can zoom into electorates to show where independents are strongest."
)

st.divider()
st.caption(
    "Data source: Australian Electoral Commission, House First Preferences by Candidate by Vote Type, "
    "cleaned and merged with polling place centroids."
)