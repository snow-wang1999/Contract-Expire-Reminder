"""本地持久化：设置、收件人名单、发送记录。都存放在 data/ 目录下。"""
import csv
import datetime as dt
import json
import os
import sys
import threading

DATA_DIR = os.environ.get("REMINDER_DATA_DIR",
                          os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

with open(os.path.join(TEMPLATE_DIR, "email.html"), encoding="utf-8") as _f:
    DEFAULT_BODY = _f.read()
with open(os.path.join(TEMPLATE_DIR, "email_en.html"), encoding="utf-8") as _f:
    DEFAULT_BODY_EN = _f.read()

DEFAULT_SETTINGS = {
    # outlook：本机 Outlook 发送（支持定时和日历邀请）；smtp：SMTP 服务器；dryrun：只记录不发送
    "mailer": "outlook" if sys.platform == "win32" else "dryrun",
    "send_hour": 9,               # 定时邮件的发送时刻（本机时间）
    "cc": "",
    "subject_template": "{customer} | {amount_fmt}维保过保|续保拓展提醒",
    "body_template": DEFAULT_BODY,
    "calendar_subject_template": "【过保】{customer} | {amount_fmt} | {service_type}",
    # 英文版（Excel“邮件语言”选 English 的行使用）
    "subject_template_en": "{customer} | {amount_fmt} Warranty Expiry | Renewal Reminder",
    "body_template_en": DEFAULT_BODY_EN,
    "calendar_subject_template_en": "[Warranty Expiry] {customer} | {amount_fmt} | {service_type}",
    "smtp": {"host": "", "port": 465, "ssl": True, "starttls": False,
             "username": "", "password": "", "sender": ""},
}

LOG_FIELDS = ["time", "key", "kind", "node", "contract_no", "customer", "expiry", "to", "cc", "action",
              "send_at", "mailer", "status", "error"]

_lock = threading.Lock()


def _path(name):
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, name)


def _read_json(name, default):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write_json(name, value):
    tmp = _path(name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    os.replace(tmp, _path(name))


def load_settings():
    saved = _read_json("settings.json", {})
    settings = {**DEFAULT_SETTINGS, **saved}
    settings["smtp"] = {**DEFAULT_SETTINGS["smtp"], **saved.get("smtp", {})}
    for key in ("subject_template", "body_template", "calendar_subject_template",
                "subject_template_en", "body_template_en", "calendar_subject_template_en"):
        settings[key] = settings.get(key) or DEFAULT_SETTINGS[key]   # 留空表示使用默认模板
    return settings


def save_settings(values):
    settings = load_settings()
    for key in DEFAULT_SETTINGS:
        if key in values:
            settings[key] = values[key]
    with _lock:
        _write_json("settings.json", settings)
    return settings


def load_recipients():
    """记住每个最终客户上次填写的邮箱名单和邮件语言：{"customer": {客户: "a;b"}, "lang": {客户: "en"}}"""
    data = _read_json("recipients.json", {})
    return {"customer": data.get("customer", {}), "lang": data.get("lang", {})}


def remember_recipients(records):
    data = load_recipients()
    for r in records:
        if r.get("customer") and r.get("emails"):
            data["customer"][r["customer"]] = ";".join(r["emails"])
            data["lang"][r["customer"]] = r.get("lang", "zh")
    with _lock:
        _write_json("recipients.json", data)
    return data


def append_log(entries):
    path = _path("send_log.csv")
    with _lock:
        new = not os.path.exists(path)
        # utf-8-sig 让 Excel 直接打开不乱码
        with open(path, "a", encoding="utf-8-sig" if new else "utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS, extrasaction="ignore")
            if new:
                writer.writeheader()
            now = dt.datetime.now().isoformat(timespec="seconds")
            for e in entries:
                writer.writerow({"time": now, **e})


def read_log():
    try:
        with open(_path("send_log.csv"), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def sent_keys():
    """已成功发送或排定过的提醒节点，用于防止重复发送。一条记录可能覆盖多个节点（逗号分隔）。"""
    return {k for row in read_log() if row.get("status") == "ok" for k in row["key"].split(",") if k}
