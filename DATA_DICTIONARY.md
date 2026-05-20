# Data Dictionary

**Project:** Beyond the Headlines — A Data Narrative on the 2025 Australian Federal Election  
**Course:** UTS 36104 · Data Visualisation and Narratives  
**Source:** Australian Electoral Commission (AEC) Tally Room · Election ID `31496`

---

## Files Overview

| File | Description | Produced by |
|------|-------------|-------------|
| `aec_cleaned.csv` | Core analysis-ready dataset (2025 election) | `clean_aec_1.py` |
| `aec_enriched.csv` | Extended dataset with enrolment, turnout, and TCP data | `enrich_aec.py` |
| `data/aec_combined_2013_2025.csv` | Multi-election dataset spanning 2013–2025 | Manually assembled |
| `australian-states.json` | GeoJSON boundaries for Australian states and territories | AEC / third-party |

---

## 1. `aec_cleaned.csv`

Merged and cleaned output combining House First Preferences with polling place centroids. One row per candidate per electoral division.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `StateAb` | string | Two-letter state/territory abbreviation | `NSW`, `VIC`, `QLD` |
| `DivisionID` | integer | Unique AEC identifier for the electoral division | `318` |
| `DivisionNm` | string | Full name of the electoral division (electorate) | `Warringah` |
| `Latitude` | float | Mean latitude of polling places in the division | `-33.77` |
| `Longitude` | float | Mean longitude of polling places in the division | `151.25` |
| `PollingPlaceCount` | integer | Number of polling places in the division | `24` |
| `CandidateName` | string | Full candidate name (title-cased) | `Zali Steggall` |
| `PartyAb` | string | AEC party abbreviation | `IND`, `ALP`, `LP` |
| `PartyNm_clean` | string | Standardised party display name | `Australian Labor Party` |
| `Elected` | boolean | Whether the candidate was elected to parliament | `True` / `False` |
| `OrdinaryVotes` | integer | Votes cast in person on election day at a polling place | `12450` |
| `AbsentVotes` | integer | Votes cast outside the candidate's home division | `834` |
| `ProvisionalVotes` | integer | Votes cast by electors whose enrolment was disputed | `112` |
| `PrePollVotes` | integer | Votes cast early in person before election day | `9203` |
| `PostalVotes` | integer | Votes cast by post | `3411` |
| `TotalVotes` | integer | Sum of all vote types for this candidate in this division | `26010` |
| `PrePollShare` | float | Proportion of total votes that were pre-poll (0–1) | `0.354` |
| `Swing` | float | Change in first-preference vote share vs previous election (percentage points) | `+4.2` |

**Source AEC file:** `HouseFirstPrefsByCandidateByVoteTypeDownload-31496.csv`  
**Joined with:** `GeneralPollingPlacesDownload-31496.csv` (aggregated to division centroids)

---

## 2. `aec_enriched.csv`

All columns from `aec_cleaned.csv` plus the following enrichment columns added by `enrich_aec.py`.

