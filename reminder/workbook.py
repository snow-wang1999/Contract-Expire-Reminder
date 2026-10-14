"""生成“待填写收件人”的 Excel：提醒名单 + 填写说明 + 产品明细 + 已排除 + 筛选条件。

客户通知：按客户分类等级排序，同一最终客户相邻；渠道通知：同一签约客户、二代相邻。
同一组（客户或签约客户+二代）用相同底色，便于整组填写相同的收件人。
"""
import datetime as dt
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .raw import product_summary

LANG_TEXT = {"zh": "中文", "en": "English"}
MODE_TEXT = {"customer": "客户", "channel": "渠道"}

HEADER_FONT = Font(bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="C7000B")
INPUT_HEADER_FILL = PatternFill("solid", fgColor="BF8F00")
FILL_ME = PatternFill("solid", fgColor="FFF2CC")
BAND_FILL = PatternFill("solid", fgColor="EDF2F9")
EXAMPLE_FILL = PatternFill("solid", fgColor="F2F2F2")


def _products(r):
    return product_summary(r.get("products", []))


def _product_text(r):
    if r.get("products"):
        return "；".join(f"{n}×{q}" for n, q in _products(r))
    return "；".join(r.get("product_lines", []))


# (表头, 取值, 列宽, 数字格式)
COMMON_COLUMNS = [
    ("代表处", lambda r: r.get("office", ""), 16, None),
    ("客户分类", lambda r: r.get("customer_class", ""), 18, None),
    ("最终客户", lambda r: r.get("customer", ""), 28, None),
    ("合同名称", lambda r: r.get("contract_name", ""), 36, None),
    ("过保时间", lambda r: _date(r["expiry"]), 12, "yyyy-mm-dd"),
    ("维保类型", lambda r: r.get("service_type", ""), 11, None),
    ("合同号", lambda r: r["contract_no"], 18, None),
    ("金额", lambda r: round(r.get("amount") or 0, 2), 12, "#,##0"),
    ("邮箱名单", lambda r: ";".join(r.get("emails", [])), 46, None),
    ("邮件语言", lambda r: LANG_TEXT[r.get("lang", "zh")], 10, None),
]
CHANNEL_COLUMNS = [
    ("签约客户", lambda r: r.get("signer", ""), 30, None),
    ("二代", lambda r: r.get("tier2", ""), 28, None),
]
TAIL_COLUMNS = [
    ("型号数", lambda r: len(_products(r)) or len(r.get("product_lines", [])), 8, None),
    ("报价项数量", lambda r: sum(q for _, q in _products(r)), 10, None),
    ("产品明细（型号×报价项数量）", _product_text, 60, None),
    ("通知模式", lambda r: MODE_TEXT[r.get("mode", "customer")], 10, None),
]
INPUT_HEADERS = ("邮箱名单", "邮件语言")


def list_columns(mode):
    return (CHANNEL_COLUMNS if mode == "channel" else []) + COMMON_COLUMNS + TAIL_COLUMNS


def column_index(mode, header):
    return [c[0] for c in list_columns(mode)].index(header) + 1


def group_key(r, mode):
    return (r.get("signer", ""), r.get("tier2", "")) if mode == "channel" else r.get("customer", "")


PRODUCT_COLUMNS = [("合同号", "contract_no"), ("过保时间", "expiry"), ("服务类型", "service_type"),
                   ("最终客户", "customer"), ("客户分类", "customer_class"), ("签约客户", "signer"), ("二代", "tier2"),
                   ("续保产品", "product"), ("服务包名称", "package"), ("报价项数量", "qty"), ("整机数量", "units"),
                   ("目录价", "amount"), ("EOS时间", "eos"), ("资产状态", "asset_status"), ("产品线LV1", "lv1"),
                   ("原始行号", "row")]
PRODUCT_WIDTHS = [18, 12, 12, 28, 18, 28, 26, 30, 36, 10, 10, 12, 12, 10, 18, 9]

