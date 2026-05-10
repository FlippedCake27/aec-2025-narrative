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
    winners[winners["ElectionYear"] == 2025]
    .groupby(["StateAb", "PartyGroup"])
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
    "WA":  {"lat": -25.5, "lon": 122.0},
    "SA":  {"lat": -30.0, "lon": 135.5},
    "TAS": {"lat": -42.5, "lon": 146.5},
    "ACT": {"lat": -35.5, "lon": 150.5},
    "NT":  {"lat": -19.0, "lon": 133.0}
}

state_data["lat"] = state_data["StateAb"].map(lambda x: state_coords[x]["lat"])
state_data["lon"] = state_data["StateAb"].map(lambda x: state_coords[x]["lon"])

import math
state_data["BubbleSize"] = state_data["TotalSeats"].apply(
    lambda s: math.sqrt(s) * 11 + 10
)

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

    state_data["BubbleLabel"] = state_data.apply(
        lambda r: f"{r['StateAb']}  {int(r['TotalSeats'])}seats", axis=1
    )

    fig_map = go.Figure()

    # Dark base layer — makes coloured bubbles pop
    fig_map.add_trace(
        go.Choropleth(
            geojson=australia_geojson,
            locations=state_data["StateName"],
            z=[1] * len(state_data),
            featureidkey="properties.STATE_NAME",
            colorscale=[[0, "#1e2d3d"], [1, "#1e2d3d"]],
            showscale=False,
            marker_line_color="#4a6080",
            marker_line_width=1.5,
            hoverinfo="skip",
        )
    )

    # Coloured bubbles, one per state
    fig_map.add_trace(
        go.Scattergeo(
            lon=state_data["lon"],
            lat=state_data["lat"],
            mode="markers",
            marker=dict(
                size=state_data["BubbleSize"],
                color=state_data["DominantBloc"].map(PARTY_COLOURS),
                opacity=0.95,
                line=dict(width=2.5, color="white"),
            ),
            text=state_data["Tooltip"],
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )

    # State abbreviation label inside bubble
    fig_map.add_trace(
        go.Scattergeo(
            lon=state_data["lon"],
            lat=state_data["lat"],
            text=state_data["StateAb"],
            mode="text",
            textfont=dict(size=12, color="white", family="Arial Black"),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Invisible traces for legend
    for bloc in PARTY_ORDER:
        if bloc in state_data["DominantBloc"].values:
            count = int(state_data.loc[state_data["DominantBloc"] == bloc, "TotalSeats"].sum())
            fig_map.add_trace(go.Scattergeo(
                lon=[None], lat=[None],
                mode="markers",
                marker=dict(size=12, color=PARTY_COLOURS[bloc]),
                name=f"{bloc} ({count} seats)",
                showlegend=True,
            ))

    fig_map.update_geos(
        fitbounds="locations",
        visible=False,
        showcountries=False,
        showcoastlines=False,
        projection_type="equirectangular",
        bgcolor="#0f1923",
    )

    fig_map.update_layout(
        title="Which bloc dominates each state?",
        height=560,
        margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="#0f1923",
        font=dict(size=13, color="white"),
        legend=dict(
            title="Dominant bloc",
            orientation="v",
            bgcolor="rgba(255,255,255,0.08)",
            bordercolor="rgba(255,255,255,0.2)",
            borderwidth=1,
            x=0.01, y=0.98,
            font=dict(color="white"),
        ),
        title_font=dict(color="white"),
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

# ── Section 2: Rise of Independents ──────────────────────────────────────────
st.markdown("## 2. The rise of independents")
st.markdown(
    """
    Insert Explanations Here
    """
)

seats_by_year = (
    winners.groupby(["ElectionYear", "PartyGroup"])
    .size()
    .reset_index(name="Seats")
)

# Ensure all parties appear in all years (fill missing with 0)
all_years = sorted(df["ElectionYear"].unique())
idx = pd.MultiIndex.from_product([all_years, PARTY_ORDER], names=["ElectionYear", "PartyGroup"])
seats_by_year = (
    seats_by_year.set_index(["ElectionYear", "PartyGroup"])
    .reindex(idx, fill_value=0)
    .reset_index()
)

fig_trend = go.Figure()

for party in PARTY_ORDER:
    party_data = seats_by_year[seats_by_year["PartyGroup"] == party].sort_values("ElectionYear")
    is_ind = party == "Independent"
    fig_trend.add_trace(go.Scatter(
        x=party_data["ElectionYear"],
        y=party_data["Seats"],
        name=party,
        mode="lines+markers",
        line=dict(
            color=PARTY_COLOURS[party],
            width=4 if is_ind else 2,
            dash="solid" if is_ind else "dot"
        ),
        marker=dict(size=10 if is_ind else 6),
        hovertemplate=f"<b>{party}</b><br>%{{x}}: %{{y}} seats<extra></extra>"
    ))

fig_trend.add_annotation(
    x=2022, y=10,
    text="Teal wave:<br>3 → 10 seats",
    showarrow=True, arrowhead=2,
    ax=-70, ay=-45,
    font=dict(size=12, color=PARTY_COLOURS["Independent"]),
    bgcolor="rgba(0,0,0,0.6)",
    bordercolor=PARTY_COLOURS["Independent"],
    borderwidth=1.5
)

fig_trend.update_layout(
    title="Seats won per election by party group (2013–2025)",
    xaxis=dict(tickvals=all_years, title="Election Year", tickformat="d"),
    yaxis_title="Seats",
    height=420,
    margin=dict(l=10, r=10, t=50, b=10),
    legend_title_text="Party bloc",
)

st.plotly_chart(fig_trend, use_container_width=True)

st.info("Insert Explanations Here")

st.divider()

# ── Section 3: Momentum — how did they win? ───────────────────────────────────
st.markdown("## 3. The momentum behind the wins")
st.markdown(
    """
    Insert Explanations Here
    """
)

w25 = winners[winners["ElectionYear"] == 2025].copy()
swing_by_party = (
    w25.groupby("PartyGroup")["Swing"]
    .mean()
    .reset_index()
    .sort_values("Swing", ascending=True)
)
swing_by_party = swing_by_party[swing_by_party["PartyGroup"].isin(["Labor", "Coalition", "Greens", "Independent"])]

fig_swing = go.Figure(go.Bar(
    x=swing_by_party["Swing"],
    y=swing_by_party["PartyGroup"],
    orientation="h",
    marker_color=[PARTY_COLOURS[p] for p in swing_by_party["PartyGroup"]],
    text=swing_by_party["Swing"].apply(lambda x: f"{x:+.1f}%"),
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>Average swing: %{text}<extra></extra>"
))

fig_swing.add_vline(x=0, line_color="white", line_width=1.5, line_dash="dash")

fig_swing.update_layout(
    title="Average swing toward winning candidates by party bloc (2025)",
    xaxis=dict(title="Average swing (%)", ticksuffix="%"),
    yaxis_title="",
    height=340,
    margin=dict(l=10, r=80, t=50, b=10),
)

st.plotly_chart(fig_swing, use_container_width=True)

st.info("Insert Explanations Here")

st.divider()

# ── Section 4: The representation gap ────────────────────────────────────────
st.markdown("## 4. The representation gap: votes vs seats")
st.markdown(
    """
    Insert Explanations Here
    """
)

df25 = df[df["ElectionYear"] == 2025]
total_votes_25 = df25["TotalVotes"].sum()

vote_share_25 = (
    df25.groupby("PartyGroup")["TotalVotes"].sum() / total_votes_25 * 100
).reset_index(name="VoteShare")

seats_25 = (
    winners[winners["ElectionYear"] == 2025]
    .groupby("PartyGroup").size()
    .reset_index(name="Seats")
)
total_seats_25 = int(seats_25["Seats"].sum())
seats_25["SeatShare"] = seats_25["Seats"] / total_seats_25 * 100

dumbbell_df = vote_share_25.merge(seats_25[["PartyGroup", "SeatShare"]], on="PartyGroup", how="left").fillna(0)
dumbbell_df = dumbbell_df[dumbbell_df["PartyGroup"].isin(PARTY_ORDER)]
dumbbell_df["SortKey"] = dumbbell_df["PartyGroup"].map({p: i for i, p in enumerate(reversed(PARTY_ORDER))})
dumbbell_df = dumbbell_df.sort_values("SortKey")

fig_db = go.Figure()

for _, row in dumbbell_df.iterrows():
    colour = PARTY_COLOURS.get(row["PartyGroup"], "#999999")
    fig_db.add_trace(go.Scatter(
        x=[row["VoteShare"], row["SeatShare"]],
        y=[row["PartyGroup"], row["PartyGroup"]],
        mode="lines",
        line=dict(color=colour, width=3),
        showlegend=False,
        hoverinfo="skip"
    ))

fig_db.add_trace(go.Scatter(
    x=dumbbell_df["VoteShare"],
    y=dumbbell_df["PartyGroup"],
    mode="markers",
    name="Vote share %",
    marker=dict(
        size=16,
        color="rgba(0,0,0,0)",
        line=dict(width=3, color=[PARTY_COLOURS.get(p, "#999") for p in dumbbell_df["PartyGroup"]])
    ),
    text=dumbbell_df["VoteShare"].apply(lambda x: f"{x:.1f}%"),
    hovertemplate="<b>%{y}</b><br>Votes: %{text}<extra></extra>"
))

fig_db.add_trace(go.Scatter(
    x=dumbbell_df["SeatShare"],
    y=dumbbell_df["PartyGroup"],
    mode="markers",
    name="Seat share %",
    marker=dict(
        size=16,
        color=[PARTY_COLOURS.get(p, "#999") for p in dumbbell_df["PartyGroup"]]
    ),
    text=dumbbell_df["SeatShare"].apply(lambda x: f"{x:.1f}%"),
    hovertemplate="<b>%{y}</b><br>Seats: %{text}<extra></extra>"
))

fig_db.update_layout(
    title="Vote share vs seat share — 2025 Australian federal election",
    xaxis=dict(title="Percentage (%)", ticksuffix="%", range=[-2, 70]),
    yaxis_title="",
    height=380,
    margin=dict(l=10, r=10, t=50, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1),
)

st.plotly_chart(fig_db, use_container_width=True)

st.info("Insert Explanations Here")

st.divider()
st.caption(
    "Data source: Australian Electoral Commission, House First Preferences by Candidate by Vote Type, "
    "cleaned and merged with polling place centroids."
)