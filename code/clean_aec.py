import pandas as pd
import requests
import io
import os

ELECTIONS = {
    2013: {"id": "17496", "date": "2013-09-07"},
    2016: {"id": "20499", "date": "2016-07-02"},
    2019: {"id": "24310", "date": "2019-05-18"},
    2022: {"id": "27966", "date": "2022-05-21"},
    2025: {"id": "31496", "date": "2025-05-03"},
}

PARTY_MAP = {
    "ALP":  "Australian Labor Party",
    "LP":   "Liberal Party",
    "NP":   "National Party",
    "GRN":  "The Greens",
    "UAP":  "United Australia Party",
    "ON":   "One Nation",
    "TEAL": "Teal Independent",
    "LNP":  "LNP",
    "IND":  "Independent",
    "CLP":  "Country Liberal Party",
    "KAP":  "Katter's Australian Party (KAP)",
    "CA":   "Centre Alliance",
    "XEN":  "Centre Alliance",
    "PUP":  "Palmer United Party",
}

FINAL_COLUMNS = [
    "ElectionYear", "ElectionDate",
    "StateAb", "DivisionID", "DivisionNm",
    "Latitude", "Longitude", "PollingPlaceCount",
    "CandidateName", "PartyAb", "PartyNm_clean", "Elected",
    "OrdinaryVotes", "AbsentVotes", "ProvisionalVotes",
    "PrePollVotes", "PostalVotes", "TotalVotes",
    "PrePollShare", "Swing",
    "Enrolment", "Turnout", "TurnoutPercentage", "TurnoutSwing",
    "TcpWinnerParty", "TcpWinnerPartyAb", "TcpMarginPct",
    "InformalVotes", "InformalPct", "SwingZScore", "SeatSafety",
]

BASE_URL = "https://results.aec.gov.au/{id}/Website/Downloads"


def fetch(url, label, skip_rows=1):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text), skiprows=skip_rows)
        df.columns = df.columns.str.strip()
        print(f"    [ok]  {label}: {len(df):,} rows")
        return df
    except Exception as e:
        print(f"    [skip] {label}: {e}")
        return None


def download_first_prefs(election_id):
    base = BASE_URL.format(id=election_id)
    df = fetch(f"{base}/HouseFirstPrefsByCandidateByVoteTypeDownload-{election_id}.csv",
               "First Preferences (by candidate/vote type)")
    if df is not None:
        return df
    return fetch(f"{base}/HouseFirstPreferencesDownload-{election_id}.csv",
                 "First Preferences (legacy name)")


def download_polling_places(election_id):
    return fetch(f"{BASE_URL.format(id=election_id)}/GeneralPollingPlacesDownload-{election_id}.csv",
                 "Polling Places")


def download_enrolment(election_id):
    return fetch(f"{BASE_URL.format(id=election_id)}/GeneralEnrolmentByDivisionDownload-{election_id}.csv",
                 "Enrolment by Division")


def download_turnout(election_id):
    return fetch(f"{BASE_URL.format(id=election_id)}/HouseTurnoutByDivisionDownload-{election_id}.csv",
                 "Turnout by Division")


def download_tcp(election_id):
    return fetch(f"{BASE_URL.format(id=election_id)}/HouseTcpByCandidateByVoteTypeDownload-{election_id}.csv",
                 "Two-Candidate Preferred")


def clean_first_prefs(df):
    before = len(df)
    df = df.dropna(subset=["TotalVotes"])
    dropped = before - len(df)
    if dropped:
        print(f"           dropped {dropped} rows with null TotalVotes")

    vote_cols = ["OrdinaryVotes", "AbsentVotes", "ProvisionalVotes",
                 "PrePollVotes", "PostalVotes", "TotalVotes", "Swing"]
    for col in vote_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["PartyNm_clean"] = df["PartyAb"].map(PARTY_MAP).fillna(
        df["PartyNm"].str.strip() if "PartyNm" in df.columns else "Unknown"
    )

    given   = df["GivenNm"].str.strip()  if "GivenNm"  in df.columns else ""
    surname = df["Surname"].str.strip()  if "Surname"   in df.columns else ""
    df["CandidateName"] = (given + " " + surname).str.strip().str.title()

    df["Elected"] = df["Elected"].astype(str).str.strip().str.upper() == "Y"

    total_safe = df["TotalVotes"].replace(0, pd.NA)
    df["PrePollShare"] = (
        pd.to_numeric(df.get("PrePollVotes", 0), errors="coerce") / total_safe
    ).round(3)

    return df


