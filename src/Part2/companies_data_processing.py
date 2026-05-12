#%% Import libraries
import pandas as pd

#%% Process RAW data for companies

gross_value = pd.read_csv("data/companies_gross_value.csv", sep=',', encoding='utf-8')
employees = pd.read_csv("data/companies_number_employees.csv", sep=',', encoding='utf-8')

companies_data = pd.concat([gross_value, employees], ignore_index=True)
companies_data = companies_data.drop_duplicates(subset=['Company'], keep='first')
companies_data = companies_data.sort_values(by='Company').reset_index(drop=True)

companies_data_path = 'data/full_list_companies.csv'
companies_data.to_csv(companies_data_path, index=False)

#%% Merge datasets and clean company names

# Load all three CSVs
full_list = pd.read_csv('data/companies/full_list_companies.csv', sep=',', encoding='utf-8')
gross_value = pd.read_csv('data/companies/companies_gross_value.csv', sep=',', encoding='utf-8')
employees = pd.read_csv('data/companies/companies_number_employees.csv', sep=',', encoding='utf-8')

# Adjust these to match your actual column names
FULL_LIST_COL   = 'Company'   # column name in full_list_companies.csv
GROSS_VALUE_COL = 'Company'   # column name in companies_gross_value.csv
EMPLOYEES_COL   = 'Company'   # column name in companies_number_employees.csv

# Normalise to uppercase for comparison (non-destructive: kept in a helper set)
final_names = set(full_list[FULL_LIST_COL].str.upper().str.strip())

#%% Filter company names

# Filter and uppercase gross_value
gross_value[GROSS_VALUE_COL] = gross_value[GROSS_VALUE_COL].str.upper().str.strip()
gv_mask = gross_value[GROSS_VALUE_COL].isin(final_names)
discarded_gv = gross_value[~gv_mask][GROSS_VALUE_COL].tolist()

gross_value_filtered = gross_value[gv_mask]

# Filter and uppercase employees 
employees[EMPLOYEES_COL] = employees[EMPLOYEES_COL].str.upper().str.strip()
emp_mask = employees[EMPLOYEES_COL].isin(final_names)
discarded_emp = employees[~emp_mask][EMPLOYEES_COL].tolist()

employees_filtered = employees[emp_mask]

# Union set of all unique companies across both filtered datasets 
all_companies = set(gross_value_filtered[GROSS_VALUE_COL]) | set(employees_filtered[EMPLOYEES_COL])
only_in_gv    = set(gross_value_filtered[GROSS_VALUE_COL]) - set(employees_filtered[EMPLOYEES_COL])
only_in_emp   = set(employees_filtered[EMPLOYEES_COL]) - set(gross_value_filtered[GROSS_VALUE_COL])
in_both       = set(gross_value_filtered[GROSS_VALUE_COL]) & set(employees_filtered[EMPLOYEES_COL])

print(f"  Total unique companies (union):  {len(all_companies)}")
print(f"  In both datasets:                {len(in_both)}")
print(f"  Only in gross_value:             {len(only_in_gv)}")
print(f"  Only in employees:               {len(only_in_emp)}")
