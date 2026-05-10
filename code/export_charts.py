"""
Export 5 slide-ready chart PNGs for Shriya's presentation.
Run from the repo root: python3 code/export_charts.py
"""

import json
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA = ROOT / "data" / "aec_cleaned.csv"
GEOJSON = ROOT / "data" / "australian-states.json"
OUT = ROOT / "slides"
OUT.mkdir(exist_ok=True)

SCALE = 2        # pixel density multiplier (2 = retina / high-res)
WIDTH, HEIGHT = 1200, 700

# ── Data prep ────────────────────────────────────────────────────────────────
df = pd.read_csv(DATA)
df = df.dropna(subset=["PartyAb"]).copy()
df["ElectedBool"] = (
    df["Elected"].astype(str).str.upper()
    .map({"TRUE": True, "FALSE": False, "Y": True, "N": False})
    .fillna(False)
)
for col in ["TotalVotes", "Swing"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

def party_group(p):
    if pd.isna(p):
        return "Other"
    p = str(p).strip()
    l = p.lower()
    if p in ["Australian Labor Party", "ALP"]:
        return "Labor"
    if p in ["Liberal Party", "LNP", "Liberal National Party of Queensland",
             "National Party", "The Nationals"]:
        return "Coalition"
    if p == "The Greens" or "greens" in l:
        return "Greens"
    if "independent" in l or "teal" in l:
        return "Independent"
    return "Other"

df["PartyGroup"] = df["PartyNm_clean"].apply(party_group)
winners = df[df["ElectedBool"]].copy()

PARTY_ORDER = ["Labor", "Coalition", "Greens", "Independent", "Other"]
PARTY_COLOURS = {
    "Labor":       "#DE3533",
    "Coalition":   "#1C4F9C",
    "Greens":      "#10C25B",
    "Independent": "#7B3FA0",
    "Other":       "#999999",
}
LAYOUT_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Arial", size=15, color="#222222"),
    margin=dict(l=60, r=40, t=70, b=60),
)

all_years = sorted(df["ElectionYear"].unique())

# ── Chart 0: Bubble map — dominant bloc by state (2025) ──────────────────────
print("Generating chart 0: bubble map …")

import math

w25 = winners[winners["ElectionYear"] == 2025]
seat_counts_map = w25.groupby(["StateAb", "PartyGroup"]).size().reset_index(name="Seats")
state_data = (
    seat_counts_map.pivot(index="StateAb", columns="PartyGroup", values="Seats")
    .fillna(0)
    .reset_index()
)
for col in PARTY_ORDER:
    if col not in state_data.columns:
        state_data[col] = 0

state_data["TotalSeats"] = state_data[PARTY_ORDER].sum(axis=1)
state_data["DominantBloc"] = state_data[PARTY_ORDER].idxmax(axis=1)

state_name_map = {
    "NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland",
    "WA": "Western Australia", "SA": "South Australia", "TAS": "Tasmania",
    "ACT": "Australian Capital Territory", "NT": "Northern Territory",
}
state_data["StateName"] = state_data["StateAb"].map(state_name_map)

# Coordinates — slightly spread eastern states to reduce overlap
state_coords = {
    "NSW": {"lat": -32.5, "lon": 147.0},
    "VIC": {"lat": -37.0, "lon": 144.5},
    "QLD": {"lat": -22.5, "lon": 144.5},
    "WA":  {"lat": -25.5, "lon": 122.0},
    "SA":  {"lat": -30.0, "lon": 135.5},
    "TAS": {"lat": -42.5, "lon": 146.5},
    "ACT": {"lat": -35.5, "lon": 150.5},
    "NT":  {"lat": -19.0, "lon": 133.0},
}
state_data["lat"] = state_data["StateAb"].map(lambda x: state_coords[x]["lat"])
state_data["lon"] = state_data["StateAb"].map(lambda x: state_coords[x]["lon"])
state_data["BubbleSize"] = state_data["TotalSeats"].apply(lambda s: math.sqrt(s) * 11 + 10)
state_data["Tooltip"] = state_data.apply(
    lambda r: (
        f"<b>{r['StateName']}</b><br>"
        f"Dominant: <b>{r['DominantBloc']}</b><br>"
        f"Total seats: {int(r['TotalSeats'])}<br>"
        + "".join(f"{p}: {int(r[p])}<br>" for p in PARTY_ORDER if r[p] > 0)
    ), axis=1
)

with open(GEOJSON, "r", encoding="utf-8") as f:
    australia_geojson = json.load(f)

fig0 = go.Figure()

# Dark base layer
fig0.add_trace(go.Choropleth(
    geojson=australia_geojson,
    locations=state_data["StateName"],
    z=[1] * len(state_data),
    featureidkey="properties.STATE_NAME",
    colorscale=[[0, "#1e2d3d"], [1, "#1e2d3d"]],
    showscale=False,
    marker_line_color="#4a6080",
    marker_line_width=1.5,
    hoverinfo="skip",
))

