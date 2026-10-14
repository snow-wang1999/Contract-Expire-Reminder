import datetime as dt
import io

import openpyxl
import pytest

from reminder import analysis, parser, planner, store


def make_xlsx(rows):
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


LEGACY_HEADER = ["代表处", "最终客户", "合同名称", "过保时间", "维保类型", "合同号", "金额", "提醒天数", "邮箱名单"]


def test_parse_legacy_format():
    content = make_xlsx([
        LEGACY_HEADER,
        ["埃及", "客户A", "合同A", dt.datetime(2027, 3, 1), "原厂", "C1", 1500000, 180, "a@x.com; b@x.com"],
        ["埃及", "客户B", "合同B", "2027/01/15", "原厂", "C2", "12,000", None, "c@x.com；d@x.com"],
        ["埃及", "客户C", "合同C", "无效日期", "原厂", "C3", 100, 30, ""],
        [None] * 9,
    ])
    records, warnings = parser.parse_file("维保日历数据.xlsx", content)
    assert [r["contract_no"] for r in records] == ["C1", "C2"]
    assert records[0]["expiry"] == "2027-03-01"
    assert records[0]["emails"] == ["a@x.com", "b@x.com"]
    assert records[1]["amount"] == 12000.0
    assert records[1]["remind_days"] is None
    assert records[1]["emails"] == ["c@x.com", "d@x.com"]
    assert len(warnings) == 1 and "C3" in warnings[0]


def test_parse_by_header_name_any_order():
    content = make_xlsx([["合同编号", "到期日期", "客户名称"], ["C9", "2027-05-06", "客户Z"]])
    records, warnings = parser.parse_file("raw.xlsx", content)
    assert warnings == []
    assert records[0]["contract_no"] == "C9"
    assert records[0]["customer"] == "客户Z"
    assert records[0]["expiry"] == "2027-05-06"


def test_parse_csv_gbk():
    content = "合同号,过保时间,代表处\nC5,2027/2/3,南非\n".encode("gbk")
    records, _ = parser.parse_file("data.csv", content)
    assert records[0]["office"] == "南非"
    assert records[0]["expiry"] == "2027-02-03"


def test_parse_excel_serial_date():
    assert parser.parse_date(46000) == dt.date(2025, 12, 9)


def test_format_amount_matches_legacy():
    assert planner.format_amount(1_500_000) == "$1.50M"
    assert planner.format_amount(12_000) == "$1.2W"
    assert planner.format_amount(999) == "$999"
    assert planner.format_amount(None) == "金额无效"


def _record(**kw):
    base = {"id": 0, "office": "埃及", "customer": "客户A", "contract_name": "合同A", "expiry": "2027-01-01",
            "service_type": "原厂", "contract_no": "C1", "amount": 20000.0, "remind_days": 180, "emails": []}
    return {**base, **kw}


SETTINGS = {**store.DEFAULT_SETTINGS, "cc": "boss@x.com"}
NOW = dt.datetime(2026, 10, 14, 10, 0)


def test_plan_actions():
    records = [
        _record(id=0, contract_no="NOW", expiry="2027-01-01", emails=["a@x.com"]),      # 提醒日 2026-07-05 已过
        _record(id=1, contract_no="DEFER", expiry="2027-06-01", emails=["a@x.com"]),    # 提醒日 2026-12-03
        _record(id=2, contract_no="FAR", expiry="2029-01-01", emails=["a@x.com"]),      # 超过 300 天
        _record(id=3, contract_no="NOBODY", expiry="2027-01-01"),
    ]
    items = {i["contract_no"]: i for i in planner.plan(records, SETTINGS, {"office": {}, "contract": {}}, set(), NOW)}
    assert items["NOW"]["action"] == "now" and items["NOW"]["selected"]
    assert items["DEFER"]["action"] == "defer"
    assert items["DEFER"]["send_at"] == "2026-12-03T09:00"
    assert items["FAR"]["action"] == "skip"
    assert items["NOBODY"]["action"] == "skip" and items["NOBODY"]["reason"] == "未填写收件人"
    assert items["NOW"]["cc"] == ["boss@x.com"]
    assert items["NOW"]["subject"] == "客户A | $2.0W存量经营续保拓展提醒"
    assert "合同编号：NOW" in items["NOW"]["body"]


def test_plan_recipient_priority_and_dedupe():
    rec = _record(emails=["excel@x.com"])
    recipients = {"office": {"埃及": "office@x.com"}, "contract": {}}
    item = planner.plan([rec], SETTINGS, recipients, set(), NOW)[0]
    assert item["to"] == ["excel@x.com"] and item["to_source"] == "Excel"

    item = planner.plan([_record()], SETTINGS, recipients, set(), NOW)[0]
    assert item["to"] == ["office@x.com"]

    recipients["contract"]["C1"] = "x@x.com; y@x.com"
    item = planner.plan([rec], SETTINGS, recipients, {item["key"]}, NOW)[0]
    assert item["to"] == ["x@x.com", "y@x.com"]
    assert item["already_sent"] and not item["selected"]


def test_analysis_buckets():
    today = dt.date(2026, 10, 14)
    records = [_record(expiry="2026-10-01", amount=100.0), _record(expiry="2026-10-20", amount=None),
               _record(expiry="2027-03-01", office="南非")]
    rp = analysis.analyze(records, today)
    counts = {b["name"]: b["count"] for b in rp["buckets"]}
    assert counts["已过保"] == 1 and counts["30天内"] == 1 and counts["91-180天"] == 1
    assert rp["total"]["amount"] == 20100.0
    egypt = next(g for g in rp["by_office"] if g["name"] == "埃及")
    assert egypt["expired"] == 1 and egypt["within_180"] == 1 and egypt["nearest"] == "2026-10-20"
    assert rp["by_month"][0]["name"] == "2026-10" and rp["by_month"][0]["count"] == 2


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", str(tmp_path))
    import app as app_module
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_end_to_end_dryrun(client):
    content = make_xlsx([LEGACY_HEADER, ["埃及", "客户A", "合同A", "2026/11/01", "原厂", "C1", 50000, 180, ""]])
    res = client.post("/api/upload", data={"file": (io.BytesIO(content), "data.xlsx")})
    assert res.status_code == 200
    records = res.get_json()["records"]

    assert client.post("/api/settings", json={"mailer": "dryrun"}).status_code == 200
    assert client.post("/api/settings", json={"subject_template": "{0}"}).status_code == 400
    client.post("/api/recipients", json={"office": {"埃及": "a@x.com"}, "contract": {}})

    items = client.post("/api/plan", json={"records": records}).get_json()["items"]
    assert items[0]["to"] == ["a@x.com"] and items[0]["action"] == "now"

    results = client.post("/api/send", json={"items": items}).get_json()["results"]
    assert results[0]["status"] == "dryrun"
    assert client.get("/api/log").get_json()["log"][0]["contract_no"] == "C1"
    # 模拟发送不计入“已发送”，真实发送前不会被去重
    assert store.sent_keys() == set()
