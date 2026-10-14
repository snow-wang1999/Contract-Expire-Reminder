"""根据提醒频率选项，为每条提醒（合同号 + 过保日期 + 服务类型）生成邮件 / 日历邀请计划。

五个选项可任意组合：
- m6 / m3 / m1：过保前 6 / 3 / 1 个月定时发送（Outlook 延迟发送）
- immediate：立即发送一次
- expiry_calendar：过保当日写入 Outlook 日历，并以会议邀请发给收件人
节点日期已过去时默认跳过；选择 past_nodes="send_now" 则立即补发。
同一条提醒当下要发的多个节点合并成一封邮件，避免一次收到多封相同内容。

渠道续保通知按合作伙伴合并：签约客户、二代、收件人、语言都相同的合同，
同一天要发的提醒合并成一封，正文用表格列出全部合同。不同二代分开发（有时直接与二代签约）。为了让更多合同合并，
渠道通知的 6/3/1 个月节点统一提前到当月 1 日（例如 2027-03-31 过保，3 个月节点为 2026-12-01）。
过保当日日历邀请按同一过保日期合并。
"""
import calendar
import datetime as dt
import html
import re

from .parser import split_emails

NODES = [("m6", 6), ("m3", 3), ("m1", 1)]

# 提醒节点名称：页面显示用中文，邮件内容按收件语言
NODE_TEXT = {
    "m6": {"zh": "提前6个月提醒", "en": "6-month reminder"},
    "m3": {"zh": "提前3个月提醒", "en": "3-month reminder"},
    "m1": {"zh": "提前1个月提醒", "en": "1-month reminder"},
    "immediate": {"zh": "即时提醒", "en": "Renewal reminder"},
    "calendar": {"zh": "过保当日日历", "en": "Expiry day"},
}

DEFAULT_OPTIONS = {"m6": True, "m3": True, "m1": True, "immediate": False,
                   "expiry_calendar": False, "past_nodes": "skip"}

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def add_months(date, months):
    month0 = date.month - 1 + months
    year, month = date.year + month0 // 12, month0 % 12 + 1
    return dt.date(year, month, min(date.day, calendar.monthrange(year, month)[1]))


def format_amount(amount):
    if amount is None:
        return "金额无效"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    if amount >= 10_000:
        return f"${amount / 10_000:.1f}W"
    return f"${amount:,.0f}"


def fill(template, fields, escape=False, raw_html=None):
    """替换 {字段名}；未知占位符原样保留，避免模板里的其他大括号报错。
    raw_html 中的字段已是 HTML，不再转义。"""
    raw_html = raw_html or {}

    def sub(m):
        if m.group(1) in raw_html:
            return raw_html[m.group(1)]
        if m.group(1) not in fields:
            return m.group(0)
        value = str(fields[m.group(1)])
        return html.escape(value) if escape else value
    return PLACEHOLDER.sub(sub, template)


def base_key(record):
    key = f"{record['contract_no']}|{record['expiry']}|{record['service_type']}"
    # 渠道通知与客户通知互不影响，同一合同两种通知可以都发
    return key + "|channel" if record.get("mode") == "channel" else key


# 英文邮件里代表处名称的翻译；未收录的国家保留原文
COUNTRY_EN = {
    "南非": "South Africa", "尼日利亚": "Nigeria", "肯尼亚": "Kenya", "加纳": "Ghana", "安哥拉": "Angola",
    "赞比亚": "Zambia", "津巴布韦": "Zimbabwe", "坦桑尼亚": "Tanzania", "乌干达": "Uganda", "埃塞俄比亚": "Ethiopia",
    "莫桑比克": "Mozambique", "博茨瓦纳": "Botswana", "纳米比亚": "Namibia", "马拉维": "Malawi", "卢旺达": "Rwanda",
    "毛里求斯": "Mauritius", "马达加斯加": "Madagascar", "刚果（金）": "DR Congo", "刚果(金)": "DR Congo",
    "刚果（布）": "Congo", "刚果(布)": "Congo", "喀麦隆": "Cameroon", "科特迪瓦": "Côte d'Ivoire", "塞内加尔": "Senegal",
    "埃及": "Egypt", "摩洛哥": "Morocco", "阿尔及利亚": "Algeria", "突尼斯": "Tunisia", "苏丹": "Sudan",
    "南部非洲": "Southern Africa", "东非": "East Africa", "西非": "West Africa", "北非": "North Africa",
}
OFFICE_SUFFIX_EN = [("多国管理部", "Multi-Country Management Dept."), ("代表处", "Representative Office"),
                    ("地区部", "Region")]