def clean_polling_places(df):
    before = len(df)
    df = df.dropna(subset=["Latitude", "Longitude"])
    print(f"           dropped {before - len(df)} rows missing coordinates")

    df = df.copy()
    df["Latitude"]  = pd.to_numeric(df["Latitude"],  errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    before = len(df)
    df = df[(df["Latitude"] != 0) & (df["Longitude"] != 0)]
    print(f"           dropped {before - len(df)} rows with zero coordinates")

    before = len(df)
    df = df[df["Latitude"].between(-44, -10) & df["Longitude"].between(113, 154)]
    print(f"           dropped {before - len(df)} rows outside Australian bbox")

    return df


def build_division_geo(pp):
    return (
        pp.groupby("DivisionID")
          .agg(
              Latitude=("Latitude", "mean"),
              Longitude=("Longitude", "mean"),
              PollingPlaceCount=("PollingPlaceID", "count"),
          )
          .reset_index()
    )


def build_tcp_summary(tcp):
    tcp = tcp.copy()
    tcp["PartyNm_clean"] = tcp["PartyAb"].map(PARTY_MAP).fillna(
        tcp["PartyNm"].str.strip() if "PartyNm" in tcp.columns else "Unknown"
    )
    tcp["Elected"] = tcp["Elected"].astype(str).str.strip().str.upper() == "Y"

    rows = []
    for div_id, grp in tcp.groupby("DivisionID"):
        if len(grp) < 2:
            continue
        total  = grp["TotalVotes"].sum()
        winner = grp[grp["Elected"]].iloc[0] if grp["Elected"].any() else grp.nlargest(1, "TotalVotes").iloc[0]
        runner = grp[~grp.index.isin([winner.name])].nlargest(1, "TotalVotes")
        if runner.empty:
            continue
        runner = runner.iloc[0]
        margin_pct = round(abs(winner["TotalVotes"] - runner["TotalVotes"]) / total * 100, 2) \
                     if total > 0 else None
        rows.append({
            "DivisionID":       div_id,
            "TcpWinnerParty":   winner["PartyNm_clean"],
            "TcpWinnerPartyAb": winner["PartyAb"],
            "TcpMarginPct":     margin_pct,
        })
    return pd.DataFrame(rows)


def add_enrichment(df, enrolment, turnout, tcp):
    if enrolment is not None and "Enrolment" in enrolment.columns:
        slim = enrolment[["DivisionID", "Enrolment"]].drop_duplicates("DivisionID")
        df = df.merge(slim, on="DivisionID", how="left")

    if turnout is not None:
        t_cols = ["DivisionID"] + [c for c in ["Turnout", "TurnoutPercentage", "TurnoutSwing"]
                                   if c in turnout.columns]
        df = df.merge(turnout[t_cols].drop_duplicates("DivisionID"), on="DivisionID", how="left")

    if tcp is not None:
        df = df.merge(build_tcp_summary(tcp), on="DivisionID", how="left")

    if "Enrolment" in df.columns and "Turnout" in df.columns:
        div_total = df.groupby("DivisionID")["TotalVotes"].transform("sum")
        df["InformalVotes"] = (df["Turnout"] - div_total).clip(lower=0)
        df["InformalPct"] = (df["InformalVotes"] / df["Turnout"].replace(0, pd.NA) * 100).round(2)

    if "Swing" in df.columns:
        df["SwingZScore"] = ((df["Swing"] - df["Swing"].mean()) / df["Swing"].std()).round(3)

    if "TcpMarginPct" in df.columns:
        df["SeatSafety"] = pd.cut(
            df["TcpMarginPct"],
            bins=[0, 2, 6, 10, 100],
            labels=["Marginal (<2%)", "Fairly Marginal (2-6%)", "Fairly Safe (6-10%)", "Safe (>10%)"],
            right=True,
        )

    return df


def process_election(year, config):
    election_id   = config["id"]
    election_date = config["date"]

    print(f"\n{'='*60}")
    print(f"  {year}  (ID: {election_id}  |  {election_date})")
    print(f"{'='*60}")

    fp_raw = download_first_prefs(election_id)
    if fp_raw is None:
        print(f"  SKIP — no first preferences data for {year}")
        return None

    pp_raw    = download_polling_places(election_id)
    enrolment = download_enrolment(election_id)
    turnout   = download_turnout(election_id)
    tcp       = download_tcp(election_id)

    fp_clean = clean_first_prefs(fp_raw)
    print(f"    first prefs clean: {len(fp_clean):,} rows")

    if pp_raw is not None:
        pp_clean = clean_polling_places(pp_raw)
        div_geo  = build_division_geo(pp_clean)
        print(f"    division geo: {len(div_geo):,} divisions")
        fp_clean = fp_clean.merge(div_geo, on="DivisionID", how="left")

    fp_clean = add_enrichment(fp_clean, enrolment, turnout, tcp)

    fp_clean["ElectionYear"] = year
    fp_clean["ElectionDate"] = election_date

    cols = [c for c in FINAL_COLUMNS if c in fp_clean.columns]
    out  = fp_clean[cols]

    path = os.path.join("data", f"aec_{year}_cleaned.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"    saved -> {path}  ({out.shape[0]:,} rows x {out.shape[1]} cols)")

    return out


def eda_summary(df):
    print(f"\n{'='*60}")
    print("  COMBINED EDA SUMMARY")
    print(f"{'='*60}")
    print(f"  Total rows        : {len(df):,}")
    print(f"  Elections         : {sorted(df['ElectionYear'].unique().tolist())}")
    print(f"  Unique divisions  : {df['DivisionNm'].nunique()}")
    print(f"  Unique candidates : {df['CandidateName'].nunique()}")

    print("\n  Rows per election:")
    for yr, grp in df.groupby("ElectionYear"):
        print(f"    {yr}: {len(grp):,} rows, {grp['DivisionNm'].nunique()} divisions")

    print("\n  Elected seats by party (all elections combined):")
    elected = (
        df[df["Elected"]]
        .drop_duplicates(subset=["ElectionYear", "DivisionNm"])
        .groupby("PartyNm_clean")
        .size()
        .sort_values(ascending=False)
        .head(10)
    )
    for party, count in elected.items():
        print(f"    {party:<45} {count:>4}")

    if "TurnoutPercentage" in df.columns:
        print("\n  Average turnout by election:")
        for yr, pct in df.drop_duplicates(["ElectionYear", "DivisionID"]).groupby(
                "ElectionYear")["TurnoutPercentage"].mean().items():
            print(f"    {yr}: {pct:.1f}%")

    print("\n  Missing values (combined):")
    for col in ["Latitude", "Longitude", "TotalVotes", "Swing", "TurnoutPercentage", "TcpMarginPct"]:
        if col in df.columns:
            n = df[col].isna().sum()
            print(f"    {col:<25} {n:>6} missing ({n / len(df) * 100:.1f}%)")


def main():
    print("AEC Multi-Election Cleaning Pipeline")
    print("Elections: 2013 · 2016 · 2019 · 2022 · 2025")
    print("=" * 60)

    os.makedirs("data", exist_ok=True)

    frames = []
    for year, config in ELECTIONS.items():
        result = process_election(year, config)
        if result is not None:
            frames.append(result)

    if not frames:
        print("\nNo data collected — check your internet connection.")
        return

    combined = pd.concat(frames, ignore_index=True)

    eda_summary(combined)

    combined_path = os.path.join("data", "aec_combined_2013_2025.csv")
    combined.to_csv(combined_path, index=False, encoding="utf-8-sig")
    print(f"\n  Combined file saved -> {combined_path}")
    print(f"  Shape: {combined.shape[0]:,} rows x {combined.shape[1]} columns")
    print("\nDone.")


if __name__ == "__main__":
    main()
