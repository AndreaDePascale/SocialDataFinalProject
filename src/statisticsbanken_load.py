import requests
import pandas as pd
import time
from io import StringIO
from tqdm import tqdm # Highly recommend installing this for the loading bar!

# --- CONFIGURATION ---
industries = [
    'CA', 'CB', 'CC', 'CD', 'CE', 'CF', 'CG', 'CH', 'CI', 'CJ', 'CK', 'CL', 'CM',
    'G', 'H', 'P', 'QA', 'QB', 'R', 'MA', 'MB', 'MC', 'N', 'O', 'K', 'L'
]
educations = ['H10', 'H20', 'H30', 'H35', 'H40', 'H50', 'H60', 'H70', 'H80', 'H90']
ages = ['15-19', '20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60-64', '65-69']
years = [str(y) for y in range(2008, 2025)]
year_chunks = [years[i:i + 5] for i in range(0, len(years), 5)]

# Get Regions
meta_res = requests.post("https://api.statbank.dk/v1/tableinfo", json={"table": "HFUDD16"}).json()
regions = [val['id'] for var in meta_res['variables'] if var['id'] == 'BOPOMR' for val in var['values'] if val['id'] != '000']

# --- DOWNLOAD HFUDD16 (Optimized) ---
hfudd16_dataframes = []

print("Downloading HFUDD16 data... (This should take ~15 mins)")
for region in tqdm(regions, desc="Processing Regions"):
    for chunk in year_chunks:
        payload = {
            "table": "HFUDD16",
            "format": "CSV",
            "valuePresentation": "Code", # CRITICAL FIX: Forces API to return clean IDs
            "variables": [
                {"code": "BOPOMR", "values": [region]},
                {"code": "UDDANNELSEF", "values": educations},
                {"code": "SOCIO", "values": ["000", "001", "002", "003"]},
                {"code": "ERHVERV", "values": industries},
                {"code": "ALDER", "values": ages},
                {"code": "KOEN", "values": ["TOT"]},
                {"code": "Tid", "values": chunk}
            ]
        }
        
        # Single, direct CSV request
        res_csv = requests.post("https://api.statbank.dk/v1/data", json=payload)
        
        if res_csv.status_code == 200:
            df_chunk = pd.read_csv(StringIO(res_csv.text), sep=';')
            # Standardize column names to uppercase just to be safe
            df_chunk.columns = df_chunk.columns.str.upper() 
            hfudd16_dataframes.append(df_chunk)
        else:
            print(f"Error for region {region}, years {chunk}: {res_csv.text}")
        
        time.sleep(0.1)

# Combine all chunks
df_hfudd = pd.concat(hfudd16_dataframes, ignore_index=True)
print(f"Raw data downloaded. Total rows before aggregation: {len(df_hfudd)}")

# --- APPLY CUSTOM AGGREGATIONS (Using exact Codes) ---
print("Applying custom aggregations...")

# Mapped using exact codes returned by the API
edu_map = {
    'H10': 'Bachelor and lower',
    'H20': 'Bachelor and lower',
    'H30': 'Bachelor and lower',
    'H35': 'Bachelor and lower',
    'H40': 'Bachelor and lower',
    'H50': 'Bachelor and lower',
    'H60': 'Bachelor and lower',
    'H70': 'Master',
    'H80': 'PhD',
    'H90': 'Not stated'
}
df_hfudd['UDDANNELSEF_AGG'] = df_hfudd['UDDANNELSEF'].map(edu_map)

# Industry grouping using exact codes
def map_industry(ind):
    if ind in ['CA', 'CB', 'CC', 'CD', 'CE', 'CF', 'CG', 'CH', 'CI', 'CJ', 'CK', 'CL', 'CM']: return 'C'
    if ind in ['G', 'H']: return 'G+H'
    if ind in ['P', 'QA', 'QB', 'R']: return 'P+Q+R'
    if ind in ['MA', 'MB', 'MC']: return 'M'
    if ind in ['N', 'O']: return 'N+O'
    if ind == 'K': return 'K'
    if ind == 'L': return 'L'
    return ind

df_hfudd['ERHVERV_AGG'] = df_hfudd['ERHVERV'].apply(map_industry)

# Age grouping using exact codes
age_map = {
    '15-19': '15-19',
    '20-24': '20-29', '25-29': '20-29',
    '30-34': '30-39', '35-39': '30-39',
    '40-44': '40-49', '45-49': '40-49',
    '50-54': '50-59', '55-59': '50-59',
    '60-64': '60-69', '65-69': '60-69'
}
df_hfudd['ALDER_AGG'] = df_hfudd['ALDER'].map(age_map)