def office_en(name):
    for suffix, suffix_en in OFFICE_SUFFIX_EN:
        if name.endswith(suffix) and name[:-len(suffix)] in COUNTRY_EN:
            return f"{COUNTRY_EN[name[:-len(suffix)]]} {suffix_en}"
    return COUNTRY_EN.get(name, name)


def days_text(days, lang="zh"):
    if lang == "en":
        if days > 0:
            return f"{days} days to expiry"
        return "expires today" if days == 0 else f"expired {-days} days ago"
    if days > 0:
        return f"距过保 {days} 天"
    return "今日过保" if days == 0 else f"已过保 {-days} 天"


def products_html(record):
    lines = record.get("product_lines") or []
    return "<br>".join(html.escape(p) for p in lines) if lines else "-"


def fields_for(record, node, ref_date, lang):
    expiry = dt.date.fromisoformat(record["expiry"])
    return {
        "office": office_en(record.get("office", "")) if lang == "en" else record.get("office", ""),
        "customer": record.get("customer", ""),
        "contract_name": record.get("contract_name", ""),
        "expiry": record["expiry"],
        "service_type": record.get("service_type", ""),
        "contract_no": record["contract_no"],
        "amount": "" if record.get("amount") is None else f"{record['amount']:,.2f}",
        "amount_fmt": format_amount(record.get("amount")),
        "node_label": NODE_TEXT[node][lang],
        "days_left": (expiry - ref_date).days,
        "days_text": days_text((expiry - ref_date).days, lang),
        "customer_class": record.get("customer_class", ""),
        "signer": record.get("signer", ""),
        "tier2": record.get("tier2", ""),
        "partner_name": record.get("tier2") or record.get("signer") or ("Partner" if lang == "en" else "合作伙伴"),
    }


def _calendar_lines(record, lang):
    products = "; ".join(record.get("product_lines") or []) or "-"
    if lang == "en":
        return [f"End customer: {record.get('customer', '')}",
                f"Contract name: {record.get('contract_name', '')}",
                f"Contract No.: {record['contract_no']}",
                f"Service type: {record.get('service_type', '')}",
                f"Products: {products}",
                f"Expiry date: {record['expiry']}"]
    return [f"最终客户：{record.get('customer', '')}",
            f"合同名称：{record.get('contract_name', '')}",
            f"合同编号：{record['contract_no']}",
            f"维保类型：{record.get('service_type', '')}",
            f"产品型号：{products}",
            f"过保时间：{record['expiry']}"]


def calendar_body(record, lang="zh"):
    if lang == "en":
        lines = [f"Warranty expiry: {record.get('customer', '')}"] + _calendar_lines(record, lang)[1:4] + [
            f"Products: {'; '.join(record.get('product_lines') or []) or '-'}",
            f"List price: {format_amount(record.get('amount'))}",
            f"Rep office: {office_en(record.get('office', ''))}",
            f"Expiry date: {record['expiry']}",
            "",
            "Please contact the customer promptly to confirm the renewal. eCrop is the source of truth."]
    else:
        lines = [f"过保提醒：{record.get('customer', '')}"] + _calendar_lines(record, lang)[1:4] + [
            f"产品型号：{'; '.join(record.get('product_lines') or []) or '-'}",
            f"目录价：{format_amount(record.get('amount'))}",
            f"代表处：{record.get('office', '')}",
            f"过保时间：{record['expiry']}",
            "",
            "请及时联系客户确认续保事宜，维保信息以 eCrop 系统为准。"]
    return "\n".join(lines)


def partner_calendar_body(records, lang):
    """渠道通知的日历邀请：不含金额和内部信息，列出同一天过保的全部合同。"""
    intro = ("The Huawei maintenance services below expire today. Please confirm the renewal with your customers."
             if lang == "en" else "以下华为维保服务今日到期，请与客户确认续保。")
    blocks = ["\n".join(_calendar_lines(r, lang)) for r in records]
    return intro + "\n\n" + "\n\n".join(blocks)


