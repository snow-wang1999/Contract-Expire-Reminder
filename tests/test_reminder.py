import datetime as dt
import io

import openpyxl
import pytest

from reminder import analysis, parser, planner, raw, store, workbook


def make_xlsx(rows):
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


RAW_HEADER = ["续保单ID", "最终客户名称", "当前合同号", "合同名称", "存量地区部", "存量代表处", "续保产品名称",
              "EOS时间", "服务结束", "资产状态", "产品线LV1", "服务类型", "目录价"]


def raw_row(contract, end, stype="Hi-Care", price=30000, eos="2035-12-31", status="使用中", lv1="数据通信",
            customer="客户A", office="南非代表处", name="合同A", product="S5731"):
    return [None, customer, contract, name, "南部非洲地区部", office, product, eos, end, status, lv1, stype, price]


RAW_ROWS = [
    RAW_HEADER,
    raw_row("C1", "2027-03-31", price=15000, product="P1"),
    raw_row("C1", "2027-03-31", price=8000, product="P2"),          # 与上一行合并：23000 > 2W
    raw_row("C1", "2027-03-31", stype="Co-Care", price=25000),      # 同合同不同服务类型：单独一条
    raw_row("C1", "2027-08-31", price=21000),                       # 同合同不同过保日期：单独一条
    raw_row("C2", "2027-05-01", price=19000),                       # 未超过 2W
    raw_row("C3", "2027-05-01", eos="2027-05-01"),                  # 已 EOS
    raw_row("C4", "2027-05-01", status="不再拓展"),
    raw_row("C5", "2027-05-01", lv1="数据中心能源及关键供电"),
    raw_row("C6", "2026-12-31"),                                    # 不在时间段
    raw_row("C7", "2028-01-01"),
]

TODAY = dt.date(2026, 10, 14)


def test_raw_transform_defaults():
    records, funnel, excluded, warnings = raw.transform(RAW_ROWS, {}, today=TODAY)
    assert funnel["period"]["start"] == "2027-01-01" and funnel["period"]["end"] == "2027-12-31"
    keys = [(r["contract_no"], r["expiry"], r["service_type"], r["amount"]) for r in records]
    assert keys == [("C1", "2027-03-31", "Co-Care", 25000), ("C1", "2027-03-31", "Hi-Care", 23000),
                    ("C1", "2027-08-31", "Hi-Care", 21000)]
    assert [p["product"] for p in records[1]["products"]] == ["P1", "P2"]
    assert records[0]["office"] == "南非代表处" and records[0]["customer"] == "客户A"
    assert {k: funnel[k] for k in ("rows", "out_of_period", "eos", "no_expand", "dc_energy", "below_min", "records")} == \
        {"rows": 10, "out_of_period": 2, "eos": 1, "no_expand": 1, "dc_energy": 1, "below_min": 1, "records": 3}
    assert {e["contract_no"]: e["reason"] for e in excluded}["C3"] == "设备已 EOS"
    assert warnings == []


def test_raw_transform_include_options_and_period():
    records, funnel, _, _ = raw.transform(RAW_ROWS, {
        "start": "2026-12-01", "end": "2028-12-31", "include_eos": True, "include_no_expand": True,
        "include_dc_energy": True, "min_amount": 0}, today=TODAY)
    assert {r["contract_no"] for r in records} == {"C1", "C2", "C3", "C4", "C5", "C6", "C7"}
    with pytest.raises(ValueError):
        raw.transform(RAW_ROWS, {"start": "2027-12-31", "end": "2027-01-01"})


def test_raw_detection():
    assert raw.is_raw_export(RAW_HEADER)
    assert not raw.is_raw_export(["代表处", "最终客户", "合同号", "过保时间"])


