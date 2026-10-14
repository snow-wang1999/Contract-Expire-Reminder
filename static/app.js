"use strict";

const state = { records: [], report: null, filename: "", recipients: { office: {}, contract: {} }, plan: [], settings: null };

const $ = (sel) => document.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function money(n) {
  if (n == null) return "-";
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e4) return `$${(n / 1e4).toFixed(1)}W`;
  return `$${Math.round(n).toLocaleString()}`;
}

async function api(path, body) {
  const opts = body instanceof FormData ? { method: "POST", body }
    : body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {};
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({ error: `服务器错误 (${res.status})` }));
  if (!res.ok) throw new Error(data.error || `请求失败 (${res.status})`);
  return data;
}

function showTab(name) {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((s) => s.classList.toggle("active", s.id === `tab-${name}`));
  if (name === "log") loadLog();
}
$("#tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) showTab(e.target.dataset.tab); });

/* ---------- ① 导入 ---------- */
async function upload(file) {
  const fd = new FormData();
  fd.append("file", file);
  $("#importResult").innerHTML = `<p class="muted">正在解析 ${esc(file.name)} …</p>`;
  try {
    const data = await api("/api/upload", fd);
    Object.assign(state, { records: data.records, report: data.report, filename: data.filename, plan: [] });
    const warn = data.warnings.length
      ? `<details class="warn" ${data.warnings.length <= 5 ? "open" : ""}><summary>${data.warnings.length} 条提示</summary><ul>${data.warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></details>` : "";
    $("#importResult").innerHTML = `<p class="ok">已读取 <b>${esc(data.filename)}</b>：有效合同 <b>${data.records.length}</b> 条。</p>${warn}
      <button onclick="showTab('report')">查看分析报告 →</button>`;
    renderReport();
    renderRecipients();
    $("#planTable").innerHTML = `<p class="empty">请在“收件人名单”页保存后生成发送计划</p>`;
  } catch (e) {
    $("#importResult").innerHTML = `<p class="err">${esc(e.message)}</p>`;
  }
}
$("#fileInput").addEventListener("change", (e) => { if (e.target.files[0]) upload(e.target.files[0]); e.target.value = ""; });
const drop = $("#drop");
drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("over"); });
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => { e.preventDefault(); drop.classList.remove("over"); if (e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]); });

/* ---------- ② 报告 ---------- */
function bars(rows, { label = "name", showAmount = true } = {}) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return `<table class="bars">${rows.map((r) => `<tr>
    <th>${esc(r[label])}</th>
    <td class="barcell"><span class="bar" style="width:${(r.count / max) * 100}%"></span></td>
    <td class="num">${r.count}</td>${showAmount ? `<td class="num">${money(r.amount)}</td>` : ""}</tr>`).join("")}</table>`;
}

function groupTable(rows) {
  return `<table class="data"><thead><tr><th>名称</th><th class="num">合同数</th><th class="num">金额</th>
    <th class="num">已过保</th><th class="num">180天内到期</th><th>最近到期</th></tr></thead><tbody>
    ${rows.map((g) => `<tr><td>${esc(g.name)}</td><td class="num">${g.count}</td><td class="num">${money(g.amount)}</td>
      <td class="num">${g.expired || ""}</td><td class="num">${g.within_180 || ""}</td><td>${esc(g.nearest || "-")}</td></tr>`).join("")}
    </tbody></table>`;
}

const BUCKET_CLASS = { "已过保": "b-expired", "30天内": "b-urgent", "31-90天": "b-soon", "91-180天": "b-mid" };

function detailRows(records) {
  return records.map((r) => `<tr><td><span class="pill ${BUCKET_CLASS[r.bucket] || ""}">${esc(r.bucket)}</span></td>
    <td>${esc(r.expiry)}</td><td class="num">${r.days_left}</td><td>${esc(r.office)}</td><td>${esc(r.customer)}</td>
    <td>${esc(r.contract_name)}</td><td>${esc(r.contract_no)}</td><td>${esc(r.service_type)}</td><td class="num">${money(r.amount)}</td></tr>`).join("");
}

