import sys,openpyxl,hashlib
def dump(p):
    wb=openpyxl.load_workbook(p,read_only=True)
    out=[]
    for ws in wb.worksheets:
        h=hashlib.sha1();n=0
        for row in ws.iter_rows(values_only=True):
            if row and row[0]=='生成时间':continue
            h.update(repr(row).encode());n+=1
        out.append((ws.title,n,h.hexdigest()[:12]))
    return out
for sc in sys.argv[2:]:
    a=dump(f'{sys.argv[1]}/R-old-{sc}.xlsx');b=dump(f'{sys.argv[1]}/R-new-{sc}.xlsx')
    print(sc,'IDENTICAL' if a==b else 'DIFF', b if a==b else (a,b))