def test_workbook_roundtrip():
    records, funnel, excluded, _ = raw.transform(RAW_ROWS, {}, today=TODAY)
    records[0]["emails"] = ["a@x.com"]
    wb = openpyxl.load_workbook(io.BytesIO(workbook.build(records, excluded, funnel)))
    assert wb.sheetnames == ["提醒名单", "填写说明", "产品明细", "已排除", "筛选条件"]
    sheet = wb["提醒名单"]
    sheet.cell(3, workbook.EMAIL_COL).value = "b@x.com；c@x.com"
    buf = io.BytesIO()
    wb.save(buf)
    parsed, warnings = parser.parse_file("filled.xlsx", buf.getvalue())
    assert warnings == []
    assert [(r["contract_no"], r["expiry"], r["service_type"], r["amount"]) for r in parsed] == \
        [(r["contract_no"], r["expiry"], r["service_type"], r["amount"]) for r in records]
    assert parsed[0]["emails"] == ["a@x.com"] and parsed[1]["emails"] == ["b@x.com", "c@x.com"]
    assert parsed[2]["emails"] == []


def test_parse_legacy_format():
    content = make_xlsx([
        ["代表处", "最终客户", "合同名称", "过保时间", "维保类型", "合同号", "金额", "提醒天数", "邮箱名单"],
        ["南非", "客户A", "合同A", dt.datetime(2027, 3, 1), "Hi-Care", "C1", 1500000, 30, "a@x.com; b@x.com"],
        ["南非", "客户B", "合同B", "无效日期", "Hi-Care", "C2", 100, 30, ""],
    ])
    records, warnings = parser.parse_file("维保日历数据.xlsx", content)
    assert [r["contract_no"] for r in records] == ["C1"]
    assert records[0]["emails"] == ["a@x.com", "b@x.com"]
    assert len(warnings) == 1


def test_add_months_clamps_day():
    assert planner.add_months(dt.date(2027, 8, 31), -6) == dt.date(2027, 2, 28)
    assert planner.add_months(dt.date(2027, 1, 15), -3) == dt.date(2026, 10, 15)


def _record(**kw):
    base = {"id": 0, "office": "南非代表处", "customer": "City & Co", "contract_name": "合同A", "expiry": "2027-03-31",
            "service_type": "Hi-Care", "contract_no": "C1", "amount": 46000.0, "emails": ["a@x.com"]}
    return {**base, **kw}


SETTINGS = {**store.DEFAULT_SETTINGS, "cc": "boss@x.com"}
NOW = dt.datetime(2026, 10, 14, 10, 0)


def by_node(items):
    return {(i["kind"], i["node"]): i for i in items}


def test_plan_default_nodes():
    # 过保 2027-03-31：6 个月节点 2026-09-30 已过，3 个月 2026-12-31、1 个月 2027-02-28 定时
    items = by_node(planner.plan([_record()], SETTINGS, set(), None, NOW))
    assert items[("email", "m6")]["action"] == "skip" and "已过" in items[("email", "m6")]["reason"]
    assert items[("email", "m3")]["action"] == "defer" and items[("email", "m3")]["send_at"] == "2026-12-31T09:00"
    assert items[("email", "m1")]["send_at"] == "2027-02-28T09:00"
    m3 = items[("email", "m3")]
    assert m3["subject"] == "City & Co | $4.6W维保过保|续保拓展提醒"
    assert "City &amp; Co" in m3["body"] and "提前3个月提醒" in m3["body"] and "距过保 90 天" in m3["body"]
    assert planner.days_text(-3) == "已过保 3 天"
    assert m3["cc"] == ["boss@x.com"] and m3["selected"]


def test_plan_past_nodes_send_now_merged_with_immediate():
    rec = _record(expiry="2026-12-31")   # 6 个月节点 2026-06-30、3 个月 2026-09-30 已过，1 个月 2026-11-30 未到
    opts = {"m6": True, "m3": True, "m1": True, "immediate": True, "past_nodes": "send_now"}
    items = planner.plan([rec], SETTINGS, set(), opts, NOW)
    now_items = [i for i in items if i["action"] == "now"]
    assert len(now_items) == 1
    assert now_items[0]["keys"] == ["C1|2026-12-31|Hi-Care|m6", "C1|2026-12-31|Hi-Care|m3",
                                    "C1|2026-12-31|Hi-Care|immediate|2026-10-14"]
    assert by_node(items)[("email", "m1")]["action"] == "defer"