GUIDE = {
    "customer": [
        "填写说明（客户通知）",
        "",
        "1. 只需要填写【提醒名单】工作表中黄色的“邮箱名单”和“邮件语言”两列，其他列请勿修改。",
        "2. 一行就是一封提醒邮件（合同号 + 过保时间 + 维保类型）。",
        "3. 名单按客户分类排序（卓越 > 战略 > 核心 > 价值 > 商业 > 未分类），同一客户的行排在一起、底色相同，收件人通常一样，可整组复制。",
        "4. 多个收件人用英文分号 ; 分隔（中文分号 ；也能识别）。可以填邮箱地址，也可以填 Outlook 能识别的姓名/工号。",
        "5. “邮件语言”默认“中文”，需要发英文版邮件（含日历邀请）的行请下拉选择“English”。",
        "6. 邮箱名单留空的行不会发送；不需要提醒的行也可以直接删除整行。",
        "7. 已带出邮箱和语言的行是根据上次填写的同一客户自动带出的，请核对。",
        "8. “产品明细”会写进邮件，一般不用改；如需修改，格式为 型号×数量，多个用 ；分隔。",
        "9. 填好后保存为 .xlsx，回到网页第③步上传。",
        "",
        "示例（灰色为示例，不要复制到提醒名单里）：",
    ],
    "channel": [
        "填写说明（渠道续保通知）",
        "",
        "1. 本名单用于通知签约客户（总代）或二代，只需要填写黄色的“邮箱名单”和“邮件语言”两列，其他列请勿修改。",
        "2. 一行就是一封提醒邮件（合同号 + 过保时间 + 维保类型）。",
        "3. 名单按签约客户排列，同一签约客户下同一二代的行排在一起、底色相同，收件人通常一样，可整组复制。",
        "4. 发给二代就填二代的联系人，发给总代就填签约客户的联系人；多个收件人用英文分号 ; 分隔。",
        "5. “邮件语言”默认“English”，需要中文版的行请下拉选择“中文”。",
        "6. 邮箱名单留空的行不会发送；不需要通知的行也可以直接删除整行。",
        "7. 已带出邮箱和语言的行是根据上次填写的同一签约客户+二代自动带出的，请核对。",
        "8. “产品明细”会写进邮件，一般不用改。",
        "9. 填好后保存为 .xlsx，回到网页第③步上传。",
        "",
        "示例（灰色为示例，不要复制到提醒名单里）：",
    ],
}

EXAMPLES = {
    "customer": [
        {"office": "南非代表处", "customer_class": "Strategic Account", "customer": "City of Tshwane",
         "contract_name": "PIN CL SA COT_Brilliantel_Services", "expiry": "2027-03-31", "service_type": "Hi-Care",
         "contract_no": "0Y071024000326", "amount": 46000, "emails": ["zhangsan@huawei.com", "lisi@huawei.com"],
         "lang": "zh", "product_lines": ["OptiXtrans E6616×4"]},
        {"office": "尼日利亚代表处", "customer_class": "Strategic Account", "customer": "Access Bank Plc",
         "contract_name": "Nigeria_Service Renewal", "expiry": "2027-06-30", "service_type": "Warranty",
         "contract_no": "0Y056625000932", "amount": 38000, "emails": ["wangwu 00123456", "zhaoliu@huawei.com"],
         "lang": "en", "product_lines": ["CloudEngine S5731-S24P4X×1"]},
    ],
    "channel": [
        {"signer": "Mustek Limited", "tier2": "Gagasi IT", "office": "南非代表处", "customer_class": "Value Account",
         "customer": "Waterberg TVET College", "contract_name": "Campus network service", "expiry": "2027-03-31",
         "service_type": "Hi-Care", "contract_no": "0Y071024000999", "amount": 26000,
         "emails": ["sales@gagasi.example.com", "pm@mustek.example.com"], "lang": "en", "mode": "channel",
         "product_lines": ["AirEngine 5761-11×11"]},
    ],
}


def _header(ws, columns):
    ws.append(columns)
    for cell in ws[1]:
        cell.font, cell.fill = HEADER_FONT, HEADER_FILL
        cell.alignment = Alignment(vertical="center")
    ws.freeze_panes = "A2"


def _widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _date(value):
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return value


