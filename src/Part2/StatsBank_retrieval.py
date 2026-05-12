#%% Import Libraries
import requests
import pandas as pd
from io import StringIO

#%% Fetch GeoJson data for Danish municipalities and regions
# Fetch municipality GeoJSON from DAWA
geojson = requests.get(
    "https://api.dataforsyningen.dk/kommuner?format=geojson"
).json()


# Extract names and codes for a base dataframe
municipalities = [
    {
        "Municipality" : f["properties"]["navn"],
        "KommuneCode"  : f["properties"]["kode"],
        "RegionName"   : f["properties"]["regionsnavn"],
        "RegionCode"   : f["properties"]["regionskode"]
    }
    for f in geojson["features"]
]
df_mun = pd.DataFrame(municipalities)

# Save to CSV
df_mun.to_csv("/data/municipalities.csv", encoding="utf-8", index=False)

#%% Fetch StatsBank data for FOLK1A (population by municipality)
BASE = "https://api.statbank.dk/v1"

############ Helper Function to fetch and parse CSV data from StatBank
def inspect_table(table_id: str) -> None:
    """Print all variables and their codes for any DST table."""
    r = requests.get(f"{BASE}/tableinfo/{table_id}", params={"lang": "en"})
    r.raise_for_status()
    meta = r.json()
    print(f"\nTable : {meta['id']} — {meta['text']}")
    print(f"Unit  : {meta['unit']}\n")
    for var in meta["variables"]:
        print(f"  Variable  : {var['id']}  ({var['text']})")
        print(f"  Elimination: {var.get('elimination', False)}")
        for v in var["values"][:10]:
            print(f"    {v['id']:15}  {v['text']}")
        if len(var["values"]) > 10:
            print(f"    ... {len(var['values'])} values total")
        print()

# inspect_table("FOLK1A")

########## Get municipality codes from DAWA
# DAWA uses zero-padded 4-digit codes ("0101"),
# DST FOLK1A uses plain 3-digit codes ("101").
def get_municipality_map() -> dict[str, str]:
    r = requests.get("https://api.dataforsyningen.dk/kommuner")
    r.raise_for_status()
    return {
        str(int(k["kode"])): k["navn"]   # "0101" to "101": "København"
        for k in r.json()
    }

name_map   = get_municipality_map()  

# List of Denamrk's municipality codes 
muni_codes = list(name_map.keys())   

######### Build request for FOLK1A
# Take Q1 (Jan 1st) of each year as the annual snapshot — 2008–2024
q1_periods = [f"{y}K1" for y in range(2008, 2025)]   

# Request filters
FILTERS = [
    {
        "code": "OMRÅDE",
        "values": muni_codes,    
    },
    {
        "code": "KØN",
        "values": ["TOT"],       # TOT = all genders combined

    },
    {
        "code": "ALDER",
        "values": ["IALT"],      # IALT = all ages combined
        
    },
    {
        "code": "CIVILSTAND",
        "values": ["TOT"],       # TOT = all marital statuses
    },
    {
        "code": "Tid",
        "values": q1_periods,    # 2008K1 … 2024K1
    },
]

######### Fetch data
# Helper function
def fetch(table_id: str, variables: list) -> pd.DataFrame:
    payload = {
        "table":     table_id,
        "format":    "BULK",          # streaming — no cell limit
        "lang":      "en",
        "delimiter": "Semicolon",
        "variables": variables,
        "valuePresentation": "Code"   # Force API to return codes instead of text
    }
    r = requests.post(f"{BASE}/data", json=payload)
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text), sep=";", thousands=".")
    df.columns = df.columns.str.strip().str.upper()
    return df

raw = fetch("FOLK1A", FILTERS)

#%% Process API results
df = (
    raw
    .rename(columns={
        "OMRÅDE":  "municipality_code",
        "TID":     "quarter",
        "INDHOLD": "population",
    })
    .assign(
        year              = lambda d: d["quarter"].str[:4].astype(int),
        municipality_name = lambda d: d["municipality_code"].astype(str).map(name_map),
    )
    # Drop the dimension columns we fixed to a single value
    .drop(columns=["KØN", "ALDER", "CIVILSTAND", "quarter"])
    [["municipality_code", "municipality_name", "year", "population"]]
    .sort_values(["municipality_name", "year"])
    .reset_index(drop=True)
)

# Save to CSV
df.to_csv("data/folk1a_population.csv",   index=False, encoding="utf-8-sig")

#%% Combine data with Averge Income from Part1
df_pop = pd.read_csv("data/folk1a_population.csv")
df_inc = pd.read_csv("../Part1/data/Part1_merged_dataset.csv", usecols=["Municipality","Year","Average Income"])
df_inc = df_inc.rename(columns={
    "Municipality": "municipality_name",
    "Year": "year",
    "Average Income": "average_income"
})

# Perform a left join to keep all rows from df_pop.
df_combined = pd.merge(
    df_pop, 
    df_inc, 
    on=["municipality_name", "year"], 
    how="left"
)

# Print missing values summary
print("Showing Christiansø (411) with NaN for average_income:")
print(df_combined[df_combined["municipality_name"] == "Christiansø"].head())

# Save combined dataset to CSV
df_combined.to_csv("../data/statsbank_combined.csv", index=False, encoding="utf-8-sig")