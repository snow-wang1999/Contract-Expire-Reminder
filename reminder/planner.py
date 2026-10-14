"""为每条合同决定收件人、邮件内容和发送方式（立即 / 定时 / 跳过）。"""
import datetime as dt

from .parser import split_emails


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def format_amount(amount):
    if amount is None:
        return "金额无效"
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    if amount >= 10_000:
        return f"${amount / 10_000:.1f}W"
    return f"${amount:,.0f}"


def compress_text(text, max_len):
    if not text:
        return ""
    return text[:max_len - 3] + "..." if len(text) > max_len else text


def reminder_key(record, remind_date):
    return f"{record['contract_no']}|{record['expiry']}|{remind_date.isoformat()}"


def resolve_recipients(record, recipients):
    """优先级：页面上按合同填写 > Excel 邮箱名单列 > 按代表处填写。"""
    manual = recipients.get("contract", {}).get(record["contract_no"])
    if manual:
        return split_emails(manual), "按合同"
    if record.get("emails"):
        return record["emails"], "Excel"
    office = recipients.get("office", {}).get(record["office"])
    if office:
        return split_emails(office), "按代表处"
    return [], ""


def render(record, settings, remind_date, days_left):
    max_len = int(settings["max_text_length"])
    fields = _SafeDict(
        office=compress_text(record["office"], max_len),
        customer=compress_text(record["customer"], max_len),
        contract_name=compress_text(record["contract_name"], max_len),
        expiry=record["expiry"],
        service_type=record["service_type"],
        contract_no=record["contract_no"],
        amount="" if record["amount"] is None else f"{record['amount']:,.2f}",
        amount_fmt=format_amount(record["amount"]),
        remind_date=remind_date.isoformat(),
        days_left=days_left,
    )
    return (settings["subject_template"].format_map(fields),
            settings["body_template"].format_map(fields))


def plan(records, settings, recipients, sent, now=None):
    now = now or dt.datetime.now()
    today = now.date()
    cc = split_emails(settings.get("cc", ""))
    items = []
    for record in records:
        expiry = dt.date.fromisoformat(record["expiry"])
        remind_days = record["remind_days"] if record["remind_days"] is not None else int(settings["default_remind_days"])
        remind_date = expiry - dt.timedelta(days=remind_days)
        delay_days = (remind_date - today).days
        key = reminder_key(record, remind_date)
        to, source = resolve_recipients(record, recipients)
        subject, body = render(record, settings, remind_date, (expiry - today).days)

        send_at = None
        if not to:
            action, reason = "skip", "未填写收件人"
        elif delay_days <= 0:
            action, reason = "now", "已到提醒日期，立即发送"
        elif delay_days > int(settings["max_delay_days"]):
            action, reason = "skip", f"距提醒日期还有 {delay_days} 天，超过 {settings['max_delay_days']} 天上限"
        else:
            action, reason = "defer", f"{delay_days} 天后定时发送"
            send_at = dt.datetime.combine(remind_date, dt.time(int(settings["send_hour"]))).isoformat(timespec="minutes")

        already_sent = key in sent
        items.append({
            "id": record["id"],
            "key": key,
            "contract_no": record["contract_no"],
            "customer": record["customer"],
            "office": record["office"],
            "expiry": record["expiry"],
            "remind_date": remind_date.isoformat(),
            "to": to,
            "to_source": source,
            "cc": cc,
            "subject": subject,
            "body": body,
            "action": action,
            "reason": reason,
            "send_at": send_at,
            "already_sent": already_sent,
            "selected": action != "skip" and not already_sent,
        })
    return items
