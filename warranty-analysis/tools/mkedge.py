import zipfile,sys,os
d=sys.argv[1]
CT='<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>'
def wb(prefix=''):
    p=prefix
    return f'<?xml version="1.0"?><{p}workbook xmlns{":"+p[:-1] if p else ""}="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><{p}sheets><{p}sheet name="第一页" sheetId="1" r:id="rId7"/><{p}sheet name="S2" sheetId="2" r:id="rId8"/></{p}sheets></{p}workbook>'
def rels(target): return f'<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId8" Type="x/worksheet" Target="worksheets/sheet2.xml"/><Relationship Target="{target}" Id="rId7" Type="x/worksheet"/></Relationships>'
sst='<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="5"><si><t>发货条码</t></si><si><r><rPr><b/></rPr><t>富</t></r><r><t xml:space="preserve"> 文本 </t></r></si><si><t>A&amp;B &lt;x&gt; &#x4E2D;&#22269;</t><rPh sb="0" eb="1"><t>ふり</t></rPh></si><si><t></t></si><si><t>  前后空格  </t></si></sst>'
rows=['<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t> 产品COA </t></is></c><c r="D1" t="s"><v>1</v></c></row>',
 '<row r="2" spans="1:5"><c r="A2" t="s"><v>2</v></c><c t="b"><v>1</v></c><c><v>3.14</v></c><c r="E2" t="b"><v>0</v></c><c r="C2" t="str"><v>a&amp;b</v></c></row>',
 '<row r="3"><c r="A3" s="2"/><c r="B3" t="s"><v>99</v></c><c r="C3" t="inlineStr"><is><r><t>多</t></r><r><t>段</t></r></is></c><c r="AA3"><f>SUM(1)</f><v>45678</v></c></row>',
 '<row r="5"><c r="B5" t="s"><v>3</v></c><c r="C5" t="s"><v>4</v></c><c r="D5" t="inlineStr"><is><t/></is></c></row>',
 '<row r="6"></row>',
 '<row r="7"><c r="A7" t="e"><v>#N/A</v></c><c r="B7" t="inlineStr"><is><t>'+'长'*3000+'</t></is></c></row>']
sheet='<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><dimension ref="A1:AA7"/><sheetData>'+''.join(rows)+'</sheetData><rowBreaks count="1"><brk id="3"/></rowBreaks></worksheet>'
def mk(name,target,method,prefix=''):
    with zipfile.ZipFile(os.path.join(d,name),'w',method) as z:
        z.writestr('[Content_Types].xml',CT)
        z.writestr('xl/workbook.xml',wb(prefix))
        z.writestr('xl/_rels/workbook.xml.rels',rels(target))
        z.writestr('xl/sharedStrings.xml',sst)
        z.writestr('xl/worksheets/sheet1.xml',sheet)
        z.writestr('xl/worksheets/sheet2.xml','<worksheet><sheetData><row><c t="inlineStr"><is><t>WRONG SHEET</t></is></c></row></sheetData></worksheet>')
mk('edge-deflate.xlsx','worksheets/sheet1.xml',zipfile.ZIP_DEFLATED)
mk('edge-stored.xlsx','worksheets/sheet1.xml',zipfile.ZIP_STORED)
mk('edge-abs-target.xlsx','/xl/worksheets/sheet1.xml',zipfile.ZIP_DEFLATED)
mk('edge-prefixed.xlsx','worksheets/sheet1.xml',zipfile.ZIP_DEFLATED,prefix='x:')
open(os.path.join(d,'edge.csv'),'wb').write('﻿发货条码,"产品,COA"\r\n"a""b",x\n"多\n行",\n,,\n末行无换行'.encode('utf-8'))