def _write_list(ws, records, mode, banding=True):
    cols = list_columns(mode)
    ws.append([c[0] for c in cols])
    start = ws.max_row
    for i, (header, *_rest) in enumerate(cols, start=1):
        cell = ws.cell(start, i)
        cell.font = HEADER_FONT
        cell.fill = INPUT_HEADER_FILL if header in INPUT_HEADERS else HEADER_FILL
    band, last_group = False, object()
    for r in records:
        ws.append([c[1](r) for c in cols])
        row = ws[ws.max_row]
        if banding and group_key(r, mode) != last_group:
            band, last_group = not band, group_key(r, mode)
        for cell, (header, _, _, fmt) in zip(row, cols):
            if fmt:
                cell.number_format = fmt
            if header in INPUT_HEADERS:
                cell.fill = FILL_ME
            elif banding and band:
                cell.fill = BAND_FILL
    _widths(ws, [c[2] for c in cols])
    return start


def build(records, excluded, funnel):
    mode = funnel["period"].get("mode", "customer")
    wb = Workbook()

    ws = wb.active
    ws.title = "提醒名单"
    _write_list(ws, records, mode)
    ws.freeze_panes = "A2"
    lang_col = get_column_letter(column_index(mode, "邮件语言"))
    lang_list = DataValidation(type="list", formula1='"中文,English"', allow_blank=True,
                               showErrorMessage=True, error="请选择 中文 或 English")
    ws.add_data_validation(lang_list)
    if ws.max_row > 1:
        lang_list.add(f"{lang_col}2:{lang_col}{ws.max_row}")

    guide = wb.create_sheet("填写说明")
    for line in GUIDE[mode]:
        guide.append([line])
    guide["A1"].font = Font(bold=True, size=14)
    header_row = _write_list(guide, EXAMPLES[mode], mode, banding=False)
    for row in guide.iter_rows(min_row=header_row + 1):
        for cell in row:
            cell.fill = EXAMPLE_FILL
    guide.column_dimensions["A"].width = max(guide.column_dimensions["A"].width, 16)

    detail = wb.create_sheet("产品明细")
    _header(detail, [c for c, _ in PRODUCT_COLUMNS])
    for r in records:
        for p in r.get("products", []):
            detail.append([p.get(k) for _, k in PRODUCT_COLUMNS])
    _widths(detail, PRODUCT_WIDTHS)

    out = wb.create_sheet("已排除")
    _header(out, ["排除原因"] + [c for c, _ in PRODUCT_COLUMNS])
    for p in excluded:
        out.append([p["reason"]] + [p.get(k) for _, k in PRODUCT_COLUMNS])
    _widths(out, [30] + PRODUCT_WIDTHS)

    cond = wb.create_sheet("筛选条件")
    period = funnel["period"]
    yes = lambda b: "包含" if b else "不包含"
    rows = [
        ["通知模式", "渠道续保通知" if mode == "channel" else "客户通知"],
        ["提醒时间段", f"{period['start']} ~ {period['end']}"],
        ["目录价门槛", f"合同合计目录价 > ${period['min_amount']:,.0f}"],
        ["已 EOS 设备", yes(period["include_eos"])],
        ["资产状态为不再拓展", yes(period["include_no_expand"])],
        ["数据中心能源及关键供电", yes(period["include_dc_energy"])],
    ]
    if mode == "channel":
        rows.append(["卓越/战略/核心客户", yes(not period.get("channel_non_key_only"))])
    else:
        rows.append(["非卓越/战略/核心客户", yes(not period.get("customer_key_only"))])
    rows += [
        [],
        ["原始数据行数", funnel["rows"]],
        ["时间段外", funnel["out_of_period"]],
        ["已 EOS", funnel["eos"]],
        ["不再拓展", funnel["no_expand"]],
        ["数据中心能源及关键供电", funnel["dc_energy"]],
        ["卓越/战略/核心客户", funnel.get("key_account", 0)],
        ["非卓越/战略/核心客户", funnel.get("non_key_account", 0)],
        ["缺少合同号/日期", funnel["bad_row"]],
        ["合并后提醒条数", funnel["groups"]],
        ["目录价未超过门槛", funnel["below_min"]],
        ["最终提醒条数", funnel["records"]],
    ]
    for row in rows:
        cond.append(row)
    _widths(cond, [24, 40])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
