"""根据提醒频率选项，为每条提醒（合同号 + 过保日期 + 服务类型）生成邮件 / 日历邀请计划。

五个选项可任意组合：
- m6 / m3 / m1：过保前 6 / 3 / 1 个月定时发送（Outlook 延迟发送）
- immediate：立即发送一次
- expiry_calendar：过保当日写入 Outlook 日历，并以会议邀请发给收件人
节点日期已过去时默认跳过；选择 past_nodes="send_now" 则立即补发。
同一条提醒当下要发的多个节点合并成一封邮件，避免一次收到多封相同内容。
"""
import calendar
import datetime as dt
import html
import re

from .parser import split_emails

NODES = [("m6", 6, "提前6个月提醒"), ("m3", 3, "提前3个月提醒"), ("m1", 1, "提前1个月提醒")]

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


def fill(template, fields, escape=False):
    """替换 {字段名}；未知占位符原样保留，避免模板里的其他大括号报错。"""
    def sub(m):
        if m.group(1) not in fields:
            return m.group(0)
        value = str(fields[m.group(1)])
        return html.escape(value) if escape else value
    return PLACEHOLDER.sub(sub, template)


def base_key(record):
    return f"{record['contract_no']}|{record['expiry']}|{record['service_type']}"


def days_text(days):
    if days > 0:
        return f"距过保 {days} 天"
    return "今日过保" if days == 0 else f"已过保 {-days} 天"


def fields_for(record, node_label, ref_date):
    expiry = dt.date.fromisoformat(record["expiry"])
    return {
        "office": record.get("office", ""),
        "customer": record.get("customer", ""),
        "contract_name": record.get("contract_name", ""),
        "expiry": record["expiry"],
        "service_type": record.get("service_type", ""),
        "contract_no": record["contract_no"],
        "amount": "" if record.get("amount") is None else f"{record['amount']:,.2f}",
        "amount_fmt": format_amount(record.get("amount")),
        "node_label": node_label,
        "days_left": (expiry - ref_date).days,
        "days_text": days_text((expiry - ref_date).days),
    }


def calendar_body(record):
    return "\n".join([
        f"过保提醒：{record.get('customer', '')}",
        f"合同名称：{record.get('contract_name', '')}",
        f"合同编号：{record['contract_no']}",
        f"维保类型：{record.get('service_type', '')}",
        f"目录价：{format_amount(record.get('amount'))}",
        f"代表处：{record.get('office', '')}",
        f"过保时间：{record['expiry']}",
        "",
        "请及时联系客户确认续保事宜，维保信息以 eCrop 系统为准。",
    ])


def plan(records, settings, sent, options=None, now=None):
    opts = {**DEFAULT_OPTIONS, **(options or {})}
    now = now or dt.datetime.now()
    today = now.date()
    send_hour = int(settings["send_hour"])
    cc = split_emails(settings.get("cc", ""))
    items = []

    for record in records:
        expiry = dt.date.fromisoformat(record["expiry"])
        to = record.get("emails") or []
        base = base_key(record)
        common = {"id": record["id"], "contract_no": record["contract_no"], "customer": record.get("customer", ""),
                  "office": record.get("office", ""), "expiry": record["expiry"],
                  "service_type": record.get("service_type", ""), "amount": record.get("amount"),
                  "to": to, "cc": cc}

        def add(kind, node, label, keys, action, reason, date, send_at=None):
            ref = date if action == "defer" else today
            f = fields_for(record, label, ref)
            if kind == "email":
                subject = fill(settings["subject_template"], f)
                body = fill(settings["body_template"], f, escape=True)
            else:
                subject = fill(settings["calendar_subject_template"], f)
                body = calendar_body(record)
            already = bool(keys) and all(k in sent for k in keys)
            if not to and action != "skip":
                action, reason = "skip", "未填写收件人"
            items.append({**common, "kind": kind, "node": node, "node_label": label, "keys": keys,
                          "date": date.isoformat(), "send_at": send_at, "action": action, "reason": reason,
                          "subject": subject, "body": body, "already_sent": already,
                          "selected": action != "skip" and not already})

        due_now = []  # 当下要发的节点，最后合并成一封
        for node, months, label in NODES:
            if not opts.get(node):
                continue
            key = f"{base}|{node}"
            node_date = add_months(expiry, -months)
            if key in sent:
                add("email", node, label, [key], "skip", "该节点之前已发送", node_date)
            elif node_date > today:
                send_at = dt.datetime.combine(node_date, dt.time(send_hour)).isoformat(timespec="minutes")
                add("email", node, label, [key], "defer", f"{(node_date - today).days} 天后定时发送", node_date, send_at)
            elif node_date == today or opts.get("past_nodes") == "send_now":
                due_now.append((key, label))
            else:
                add("email", node, label, [key], "skip", f"节点日期 {node_date} 已过", node_date)

        if opts.get("immediate"):
            due_now.append((f"{base}|immediate|{today.isoformat()}", "即时提醒"))
        if due_now:
            keys = [k for k, _ in due_now]
            label = due_now[-1][1] if len(due_now) == 1 else "即时提醒"
            reason = "立即发送" + (f"（合并 {len(due_now)} 个节点）" if len(due_now) > 1 else "")
            add("email", "now", label, keys, "now", reason, today)

        if opts.get("expiry_calendar"):
            key = f"{base}|calendar"
            if expiry < today:
                add("calendar", "calendar", "过保当日日历", [key], "skip", "过保日期已过", expiry)
            else:
                add("calendar", "calendar", "过保当日日历", [key], "now", "立即发出日历邀请", expiry)
    return items