function renderReport() {
  const rp = state.report;
  if (!rp) return;
  const b = Object.fromEntries(rp.buckets.map((x) => [x.name, x]));
  const within180 = ["30天内", "31-90天", "91-180天"].reduce((s, k) => s + b[k].count, 0);
  const within180Amt = ["30天内", "31-90天", "91-180天"].reduce((s, k) => s + b[k].amount, 0);
  $("#reportMeta").textContent = `数据：${state.filename} · 统计日期：${rp.today}`;
  $("#report").innerHTML = `
    <div class="kpis">
      <div class="kpi"><span>合同总数</span><b>${rp.total.count}</b><small>${rp.total.offices} 个代表处 · ${rp.total.customers} 个客户</small></div>
      <div class="kpi"><span>合同总金额</span><b>${money(rp.total.amount)}</b></div>
      <div class="kpi alert"><span>已过保</span><b>${b["已过保"].count}</b><small>${money(b["已过保"].amount)}</small></div>
      <div class="kpi warnk"><span>180 天内到期</span><b>${within180}</b><small>${money(within180Amt)}</small></div>
    </div>
    <div class="cols">
      <div class="card"><h2>按到期紧急程度</h2>${bars(rp.buckets)}</div>
      <div class="card"><h2>未来 12 个月到期分布</h2>${bars(rp.by_month)}</div>
    </div>
    <div class="card"><h2>按代表处</h2>${groupTable(rp.by_office)}</div>
    <div class="card"><h2>按维保类型</h2>${groupTable(rp.by_type)}</div>
    <div class="card"><h2>合同明细</h2>
      <div class="toolbar noprint"><select id="bucketFilter"><option value="">全部</option>${rp.buckets.map((x) => `<option>${esc(x.name)}</option>`).join("")}</select>
      <input type="search" id="detailFilter" placeholder="搜索客户 / 合同 / 代表处"></div>
      <table class="data"><thead><tr><th>状态</th><th>过保时间</th><th class="num">剩余天数</th><th>代表处</th><th>最终客户</th><th>合同名称</th><th>合同号</th><th>维保类型</th><th class="num">金额</th></tr></thead>
      <tbody id="detailBody">${detailRows(rp.records)}</tbody></table></div>`;
  const filter = () => {
    const bucket = $("#bucketFilter").value, q = $("#detailFilter").value.trim().toLowerCase();
    $("#detailBody").innerHTML = detailRows(rp.records.filter((r) => (!bucket || r.bucket === bucket)
      && (!q || [r.customer, r.contract_name, r.contract_no, r.office].join(" ").toLowerCase().includes(q))));
  };
  $("#bucketFilter").addEventListener("change", filter);
  $("#detailFilter").addEventListener("input", filter);
}

