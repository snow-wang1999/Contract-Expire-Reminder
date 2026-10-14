"""过保数据分析：按紧急程度、代表处、维保类型、到期月份汇总。"""
import datetime as dt
from collections import OrderedDict

from .ordering import class_rank

# (标签, 距过保天数下限, 上限)，上下限均含
BUCKETS = [
    ("已过保", None, -1),
    ("30天内", 0, 30),
    ("31-90天", 31, 90),
    ("91-180天", 91, 180),
    ("181-365天", 181, 365),
    ("1年以上", 366, None),
]


def bucket_of(days_left):
    for label, low, high in BUCKETS:
        if (low is None or days_left >= low) and (high is None or days_left <= high):
            return label
    return BUCKETS[-1][0]


def _group(records, key):
    groups = {}
    for r in records:
        name = r.get(key) or "（未填写）"
        g = groups.setdefault(name, {"name": name, "count": 0, "amount": 0.0,
                                     "within_180": 0, "expired": 0, "nearest": None})
        g["count"] += 1
        g["amount"] += r["amount"] or 0
        if r["days_left"] < 0:
            g["expired"] += 1
        elif r["days_left"] <= 180:
            g["within_180"] += 1
        if (g["nearest"] is None or r["expiry"] < g["nearest"]):
            g["nearest"] = r["expiry"]
    return sorted(groups.values(), key=lambda g: (-g["amount"], -g["count"]))


def analyze(records, today=None, period=None):
    """period: {"start": iso, "end": iso}；有时按该时间段逐月统计，否则统计未来 12 个月。"""
    today = today or dt.date.today()
    enriched = []
    for r in records:
        days_left = (dt.date.fromisoformat(r["expiry"]) - today).days
        enriched.append({**r, "days_left": days_left, "bucket": bucket_of(days_left)})

    buckets = OrderedDict((label, {"name": label, "count": 0, "amount": 0.0}) for label, _, _ in BUCKETS)
    for r in enriched:
        b = buckets[r["bucket"]]
        b["count"] += 1
        b["amount"] += r["amount"] or 0

    # 逐月到期分布：提醒时间段内（最多 24 个月），默认未来 12 个月（含本月）
    months = OrderedDict()
    first = dt.date.fromisoformat(period["start"]) if period else today
    last = dt.date.fromisoformat(period["end"]) if period else None
    y, m = first.year, first.month
    for _ in range(24 if period else 12):
        if last and (y, m) > (last.year, last.month):
            break
        months[f"{y:04d}-{m:02d}"] = {"name": f"{y:04d}-{m:02d}", "count": 0, "amount": 0.0}
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for r in enriched:
        g = months.get(r["expiry"][:7])
        if g:
            g["count"] += 1
            g["amount"] += r["amount"] or 0

    return {
        "today": today.isoformat(),
        "total": {
            "count": len(enriched),
            "amount": sum(r["amount"] or 0 for r in enriched),
            "offices": len({r["office"] for r in enriched}),
            "customers": len({r["customer"] for r in enriched}),
        },
        "buckets": list(buckets.values()),
        "by_office": _group(enriched, "office"),
        "by_type": _group(enriched, "service_type"),
        "by_customer": _group(enriched, "customer")[:10],
        "by_class": sorted(_group(enriched, "customer_class"), key=lambda g: class_rank(g["name"].replace("（未填写）", ""))),
        "by_signer": _group(enriched, "signer") if any(r.get("mode") == "channel" for r in enriched) else [],
        "by_month": list(months.values()),
        "records": enriched,   # 保持名单原有顺序（按客户分类 / 签约客户分组排好）
    }
