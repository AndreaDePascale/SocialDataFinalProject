import pandas as pd

# 1. Load the dataset
df = pd.read_csv('data/IFOR35_Processed.csv')

# 2. Rename the Columns
column_mapping = {
    'DECILGEN': 'Decile',
    'KOMMUNEDK': 'Municipality',
    'PRISENHED': 'Price_Unit',
    'TID': 'Year',
    'INDHOLD': 'Average_Income'
}
df.rename(columns=column_mapping, inplace=True)

# 3. Drop "Hele landet" (All Denmark)
# This fulfills your requirement of not having the aggregated "All municipalities" entry
df = df[df['Municipality'] != 'Hele landet']

# 4. Translate the Deciles to English
decile_map = {
    '1. decil': '1st Decile',
    '2. decil': '2nd Decile',
    '3. decil': '3rd Decile',
    '4. decil': '4th Decile',
    '5. decil': '5th Decile',
    '6. decil': '6th Decile',
    '7. decil': '7th Decile',
    '8. decil': '8th Decile',
    '9. decil': '9th Decile',
    '10. decil': '10th Decile'
}
df['Decile'] = df['Decile'].map(decile_map)

# 5. Translate the Price Units to English
price_map = {
    'Faste priser (seneste dataårs prisniveau)': 'Constant prices',
    'Nominelle priser': 'Nominal prices'
}
df['Price_Unit'] = df['Price_Unit'].map(price_map)

# 6. Save the final readable dataset
output_filename = 'data/IFOR35_Final_Readable.csv'
df.to_csv(output_filename, index=False)

print(f"Success! Your cleaned and readable dataset has been saved as '{output_filename}'.")