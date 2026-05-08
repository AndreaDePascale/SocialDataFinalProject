import pandas as pd
import os

def merge_datasets(ifor35_path, hfudd16_path, output_path):
    # Load IFOR35 dataset
    df_income = pd.read_csv(ifor35_path)
    
    # Filter for 'Constant prices' to get real average income
    df_income = df_income[df_income['Price_Unit'] == 'Constant prices']
    
    # Calculate the mean Average_Income per Municipality and Year
    df_income_agg = df_income.groupby(['Municipality', 'Year'])['Average_Income'].mean().reset_index()
    
    # Load HFUDD16 dataset
    df_edu = pd.read_csv(hfudd16_path)
    
    # Aggregate counts by Region_Name (Municipality), Year, and Socioeconomic_Status
    df_edu_grouped = df_edu.groupby(['Region_Name', 'Year', 'Socioeconomic_Status'])['Count'].sum().reset_index()
    
    # Pivot to get statuses as columns (index = Municipality + Year)
    df_edu_pivot = df_edu_grouped.pivot_table(
        index=['Region_Name', 'Year'],
        columns='Socioeconomic_Status',
        values='Count',
        aggfunc='sum'
    ).fillna(0)
    df_edu_pivot.columns.name = None
    
    # Calculate ratios
    total = df_edu_pivot.sum(axis=1)
    df_edu_pivot['Employed_Ratio'] = df_edu_pivot.get('Employed', 0) / total
    df_edu_pivot['Unemployed_Ratio'] = df_edu_pivot.get('Unemployed', 0) / total
    df_edu_pivot['Enrolled_Ratio'] = df_edu_pivot.get('Enrolled in education', 0) / total
    df_edu_pivot['Outside_Ratio'] = df_edu_pivot.get('Outside the labour force', 0) / total
    
    # Reset index and rename Region_Name to Municipality to allow merging
    df_edu_pivot = df_edu_pivot.reset_index().rename(columns={'Region_Name': 'Municipality'})
    
    # Merge datasets on both Municipality and Year
    df_merged = pd.merge(df_income_agg, df_edu_pivot, on=['Municipality', 'Year'], how='inner')
    
    # Select the required columns
    df_final = df_merged[['Municipality', 'Year', 'Average_Income', 'Employed_Ratio', 'Unemployed_Ratio', 'Enrolled_Ratio', 'Outside_Ratio']]
    
    # Rename Average_Income to Average Income as requested
    df_final = df_final.rename(columns={'Average_Income': 'Average Income'})
    
    # Save the final dataset
    df_final.to_csv(output_path, index=False)
    print(f"Merged dataset successfully saved to {output_path}")
    
    return df_final

if __name__ == '__main__':
    # Define paths
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ifor35_path = os.path.join(base_dir, 'data', 'IFOR35_Final_Readable.csv')
    hfudd16_path = os.path.join(base_dir, 'data', 'HFUDD16_Final_Readable.csv')
    output_path = os.path.join(base_dir, 'data', 'Merged_Dataset.csv')
    
    # If paths don't exist in base_dir, fallback to relative paths
    if not os.path.exists(ifor35_path):
        ifor35_path = 'data/IFOR35_Final_Readable.csv'
        hfudd16_path = 'data/HFUDD16_Final_Readable.csv'
        output_path = 'data/Merged_Dataset.csv'
        
    merge_datasets(ifor35_path, hfudd16_path, output_path)
