import pandas as pd
import requests

# 1. Load the processed dataset
# We force 'BOPOMR' to be read as a string so pandas doesn't accidentally drop 
# the leading zeros on regions like '084' (Region Hovedstaden)
df = pd.read_csv('data/HFUDD16_Processed.csv', dtype={'BOPOMR': str})

# 2. Rename the Columns
column_mapping = {
    'BOPOMR': 'Region_Code',
    'UDDANNELSEF_AGG': 'Education_Level',
    'SOCIO': 'Socioeconomic_Status',
    'ERHVERV_AGG': 'Industry_Group',
    'ALDER_AGG': 'Age_Group',
    'TID': 'Year',
    'INDHOLD': 'Count'
}
df.rename(columns=column_mapping, inplace=True)

# Restore the leading zeros (e.g., "81" becomes "081")
df['Region_Code'] = df['Region_Code'].str.zfill(3)

# 3. Map Socioeconomic Status
# Translating the 0, 1, 2, 3 codes back to their official descriptions
socio_map = {
    0: 'Enrolled in education',
    1: 'Employed',
    2: 'Unemployed',
    3: 'Outside the labour force'
}
df['Socioeconomic_Status'] = df['Socioeconomic_Status'].map(socio_map)

# 4. Map Industry Groups
# Giving highly readable names to the aggregated categories you created earlier
industry_map = {
    'C': 'Manufacturing',
    'G+H': 'Trade and Transportation',
    'P+Q+R': 'Education, Health, Arts and Recreation',
    'M': 'Consultancy, R&D and Business Services',
    'N+O': 'Administrative and Public Services',
    'K': 'Financial and Insurance',
    'L': 'Real Estate',
    'X': 'Activity not stated'  # Covers Unemployed and Outside the labour force
}
df['Industry_Group'] = df['Industry_Group'].map(industry_map)

# 5. Fetch and Map Region/Municipality Names Dynamically
print("Fetching region names from the StatBank API...")
meta_res = requests.post("https://api.statbank.dk/v1/tableinfo", json={"table": "HFUDD16"}).json()

# Extract the 'BOPOMR' variables from the API metadata
bopomr_metadata = next(var for var in meta_res['variables'] if var['id'] == 'BOPOMR')

# Create a dictionary like {'101': 'Copenhagen', '084': 'Region Hovedstaden'}
region_name_map = {val['id']: val['text'] for val in bopomr_metadata['values']}

# Insert the new readable name column right next to the code column
df.insert(1, 'Region_Name', df['Region_Code'].map(region_name_map))

# 6. Save the final, readable dataset
output_filename = 'data/HFUDD16_Final_Readable.csv'
df.to_csv(output_filename, index=False)

print(f"Success! Your readable dataset has been saved as '{output_filename}'.")