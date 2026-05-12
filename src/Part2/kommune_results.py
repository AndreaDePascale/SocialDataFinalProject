#%% Import Libraries
from __future__ import annotations

from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

#%% Config
UNITS_PATH = Path("data/cvr_production_units_geocoded.csv")
STATS_PATH = Path("data/statsbank_combined.csv")
OUT_DIR = Path("data")
OUT_DIR.mkdir(exist_ok=True)

YEAR_START, YEAR_END = 2008, 2024
MIN_DURATION_DAYS = 30   # filter same-day-or-very-short units (registration artifacts)

#%% Load and clean
def load_units(path: Path) -> pd.DataFrame:
    """Load production units, parse the two different date formats, clean."""
    df = pd.read_csv(
        path,
        dtype={"KommuneCode": str, "RegionCode": str, "UnitZipcode": str},
        low_memory=False,
    )
    # Drop the unnamed index column if present
    df = df.loc[:, ~df.columns.str.match(r"^Unnamed")]

    # Pad KommuneCode to 4 digits (e.g. "223" -> "0223") for joins with GeoJSON
    df["KommuneCode"] = df["KommuneCode"].str.zfill(4)

    # Parse dates. Start uses "15/06 - 1991", end uses ISO "2010-02-23".
    df["StartDate"] = pd.to_datetime(
        df["UnitStartdate"].str.replace(" ", "", regex=False),
        format="%d/%m-%Y", errors="coerce",
    )
    df["EndDate"] = pd.to_datetime(df["UnitEnddate"], errors="coerce")

    # Filter registration artifacts (open and close within MIN_DURATION_DAYS)
    duration = (df["EndDate"] - df["StartDate"]).dt.days
    artifact = duration.notna() & (duration < MIN_DURATION_DAYS)
    n_drop = int(artifact.sum())
    df = df.loc[~artifact].copy()
    print(f"  dropped {n_drop:,} short-lived registration artifacts (<{MIN_DURATION_DAYS} days)")

    # Filter out specific company names
    if 'CompanyName' in df.columns:
        n_before = len(df)
        # Remove municipalities and regions 
        df = df[~df['CompanyName'].str.contains('Kommune|Region', case=False, na=False)]
        # Remove supermarkets and retail chains
        df = df[~df['CompanyName'].str.contains('Salling|365discount|COOP|POST|politi|COMPASS', case=False, na=False)]
        print(f"  dropped {n_before - len(df):,} units based on company name filters")

    df["StartYear"] = df["StartDate"].dt.year
    df["EndYear"] = df["EndDate"].dt.year
    return df


def load_stats(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["KommuneCode"] = df["municipality_code"].astype(int).map(lambda x: f"{x:04d}")
    return df


units = load_units(UNITS_PATH)
stats = load_stats(STATS_PATH)

#%% Compute openings, closings, active stock per (kommune, year)
years = list(range(YEAR_START, YEAR_END + 1))

# Openings: count by start year
opens = (
    units[units["StartYear"].between(YEAR_START, YEAR_END)]
    .groupby(["KommuneCode", "StartYear"]).size()
    .rename("openings").reset_index().rename(columns={"StartYear": "year"})
)

# Closings: count by end year
closes = (
    units[units["EndYear"].between(YEAR_START, YEAR_END)]
    .groupby(["KommuneCode", "EndYear"]).size()
    .rename("closings").reset_index().rename(columns={"EndYear": "year"})
)

# Active stock at year-end t: started on/before Dec 31 t AND (no end date OR ended after t)
def active_stock(df: pd.DataFrame, year: int) -> pd.Series:
    cutoff = pd.Timestamp(f"{year}-12-31")
    mask = (df["StartDate"] <= cutoff) & (
        df["EndDate"].isna() | (df["EndDate"] > cutoff)
    )
    return df.loc[mask].groupby("KommuneCode").size()

stock_records = []
for y in years:
    s = active_stock(units, y)
    for kcode, n in s.items():
        stock_records.append({"KommuneCode": kcode, "year": y, "active": int(n)})
stock = pd.DataFrame(stock_records)

# Build complete panel: every (kommune, year) combo, filled with zeros
all_kcodes = sorted({str(x) for x in units["KommuneCode"].dropna()} | {str(x) for x in stats["KommuneCode"].dropna()})
panel = pd.MultiIndex.from_product([all_kcodes, years], names=["KommuneCode", "year"]).to_frame(index=False)
panel = (panel
    .merge(opens, on=["KommuneCode", "year"], how="left")
    .merge(closes, on=["KommuneCode", "year"], how="left")
    .merge(stock, on=["KommuneCode", "year"], how="left")
)
panel[["openings", "closings", "active"]] = panel[["openings", "closings", "active"]].fillna(0).astype(int)
panel["net_change"] = panel["openings"] - panel["closings"]

# Attach kommune name (use most recent name from the units file as authoritative)
name_lookup = (units.dropna(subset=["KommuneName"])
                    .drop_duplicates("KommuneCode")
                    .set_index("KommuneCode")["KommuneName"])
panel["KommuneName"] = panel["KommuneCode"].map(name_lookup)
# Fall back to stats names if missing
stats_names = stats.drop_duplicates("KommuneCode").set_index("KommuneCode")["municipality_name"]
panel["KommuneName"] = panel["KommuneName"].fillna(panel["KommuneCode"].map(stats_names))


#%% Also dump the panel as CSV for use in the explanatory phase
panel_with_stats = panel.merge(
    stats[["KommuneCode", "year", "population", "average_income"]],
    on=["KommuneCode", "year"], how="left",
)
panel_with_stats.to_csv(OUT_DIR / "kommune_year_panel.csv", index=False)