"""客户分类等级与提醒名单排序。

客户通知：高级别客户在前，同一最终客户的提醒相邻（收件人大概率相同，方便一起填写）。
渠道通知：同一签约客户（总代）相邻，其中同一二代再相邻。
"""

# (等级名称, 识别关键字)；按顺序越靠前级别越高。识别时忽略大小写
# 导出数据中：Strategic Account=战略，Core Account=核心，Value Account=价值，Small&Medium Account=商业
CLASS_LEVELS = [
    ("卓越", ["卓越", "excellen", "premier", "top"]),
    ("战略", ["战略", "strategic"]),
    ("核心", ["核心", "core"]),
    ("价值", ["价值", "value"]),
    ("商业", ["商业", "small", "medium", "commercial"]),
]
KEY_ACCOUNT_RANK = 3          # 等级 1~3 为卓越 / 战略 / 核心客户（“卓战核”）
OTHER_RANK = len(CLASS_LEVELS) + 1
BLANK_RANK = len(CLASS_LEVELS) + 2


def class_rank(customer_class):
    text = (customer_class or "").strip().lower()
    if not text:
        return BLANK_RANK
    for rank, (_, keywords) in enumerate(CLASS_LEVELS, start=1):
        if any(k in text for k in keywords):
            return rank
    return OTHER_RANK


def class_label(customer_class):
    """中文等级名，如 “Strategic Account” -> “战略”；空值为“未分类”。"""
    rank = class_rank(customer_class)
    if rank <= len(CLASS_LEVELS):
        return CLASS_LEVELS[rank - 1][0]
    return "未分类" if rank == BLANK_RANK else "其他"


def is_key_account(customer_class):
    return class_rank(customer_class) <= KEY_ACCOUNT_RANK


def _totals(records, key):
    totals = {}
    for r in records:
        totals[key(r)] = totals.get(key(r), 0) + (r.get("amount") or 0)
    return totals


def sort_records(records, mode="customer"):
    if mode == "channel":
        signer_total = _totals(records, lambda r: r.get("signer", ""))
        return sorted(records, key=lambda r: (
            -signer_total[r.get("signer", "")], r.get("signer", ""), r.get("tier2", ""),
            class_rank(r.get("customer_class")), r.get("customer", ""), r["expiry"], -(r.get("amount") or 0)))
    # 同一客户在不同行里分类应一致；以该客户的最高等级为准
    best = {}
    for r in records:
        best[r.get("customer", "")] = min(best.get(r.get("customer", ""), BLANK_RANK), class_rank(r.get("customer_class")))
    customer_total = _totals(records, lambda r: r.get("customer", ""))
    return sorted(records, key=lambda r: (
        best[r.get("customer", "")], -customer_total[r.get("customer", "")], r.get("customer", ""),
        r["expiry"], -(r.get("amount") or 0)))
