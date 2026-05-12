#%% Load libraries and data
import pandas as pd
import json
import time
import requests

# Load cvr_production_units_final.json
with open('data/cvr_production_units_final.json', 'r', encoding='utf-8') as f:
    results = json.load(f)

#%% Process CVR API results to build production units DataFrame

# Build production units DataFrame ─────────────────────────────────────────
data_rows  = []
index_list = []
keys    = ['name', 'address', 'zipcode', 'city', 'startdate', 'enddate', 'employees']
columns = ['UnitPno', 'CompanyVat', 'CompanyName', 'UnitName', 'UnitAddress', 'UnitZipcode', 'UnitCity', 'UnitStartdate', 'UnitEnddate', 'UnitEmployees']

for res in results:
    for unit in res.get('productionunits', []):
        pno    = unit.get('pno', None)
        values = [pno , res['vat'], res['name']] + [unit.get(key, None) for key in keys]
        data_rows.append(values)
        index_list.append(pno)

df_units = pd.DataFrame(data_rows, columns=columns)
# df_units.index.name = 'pno'
print(f"Total production units: {len(df_units)}")

#%% Filter data for the range 2008-2024
# Units operative from 2008 onwards (either still open or closed after 2008)

# Parse UnitEnddate and filter 
df_units['UnitEnddate'] = pd.to_datetime(
    df_units['UnitEnddate'].str.replace(' - ', '/', regex=False),  
    format='%d/%m/%Y',
    errors='coerce'                                                 
)

cutoff = pd.Timestamp('2008-01-01')

# Keep rows where UnitEnddate is NaT (still open) OR closed on/after 2008
df_units = df_units[df_units['UnitEnddate'].isna() | (df_units['UnitEnddate'] >= cutoff)]
print(f"Units after purge (operative from 2008 onwards): {len(df_units)}")

#%% Geocode adresses for each production unit

# Geocode addresses using DAWA (Danish Address Web API)
DAWA_URL = "https://api.dataforsyningen.dk/adresser"

def geocode_danish_address(address, zipcode, city):
    try:
        params = {
            'q'       : f"{address}, {zipcode} {city}",
            'per_side': 1,
            'struktur': 'nestet'
        }
        resp = requests.get(DAWA_URL, params=params, timeout=10)
        resp.raise_for_status()
        hits = resp.json()
        if hits:
            hit          = hits[0]
            coords       = hit['adgangsadresse']['vejpunkt']['koordinater']
            kommune      = hit['adgangsadresse']['kommune']
            region       = hit['adgangsadresse']['region']
            kommune_name = kommune.get('navn', None)
            kommune_code = kommune.get('kode', None)
            region_name  = region.get('navn', None)
            region_code  = region.get('kode', None)
            return coords[1], coords[0], kommune_name, kommune_code, region_name, region_code
    except Exception as e:
        print(f"Failed [{address}, {zipcode}]: {e}")
    return None, None, None, None, None, None

lats, lons, kommune_names, kommune_codes, region_names, region_codes = [], [], [], [], [], []

for i, (_, row) in enumerate(df_units.iterrows()):
    lat, lon, k_name, k_code, r_name, r_code = geocode_danish_address(row['UnitAddress'], row['UnitZipcode'], row['UnitCity'])
    lats.append(lat)
    lons.append(lon)
    kommune_names.append(k_name)
    kommune_codes.append(k_code)
    region_names.append(r_name)
    region_codes.append(r_code)

    if (i + 1) % 50 == 0:
        print(f"  Geocoded {i + 1}/{len(df_units)}...")
    time.sleep(0.05)

df_units['Lat']         = lats
df_units['Lon']         = lons
df_units['KommuneName'] = kommune_names
df_units['KommuneCode'] = kommune_codes
df_units['RegionName']  = region_names
df_units['RegionCode']  = region_codes

failed = df_units['Lat'].isna().sum()
print(f"Geocoded {len(df_units) - failed}/{len(df_units)} units successfully")
print(f"Failed to geocode: {failed} units")

#%% Save results to CSV
# ── Save ──────────────────────────────────────────────────────────────────────
df_units.to_csv('data/cvr_production_units_geocoded.csv', encoding='utf-8')