CONTRACT_HEADERS = {
    "zh": ["最终客户", "合同名称", "合同编号", "维保类型", "产品型号", "过保时间", "剩余天数"],
    "en": ["End Customer", "Contract Name", "Contract No.", "Service Type", "Products", "Expiry Date", "Days Left"],
}


def contracts_table(records, ref_date, lang):
    """渠道合并邮件中的合同列表（HTML，内联样式，兼容 Outlook）。"""
    th = 'style="padding:6px 8px;border-bottom:2px solid #c7000b;text-align:left;font-size:12px;color:#666;"'
    td = 'style="padding:6px 8px;border-bottom:1px solid #e6e6e6;vertical-align:top;font-size:13px;color:#333;"'
    head = "".join(f"<th {th}>{h}</th>" for h in CONTRACT_HEADERS[lang])
    rows = []
    for r in sorted(records, key=lambda r: (r["expiry"], r.get("customer", ""))):
        days = (dt.date.fromisoformat(r["expiry"]) - ref_date).days
        cells = [f"<strong>{html.escape(r.get('customer', ''))}</strong>", html.escape(r.get("contract_name", "")),
                 html.escape(r["contract_no"]), html.escape(r.get("service_type", "")), products_html(r),
                 html.escape(r["expiry"]), html.escape(days_text(days, lang))]
        rows.append("<tr>" + "".join(f"<td {td}>{c}</td>" for c in cells) + "</tr>")
    return (f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f"<tr>{head}</tr>{''.join(rows)}</table>")


def partner_name(records, lang):
    """称呼：组内二代都相同用二代，否则签约客户都相同用签约客户，否则泛称“合作伙伴”。"""
    for field in ("tier2", "signer"):
        names = {r.get(field, "") for r in records}
        if len(names) == 1 and next(iter(names)):
            return next(iter(names))
    return "Partner" if lang == "en" else "合作伙伴"


def _record_units(record, sent, opts, today, send_hour):
    """一条提醒的各个发送节点（尚未生成邮件内容）。"""
    expiry = dt.date.fromisoformat(record["expiry"])
    channel = record.get("mode") == "channel"
    base = base_key(record)
    units = []

    def add(kind, node, keys, action, reason, date, send_at=None, label_node=None):
        units.append({"record": record, "kind": kind, "node": node, "keys": keys, "action": action,
                      "reason": reason, "date": date, "send_at": send_at, "label_node": label_node or node,
                      "already_sent": bool(keys) and all(k in sent for k in keys)})

    due_now = []  # 当下要发的节点，最后合并成一封
    for node, months in NODES:
        if not opts.get(node):
            continue
        key = f"{base}|{node}"
        node_date = add_months(expiry, -months)
        if channel:
            node_date = node_date.replace(day=1)
        if key in sent:
            add("email", node, [key], "skip", ("sent_before", {}), node_date)
        elif node_date > today:
            send_at = dt.datetime.combine(node_date, dt.time(send_hour)).isoformat(timespec="minutes")
            add("email", node, [key], "defer", ("defer", {"days": (node_date - today).days}), node_date, send_at)
        elif node_date == today or opts.get("past_nodes") == "send_now":
            due_now.append((key, node))
        else:
            add("email", node, [key], "skip", ("past", {"date": node_date.isoformat()}), node_date)

    if opts.get("immediate"):
        due_now.append((f"{base}|immediate|{today.isoformat()}", "immediate"))
    if due_now:
        label_node = due_now[0][1] if len(due_now) == 1 else "immediate"
        reason = ("now_merged", {"n": len(due_now)}) if len(due_now) > 1 else ("now", {})
        add("email", "now", [k for k, _ in due_now], "now", reason, today, label_node=label_node)

    if opts.get("expiry_calendar"):
        key = f"{base}|calendar"
        if expiry < today:
            add("calendar", "calendar", [key], "skip", ("expired", {}), expiry)
        else:
            add("calendar", "calendar", [key], "now", ("calendar_now", {}), expiry)

    if not record.get("emails"):
        for u in units:
            if u["action"] != "skip":
                u["action"], u["reason"] = "skip", ("no_recipients", {})
    return units