$("#exportReport").addEventListener("click", async () => {
  if (!state.report) return alert("请先导入数据");
  const css = await (await fetch("/static/style.css")).text();
  const clone = $("#report").cloneNode(true);
  clone.querySelectorAll(".noprint").forEach((n) => n.remove());
  clone.querySelector("#detailBody").innerHTML = detailRows(state.report.records);
  const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>过保分析报告 ${state.report.today}</title>
    <style>${css}</style></head><body><main><h1>过保分析报告</h1><p class="muted">${esc($("#reportMeta").textContent)}</p>${clone.innerHTML}</main></body></html>`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  a.download = `过保分析报告_${state.report.today}.html`;
  a.click();
  URL.revokeObjectURL(a.href);
});

/* ---------- ③ 收件人 ---------- */
function renderRecipients() {
  if (!state.records.length) return;
  const offices = {};
  state.records.forEach((r) => { (offices[r.office] ||= { count: 0, excel: 0 }).count++; if (r.emails.length) offices[r.office].excel++; });
  $("#officeTable").innerHTML = `<table class="data"><thead><tr><th>代表处</th><th class="num">合同数</th><th class="num">Excel已带邮箱</th><th>收件人</th></tr></thead><tbody>
    ${Object.entries(offices).map(([name, o]) => `<tr><td>${esc(name || "（未填写）")}</td><td class="num">${o.count}</td><td class="num">${o.excel}</td>
      <td><input class="wide" data-office="${esc(name)}" value="${esc(state.recipients.office[name] || "")}" placeholder="a@example.com; b@example.com"></td></tr>`).join("")}
    </tbody></table>`;
  renderContractTable();
}

function renderContractTable() {
  const q = $("#contractFilter").value.trim().toLowerCase();
  const rows = state.records.filter((r) => !q || [r.contract_no, r.customer, r.office].join(" ").toLowerCase().includes(q));
  $("#contractTable").innerHTML = `<table class="data"><thead><tr><th>合同号</th><th>最终客户</th><th>代表处</th><th>过保时间</th><th>Excel 邮箱</th><th>单独指定收件人</th></tr></thead><tbody>
    ${rows.map((r) => `<tr><td>${esc(r.contract_no)}</td><td>${esc(r.customer)}</td><td>${esc(r.office)}</td><td>${esc(r.expiry)}</td>
      <td class="small">${esc(r.emails.join("; "))}</td>
      <td><input class="wide" data-contract="${esc(r.contract_no)}" value="${esc(state.recipients.contract[r.contract_no] || "")}"></td></tr>`).join("")}
    </tbody></table>`;
}
$("#contractFilter").addEventListener("input", renderContractTable);

// 输入时即时写回 state，搜索重绘表格也不会丢失已填内容
document.addEventListener("input", (e) => {
  const t = e.target;
  if (t.dataset.office !== undefined) state.recipients.office[t.dataset.office] = t.value;
  if (t.dataset.contract !== undefined) state.recipients.contract[t.dataset.contract] = t.value;
});

$("#saveRecipients").addEventListener("click", async () => {
  try {
    state.recipients = await api("/api/recipients", state.recipients);
    $("#recipientsStatus").textContent = "已保存";
    await buildPlan();
    showTab("send");
  } catch (e) { $("#recipientsStatus").textContent = e.message; }
});

/* ---------- ④ 发送 ---------- */
const ACTION_TEXT = { now: "立即发送", defer: "定时发送", skip: "跳过" };

async function buildPlan() {
  if (!state.records.length) return;
  const data = await api("/api/plan", { records: state.records });
  state.plan = data.items;
  renderPlan();
}

function renderPlan() {
  const p = state.plan;
  const count = (f) => p.filter(f).length;
  $("#planSummary").textContent = `共 ${p.length} 条：立即 ${count((i) => i.action === "now")} · 定时 ${count((i) => i.action === "defer")} · 跳过 ${count((i) => i.action === "skip")} · 已发过 ${count((i) => i.already_sent)}`;
  $("#planTable").innerHTML = `<table class="data"><thead><tr><th></th><th>合同号</th><th>最终客户</th><th>收件人</th><th>过保时间</th><th>提醒日期</th><th>方式</th><th>结果</th><th></th></tr></thead><tbody>
    ${p.map((i, idx) => `<tr class="${i.action === "skip" ? "dim" : ""}">
      <td><input type="checkbox" data-idx="${idx}" ${i.selected ? "checked" : ""} ${i.action === "skip" ? "disabled" : ""}></td>
      <td>${esc(i.contract_no)}</td><td>${esc(i.customer)}</td>
      <td class="small">${esc(i.to.join("; ")) || '<span class="err">未填写</span>'}${i.to_source ? ` <span class="muted">(${esc(i.to_source)})</span>` : ""}</td>
      <td>${esc(i.expiry)}</td><td>${esc(i.remind_date)}</td>
      <td><span class="pill a-${i.action}">${ACTION_TEXT[i.action]}</span><div class="small muted">${esc(i.send_at ? i.send_at.replace("T", " ") : i.reason)}</div></td>
      <td class="small" id="res-${idx}">${i.already_sent ? '<span class="muted">之前已发送</span>' : ""}</td>
      <td><button class="link" data-preview="${idx}">预览</button></td></tr>`).join("")}
    </tbody></table>`;
  updateSendBtn();
}

function updateSendBtn() {
  const n = state.plan.filter((i) => i.selected).length;
  $("#sendBtn").textContent = `发送选中 (${n})`;
  $("#sendBtn").disabled = n === 0;
}

$("#planTable").addEventListener("change", (e) => {
  if (e.target.dataset.idx !== undefined) { state.plan[+e.target.dataset.idx].selected = e.target.checked; updateSendBtn(); }
});
$("#planTable").addEventListener("click", (e) => {
  const idx = e.target.dataset.preview;
  if (idx === undefined) return;
  const i = state.plan[+idx];
  $("#previewSubject").textContent = i.subject;
  $("#previewTo").textContent = `收件人：${i.to.join("; ") || "（未填写）"}${i.cc.length ? `　抄送：${i.cc.join("; ")}` : ""}　${i.send_at ? `定时：${i.send_at.replace("T", " ")}` : ""}`;
  $("#previewBody").textContent = i.body;
  $("#previewDialog").showModal();
});
$("#selectAll").addEventListener("click", () => { state.plan.forEach((i) => { i.selected = i.action !== "skip" && !i.already_sent; }); renderPlan(); });
$("#selectNone").addEventListener("click", () => { state.plan.forEach((i) => { i.selected = false; }); renderPlan(); });
$("#refreshPlan").addEventListener("click", () => buildPlan().catch((e) => alert(e.message)));

$("#sendBtn").addEventListener("click", async () => {
  const chosen = state.plan.map((i, idx) => ({ ...i, idx })).filter((i) => i.selected);
  if (!chosen.length) return;
  const mailerName = $("#mailerBadge").textContent;
  const resent = chosen.filter((i) => i.already_sent).length;
  if (!confirm(`确定通过【${mailerName}】发送 ${chosen.length} 封提醒邮件吗？${resent ? `\n其中 ${resent} 封之前已发送过，将重复发送。` : ""}`)) return;
  $("#sendBtn").disabled = true;
  $("#sendBtn").textContent = "发送中…";
  try {
    const { results } = await api("/api/send", { items: chosen });
    results.forEach((r, k) => {
      const idx = chosen[k].idx;
      const label = { ok: '<span class="ok">✔ 成功</span>', dryrun: '<span class="muted">模拟成功</span>', skipped: '<span class="muted">未发送</span>', failed: '<span class="err">✘ 失败</span>' }[r.status];
      $(`#res-${idx}`).innerHTML = `${label}${r.error ? `<div class="err small">${esc(r.error)}</div>` : ""}`;
      if (r.status === "ok") { state.plan[idx].already_sent = true; state.plan[idx].selected = false; }
    });
    const ok = results.filter((r) => r.status === "ok" || r.status === "dryrun").length;
    alert(`完成：成功 ${ok} / ${results.length}`);
  } catch (e) {
    alert(e.message);
  }
  document.querySelectorAll("#planTable input[type=checkbox]").forEach((c) => { c.checked = state.plan[+c.dataset.idx].selected; });
  updateSendBtn();
});

