#%% Loading and preparing data for CVR API fetching
import requests
import time
import pandas as pd
from pathlib import Path
import json


companies_data = pd.read_csv("../data/companies/full_list_companies.csv", sep=',', encoding='utf-8')
companies_list = companies_data['Company'].tolist()

# ----------------------------
# Note: We had to split the list of companies into batches to avoid hitting API rate limits per day
# Max 50 requests per day

#companies = companies_list[:36] # Done
#companies = companies_list[36:86] # Done
#companies = companies_list[86:136] # Done
companies = companies_list[136:] # Last batch performed

#%% CVR API fetching setup
# CVR API Base URL
BASE_URL = "https://cvrapi.dk/api"

# Default params for the API
# IMPORTANT: Provide a User-Agent identifying your application to avoid being blocked
headers = {
    "User-Agent": "DTU MSc HCAI - Project Social Data Analysis - Educational Use - Edgar Fabregat s242781@dtu.dk"
}

#%% Fetch data from CVR API for each company

results = []

for company in companies:
    print(f"Searching for: {company}")
    params = {
        "country": "dk",
        "search": company
    }
    
    response = requests.get(BASE_URL, params=params, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if "error" in data:
            if data['error'] == 'QUOTA_EXCEEDED':
                print("API quota exceeded. Stopping further requests.")
                break
            print(f"Error for {company}: {data['error']}")
        else:
            results.append(data)
            print(f"Success: Found {data.get('name', 'Unknown')}, CVR: {data.get('vat', 'Unknown')}")
    else:
        print(f"  Failed with status code: {response.status_code}")
        
    # Add a short delay
    time.sleep(4)

print(f"Fetched data for {len(results)} companies.")

#%% Processed results
data_rows = []
index_list = []
keys = ['name', 'address', 'zipcode', 'city', 'startdate', 'enddate', 'employees']
columns = ['CompanyVat', 'CompanyName', 'UnitName', 'UnitAddress', 'UnitZipcode', 'UnitCity', 'UnitStartdate', 'UnitEnddate', 'UnitEmployees']

for res in results:
    for unit in res.get('productionunits', []):
        pno = unit.get('pno', None)
        values = [res['vat'], res['name']] + [unit.get(key, None) for key in keys]
        
        data_rows.append(values)
        index_list.append(pno)

# Create DataFrame
df_units = pd.DataFrame(data_rows, columns=columns, index=index_list)
#df_units.set_index('pno', inplace=True)
df_units.index.name = 'pno'

#%% Save Results
# Save to CSV (append if file exists, otherwise create new)
output_dir = Path("data")
output_dir.mkdir(parents=True, exist_ok=True)

# Check if output file exists, if so, appendt to the file, otherwise create a new one
output_file = output_dir / "cvr_production_units.csv"
if output_file.exists():
    df_units.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8')
else:
    df_units.to_csv(output_file, index=False, encoding='utf-8')

# Save to JSON (append if file exists, otherwise create new)
df_cvr = pd.DataFrame(results)

output_json_file = output_dir / "cvr_production_units.json"
if output_json_file.exists():
    df_cvr.to_json(output_json_file, orient='records', indent=4, mode='a')
else:
    df_cvr.to_json(output_json_file, orient='records', indent=4)

#%% Post-processing: Clean and filter the CVR data

# Load CSV file
complete_df = pd.read_csv("data/cvr_production_units.csv", encoding='utf-8')    

# Load JSON file
with open("data/cvr_production_units.json", encoding='utf-8') as f:
    complete_json = json.load(f)
if not isinstance(complete_json, list):
    complete_json = [complete_json]

df_complete_json = pd.DataFrame(complete_json)

#%% Process duplicates in CSV and JSON data

# Remove duplicates CSV
df_csv_deduplicated = complete_df.drop_duplicates(subset=['CompanyVat', 'CompanyName', 'UnitName', 'UnitAddress', 'UnitZipcode', 'UnitCity'], keep='first')

# Remove duplicates JSON
df_deduplicated = df_complete_json.drop_duplicates(subset=['vat'], keep='first')

###### Check duplicated companeis

# Get unique names from deduplicated JSON data
deduplicated_names = sorted(df_deduplicated['name'].unique().tolist())

# Create comparison DataFrame
comparison_data = []
max_len = max(len(companies_list), len(deduplicated_names))

for i in range(max_len):
    company_name = companies_list[i] if i < len(companies_list) else "---"
    dedup_name = deduplicated_names[i] if i < len(deduplicated_names) else "---"
    
    # Mark if missing
    status = "✓" if dedup_name == "---" else ("✓" if company_name == dedup_name else "MISMATCH")
    
    comparison_data.append({
        'Index': i + 1,
        'Company List': company_name,
        'Deduplicated Data': dedup_name,
        'Status': status
    })

comparison_df = pd.DataFrame(comparison_data)

# Show full comparison
print("\nSide-by-side comparison:")
print(comparison_df.to_string(index=False))

#%% Remmove duplicates form CSV and JSON data after visual inspection
# Companies to remove
csv_companies_to_remove = ['Forsvaret', 'HABITUS HOUSING AND DAY CARE', 'Nuuday', 'NUUDAY']
json_companies_to_remove = ['Jonathan Heavens Wolt Denmark', 'Edifice Housing and Projects A/S']

# Filter CSV - remove by CompanyName
df_csv_cleaned = df_csv_deduplicated[~df_csv_deduplicated['CompanyName'].isin(csv_companies_to_remove)].copy()
print(f"CSV records removed: {len(df_csv_deduplicated) - len(df_csv_cleaned)}")

# Filter JSON - remove by name
df_json_cleaned = df_deduplicated[~df_deduplicated['name'].isin(json_companies_to_remove)].copy()
print(f"JSON records removed: {len(df_deduplicated) - len(df_json_cleaned)}")

# Filter companies list - remove unwanted companies
df_companies_cleaned = companies_data[~companies_data['Company'].isin(csv_companies_to_remove)].copy()
print(f"Companies list records removed: {len(companies_data) - len(df_companies_cleaned)}")


#%% Save Final Cleaned Data
# Save cleaned CSV file
df_csv_cleaned.to_csv("data/cvr_production_units_final.csv", index=False, encoding='utf-8')

# Save cleaned JSON file
final_json_cleaned = df_json_cleaned.to_dict('records')
with open("data/cvr_production_units_final.json", 'w', encoding='utf-8') as f:
    json.dump(final_json_cleaned, f, indent=4, ensure_ascii=False)

# Save cleaned companies list
df_companies_cleaned.to_csv("data/full_list_companies.csv", index=False, encoding='utf-8')