### Enrolment

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Enrolment` | integer | Total enrolled voters in the division | `98342` |

**Source AEC file:** `GeneralEnrolmentByDivisionDownload-31496.csv`

### Turnout

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `Turnout` | integer | Total formal + informal votes cast in the division | `91205` |
| `TurnoutPercentage` | float | Turnout as a percentage of enrolment | `92.7` |
| `TurnoutSwing` | float | Change in turnout percentage vs previous election (pp) | `-0.8` |

**Source AEC file:** `HouseTurnoutByDivisionDownload-31496.csv`

### Two-Candidate Preferred (TCP)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `TcpWinnerParty` | string | Standardised party name of the TCP winner | `Australian Labor Party` |
| `TcpWinnerPartyAb` | string | AEC abbreviation of the TCP winner's party | `ALP` |
| `TcpMarginPct` | float | Winning margin as a percentage of total TCP votes | `5.34` |
| `TcpTotalVotes` | integer | Total votes in the two-candidate preferred count | `88712` |

**Source AEC file:** `HouseTcpByCandidateByVoteTypeDownload-31496.csv`

### Derived Columns

| Column | Type | Description | Formula |
|--------|------|-------------|---------|
| `InformalVotes` | integer | Estimated informal votes (clipped at 0) | `Turnout − sum(TotalVotes per division)` |
| `InformalPct` | float | Informal votes as a percentage of total turnout | `InformalVotes / Turnout × 100` |
| `SwingZScore` | float | Standardised swing score (z-score across all candidates) | `(Swing − mean) / std` |
| `SeatSafety` | category | Safety classification based on TCP margin | See bands below |

**`SeatSafety` bands:**

| Label | TCP Margin Range |
|-------|-----------------|
| `Marginal (<2%)` | 0 – 2% |
| `Fairly Marginal (2–6%)` | 2 – 6% |
| `Fairly Safe (6–10%)` | 6 – 10% |
| `Safe (>10%)` | > 10% |

---

## 3. `data/aec_combined_2013_2025.csv`

Multi-election dataset used by `independents.py` to analyse independent candidate trends across five federal elections.

Contains the same core columns as `aec_enriched.csv` with the addition of:

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `ElectionYear` | integer | Federal election year | `2013`, `2016`, `2019`, `2022`, `2025` |
| `IsInd` | boolean | `True` if the candidate is an independent or teal independent | `True` |

**Elections covered:** 2013 · 2016 · 2019 · 2022 · 2025

---

## 4. `australian-states.json`

GeoJSON file containing polygon boundaries for all 8 Australian states and territories. Used by Plotly Choropleth in `streamlit_app.py`.

| Property | Description |
|----------|-------------|
| `STATE_NAME` | Full state name — used as the join key in the choropleth (`featureidkey: "properties.STATE_NAME"`) |

**Valid values for `STATE_NAME`:**  
`New South Wales`, `Victoria`, `Queensland`, `Western Australia`, `South Australia`, `Tasmania`, `Australian Capital Territory`, `Northern Territory`

---

## Party Reference

| `PartyAb` | `PartyNm_clean` | Colour |
|-----------|-----------------|--------|
| `ALP` | Australian Labor Party | `#E31837` |
| `LP` | Liberal Party | `#1C4F8C` |
| `LNP` | LNP | `#2980B9` |
| `NP` | National Party | `#006644` |
| `GRN` | The Greens | `#009B3A` |
| `IND` | Independent | `#008B8B` |
| `TEAL` | Teal Independent | `#20B2AA` |
| `ON` | One Nation | `#FF6B00` |
| `UAP` | United Australia Party | `#F4D03F` |

---

## Data Pipeline

```
AEC Tally Room (results.aec.gov.au/31496)
        │
        ├─ HouseFirstPreferences ─────────┐
        │                                 │
        └─ GeneralPollingPlaces ──────────┤ clean_aec_1.py ──► aec_cleaned.csv
                                          │
        ┌─ GeneralEnrolment ──────────────┤
        │                                 │
        ├─ HouseTurnout ──────────────────┤ enrich_aec.py ───► aec_enriched.csv
        │                                 │
        └─ HouseTcpByCandidate ───────────┘
                                          │
                                          └── (+ prior elections) ─► aec_combined_2013_2025.csv
```

---

## Notes

- All AEC source CSVs include a single metadata header row that is skipped on load (`skiprows=1`).
- Rows with missing `TotalVotes` are dropped during cleaning (informal / phantom rows from the AEC file).
- Polling place coordinates are aggregated to division-level centroids (mean lat/long) before merging.
- `Swing` values are sourced directly from the AEC file and reflect first-preference change vs the 2022 election.
- The `PartyGroup` column used in `streamlit_app.py` is computed at runtime and is not stored in any CSV.