# Check for any unmapped values that might cause data dropping
if df_hfudd[['UDDANNELSEF_AGG', 'ERHVERV_AGG', 'ALDER_AGG']].isnull().any().any():
    print("Warning: Some mappings resulted in NaN. Check API code formats.")

# Group and Sum
final_hfudd = df_hfudd.groupby(
    ['BOPOMR', 'UDDANNELSEF_AGG', 'SOCIO', 'ERHVERV_AGG', 'ALDER_AGG', 'TID']
)['INDHOLD'].sum().reset_index()

# Save to CSV
final_hfudd.to_csv("HFUDD16_Processed.csv", index=False)
print(f"Aggregation complete! Saved {len(final_hfudd)} rows to CSV.")



# # --- 3. DOWNLOAD IFOR35 ---
# # IFOR35 is small enough (~79,000 rows max) to download in one single request
# print("Downloading IFOR35 data...")
# payload_ifor35 = {
#     "table": "IFOR35",
#     "format": "CSV",
#     "variables": [
#         {"code": "DECILGEN", "values": ["*"]}, # All deciles
#         {"code": "KOMMUNEDK", "values": ["*"]}, # All municipalities
#         {"code": "PRISENHED", "values": ["005", "006"]}, # Both price units
#         {"code": "Tid", "values": ["*"]} # All years
#     ]
# }
# res_ifor35 = requests.post("https://api.statbank.dk/v1/data", json=payload_ifor35)
# df_ifor35 = pd.read_csv(StringIO(res_ifor35.text), sep=';')
# # Remove "All Denmark"
# df_ifor35 = df_ifor35[df_ifor35['KOMMUNEDK'] != 'All Denmark']
# print(f"IFOR35 Downloaded. Total rows: {len(df_ifor35)}")

# # --- 4. APPLY CUSTOM AGGREGATIONS TO HFUDD16 ---
# print("Applying custom aggregations...")

# # Education Map
# edu_map = {
#     'H10 Primary education': 'Bachelor and lower',
#     'H20 Upper secondary education': 'Bachelor and lower',
#     'H30 Vocational Education and Training (VET)': 'Bachelor and lower',
#     'H35 Qualifying educational programs': 'Bachelor and lower',
#     'H40 Short cycle higher education': 'Bachelor and lower',
#     'H50 Vocational bachelors educations': 'Bachelor and lower',
#     'H60 Bachelors programs': 'Bachelor and lower',
#     'H70 Masters programs': 'Master',
#     'H80 PhD programs': 'PhD',
#     'H90 Not stated': 'Not stated'
# }
# df_hfudd['UDDANNELSEF_AGG'] = df_hfudd['UDDANNELSEF'].map(edu_map)

# # Industry Map
# def map_industry(ind):
#     if ind.startswith('C') and ind != 'Construction': return 'C'
#     if ind.startswith('G') or ind.startswith('H'): return 'G+H'
#     if ind.startswith('P') or ind.startswith('Q') or ind == 'R Arts, entertainment and recreation activities': return 'P+Q+R'
#     if ind.startswith('M'): return 'M'
#     if ind == 'N Travel agent, cleaning, and other operationel services' or ind.startswith('O'): return 'N+O'
#     if ind.startswith('K'): return 'K'
#     if ind.startswith('L'): return 'L'
#     return ind

# df_hfudd['ERHVERV_AGG'] = df_hfudd['ERHVERV'].apply(map_industry)

# # Age Map
# age_map = {
#     '15-19 years': '15-19',
#     '20-24 years': '20-29', '25-29 years': '20-29',
#     '30-34 years': '30-39', '35-39 years': '30-39',
#     '40-44 years': '40-49', '45-49 years': '40-49',
#     '50-54 years': '50-59', '55-59 years': '50-59',
#     '60-64 years': '60-69', '65-69 years': '60-69'
# }
# df_hfudd['ALDER_AGG'] = df_hfudd['ALDER'].map(age_map)

# # Group by the new columns and sum the values
# final_hfudd = df_hfudd.groupby(
#     ['BOPOMR', 'UDDANNELSEF_AGG', 'SOCIO', 'ERHVERV_AGG', 'ALDER_AGG', 'TID']
# )['INDHOLD'].sum().reset_index()

# print("Aggregation complete!")

# # Save to CSV
# final_hfudd.to_csv("HFUDD16_Processed.csv", index=False)
# df_ifor35.to_csv("IFOR35_Processed.csv", index=False)
# print("Files saved successfully.")