/* ---------- 记录 ---------- */
async function loadLog() {
  const { log } = await api("/api/log");
  const statusText = { ok: "成功", dryrun: "模拟", skipped: "未发送", failed: "失败" };
  $("#logTable").innerHTML = log.length ? `<table class="data"><thead><tr><th>时间</th><th>合同号</th><th>客户</th><th>收件人</th><th>方式</th><th>定时</th><th>发信</th><th>状态</th><th>错误</th></tr></thead><tbody>
    ${log.map((r) => `<tr><td>${esc(r.time)}</td><td>${esc(r.contract_no)}</td><td>${esc(r.customer)}</td><td class="small">${esc(r.to)}</td>
      <td>${esc(ACTION_TEXT[r.action] || r.action)}</td><td>${esc(r.send_at)}</td><td>${esc(r.mailer)}</td>
      <td class="${r.status === "failed" ? "err" : ""}">${esc(statusText[r.status] || r.status)}</td><td class="small err">${esc(r.error)}</td></tr>`).join("")}
    </tbody></table>` : `<p class="empty">暂无记录</p>`;
}
$("#reloadLog").addEventListener("click", loadLog);

/* ---------- 设置 ---------- */
const MAILER_NAME = { outlook: "Outlook", smtp: "SMTP", dryrun: "模拟发送" };

function fillSettings(s) {
  state.settings = s;
  const form = $("#settingsForm");
  for (const el of form.elements) {
    if (!el.name) continue;
    const [a, b] = el.name.split(".");
    const v = b ? s[a][b] : s[a];
    if (el.type === "checkbox") el.checked = !!v; else el.value = v ?? "";
  }
  $("#mailerBadge").textContent = MAILER_NAME[s.mailer] || s.mailer;
  $("#mailerBadge").className = `badge ${s.mailer === "dryrun" ? "badge-dry" : ""}`;
}

$("#settingsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const values = { smtp: {} };
  for (const el of e.target.elements) {
    if (!el.name) continue;
    const [a, b] = el.name.split(".");
    const v = el.type === "checkbox" ? el.checked : el.type === "number" ? Number(el.value) : el.value;
    if (b) values[a][b] = v; else values[a] = v;
  }
  try {
    fillSettings(await api("/api/settings", values));
    $("#settingsStatus").textContent = "已保存";
    if (state.plan.length) buildPlan();
  } catch (err) { $("#settingsStatus").textContent = err.message; }
});

(async function init() {
  try {
    fillSettings(await api("/api/settings"));
    state.recipients = await api("/api/recipients");
  } catch (e) { alert(`无法连接服务：${e.message}`); }
})();