# Coloured bubbles
fig0.add_trace(go.Scattergeo(
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

# State labels inside bubbles
fig0.add_trace(go.Scattergeo(
    lon=state_data["lon"],
    lat=state_data["lat"],
    text=state_data["StateAb"],
    mode="text",
    textfont=dict(size=13, color="white", family="Arial Black"),
    showlegend=False,
    hoverinfo="skip",
))

# Legend traces
for bloc in PARTY_ORDER:
    if bloc in state_data["DominantBloc"].values:
        count = int(state_data.loc[state_data["DominantBloc"] == bloc, "TotalSeats"].sum())
        fig0.add_trace(go.Scattergeo(
            lon=[None], lat=[None],
            mode="markers",
            marker=dict(size=14, color=PARTY_COLOURS[bloc]),
            name=f"{bloc} ({count} seats)",
            showlegend=True,
        ))

fig0.update_geos(
    fitbounds="locations", visible=False,
    showcountries=False, showcoastlines=False,
    projection_type="equirectangular",
    bgcolor="#0f1923",
)
fig0.update_layout(
    paper_bgcolor="#0f1923",
    title=dict(text="Which bloc dominates each state? — 2025", font=dict(color="white")),
    height=650, width=WIDTH,
    margin=dict(l=10, r=10, t=60, b=10),
    font=dict(family="Arial", size=15, color="white"),
    legend=dict(
        title="Dominant bloc",
        bgcolor="rgba(255,255,255,0.08)",
        bordercolor="rgba(255,255,255,0.2)",
        borderwidth=1,
        font=dict(color="white"),
    ),
)
fig0.write_image(OUT / "chart0_bubble_map.png", scale=SCALE)
print("  ✓ chart0_bubble_map.png")

# ── Chart 1: Stacked bar — seat distribution by state (2025) ─────────────────
print("Generating chart 1: seat distribution by state …")

w25 = winners[winners["ElectionYear"] == 2025]
seat_counts = w25.groupby(["StateAb", "PartyGroup"]).size().reset_index(name="Seats")
state_long = (
    seat_counts.pivot(index="StateAb", columns="PartyGroup", values="Seats")
    .fillna(0)
    .reset_index()
)
for col in PARTY_ORDER:
    if col not in state_long.columns:
        state_long[col] = 0

state_long_melted = state_long.melt(id_vars="StateAb", value_vars=PARTY_ORDER,
                                    var_name="PartyGroup", value_name="Seats")

fig1 = px.bar(
    state_long_melted,
    x="StateAb", y="Seats", color="PartyGroup",
    category_orders={"PartyGroup": PARTY_ORDER},
    color_discrete_map=PARTY_COLOURS,
    title="How seats are distributed across states — 2025",
)
fig1.update_layout(
    **LAYOUT_BASE,
    xaxis_title="State / Territory",
    yaxis_title="Seats",
    legend_title_text="Party bloc",
    barmode="stack",
    height=HEIGHT, width=WIDTH,
)
fig1.write_image(OUT / "chart1_seats_by_state.png", scale=SCALE)
print("  ✓ chart1_seats_by_state.png")

# ── Chart 2: Line — independent seats over time (2013–2025) ─────────────────
print("Generating chart 2: independent seats over time …")

seats_by_year = winners.groupby(["ElectionYear", "PartyGroup"]).size().reset_index(name="Seats")
idx = pd.MultiIndex.from_product([all_years, PARTY_ORDER], names=["ElectionYear", "PartyGroup"])
seats_by_year = (
    seats_by_year.set_index(["ElectionYear", "PartyGroup"])
    .reindex(idx, fill_value=0)
    .reset_index()
)

fig2 = go.Figure()
for party in PARTY_ORDER:
    d = seats_by_year[seats_by_year["PartyGroup"] == party].sort_values("ElectionYear")
    is_ind = party == "Independent"
    fig2.add_trace(go.Scatter(
        x=d["ElectionYear"], y=d["Seats"],
        name=party, mode="lines+markers",
        line=dict(color=PARTY_COLOURS[party], width=5 if is_ind else 2,
                  dash="solid" if is_ind else "dot"),
        marker=dict(size=12 if is_ind else 7),
        hovertemplate=f"<b>{party}</b><br>%{{x}}: %{{y}} seats<extra></extra>",
    ))

fig2.add_annotation(
    x=2022, y=10,
    text="Teal wave:<br>3 → 10 seats",
    showarrow=True, arrowhead=2, ax=-70, ay=-50,
    font=dict(size=13, color=PARTY_COLOURS["Independent"]),
    bgcolor="rgba(255,255,255,0.85)",
    bordercolor=PARTY_COLOURS["Independent"],
    borderwidth=1.5,
)
fig2.update_layout(
    **LAYOUT_BASE,
    title="Seats won per election by party bloc (2013–2025)",
    xaxis=dict(tickvals=all_years, title="Election Year", tickformat="d"),
    yaxis_title="Seats won",
    legend_title_text="Party bloc",
    height=HEIGHT, width=WIDTH,
)
fig2.write_image(OUT / "chart2_independent_rise.png", scale=SCALE)
print("  ✓ chart2_independent_rise.png")

# ── Chart 3: Horizontal bar — average swing by party (2025 winners) ──────────
print("Generating chart 3: average swing by party …")

swing_df = (
    w25[w25["PartyGroup"].isin(["Labor", "Coalition", "Greens", "Independent"])]
    .groupby("PartyGroup")["Swing"].mean()
    .reset_index()
    .sort_values("Swing", ascending=True)
)

fig3 = go.Figure(go.Bar(
    x=swing_df["Swing"],
    y=swing_df["PartyGroup"],
    orientation="h",
    marker_color=[PARTY_COLOURS[p] for p in swing_df["PartyGroup"]],
    text=swing_df["Swing"].apply(lambda x: f"{x:+.1f}%"),
    textposition="outside",
    textfont=dict(size=15),
))
fig3.add_vline(x=0, line_color="#555555", line_width=1.5, line_dash="dash")
fig3.update_layout(
    **LAYOUT_BASE,
    title="Average swing toward winning candidates by party bloc — 2025",
    xaxis=dict(title="Average swing (%)", ticksuffix="%", range=[-6, 11]),
    yaxis_title="",
    height=500, width=WIDTH,
)
fig3.write_image(OUT / "chart3_swing_by_party.png", scale=SCALE)
print("  ✓ chart3_swing_by_party.png")

# ── Chart 4: Dumbbell — vote share vs seat share (2025) ──────────────────────
print("Generating chart 4: vote share vs seat share …")

total_v = df[df["ElectionYear"] == 2025]["TotalVotes"].sum()
vote_s = (
    df[df["ElectionYear"] == 2025]
    .groupby("PartyGroup")["TotalVotes"].sum() / total_v * 100
).reset_index(name="VoteShare")

seats_25 = w25.groupby("PartyGroup").size().reset_index(name="Seats")
seats_25["SeatShare"] = seats_25["Seats"] / seats_25["Seats"].sum() * 100

ddf = vote_s.merge(seats_25[["PartyGroup", "SeatShare"]], on="PartyGroup", how="left").fillna(0)
ddf = ddf[ddf["PartyGroup"].isin(PARTY_ORDER)].copy()
ddf["SortKey"] = ddf["PartyGroup"].map({p: i for i, p in enumerate(PARTY_ORDER)})
ddf = ddf.sort_values("SortKey", ascending=False)

fig4 = go.Figure()
for _, row in ddf.iterrows():
    c = PARTY_COLOURS.get(row["PartyGroup"], "#999")
    fig4.add_trace(go.Scatter(
        x=[row["VoteShare"], row["SeatShare"]],
        y=[row["PartyGroup"], row["PartyGroup"]],
        mode="lines",
        line=dict(color=c, width=4),
        showlegend=False, hoverinfo="skip",
    ))

fig4.add_trace(go.Scatter(
    x=ddf["VoteShare"], y=ddf["PartyGroup"],
    mode="markers", name="Vote share %",
    marker=dict(size=18, color="white",
                line=dict(width=3, color=[PARTY_COLOURS.get(p, "#999") for p in ddf["PartyGroup"]])),
    text=ddf["VoteShare"].apply(lambda x: f"{x:.1f}%"),
    hovertemplate="<b>%{y}</b><br>Votes: %{text}<extra></extra>",
))
fig4.add_trace(go.Scatter(
    x=ddf["SeatShare"], y=ddf["PartyGroup"],
    mode="markers", name="Seat share %",
    marker=dict(size=18, color=[PARTY_COLOURS.get(p, "#999") for p in ddf["PartyGroup"]]),
    text=ddf["SeatShare"].apply(lambda x: f"{x:.1f}%"),
    hovertemplate="<b>%{y}</b><br>Seats: %{text}<extra></extra>",
))

fig4.update_layout(
    **LAYOUT_BASE,
    title="Vote share vs seat share — 2025 Australian federal election",
    xaxis=dict(title="Percentage (%)", ticksuffix="%", range=[-2, 70]),
    yaxis_title="",
    legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
    height=550, width=WIDTH,
)
fig4.write_image(OUT / "chart4_vote_vs_seat.png", scale=SCALE)
print("  ✓ chart4_vote_vs_seat.png")

print(f"\nAll 5 charts saved to: {OUT}/")
