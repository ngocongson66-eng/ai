import pandas as pd
excel_path = r'C:\Users\Son\Downloads\Hung_Phat_Test_Data_5_Steps.xlsx'
xl = pd.ExcelFile(excel_path)
for s in xl.sheet_names:
    print(f"\n================ SHEET: {s} ================")
    df = xl.parse(s)
    print(df.to_string())
