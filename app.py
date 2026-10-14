"""过保提醒 HTML 服务：上传过保数据 -> 分析报告 -> 填写收件人 -> 批量发送提醒邮件。

启动：python app.py，然后浏览器打开 http://127.0.0.1:5000
"""
import datetime as dt
import os
import threading
import webbrowser

from flask import Flask, jsonify, request, send_from_directory

from reminder import analysis, mailer, parser, planner, store

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
app.json.ensure_ascii = False

_send_lock = threading.Lock()


def _bad_request(message):
    return jsonify({"error": message}), 400


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.post("/api/upload")
def upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return _bad_request("请选择文件")
    try:
        records, warnings = parser.parse_file(f.filename, f.read())
    except Exception as e:
        return _bad_request(f"文件解析失败：{e}")
    return jsonify({"filename": f.filename, "records": records, "warnings": warnings,
                    "report": analysis.analyze(records)})


@app.get("/api/settings")
def get_settings():
    return jsonify(store.load_settings())


@app.post("/api/settings")
def post_settings():
    values = request.get_json(force=True)
    sample = {"office": "示例代表处", "customer": "示例客户", "contract_name": "示例合同",
              "expiry": "2030-01-01", "service_type": "原厂维保", "contract_no": "C001",
              "amount": 123456.0, "remind_days": 180, "emails": []}
    try:
        planner.render(sample, {**store.load_settings(), **values}, dt.date(2029, 7, 5), 100)
    except (ValueError, IndexError, AttributeError, KeyError) as e:
        return _bad_request(f"邮件模板格式有误：{e}（占位符需写成 {{字段名}}，大括号本身请写成 {{{{ }}}}）")
    return jsonify(store.save_settings(values))


@app.get("/api/recipients")
def get_recipients():
    return jsonify(store.load_recipients())


@app.post("/api/recipients")
def post_recipients():
    return jsonify(store.save_recipients(request.get_json(force=True)))


@app.post("/api/plan")
def make_plan():
    records = request.get_json(force=True).get("records", [])
    items = planner.plan(records, store.load_settings(), store.load_recipients(), store.sent_keys())
    return jsonify({"items": items})


@app.post("/api/send")
def send():
    items = request.get_json(force=True).get("items", [])
    if not items:
        return _bad_request("没有选中要发送的邮件")
    if not _send_lock.acquire(blocking=False):
        return _bad_request("正在发送中，请等待当前批次完成")
    settings = store.load_settings()
    results = []
    try:
        try:
            with mailer.create(settings) as m:
                for item in items:
                    send_at = item.get("send_at") if item.get("action") == "defer" else None
                    entry = {k: item.get(k, "") for k in ("key", "contract_no", "customer", "action")}
                    entry.update(to=";".join(item["to"]), cc=";".join(item.get("cc", [])),
                                 send_at=send_at or "", mailer=m.name)
                    if send_at and not m.supports_defer:
                        entry.update(status="skipped", error="当前发信方式不支持定时，请到提醒日期后再发送")
                    else:
                        try:
                            m.send(item["to"], item.get("cc", []), item["subject"], item["body"], send_at)
                            entry["status"] = "dryrun" if m.name == "dryrun" else "ok"
                        except Exception as e:
                            entry.update(status="failed", error=str(e))
                    results.append(entry)
        except mailer.MailerError as e:
            return _bad_request(str(e))
        finally:
            store.append_log(results)
    finally:
        _send_lock.release()
    return jsonify({"results": results})


@app.get("/api/log")
def get_log():
    return jsonify({"log": list(reversed(store.read_log()))[:500]})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    # 只监听本机，避免同网段其他人访问到发信接口
    app.run(host="127.0.0.1", port=port, debug=False)
