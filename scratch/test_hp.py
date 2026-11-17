import sys, os
sys.path.insert(0, os.path.abspath('.'))
import pandas as pd
from src.hung_phat_analytics import is_hung_phat_workbook, analyze_hung_phat_data

xl = pd.ExcelFile('Hung_Phat_Test_Data_5_Steps.xlsx')
print('Is Hung Phat:', is_hung_phat_workbook(xl))
res = analyze_hung_phat_data(xl)
print('Audit records:', len(res['audit_records']))
print('Warnings/Issues:', res['warning_count'])
print('Regional KPI:')
for r in res['regional_kpi']:
    print(f" - {r['region']}: Score {r['total_score']} | {r['target_enterprises']} DN | Rate: {r['interest_rate_str']} | {r['rank_label']}")
print('BLUF Headline:', res['bluf_summary']['headline'])
