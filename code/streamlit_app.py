# IMPORTS
# Standard libraries for the app, data handling, charts, and file paths
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import json
import math

# PAGE CONFIG
# Sets the browser tab title, icon, and uses the full screen width
st.set_page_config(
    page_title="AEC 2025 — Beyond the Headlines",
    page_icon="🗳️",
    layout="wide"
)

# App title and subtitle shown at the top of the page
st.title("🗳️ Beyond the Headlines")
st.markdown("##### A data narrative on the 2025 Australian federal election")
st.caption("UTS 36104 · Data Visualisation and Narratives · Group project")
st.divider()

# LOAD DATA
csv_path = Path(__file__).parent.parent / "data" / "aec_cleaned.csv"
df = pd.read_csv(csv_path)

# Drop rows with no party abbreviation — these are unusable for analysis
df = df.dropna(subset=["PartyAb"]).copy()

# Convert the Elected column (which may be "Y", "TRUE", or "1") into a proper boolean
df["ElectedBool"] = df["Elected"].astype(str).str.upper().isin(["TRUE", "Y", "1"])

# Make sure vote and swing columns are numeric — some may come in as strings
for col in ["TotalVotes", "Swing", "PrePollShare"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# PARTY GROUPING
# Maps each party name to one of five broad blocs for consistent colour coding
# Handles variations like "LNP" vs "Liberal Party" vs "Liberal National Party of Queensland"
def party_group(name):
    if pd.isna(name):
        return "Other"
    name = str(name).strip()
    lower = name.lower()
    if name in ["Australian Labor Party", "ALP"]:
        return "Labor"
    if name in ["Liberal Party", "LNP", "Liberal National Party of Queensland", "National Party", "The Nationals"]:
        return "Coalition"
    if name == "The Greens" or "greens" in lower:
        return "Greens"
    if "independent" in lower or "teal" in lower:
        return "Independent"
    return "Other"

df["PartyGroup"] = df["PartyNm_clean"].apply(party_group)

# SHARED COLOUR AND ORDER CONSTANTS
# Used consistently across every chart so colours always mean the same party
PARTY_COLOURS = {
    "Labor": "#DE3533",
    "Coalition": "#1C4F9C",
    "Greens": "#10C25B",
    "Independent": "#7B3FA0",
    "Other": "#999999",
}
# This order controls how parties stack in bar charts and appear in legends
PARTY_ORDER = ["Labor", "Coalition", "Greens", "Independent", "Other"]

# Full state names used to match the GeoJSON property names
STATE_NAMES = {
    "NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland",
    "WA": "Western Australia", "SA": "South Australia", "TAS": "Tasmania",
    "ACT": "Australian Capital Territory", "NT": "Northern Territory"
}

# Approximate centre coordinates for each state — used to place bubbles on the map
STATE_COORDS = {
    "NSW": (-32.5, 147.0), "VIC": (-37.0, 144.5), "QLD": (-22.5, 144.5),
    "WA":  (-25.5, 122.0), "SA":  (-30.0, 135.5), "TAS": (-42.5, 146.5),
    "ACT": (-35.5, 150.5), "NT":  (-19.0, 133.0)
}

# WINNERS TABLE
# Filter down to only the winning candidates
# Fallback: if ElectedBool is all False (data issue), pick the top vote-getter per division
winners = df[df["ElectedBool"]].copy()
if winners.empty:
    winners = (
        df.sort_values(["DivisionID", "TotalVotes"], ascending=[True, False])
        .groupby("DivisionID", as_index=False).first()
    )

# GEOJSON
# Load the Australian state boundaries once — reused in Sections 1 and 4
with open(Path("data/australian-states.json"), "r", encoding="utf-8") as f:
    australia_geojson = json.load(f)

# SECTION 1 DATA PREP
# Count how many seats each party won per state in 2025
seat_counts = (
    winners[winners["ElectionYear"] == 2025]
    .groupby(["StateAb", "PartyGroup"]).size().reset_index(name="Seats")
)

# Pivot so each party becomes its own column, one row per state
state_data = (
    seat_counts.pivot(index="StateAb", columns="PartyGroup", values="Seats")
    .fillna(0).reset_index()
)

# Make sure all five party columns exist even if a party won zero seats
for col in PARTY_ORDER:
    if col not in state_data.columns:
        state_data[col] = 0

# Add summary columns: total seats and which party group won the most
state_data["TotalSeats"]   = state_data[PARTY_ORDER].sum(axis=1)
state_data["DominantBloc"] = state_data[PARTY_ORDER].idxmax(axis=1)

# Attach full state names and coordinates for the map
state_data["StateName"] = state_data["StateAb"].map(STATE_NAMES)
state_data["lat"] = state_data["StateAb"].map(lambda x: STATE_COORDS[x][0])
state_data["lon"] = state_data["StateAb"].map(lambda x: STATE_COORDS[x][1])

# Bubble size scales with seat count using square root so large states don't dwarf small ones
state_data["BubbleSize"] = state_data["TotalSeats"].apply(lambda s: math.sqrt(s) * 11 + 10)

# Pre-build the hover tooltip HTML for each state bubble
state_data["Tooltip"] = state_data.apply(
    lambda r: (
        f"<b>{r['StateName']}</b><br>"
        f"Dominant bloc: <b>{r['DominantBloc']}</b><br>"
        f"Total seats: {int(r['TotalSeats'])}<br>"
        f"Labor: {int(r['Labor'])}<br>"
        f"Coalition: {int(r['Coalition'])}<br>"
        f"Greens: {int(r['Greens'])}<br>"
        f"Independent: {int(r['Independent'])}<br>"
        f"Other: {int(r['Other'])}"
    ), axis=1
)

# SECTION 1 — AUSTRALIA'S CURRENT ELECTORAL MAP
# Shows a bubble map (dominant bloc per state) + stacked bar chart (seats by state)
st.markdown("## 1. Australia's current electoral map")
st.markdown("Insert Explanations Here")

# Filter winners to 2025 only for the summary metrics at the top
w25 = winners[winners["ElectionYear"] == 2025]

# Three headline numbers shown as metric cards
k1, k2, k3 = st.columns(3)
k1.metric("Independent-held seats (2025)", int((w25["PartyGroup"] == "Independent").sum()))
k2.metric("States with independent wins",  int(w25[w25["PartyGroup"] == "Independent"]["StateAb"].nunique()))
k3.metric("States in this overview",       int(state_data["StateAb"].nunique()))

# Split the row into a wider left column (map) and narrower right column (bar chart)
left, right = st.columns([1.25, 1])

with left:
    fig_map = go.Figure()

    # Layer 1: flat dark choropleth, just gives the states their outlines and background colour
    fig_map.add_trace(go.Choropleth(
        geojson=australia_geojson,
        locations=state_data["StateName"],
        z=[1] * len(state_data),
        featureidkey="properties.STATE_NAME",
        colorscale=[[0, "#1e2d3d"], [1, "#1e2d3d"]],
        showscale=False,
        marker_line_color="#4a6080",
        marker_line_width=1.5,
        hoverinfo="skip",           # tooltips come from the bubble layer instead
    ))

    # Layer 2: coloured bubbles centred on each state, sized by total seats
    fig_map.add_trace(go.Scattergeo(
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
    ))

    # Layer 3: state abbreviation labels drawn on top of the bubbles
    fig_map.add_trace(go.Scattergeo(
        lon=state_data["lon"],
        lat=state_data["lat"],
        text=state_data["StateAb"],
        mode="text",
        textfont=dict(size=12, color="white", family="Arial Black"),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Layer 4: invisible dummy traces used only to generate the legend entries
    for bloc in PARTY_ORDER:
        if bloc in state_data["DominantBloc"].values:
            count = int(state_data.loc[state_data["DominantBloc"] == bloc, "TotalSeats"].sum())
            fig_map.add_trace(go.Scattergeo(
                lon=[None], lat=[None], mode="markers",
                marker=dict(size=12, color=PARTY_COLOURS[bloc]),
                name=f"{bloc} ({count} seats)",
                showlegend=True,
            ))

    # Fit the map view to Australia and remove default geo decorations
    fig_map.update_geos(
        fitbounds="locations", visible=False,
        showcountries=False, showcoastlines=False,
        projection_type="equirectangular", bgcolor="#0f1923",
    )
    fig_map.update_layout(
        title="Which bloc dominates each state?",
        height=560, margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="#0f1923", font=dict(size=13, color="white"),
        legend=dict(
            title="Dominant bloc", orientation="v",
            bgcolor="rgba(255,255,255,0.08)", bordercolor="rgba(255,255,255,0.2)",
            borderwidth=1, x=0.01, y=0.98, font=dict(color="white"),
        ),
        title_font=dict(color="white"),
    )
    st.plotly_chart(fig_map, use_container_width=True)

with right:
    # Reshape state_data from wide (one column per party) to long (one row per state+party)
    state_long = state_data[["StateAb"] + PARTY_ORDER].melt(
        id_vars="StateAb", var_name="PartyGroup", value_name="Seats"
    )

    # Calculate each party's percentage share within its state for the in-bar labels
    state_long["Total"] = state_long.groupby("StateAb")["Seats"].transform("sum")
    state_long["Pct"]   = (state_long["Seats"] / state_long["Total"] * 100).round(0)

    # Only show the label if the segment is big enough to fit text (≥8%)
    state_long["Label"] = state_long.apply(
        lambda r: f"{int(r['Pct'])}%" if r["Seats"] > 0 and r["Pct"] >= 8 else "", axis=1
    )

    fig_bar = px.bar(
        state_long, x="StateAb", y="Seats",
        color="PartyGroup", text="Label",
        category_orders={"PartyGroup": PARTY_ORDER},
        color_discrete_map=PARTY_COLOURS,
        title="How seats are distributed across states",
        template="plotly_dark",
        custom_data=["PartyGroup", "Seats", "Pct"]   # passed into the hover template below
    )
    # Force all percentage labels to be horizontal (Plotly auto-rotates them otherwise)
    fig_bar.update_traces(
        textposition="inside", insidetextanchor="middle", textangle=0,
        textfont=dict(size=11, color="white"),
        hovertemplate="<b>%{x}</b> — %{customdata[0]}<br>Seats: %{customdata[1]:.0f} (%{customdata[2]:.0f}%)<extra></extra>"
    )
    fig_bar.update_layout(
        height=420, margin=dict(l=10, r=10, t=50, b=10),
        xaxis_title="State", yaxis_title="Seats",
        legend_title_text="Bloc", barmode="stack",
        paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
        font=dict(color="#e8edf2"),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.info("Insert Explanations Here")
st.caption(
    "This overview is intentionally shown at the state level. "
    "Later sections zoom into electorates to show where independents are strongest."
)

st.divider()

# SECTION 2 — THE RISE OF INDEPENDENTS
# Line chart showing seats won by each party group across every election 2013–2025
st.markdown("## 2. The rise of independents")
st.markdown("Insert Explanations Here")

# Count seats won per party per election year
seats_by_year = (
    winners.groupby(["ElectionYear", "PartyGroup"]).size().reset_index(name="Seats")
)

# Fill in zeros for any party/year combinations that are missing
# (e.g. if Independents won 0 seats in 2013, that row won't exist without this step)
all_years = sorted(df["ElectionYear"].unique())
idx = pd.MultiIndex.from_product([all_years, PARTY_ORDER], names=["ElectionYear", "PartyGroup"])
seats_by_year = (
    seats_by_year.set_index(["ElectionYear", "PartyGroup"])
    .reindex(idx, fill_value=0).reset_index()
)

fig_trend = go.Figure()

# Add one line per party — Independent gets a thicker solid line to make it stand out
for party in PARTY_ORDER:
    pdata = seats_by_year[seats_by_year["PartyGroup"] == party].sort_values("ElectionYear")
    is_ind = party == "Independent"
    fig_trend.add_trace(go.Scatter(
        x=pdata["ElectionYear"], y=pdata["Seats"],
        name=party, mode="lines+markers",
        line=dict(color=PARTY_COLOURS[party], width=4 if is_ind else 2, dash="solid" if is_ind else "dot"),
        marker=dict(size=10 if is_ind else 6),
        hovertemplate=f"<b>{party}</b><br>%{{x}}: %{{y}} seats<extra></extra>"
    ))

# Annotation pointing to the 2022 teal wave — a key moment in the narrative
fig_trend.add_annotation(
    x=2022, y=10, text="Teal wave:<br>3 → 10 seats",
    showarrow=True, arrowhead=2, ax=-70, ay=-45,
    font=dict(size=12, color=PARTY_COLOURS["Independent"]),
    bgcolor="rgba(0,0,0,0.6)",
    bordercolor=PARTY_COLOURS["Independent"], borderwidth=1.5
)
fig_trend.update_layout(
    title="Seats won per election by party group (2013–2025)",
    xaxis=dict(tickvals=all_years, title="Election Year", tickformat="d"),
    yaxis_title="Seats", height=420,
    margin=dict(l=10, r=10, t=50, b=10),
    legend_title_text="Party bloc",
    paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
    font=dict(color="#e8edf2"),
)
st.plotly_chart(fig_trend, use_container_width=True)
st.info("Insert Explanations Here")

st.divider()

# SECTION 3 — THE MOMENTUM BEHIND THE WINS
# Horizontal bar chart of average first-preference swing for 2025 winners by party
st.markdown("## 3. The momentum behind the wins")
st.markdown("Insert Explanations Here")

# Average swing for winning candidates only, grouped by party bloc
# Swing = change in first-preference vote share compared to the previous election
swing_by_party = (
    w25.groupby("PartyGroup")["Swing"].mean()
    .reset_index().sort_values("Swing", ascending=True)
)
# Exclude "Other" as it's a catch-all that doesn't tell a clean story
swing_by_party = swing_by_party[swing_by_party["PartyGroup"].isin(["Labor", "Coalition", "Greens", "Independent"])]

fig_swing = go.Figure(go.Bar(
    x=swing_by_party["Swing"],
    y=swing_by_party["PartyGroup"],
    orientation="h",
    marker_color=[PARTY_COLOURS[p] for p in swing_by_party["PartyGroup"]],
    text=swing_by_party["Swing"].apply(lambda x: f"{x:+.1f}%"),
    textposition="outside",
    hovertemplate="<b>%{y}</b><br>Average swing: %{x:+.2f}%<extra></extra>"
))

# Vertical reference line at zero so positive/negative swings are immediately clear
fig_swing.add_vline(x=0, line_color="white", line_width=1.5, line_dash="dash")
fig_swing.update_layout(
    title="Average swing toward winning candidates by party bloc (2025)",
    xaxis=dict(title="Average swing (%)", ticksuffix="%"),
    yaxis_title="", height=340,
    margin=dict(l=10, r=80, t=50, b=10),
    paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
    font=dict(color="#e8edf2"),
)
st.plotly_chart(fig_swing, use_container_width=True)
st.info("Insert Explanations Here")

st.divider()

# SECTION 4 — WHERE ARE INDEPENDENTS STRONGEST?
# Scatter map showing every independent candidate's vote share across all electorates
# Elected candidates shown as solid dots; unsuccessful ones as faint hollow dots
st.markdown("## 4. Where are independents strongest?")
st.markdown("Insert Explanations Here")

# Start with all 2025 candidates and calculate each one's share of their division's total vote
df25_all = df[df["ElectionYear"] == 2025].copy()
div_totals = df25_all.groupby("DivisionID")["TotalVotes"].sum().reset_index(name="DivisionTotal")
df25_all = df25_all.merge(div_totals, on="DivisionID", how="left")
df25_all["VoteSharePct"] = (df25_all["TotalVotes"] / df25_all["DivisionTotal"] * 100).round(1)

# Keep only independent candidates, and if a division had multiple independents,
# keep the one with the highest vote share (most relevant for the map)
ind_best = (
    df25_all[df25_all["PartyGroup"] == "Independent"]
    .sort_values("VoteSharePct", ascending=False)
    .groupby("DivisionID", as_index=False).first()
    .dropna(subset=["Latitude", "Longitude"])   # drop any rows missing map coordinates
)

# Split into winners and non-winners so they can be styled differently
ind_winners = ind_best[ind_best["ElectedBool"]]
ind_others  = ind_best[~ind_best["ElectedBool"]]

fig_ind = go.Figure()

# Base layer: same flat dark choropleth as Section 1 for consistent look
fig_ind.add_trace(go.Choropleth(
    geojson=australia_geojson,
    locations=state_data["StateName"],
    z=[1] * len(state_data),
    featureidkey="properties.STATE_NAME",
    colorscale=[[0, "#1e2d3d"], [1, "#1e2d3d"]],
    showscale=False, marker_line_color="#4a6080", marker_line_width=1.5, hoverinfo="skip",
))

# Faint hollow dots for independents who ran but didn't win
# Bubble size is proportional to their vote share so strength is visible at a glance
fig_ind.add_trace(go.Scattergeo(
    lon=ind_others["Longitude"], lat=ind_others["Latitude"],
    mode="markers", name="Did not win",
    marker=dict(
        size=ind_others["VoteSharePct"] / 2.5 + 4,
        color="rgba(123, 63, 160, 0.3)",
        line=dict(width=1.5, color=PARTY_COLOURS["Independent"]),
    ),
    text=ind_others.apply(
        lambda r: (
            f"<b>{r['DivisionNm']}</b> ({r['StateAb']})<br>"
            f"{r['CandidateName']}<br>"
            f"Vote share: {r['VoteSharePct']:.1f}%<br>"
            f"Did not win"
        ), axis=1
    ),
    hovertemplate="%{text}<extra></extra>",
))

# Bright solid dots for elected independents — larger and with a white border to pop
fig_ind.add_trace(go.Scattergeo(
    lon=ind_winners["Longitude"], lat=ind_winners["Latitude"],
    mode="markers", name="Elected",
    marker=dict(
        size=ind_winners["VoteSharePct"] / 2.5 + 8,
        color=PARTY_COLOURS["Independent"],
        line=dict(width=2, color="white"),
    ),
    text=ind_winners.apply(
        lambda r: (
            f"<b>{r['DivisionNm']}</b> ({r['StateAb']})<br>"
            f"{r['CandidateName']}<br>"
            f"Vote share: {r['VoteSharePct']:.1f}%<br>"
            f"✓ Elected"
        ), axis=1
    ),
    hovertemplate="%{text}<extra></extra>",
))
fig_ind.update_geos(
    fitbounds="locations", visible=False,
    showcountries=False, showcoastlines=False,
    projection_type="equirectangular", bgcolor="#0f1923",
)
fig_ind.update_layout(
    title="Independent candidate vote share by electorate (2025)",
    height=560, margin=dict(l=10, r=10, t=50, b=10),
    paper_bgcolor="#0f1923", font=dict(size=13, color="#e8edf2"),
    legend=dict(
        title="", orientation="v",
        bgcolor="rgba(255,255,255,0.08)", bordercolor="rgba(255,255,255,0.2)",
        borderwidth=1, x=0.01, y=0.98, font=dict(color="white"),
    ),
)
st.plotly_chart(fig_ind, use_container_width=True)
st.info("Insert Explanations Here")

st.divider()

# SECTION 5 — THE REPRESENTATION GAP: VOTES VS SEATS
# Dumbbell chart comparing how many votes each party got vs how many seats they won
# The gap between the two dots shows how fairly (or unfairly) the system translates votes to seats
st.markdown("## 5. The representation gap: votes vs seats")
st.markdown("Insert Explanations Here")

# Vote share: each party's total first-preference votes as a % of all 2025 votes
df25 = df[df["ElectionYear"] == 2025]
total_votes_25 = df25["TotalVotes"].sum()
vote_share_25 = (
    df25.groupby("PartyGroup")["TotalVotes"].sum() / total_votes_25 * 100
).reset_index(name="VoteShare")

# Seat share: how many seats each party won as a % of total seats
seats_25 = w25.groupby("PartyGroup").size().reset_index(name="Seats")
total_seats_25 = int(seats_25["Seats"].sum())
seats_25["SeatShare"] = seats_25["Seats"] / total_seats_25 * 100

# Merge vote share and seat share into one table for the dumbbell chart
dumbbell_df = vote_share_25.merge(seats_25[["PartyGroup", "SeatShare", "Seats"]], on="PartyGroup", how="left").fillna(0)
dumbbell_df = dumbbell_df[dumbbell_df["PartyGroup"].isin(PARTY_ORDER)]

# Sort so parties appear in a consistent vertical order matching PARTY_ORDER
dumbbell_df["SortKey"] = dumbbell_df["PartyGroup"].map({p: i for i, p in enumerate(reversed(PARTY_ORDER))})
dumbbell_df = dumbbell_df.sort_values("SortKey")

fig_db = go.Figure()

# Draw a coloured horizontal line connecting the two dots for each party
for _, row in dumbbell_df.iterrows():
    colour = PARTY_COLOURS.get(row["PartyGroup"], "#999999")
    fig_db.add_trace(go.Scatter(
        x=[row["VoteShare"], row["SeatShare"]],
        y=[row["PartyGroup"], row["PartyGroup"]],
        mode="lines", line=dict(color=colour, width=3),
        showlegend=False, hoverinfo="skip"
    ))

# Left dot (hollow) = vote share — open circle to visually suggest "input"
fig_db.add_trace(go.Scatter(
    x=dumbbell_df["VoteShare"],
    y=dumbbell_df["PartyGroup"],
    mode="markers+text", name="Vote share %",
    marker=dict(
        size=16, color="rgba(0,0,0,0)",
        line=dict(width=3, color=[PARTY_COLOURS.get(p, "#999") for p in dumbbell_df["PartyGroup"]])
    ),
    text=dumbbell_df["VoteShare"].apply(lambda x: f"{x:.1f}%"),
    textposition="middle left",     # label sits to the left of the dot
    textfont=dict(size=11, color="#e8edf2"),
    customdata=dumbbell_df[["SeatShare", "Seats"]].values,
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Votes: %{text}<br>"
        "Seats: %{customdata[0]:.1f}% (%{customdata[1]:.0f} seats)<extra></extra>"
    )
))

# Right dot (filled) = seat share — solid circle to suggest "outcome"
fig_db.add_trace(go.Scatter(
    x=dumbbell_df["SeatShare"],
    y=dumbbell_df["PartyGroup"],
    mode="markers+text", name="Seat share %",
    marker=dict(
        size=16,
        color=[PARTY_COLOURS.get(p, "#999") for p in dumbbell_df["PartyGroup"]]
    ),
    text=dumbbell_df["SeatShare"].apply(lambda x: f"{x:.1f}%"),
    textposition="middle right",    # label sits to the right of the dot
    textfont=dict(size=11, color="#e8edf2"),
    customdata=dumbbell_df[["VoteShare", "Seats"]].values,
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Seats: %{text} (%{customdata[1]:.0f} seats)<br>"
        "Votes: %{customdata[0]:.1f}%<extra></extra>"
    )
))

# Widen the x-axis range a little to give the text labels room on both sides
fig_db.update_layout(
    title="Vote share vs seat share — 2025 Australian federal election",
    xaxis=dict(title="Percentage (%)", ticksuffix="%", range=[-8, 78]),
    yaxis_title="", height=380,
    margin=dict(l=10, r=10, t=50, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.08, xanchor="right", x=1),
    paper_bgcolor="#0f1923", plot_bgcolor="#0f1923",
    font=dict(color="#e8edf2"),
)
st.plotly_chart(fig_db, use_container_width=True)
st.info("Insert Explanations Here")

st.divider()
st.caption(
    "Data source: Australian Electoral Commission, House First Preferences by Candidate by Vote Type, "
    "cleaned and merged with polling place centroids."
)