REASON_TEXT = {
    "sent_before": "该节点之前已发送",
    "defer": "{days} 天后定时发送",
    "past": "节点日期 {date} 已过",
    "now": "立即发送",
    "now_merged": "立即发送（合并 {n} 个节点）",
    "expired": "过保日期已过",
    "calendar_now": "立即发出日历邀请",
    "no_recipients": "未填写收件人",
}


def _item(units, settings, today):
    """把一个或多个节点（渠道通知按伙伴合并）生成一条发送项。"""
    first = units[0]
    records = list({id(u["record"]): u["record"] for u in units}.values())
    record = records[0]
    lang = "en" if record.get("lang") == "en" else "zh"
    channel = record.get("mode") == "channel"
    suffix = "_en" if lang == "en" else ""
    label_node = first["label_node"] if all(u["label_node"] == first["label_node"] for u in units) else "immediate"
    ref = first["date"] if first["action"] == "defer" else today
    f = fields_for(record, label_node, ref, lang)
    f.update(partner_name=partner_name(records, lang), count=len(records),
             first_expiry=min(r["expiry"] for r in records))

    if channel:
        if first["kind"] == "email":
            subject = fill(settings["subject_template_partner" + suffix], f)
            body = fill(settings["body_template_partner" + suffix], f, escape=True,
                        raw_html={"contracts_table": contracts_table(records, ref, lang),
                                  "products": products_html(record)})
        else:
            subject = fill(settings["calendar_subject_template_partner" + suffix], f)
            body = partner_calendar_body(records, lang)
    elif first["kind"] == "email":
        subject = fill(settings["subject_template" + suffix], f)
        body = fill(settings["body_template" + suffix], f, escape=True, raw_html={"products": products_html(record)})
    else:
        subject = fill(settings["calendar_subject_template" + suffix], f)
        body = calendar_body(record, lang)

    code, params = first["reason"]
    if len(units) > 1 and first["action"] != "skip":
        params = {**params, "contracts": len(records)}
    nos = [r["contract_no"] for r in records]
    return {
        "id": record["id"], "ids": [r["id"] for r in records], "count": len(records),
        "contract_no": ";".join(nos),
        "contract_nos": nos,
        "customer": "; ".join(dict.fromkeys(r.get("customer", "") for r in records)),
        "office": record.get("office", ""),
        "expiry": min(r["expiry"] for r in records),
        "service_type": " / ".join(dict.fromkeys(r.get("service_type", "") for r in records)),
        "amount": sum(r.get("amount") or 0 for r in records),
        "to": record.get("emails") or [], "cc": split_emails(settings.get("cc", "")),
        "lang": lang, "mode": "channel" if channel else "customer",
        "customer_class": record.get("customer_class", ""), "signer": record.get("signer", ""),
        "tier2": record.get("tier2", ""), "partner": partner_name(records, lang) if channel else "",
        "kind": first["kind"], "node": first["node"], "node_label": NODE_TEXT[label_node]["zh"],
        "label_node": label_node, "keys": [k for u in units for k in u["keys"]],
        "date": first["date"].isoformat(), "send_at": first["send_at"], "action": first["action"],
        "reason_code": code, "reason_params": params, "reason": REASON_TEXT[code].format(**params),
        "subject": subject, "body": body, "already_sent": all(u["already_sent"] for u in units),
        "selected": first["action"] != "skip" and not all(u["already_sent"] for u in units),
    }


def _partner_group(unit):
    r = unit["record"]
    when = unit["send_at"] if unit["action"] == "defer" else (
        unit["date"].isoformat() if unit["kind"] == "calendar" else "now")
    return (r.get("signer", ""), r.get("tier2", ""), tuple(sorted(e.lower() for e in r.get("emails") or [])),
            r.get("lang", "zh"), unit["kind"], unit["action"], when)


def plan(records, settings, sent, options=None, now=None):
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    today = (now or dt.datetime.now()).date()
    send_hour = int(settings["send_hour"])
    items, groups = [], {}
    for record in records:
        for unit in _record_units(record, sent, opts, today, send_hour):
            if record.get("mode") != "channel" or unit["action"] == "skip" or unit["already_sent"]:
                items.append(unit)
            else:
                key = _partner_group(unit)
                if key not in groups:
                    groups[key] = []
                    items.append(groups[key])     # 占位，保持在该伙伴第一次出现的位置
                groups[key].append(unit)
    return [_item(x if isinstance(x, list) else [x], settings, today) for x in items]
