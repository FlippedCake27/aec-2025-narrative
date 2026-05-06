import pandas as pd
import requests
import io

ELECTION_ID = "31496"

URLS = {
    "first_prefs":    f"https://results.aec.gov.au/{ELECTION_ID}/Website/Downloads/HouseFirstPrefsByCandidateByVoteTypeDownload-{ELECTION_ID}.csv",
    "polling_places": f"https://results.aec.gov.au/{ELECTION_ID}/Website/Downloads/GeneralPollingPlacesDownload-{ELECTION_ID}.csv",
}

OUTPUT_FILE = "aec_cleaned.csv"

FINAL_COLUMNS = [
    "StateAb", "DivisionID", "DivisionNm",
    "Latitude", "Longitude", "PollingPlaceCount",
    "CandidateName", "PartyAb", "PartyNm_clean", "Elected",
    "OrdinaryVotes", "AbsentVotes", "ProvisionalVotes",
    "PrePollVotes", "PostalVotes", "TotalVotes",
    "PrePollShare", "Swing",
]


def download_csv(url: str, label: str) -> pd.DataFrame:
    print(f"[download] {label} ...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    df = pd.read_csv(io.StringIO(response.text), skiprows=1)
    print(f"           → {len(df):,} rows, {len(df.columns)} columns")
    return df


def clean_first_prefs(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[clean] First Preferences ...")
    df.columns = df.columns.str.strip()

    before = len(df)
    df = df.dropna(subset=["TotalVotes"])
    print(f"         Dropped {before - len(df)} rows with null TotalVotes")

    vote_cols = ["OrdinaryVotes", "AbsentVotes", "ProvisionalVotes",
                 "PrePollVotes", "PostalVotes", "TotalVotes", "Swing"]
    for col in vote_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    party_map = {
        "ALP":  "Australian Labor Party",
        "LP":   "Liberal Party",
        "NP":   "National Party",
        "GRN":  "The Greens",
        "UAP":  "United Australia Party",
        "ON":   "One Nation",
        "TEAL": "Teal Independent",
    }
    df["PartyNm_clean"] = df["PartyAb"].map(party_map).fillna(df["PartyNm"].str.strip())
    df["CandidateName"] = (df["GivenNm"].str.strip() + " " + df["Surname"].str.strip()).str.title()
    df["Elected"] = df["Elected"].astype(str).str.strip().str.upper() == "Y"
    df["PrePollShare"] = (df["PrePollVotes"] / df["TotalVotes"].replace(0, pd.NA)).round(3)

    print(f"         → {len(df):,} rows after cleaning")
    return df


def clean_polling_places(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[clean] Polling Places ...")
    df.columns = df.columns.str.strip()

    before = len(df)
    df = df.dropna(subset=["Latitude", "Longitude"])
    print(f"         Dropped {before - len(df)} rows missing coordinates")

    df = df.copy()
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    before = len(df)
    df = df[(df["Latitude"] != 0) & (df["Longitude"] != 0)]
    print(f"         Dropped {before - len(df)} rows with zero coordinates")

    before = len(df)
    df = df[df["Latitude"].between(-44, -10) & df["Longitude"].between(113, 154)]
    print(f"         Dropped {before - len(df)} rows outside Australian bbox")

    print(f"         → {len(df):,} rows after cleaning")
    return df


def merge_datasets(fp: pd.DataFrame, pp: pd.DataFrame) -> pd.DataFrame:
    print("\n[merge] Aggregating polling places to division centroids ...")

    division_geo = (
        pp.groupby("DivisionID")
          .agg(
              Latitude=("Latitude", "mean"),
              Longitude=("Longitude", "mean"),
              PollingPlaceCount=("PollingPlaceID", "count"),
          )
          .reset_index()
    )

    print(f"         → {len(division_geo):,} divisions with coordinates")

    merged = fp.merge(division_geo, on="DivisionID", how="left")
    matched = merged["Latitude"].notna().sum()
    print(f"         → {len(merged):,} rows total, {matched:,} ({matched/len(merged)*100:.1f}%) have coordinates")
    return merged


def export(df: pd.DataFrame) -> None:
    cols = [c for c in FINAL_COLUMNS if c in df.columns]
    out = df[cols]
    out.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n[export] Saved → {OUTPUT_FILE}")
    print(f"         Shape: {out.shape[0]:,} rows × {out.shape[1]} columns")


def eda_summary(df: pd.DataFrame) -> None:
    print("\n" + "="*60)
    print("EDA SUMMARY")
    print("="*60)

    print(f"\nTotal candidate rows               : {len(df):,}")
    print(f"Unique divisions (electorates)     : {df['DivisionNm'].nunique()}")
    print(f"Unique divisions with coordinates  : {df['Latitude'].notna().sum()}")
    print(f"Unique candidates                  : {df['CandidateName'].nunique()}")

    print("\nTop 10 parties by total votes:")
    party_totals = (
        df.groupby("PartyNm_clean")["TotalVotes"]
          .sum()
          .sort_values(ascending=False)
          .head(10)
    )
    for party, votes in party_totals.items():
        print(f"  {party:<40} {votes:>10,.0f}")

    print("\nElected members by party:")
    elected = (
        df[df["Elected"]]
          .drop_duplicates(subset=["DivisionNm"])
          .groupby("PartyNm_clean")
          .size()
          .sort_values(ascending=False)
    )
    for party, count in elected.items():
        print(f"  {party:<40} {count:>4} seats")

    print("\nMissing values in key columns:")
    for col in ["Latitude", "Longitude", "TotalVotes", "Swing", "PartyNm_clean"]:
        if col in df.columns:
            print(f"  {col:<20} {df[col].isna().sum():>6} missing")

    print("\n" + "="*60)


def main():
    print("AEC 2025 Federal Election — Data Cleaning Pipeline")
    print("=" * 60)

    fp_raw = download_csv(URLS["first_prefs"], "House First Preferences")
    pp_raw = download_csv(URLS["polling_places"], "General Polling Places")

    fp_clean = clean_first_prefs(fp_raw)
    pp_clean = clean_polling_places(pp_raw)

    merged = merge_datasets(fp_clean, pp_clean)

    eda_summary(merged)
    export(merged)

    print("\nDone. Import aec_cleaned.csv into Tableau to begin visualisation.")


if __name__ == "__main__":
    main()