def test_plan_dedupe_calendar_and_missing_recipients():
    rec = _record()
    sent = {"C1|2027-03-31|Hi-Care|m3"}
    opts = {"m6": False, "m3": True, "m1": False, "expiry_calendar": True}
    items = by_node(planner.plan([rec], SETTINGS, sent, opts, NOW))
    assert items[("email", "m3")]["already_sent"] and not items[("email", "m3")]["selected"]
    cal = items[("calendar", "calendar")]
    assert cal["action"] == "now" and cal["date"] == "2027-03-31"
    assert cal["subject"] == "【过保】City & Co | $4.6W | Hi-Care" and "合同编号：C1" in cal["body"]

    items = planner.plan([_record(emails=[])], SETTINGS, set(), opts, NOW)
    assert all(i["action"] == "skip" and not i["selected"] for i in items)


def test_analysis_period_months():
    rp = analysis.analyze([_record(), _record(expiry="2027-12-01", customer="B")], TODAY,
                          {"start": "2027-01-01", "end": "2027-12-31"})
    assert [m["name"] for m in rp["by_month"]][:1] == ["2027-01"] and len(rp["by_month"]) == 12
    assert rp["by_month"][2]["count"] == 1 and rp["by_month"][11]["count"] == 1


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", str(tmp_path))
    import app as app_module
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_end_to_end_dryrun(client):
    content = make_xlsx(RAW_ROWS)
    res = client.post("/api/raw", data={"file": (io.BytesIO(content), "raw.xlsx"), "start": "2027-01-01",
                                        "end": "2027-12-31", "min_amount": "20000", "include_eos": "false"})
    assert res.status_code == 200, res.get_json()
    assert res.get_json()["funnel"]["records"] == 3

    # 原始数据传到第③步会被拦下
    assert client.post("/api/upload", data={"file": (io.BytesIO(content), "raw.xlsx")}).status_code == 400

    template = client.get("/api/template")
    assert template.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(template.data))
    for row in range(2, wb["提醒名单"].max_row + 1):
        wb["提醒名单"].cell(row, workbook.EMAIL_COL).value = "a@x.com"
    buf = io.BytesIO()
    wb.save(buf)
    filled = client.post("/api/upload", data={"file": (io.BytesIO(buf.getvalue()), "filled.xlsx")}).get_json()
    assert all(r["emails"] == ["a@x.com"] for r in filled["records"])

    client.post("/api/settings", json={"mailer": "dryrun"})
    opts = {"m6": True, "m3": True, "m1": True, "immediate": True, "expiry_calendar": True}
    items = client.post("/api/plan", json={"records": filled["records"], "options": opts}).get_json()["items"]
    chosen = [i for i in items if i["selected"]]
    assert {i["kind"] for i in chosen} == {"email", "calendar"}
    results = client.post("/api/send", json={"items": chosen}).get_json()["results"]
    assert {r["status"] for r in results} == {"dryrun"}

    # 再次导入原始数据时按客户带出上次的邮箱
    again = client.post("/api/raw", data={"file": (io.BytesIO(content), "raw.xlsx")}).get_json()
    assert again["records"] == [] or all(r["emails"] == ["a@x.com"] for r in again["records"])


def test_product_summary_merges_same_model():
    products = [{"product": "S5735", "qty": 5}, {"product": "AR611", "qty": 1}, {"product": "S5735", "qty": 2},
                {"product": "", "qty": None}]
    assert raw.product_summary(products) == [("S5735", 7), ("AR611", 1), ("（未注明型号）", 0)]
