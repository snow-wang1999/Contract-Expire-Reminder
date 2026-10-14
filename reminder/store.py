"""本地持久化：设置、收件人名单、发送记录。都存放在 data/ 目录下。"""
import csv
import datetime as dt
import json
import os
import sys
import threading

DATA_DIR = os.environ.get("REMINDER_DATA_DIR",
                          os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))

DEFAULT_BODY = """⏰ 合同到期提醒 | {expiry}

▫️ 代表处：{office}
▫️ 合同名称：{contract_name}
▫️ 维保类型：{service_type}
▫️ 合同编号：{contract_no}

📌 续保关键时间节点：
• 6个月前：启动客户沟通与商机验证
• 3个月前：制定服务方案/确认维保范围与等级
• 1个月前：完成合同续签准备

🔧 技术支持：
• 价值呈现材料准备 联系王雪健 00621410
• 埃及MSSD团队报价支持
• AMS团队支持网络巡检（按需）

📢 系统通知：过保通知函已实现自动制作
请及时联系客户确认续保事宜！
"""

DEFAULT_SETTINGS = {
    # outlook：本机 Outlook 发送（支持定时）；smtp：SMTP 服务器；dryrun：只记录不发送
    "mailer": "outlook" if sys.platform == "win32" else "dryrun",
    "default_remind_days": 180,   # Excel 中没有“提醒天数”时使用
    "max_delay_days": 300,        # 提醒日期距今超过此天数则暂不排定
    "send_hour": 9,               # 定时邮件的发送时刻（本机时间）
    "max_text_length": 200,
    "cc": "",
    "subject_template": "{customer} | {amount_fmt}存量经营续保拓展提醒",
    "body_template": DEFAULT_BODY,
    "smtp": {"host": "", "port": 465, "ssl": True, "starttls": False,
             "username": "", "password": "", "sender": ""},
}

LOG_FIELDS = ["time", "key", "contract_no", "customer", "to", "cc", "action",
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
    """{"office": {代表处: "a;b"}, "contract": {合同号: "a;b"}}"""
    data = _read_json("recipients.json", {})
    return {"office": data.get("office", {}), "contract": data.get("contract", {})}


def save_recipients(values):
    data = {"office": {k: v for k, v in values.get("office", {}).items() if v.strip()},
            "contract": {k: v for k, v in values.get("contract", {}).items() if v.strip()}}
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
    """已成功发送或排定过的提醒，用于防止重复发送。"""
    return {row["key"] for row in read_log() if row.get("status") == "ok"}
