import zipfile,sys
src,dst,k=sys.argv[1],sys.argv[2],int(sys.argv[3])
zi=zipfile.ZipFile(src)
x=zi.read('xl/worksheets/sheet1.xml')
a=x.index(b'<sheetData>')+len(b'<sheetData>'); h=x.index(b'</row>',a)+6; e=x.index(b'</sheetData>')
head,body,tail=x[:h],x[h:e],x[e:]
with zipfile.ZipFile(dst,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as zo:
    for it in zi.infolist():
        if it.filename=='xl/worksheets/sheet1.xml':
            with zo.open(it.filename,'w',force_zip64=False) as w:
                w.write(head)
                for i in range(k): w.write(body)
                w.write(tail)
        else: zo.writestr(it.filename,zi.read(it.filename))
print(len(head)+len(body)*k+len(tail))
