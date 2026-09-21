import gspread, sys
from google.oauth2.service_account import Credentials
c=Credentials.from_service_account_file('credentials.json',scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
g=gspread.authorize(c)
ss=g.open_by_key("1GJO1YgfPY1QSTX-7ZhBA4xI7teKsajf04-MVPkMdp9s")
rows=ss.worksheet("Generation Status").get_all_values()
print("=== AI GS (num|D|G|J|K|L|sysrem tail|P)")
for r in rows[3:]:
    if not r[1]: continue
    print("|".join([r[1],r[3],r[6],r[9],r[10],r[11],(r[12] or '')[-170:],(r[15] if len(r)>15 else '')]))
print("=== Weekly Picks (last 3)")
for r in ss.worksheet("Weekly Picks").get_all_values()[-3:]: print([x[:70] for x in r])
q=ss.worksheet("Generation Queue").get_all_values()
print("=== Queue last 10: #,year,month,fabric,type,variant | urls")
for r in q[-10:]: print(r[0],r[1],r[2],r[3],r[4],r[5],'|',(r[13] or '')[:50])
e=g.open_by_key("1DoOtov9T1A7qqJvPy-IhJC8OzQjweM0PdpOC_jJ8hEw")
print("=== EDU GS (B#|C topic|D|E|H|K|L|M|N tail|O)")
for r in e.worksheet("Generation Status").get_all_values()[3:]:
    if not r[1]: continue
    print("|".join([r[1],r[2],r[3],r[4],r[7],r[10],r[11],r[12],(r[13] or '')[-120:],r[14] if len(r)>14 else '']))
print("=== EDU queue: A#,D topic,E type,F series | Q urls count | R")
for r in e.worksheet("Generation Queue").get_all_values()[1:]:
    print(r[0],r[3],r[4],r[5],'|',len((r[16] or '').split()),'|',r[17][:40] if len(r)>17 else '', '|', (r[18][:40] if len(r)>18 else ''))
