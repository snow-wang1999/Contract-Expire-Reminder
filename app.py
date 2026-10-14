"""过保提醒 HTML 服务。

① 拖入系统导出的原始续保数据，选择筛选参数 → ② 查看分析报告，下载待填写名单
③ 填写邮箱名单后上传 → ④ 选择提醒频率，预览并批量发送（Outlook 定时邮件 / 日历邀请）

启动：python app.py，然后浏览器打开 http://127.0.0.1:5000
"""
import io
import os
import threading
import urllib.parse
import webbrowser

from flask import Flask, jsonify, request, send_file, send_from_directory

from reminder import analysis, mailer, parser, planner, raw, store, workbook

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.json.ensure_ascii = False

_send_lock = threading.Lock()
_last_import = {}   # 最近一次原始数据整理结果，用于下载待填写名单


def _bad_request(message):
    return jsonify({"error": message}), 400


def _read_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        raise ValueError("请选择文件")
    rows = parser.read_rows(f.filename, f.read())
    if not rows:
        raise ValueError("文件为空")
    return f.filename, rows


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/defaults")
def defaults():
    start, end = raw.default_period()
    return jsonify({"start": start.isoformat(), "end": end.isoformat(), "raw": raw.DEFAULT_OPTIONS,
                    "plan": planner.DEFAULT_OPTIONS})


@app.post("/api/raw")
def import_raw():
    """原始导出数据 → 筛选、合并 → 提醒清单。"""
    try:
        filename, rows = _read_upload()
        if not raw.is_raw_export(rows[0]):
            return _bad_request("这不是系统导出的原始续保数据（缺少“当前合同号/服务结束/目录价”列）。"
                                "已填好邮箱的提醒名单请在第③步上传。")
        form = request.form
        options = {"start": form.get("start"), "end": form.get("end"),
                   "include_eos": form.get("include_eos") == "true",
                   "include_no_expand": form.get("include_no_expand") == "true",
                   "include_dc_energy": form.get("include_dc_energy") == "true",
                   "min_amount": float(form.get("min_amount") or raw.DEFAULT_OPTIONS["min_amount"]),
                   "mode": form.get("mode") or "customer",
                   "channel_non_key_only": form.get("channel_non_key_only", "true") == "true"}
        records, funnel, excluded, warnings = raw.transform(rows, options)
    except Exception as e:
        return _bad_request(f"原始数据处理失败：{e}")

    # 带出上次填写的邮箱名单和语言（客户通知按最终客户，渠道通知按签约客户+二代）
    memory = store.load_recipients()
    for r in records:
        kind, key = store.memory_key(r)
        if key in memory[kind]:
            r["emails"] = parser.split_emails(memory[kind][key])
            r["lang"] = memory["lang" if kind == "customer" else "channel_lang"].get(key, r["lang"])

    _last_import.clear()
    _last_import.update(records=records, excluded=excluded, funnel=funnel)
    return jsonify({"filename": filename, "records": records, "funnel": funnel, "warnings": warnings,
                    "excluded": len(excluded), "report": analysis.analyze(records, period=funnel["period"])})


@app.get("/api/template")
def download_template():
    if not _last_import:
        return _bad_request("请先导入原始数据")
    period = _last_import["funnel"]["period"]
    content = workbook.build(_last_import["records"], _last_import["excluded"], _last_import["funnel"])
    kind = "渠道" if period.get("mode") == "channel" else "客户"
    name = f"过保提醒名单_{kind}_待填写_{period['start']}_{period['end']}.xlsx"
    resp = send_file(io.BytesIO(content), as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp.headers["Content-Disposition"] = (f"attachment; filename=\"reminder_list_{period.get('mode', 'customer')}_{period['start']}_{period['end']}.xlsx\"; "
                                           f"filename*=UTF-8''{urllib.parse.quote(name)}")
    return resp


@app.post("/api/upload")
def upload_filled():
    """上传已填写邮箱名单的提醒名单（也兼容旧版“维保日历数据.xlsx”）。"""
    try:
        filename, rows = _read_upload()
        if raw.is_raw_export(rows[0]):
            return _bad_request("这是系统导出的原始数据，请在第①步导入并下载待填写名单。")
        records, warnings = parser.parse_rows(rows)
    except Exception as e:
        return _bad_request(f"文件解析失败：{e}")
    missing = sum(1 for r in records if not r["emails"])
    if missing:
        warnings.insert(0, f"有 {missing} 条未填写邮箱名单，这些提醒不会发送")
    store.remember_recipients(records)
    period = _last_import.get("funnel", {}).get("period")
    return jsonify({"filename": filename, "records": records, "warnings": warnings,
                    "report": analysis.analyze(records, period=period)})


@app.get("/api/settings")
def get_settings():
    return jsonify(store.load_settings())


@app.post("/api/settings")
def post_settings():
    return jsonify(store.save_settings(request.get_json(force=True)))


@app.post("/api/plan")
def make_plan():
    body = request.get_json(force=True)
    items = planner.plan(body.get("records", []), store.load_settings(), store.sent_keys(), body.get("options"))
    return jsonify({"items": items})


@app.post("/api/send")
def send():
    items = request.get_json(force=True).get("items", [])
    if not items:
        return _bad_request("没有选中要发送的提醒")
    if not _send_lock.acquire(blocking=False):
        return _bad_request("正在发送中，请等待当前批次完成")
    settings = store.load_settings()
    results = []
    try:
        try:
            with mailer.create(settings) as m:
                for item in items:
                    send_at = item.get("send_at") if item.get("action") == "defer" else None
                    entry = {k: item.get(k, "") for k in ("kind", "node", "contract_no", "customer", "expiry", "action")}
                    entry.update(key=",".join(item.get("keys", [])), to=";".join(item["to"]),
                                 cc=";".join(item.get("cc", [])), send_at=send_at or "", mailer=m.name)
                    if item.get("kind") == "calendar" and not m.supports_calendar:
                        entry.update(status="skipped", error="当前发信方式不支持日历邀请，请使用 Outlook")
                    elif send_at and not m.supports_defer:
                        entry.update(status="skipped", error="当前发信方式不支持定时，请到提醒日期后再发送")
                    else:
                        try:
                            if item.get("kind") == "calendar":
                                m.invite(item["to"], item.get("cc", []), item["subject"], item["body"], item["date"])
                            else:
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


def _free_port(preferred):
    """优先用指定端口，被占用时依次往后找。"""
    import socket
    for port in range(preferred, preferred + 20):
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


if __name__ == "__main__":
    port = _free_port(int(os.environ.get("PORT", 5000)))
    url = f"http://127.0.0.1:{port}"
    print(f"过保提醒服务已启动：{url}\n使用期间请不要关闭本窗口。", flush=True)
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    # 只监听本机，避免同网段其他人访问到发信接口
    try:
        from waitress import serve   # 正式的 WSGI 服务器（纯 Python，随离线包附带）
    except ImportError:
        app.run(host="127.0.0.1", port=port, debug=False)
    else:
        serve(app, host="127.0.0.1", port=port, threads=4, _quiet=True)
