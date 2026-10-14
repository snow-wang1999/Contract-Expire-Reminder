"""把系统导出的续保单明细（原始数据，每行一个产品）整理成提醒清单。

规则（原来由人工整理，现封装进程序）：
1. 只保留“服务结束”落在提醒时间段内的行
2. 默认去掉：已 EOS（EOS时间 <= 服务结束）、资产状态为“不再拓展”、产品线LV1 为“数据中心能源及关键供电”
3. 按 当前合同号 + 服务结束 + 服务类型 合并，目录价相加；每个组合单独一封提醒
4. 只保留合并后目录价大于门槛（默认 2 万美元）的组合
"""
import datetime as dt

from .parser import parse_amount, parse_date, parse_int

RAW_SIGNATURE = ("当前合同号", "服务结束", "目录价")

EXCLUDED_LV1 = "数据中心能源及关键供电"
EXCLUDED_ASSET_STATUS = "不再拓展"

DEFAULT_OPTIONS = {
    "start": None,               # 默认下一年 1 月 1 日
    "end": None,                 # 默认下一年 12 月 31 日
    "include_eos": False,
    "include_no_expand": False,
    "include_dc_energy": False,
    "min_amount": 20000,
}


def is_raw_export(header_row):
    names = {str(h).strip() for h in header_row if h is not None}
    return all(col in names for col in RAW_SIGNATURE)


def default_period(today=None):
    year = (today or dt.date.today()).year + 1
    return dt.date(year, 1, 1), dt.date(year, 12, 31)


def _text(value):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def product_summary(products):
    """同型号合并，返回 [(型号, 报价项数量合计)]，按数量从多到少。导出表一行是一个型号，数量在“服务报价项数量”里。"""
    totals = {}
    for p in products:
        name = p.get("product") or "（未注明型号）"
        totals[name] = totals.get(name, 0) + (p.get("qty") or 0)
    return sorted(totals.items(), key=lambda kv: -kv[1])


def transform(rows, options=None, today=None):
    """rows 为含表头的二维列表。返回 (records, funnel, excluded, warnings)。"""
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    default_start, default_end = default_period(today)
    start = parse_date(opts["start"]) or default_start
    end = parse_date(opts["end"]) or default_end
    if start > end:
        raise ValueError("提醒时间段的开始日期晚于结束日期")
    min_amount = float(opts["min_amount"] or 0)

    header = [_text(h) for h in rows[0]]
    idx = {name: i for i, name in reversed(list(enumerate(header))) if name}

    def get(row, name):
        i = idx.get(name)
        return row[i] if i is not None and i < len(row) else None

    funnel = {"rows": 0, "out_of_period": 0, "eos": 0, "no_expand": 0, "dc_energy": 0,
              "bad_row": 0, "kept_rows": 0, "groups": 0, "below_min": 0, "records": 0}
    excluded, warnings, groups = [], [], {}

    for line_no, row in enumerate(rows[1:], start=2):
        if not any(v not in (None, "") for v in row):
            continue
        funnel["rows"] += 1
        contract_no = _text(get(row, "当前合同号"))
        expiry = parse_date(get(row, "服务结束"))
        eos = parse_date(get(row, "EOS时间")) or parse_date(get(row, "续保产品EOS时间"))
        info = {
            "row": line_no,
            "contract_no": contract_no,
            "customer": _text(get(row, "最终客户名称")),
            "product": _text(get(row, "续保产品名称")) or _text(get(row, "Offering 名称")),
            "service_type": _text(get(row, "服务类型")),
            "expiry": expiry.isoformat() if expiry else _text(get(row, "服务结束")),
            "eos": eos.isoformat() if eos else "",
            "asset_status": _text(get(row, "资产状态")),
            "lv1": _text(get(row, "产品线LV1")),
            "amount": parse_amount(get(row, "目录价")),
            "qty": parse_int(get(row, "服务报价项数量")),
            "units": parse_int(get(row, "整机标识数量")),
            "package": _text(get(row, "服务包名称")),
        }

        reason = None
        if not contract_no or expiry is None:
            reason, key = "缺少合同号或服务结束日期", "bad_row"
        elif not (start <= expiry <= end):
            reason, key = "过保时间不在提醒时间段内", "out_of_period"
        elif not opts["include_eos"] and eos is not None and eos <= expiry:
            reason, key = "设备已 EOS", "eos"
        elif not opts["include_no_expand"] and info["asset_status"] == EXCLUDED_ASSET_STATUS:
            reason, key = "资产状态为不再拓展", "no_expand"
        elif not opts["include_dc_energy"] and info["lv1"] == EXCLUDED_LV1:
            reason, key = "产品线为数据中心能源及关键供电", "dc_energy"
        if reason:
            funnel[key] += 1
            excluded.append({**info, "reason": reason})
            continue

        funnel["kept_rows"] += 1
        group_key = (contract_no, expiry, info["service_type"])
        g = groups.get(group_key)
        if g is None:
            g = groups[group_key] = {
                "office": _text(get(row, "存量代表处")),
                "region": _text(get(row, "存量地区部")),
                "customer": info["customer"],
                "contract_name": _text(get(row, "合同名称")),
                "expiry": expiry.isoformat(),
                "service_type": info["service_type"],
                "contract_no": contract_no,
                "amount": 0.0,
                "products": [],
            }
        g["contract_name"] = g["contract_name"] or _text(get(row, "合同名称"))
        g["amount"] += info["amount"] or 0
        g["products"].append(info)
        if info["amount"] is None:
            warnings.append(f"第 {line_no} 行（合同 {contract_no}）目录价为空，按 0 计算")

    funnel["groups"] = len(groups)
    records = []
    for g in sorted(groups.values(), key=lambda g: (g["expiry"], -g["amount"])):
        if g["amount"] <= min_amount:
            funnel["below_min"] += 1
            for p in g["products"]:
                excluded.append({**p, "reason": f"合同合计目录价 ${g['amount']:,.0f} 未超过门槛"})
            continue
        records.append({**g, "id": len(records), "remind_days": None, "emails": [], "lang": "zh",
                        "product_lines": [f"{n}×{q}" for n, q in product_summary(g["products"])]})
    funnel["records"] = len(records)

    period = {"start": start.isoformat(), "end": end.isoformat(), "min_amount": min_amount,
              "include_eos": bool(opts["include_eos"]), "include_no_expand": bool(opts["include_no_expand"]),
              "include_dc_energy": bool(opts["include_dc_energy"])}
    return records, {**funnel, "period": period}, excluded, warnings
