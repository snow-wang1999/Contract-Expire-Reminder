"use strict";

const state = { rawFile: null, records: [], report: null, funnel: null, source: "", plan: [], settings: null };

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

function setupDrop(zoneSel, inputSel, handler) {
  const zone = $(zoneSel);
  $(inputSel).addEventListener("change", (e) => { if (e.target.files[0]) handler(e.target.files[0]); e.target.value = ""; });
  zone.addEventListener("dragover", (e) => { e.preventDefault(); zone.classList.add("over"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("over"));
  zone.addEventListener("drop", (e) => { e.preventDefault(); zone.classList.remove("over"); if (e.dataTransfer.files[0]) handler(e.dataTransfer.files[0]); });
}

function warningsHtml(list) {
  if (!list.length) return "";
  return `<details class="warn" ${list.length <= 5 ? "open" : ""}><summary>${list.length} 条提示</summary><ul>${list.map((w) => `<li>${esc(w)}</li>`).join("")}</ul></details>`;
}

function setRecords(records, report, source) {
  Object.assign(state, { records, report, source, plan: [] });
  renderReport();
  $("#planTable").innerHTML = `<p class="empty">点击“生成提醒计划”</p>`;
  $("#planSummary").textContent = "";
  updateSendBtn();
}

/* ---------- ① 导入原始数据 ---------- */
async function importRaw(file) {
  state.rawFile = file;
  const fd = new FormData();
  fd.append("file", file);
  fd.append("start", $("#optStart").value);
  fd.append("end", $("#optEnd").value);
  fd.append("min_amount", $("#optMin").value);
  fd.append("include_eos", $("#optEos").checked);
  fd.append("include_no_expand", $("#optNoExpand").checked);
  fd.append("include_dc_energy", $("#optDc").checked);
  fd.append("mode", currentMode());
  fd.append("channel_non_key_only", $("#optNonKey").checked);
  $("#rawResult").innerHTML = `<p class="muted">正在处理 ${esc(file.name)} …</p>`;
  try {
    const data = await api("/api/raw", fd);
    state.funnel = data.funnel;
    setRecords(data.records, data.report, `${data.filename}（原始数据）`);
    const f = data.funnel;
    const prefilled = data.records.filter((r) => r.emails.length).length;
    $("#rawResult").innerHTML = `
      <p class="ok">已处理 <b>${esc(data.filename)}</b>：得到 <b>${f.records}</b> 条需要提醒的合同（过保 ${esc(f.period.start)} ~ ${esc(f.period.end)}，合计目录价 &gt; ${money(f.period.min_amount)}）。${prefilled ? `其中 ${prefilled} 条已按客户带出上次填写的邮箱。` : ""}</p>
      ${funnelHtml(f)}${warningsHtml(data.warnings)}
      <div class="toolbar"><button onclick="showTab('report')">查看分析报告 →</button>
      <button class="secondary" onclick="location.href='/api/template'">下载待填写名单 (Excel)</button>
      <span class="muted small">修改上面的参数后，可点击 <button class="link" id="rerun">按新参数重新整理</button></span></div>`;
    $("#rerun").addEventListener("click", () => importRaw(state.rawFile));
  } catch (e) {
    $("#rawResult").innerHTML = `<p class="err">${esc(e.message)}</p>`;
  }
}
setupDrop("#rawDrop", "#rawInput", importRaw);

function currentMode() {
  return document.querySelector("input[name=mode]:checked").value;
}

function updateModeUi() {
  const channel = currentMode() === "channel";
  $("#channelOpt").hidden = !channel;
  $("#modeHint").textContent = channel
    ? "按签约客户、二代分组排列，收件人填写总代或二代的联系人；邮件不含金额和内部信息，默认英文。"
    : "按客户分类（卓越 > 战略 > 核心 > 价值 > 商业）排列，同一客户相邻；默认中文。";
}
document.querySelectorAll("input[name=mode]").forEach((r) => r.addEventListener("change", updateModeUi));
updateModeUi();

const isChannel = () => state.records.some((r) => r.mode === "channel");
const groupOf = (r) => (r.mode === "channel" ? `${r.signer}|${r.tier2}` : r.customer);

// 同一组（客户 / 签约客户+二代）相同底色
function bandClasses(records) {
  let band = false, last;
  return records.map((r) => { if (groupOf(r) !== last) { band = !band; last = groupOf(r); } return band ? "band" : ""; });
}

function funnelHtml(f) {
  const rows = [
    ["原始数据行数", f.rows, "", true],
    ["过保时间不在时间段内", -f.out_of_period, ""],
    ["已 EOS 设备", -f.eos, f.period.include_eos ? "（已选择包含）" : ""],
    ["资产状态为不再拓展", -f.no_expand, f.period.include_no_expand ? "（已选择包含）" : ""],
    ["数据中心能源及关键供电", -f.dc_energy, f.period.include_dc_energy ? "（已选择包含）" : ""],
    ["卓越 / 战略 / 核心客户", -(f.key_account || 0), ""],
    ["缺少合同号或日期", -f.bad_row, ""],
    ["按 合同号+过保时间+服务类型 合并后", f.groups, "条", true],
    [`合计目录价未超过 ${money(f.period.min_amount)}`, -f.below_min, ""],
    ["最终需要提醒", f.records, "条", true],
  ];
  return `<table class="data funnel"><tbody>${rows.filter(([, v, , always]) => always || v !== 0).map(([k, v, note]) =>
    `<tr class="${k.startsWith("最终") ? "strong" : ""}"><td>${esc(k)}</td><td class="num">${v < 0 ? `−${-v}` : v}</td><td class="muted">${esc(note)}</td></tr>`).join("")}</tbody></table>`;
}

/* ---------- ② 报告 ---------- */
function bars(rows) {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return `<table class="bars">${rows.map((r) => `<tr>
    <th>${esc(r.name)}</th>
    <td class="barcell"><span class="bar" style="width:${(r.count / max) * 100}%"></span></td>
    <td class="num">${r.count}</td><td class="num">${money(r.amount)}</td></tr>`).join("")}</table>`;
}

function groupTable(rows, title = "名称") {
  return `<table class="data"><thead><tr><th>${title}</th><th class="num">提醒条数</th><th class="num">目录价合计</th><th>最早过保</th></tr></thead><tbody>
    ${rows.map((g) => `<tr><td>${esc(g.name)}</td><td class="num">${g.count}</td><td class="num">${money(g.amount)}</td><td>${esc(g.nearest || "-")}</td></tr>`).join("")}
    </tbody></table>`;
}

function detailHead() {
  return `<tr>${isChannel() ? "<th>签约客户</th><th>二代</th>" : ""}<th>代表处</th><th>客户分类</th><th>最终客户</th><th>合同名称</th><th>过保时间</th><th>维保类型</th><th>合同号</th><th class="num">金额</th><th>邮箱名单</th></tr>`;
}

function detailRows(records) {
  const bands = bandClasses(records), channel = isChannel();
  return records.map((r, i) => `<tr class="${bands[i]}">${channel ? `<td>${esc(r.signer)}</td><td>${esc(r.tier2)}</td>` : ""}
    <td>${esc(r.office)}</td><td class="small">${esc(r.customer_class)}</td><td>${esc(r.customer)}</td><td>${esc(r.contract_name)}</td>
    <td class="nowrap">${esc(r.expiry)}</td><td>${esc(r.service_type)}</td><td class="nowrap">${esc(r.contract_no)}</td><td class="num">${money(r.amount)}</td>
    <td class="small">${r.emails.length ? esc(r.emails.join("; ")) : '<span class="muted">待填写</span>'}</td></tr>`).join("");
}

function renderReport() {
  const rp = state.report;
  if (!rp) return;
  const types = rp.by_type.map((t) => `${esc(t.name)} ${t.count}`).join(" · ");
  $("#reportMeta").textContent = `数据：${state.source} · 统计日期：${rp.today}`;
  $("#report").innerHTML = `
    <div class="kpis">
      <div class="kpi"><span>需要提醒</span><b>${rp.total.count}</b><small>${rp.total.offices} 个代表处 · ${rp.total.customers} 个客户</small></div>
      <div class="kpi"><span>目录价合计</span><b>${money(rp.total.amount)}</b></div>
      <div class="kpi"><span>按维保类型</span><b class="kpi-sm">${types || "-"}</b></div>
      <div class="kpi warnk"><span>待填写邮箱</span><b>${state.records.filter((r) => !r.emails.length).length}</b></div>
    </div>
    ${state.funnel && state.source.endsWith("（原始数据）") ? `<div class="card"><h2>筛选过程</h2>${funnelHtml(state.funnel)}</div>` : ""}
    <div class="cols">
      <div class="card"><h2>按过保月份</h2>${bars(rp.by_month)}</div>
      <div class="card"><h2>按维保类型</h2>${bars(rp.by_type)}</div>
    </div>
    <div class="cols">
      <div class="card"><h2>按客户分类</h2>${bars(rp.by_class)}</div>
      <div class="card"><h2>按代表处</h2>${groupTable(rp.by_office, "代表处")}</div>
    </div>
    <div class="cols">
      ${rp.by_signer.length ? `<div class="card"><h2>按签约客户（总代）</h2>${groupTable(rp.by_signer, "签约客户")}</div>` : ""}
      <div class="card"><h2>目录价前 10 客户</h2>${groupTable(rp.by_customer, "最终客户")}</div>
    </div>
    <div class="card"><h2>${isChannel() ? "渠道续保通知名单" : "提醒名单"}（过保目录价 &gt; ${money(state.funnel?.period.min_amount ?? 20000)}）</h2>
      <div class="toolbar noprint"><input type="search" id="detailFilter" placeholder="搜索客户 / 签约客户 / 合同 / 代表处"></div>
      <table class="data"><thead>${detailHead()}</thead>
      <tbody id="detailBody">${detailRows(rp.records)}</tbody></table></div>`;
  $("#detailFilter").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    $("#detailBody").innerHTML = detailRows(rp.records.filter((r) => !q || [r.customer, r.contract_name, r.contract_no, r.office, r.signer, r.tier2].join(" ").toLowerCase().includes(q)));
  });
}

$("#downloadTemplate").addEventListener("click", () => {
  if (!state.funnel) return alert("请先在第①步导入原始数据");
  location.href = "/api/template";
});

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

/* ---------- ③ 上传已填写名单 ---------- */
async function uploadFilled(file) {
  const fd = new FormData();
  fd.append("file", file);
  $("#fillResult").innerHTML = `<p class="muted">正在读取 ${esc(file.name)} …</p>`;
  try {
    const data = await api("/api/upload", fd);
    setRecords(data.records, data.report, data.filename);
    const filled = data.records.filter((r) => r.emails.length).length;
    $("#fillResult").innerHTML = `<p class="ok">已读取 <b>${esc(data.filename)}</b>：${data.records.length} 条提醒，已填写邮箱 <b>${filled}</b> 条。</p>
      ${warningsHtml(data.warnings)}<div class="toolbar"><button onclick="showTab('send')">下一步：提醒计划 →</button></div>`;
    renderFillTable();
  } catch (e) {
    $("#fillResult").innerHTML = `<p class="err">${esc(e.message)}</p>`;
  }
}
setupDrop("#fillDrop", "#fillInput", uploadFilled);

function renderFillTable() {
  const bands = bandClasses(state.records), channel = isChannel();
  $("#fillTable").innerHTML = `<p class="muted small">可以在下表直接修改邮箱名单和邮件语言（只对本次发送生效）。同一${channel ? "签约客户 / 二代" : "客户"}的行底色相同。</p>
    <table class="data"><thead><tr>${channel ? "<th>签约客户</th><th>二代</th>" : ""}<th>客户分类</th><th>最终客户</th><th>合同号</th><th>过保时间</th><th>维保类型</th><th class="num">金额</th><th>产品型号</th><th>邮箱名单</th><th>邮件语言</th></tr></thead><tbody>
    ${state.records.map((r, i) => `<tr class="${bands[i]}">${channel ? `<td>${esc(r.signer)}</td><td>${esc(r.tier2)}</td>` : ""}<td class="small">${esc(r.customer_class)}</td><td>${esc(r.customer)}</td><td class="nowrap">${esc(r.contract_no)}</td><td class="nowrap">${esc(r.expiry)}</td><td>${esc(r.service_type)}</td>
      <td class="num">${money(r.amount)}</td><td class="small">${(r.product_lines || []).map(esc).join("<br>") || "-"}</td>
      <td><input class="wide ${r.emails.length ? "" : "missing"}" data-rec="${i}" value="${esc(r.emails.join("; "))}" placeholder="未填写，不会发送"></td>
      <td><select data-lang="${i}"><option value="zh" ${r.lang === "en" ? "" : "selected"}>中文</option><option value="en" ${r.lang === "en" ? "selected" : ""}>English</option></select></td></tr>`).join("")}
    </tbody></table>`;
}
$("#fillTable").addEventListener("change", (e) => {
  if (e.target.dataset.lang !== undefined) state.records[+e.target.dataset.lang].lang = e.target.value;
});
$("#fillTable").addEventListener("input", (e) => {
  const i = e.target.dataset.rec;
  if (i === undefined) return;
  state.records[+i].emails = e.target.value.split(/[;；,，\n]+/).map((s) => s.trim()).filter(Boolean);
  e.target.classList.toggle("missing", !state.records[+i].emails.length);
});

/* ---------- ④ 计划与发送 ---------- */
const KIND_TEXT = { email: "邮件", calendar: "日历邀请" };
const ACTION_TEXT = { now: "立即", defer: "定时", skip: "跳过" };

function planOptions() {
  const opts = {};
  document.querySelectorAll("[data-opt]").forEach((c) => { opts[c.dataset.opt] = c.checked; });
  opts.past_nodes = document.querySelector("input[name=pastNodes]:checked").value;
  return opts;
}

$("#buildPlan").addEventListener("click", async () => {
  if (!state.records.length) return alert("请先导入数据并上传收件人名单");
  const opts = planOptions();
  if (!["m6", "m3", "m1", "immediate", "expiry_calendar"].some((k) => opts[k])) return alert("请至少选择一种提醒频率");
  try {
    state.plan = (await api("/api/plan", { records: state.records, options: opts })).items;
    renderPlan();
  } catch (e) { alert(e.message); }
});

function renderPlan() {
  const p = state.plan;
  const count = (f) => p.filter(f).length;
  $("#planSummary").textContent = `共 ${p.length} 项：立即 ${count((i) => i.action === "now")} · 定时 ${count((i) => i.action === "defer")} · 跳过 ${count((i) => i.action === "skip")}（其中未填收件人 ${count((i) => i.reason === "未填写收件人")}，之前已发送 ${count((i) => i.already_sent)}）`;
  const hide = $("#hideSkipped").checked;
  const rows = p.map((i, idx) => ({ i, idx })).filter(({ i }) => !hide || i.result || (i.action !== "skip" && !i.already_sent));
  $("#planTable").innerHTML = rows.length ? `<table class="data"><thead><tr><th></th><th>合同号</th><th>最终客户</th><th>维保类型</th><th>过保时间</th><th class="num">金额</th><th>内容</th><th>发送</th><th>收件人</th><th>结果</th><th></th></tr></thead><tbody>
    ${rows.map(({ i, idx }) => `<tr class="${i.action === "skip" || i.already_sent ? "dim" : ""}">
      <td><input type="checkbox" data-idx="${idx}" ${i.selected ? "checked" : ""} ${i.action === "skip" ? "disabled" : ""}></td>
      <td class="nowrap">${esc(i.contract_no)}</td><td>${esc(i.customer)}<div class="small muted">${esc([i.customer_class, i.mode === "channel" ? `渠道：${i.tier2 || i.signer}` : ""].filter(Boolean).join(" · "))}</div></td><td>${esc(i.service_type)}</td><td class="nowrap">${esc(i.expiry)}</td><td class="num">${money(i.amount)}</td>
      <td class="nowrap">${KIND_TEXT[i.kind]} <span class="pill">${i.lang === "en" ? "EN" : "中"}</span><div class="small muted">${esc(i.node_label)}</div></td>
      <td><span class="pill a-${i.action}">${ACTION_TEXT[i.action]}</span><div class="small muted">${esc(i.send_at ? i.send_at.replace("T", " ") : i.reason)}</div></td>
      <td class="small">${esc(i.to.join("; ")) || '<span class="err">未填写</span>'}</td>
      <td class="small">${resultHtml(i)}</td>
      <td class="nowrap"><button class="link" data-preview="${idx}">预览</button></td></tr>`).join("")}
    </tbody></table>` : `<p class="empty">没有可发送的提醒${hide ? "（已隐藏跳过项）" : ""}</p>`;
  updateSendBtn();
}
$("#hideSkipped").addEventListener("change", () => { if (state.plan.length) renderPlan(); });

const RESULT_TEXT = { ok: '<span class="ok">✔ 成功</span>', dryrun: '<span class="muted">模拟成功</span>', skipped: '<span class="muted">未发送</span>', failed: '<span class="err">✘ 失败</span>' };

function resultHtml(i) {
  if (i.result) return `${RESULT_TEXT[i.result.status]}${i.result.error ? `<div class="err small">${esc(i.result.error)}</div>` : ""}`;
  return i.already_sent ? '<span class="muted">之前已发送</span>' : "";
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
  $("#previewTo").textContent = `收件人：${i.to.join("; ") || "（未填写）"}${i.cc.length ? `　抄送：${i.cc.join("; ")}` : ""}　${i.send_at ? `定时：${i.send_at.replace("T", " ")}` : i.kind === "calendar" ? `日程日期：${i.date}（全天）` : "立即发送"}`;
  const isEmail = i.kind === "email";
  $("#previewFrame").hidden = !isEmail;
  $("#previewText").hidden = isEmail;
  if (isEmail) $("#previewFrame").srcdoc = i.body; else $("#previewText").textContent = i.body;
  $("#previewDialog").showModal();
});
$("#selectAll").addEventListener("click", () => { state.plan.forEach((i) => { i.selected = i.action !== "skip" && !i.already_sent; }); renderPlan(); });
$("#selectNone").addEventListener("click", () => { state.plan.forEach((i) => { i.selected = false; }); renderPlan(); });

$("#sendBtn").addEventListener("click", async () => {
  const chosen = state.plan.map((i, idx) => ({ ...i, idx })).filter((i) => i.selected);
  if (!chosen.length) return;
  const mailerName = $("#mailerBadge").textContent;
  const n = (f) => chosen.filter(f).length;
  if (!confirm(`确定通过【${mailerName}】发出以下内容吗？\n立即邮件 ${n((i) => i.kind === "email" && i.action === "now")} 封\n定时邮件 ${n((i) => i.action === "defer")} 封\n日历邀请 ${n((i) => i.kind === "calendar")} 个`)) return;
  $("#sendBtn").disabled = true;
  $("#sendBtn").textContent = "发送中…";
  try {
    const { results } = await api("/api/send", { items: chosen });
    results.forEach((r, k) => {
      const item = state.plan[chosen[k].idx];
      item.result = r;
      if (r.status === "ok") { item.already_sent = true; item.selected = false; }
    });
    renderPlan();
    const ok = results.filter((r) => r.status === "ok" || r.status === "dryrun").length;
    alert(`完成：成功 ${ok} / ${results.length}${ok < results.length ? "\n失败或未发送的项目请查看“结果”列" : ""}`);
  } catch (e) {
    alert(e.message);
    updateSendBtn();
  }
});

/* ---------- 记录 ---------- */
async function loadLog() {
  const { log } = await api("/api/log");
  const statusText = { ok: "成功", dryrun: "模拟", skipped: "未发送", failed: "失败" };
  $("#logTable").innerHTML = log.length ? `<table class="data"><thead><tr><th>时间</th><th>合同号</th><th>客户</th><th>过保时间</th><th>内容</th><th>方式</th><th>定时</th><th>收件人</th><th>发信</th><th>状态</th><th>错误</th></tr></thead><tbody>
    ${log.map((r) => `<tr><td>${esc(r.time)}</td><td>${esc(r.contract_no)}</td><td>${esc(r.customer)}</td><td>${esc(r.expiry)}</td>
      <td>${esc(KIND_TEXT[r.kind] || r.kind)} <span class="muted small">${esc(r.node)}</span></td><td>${esc(ACTION_TEXT[r.action] || r.action)}</td><td>${esc(r.send_at)}</td>
      <td class="small">${esc(r.to)}</td><td>${esc(r.mailer)}</td>
      <td class="${r.status === "failed" ? "err" : ""}">${esc(statusText[r.status] || r.status)}</td><td class="small err">${esc(r.error)}</td></tr>`).join("")}
    </tbody></table>` : `<p class="empty">暂无记录</p>`;
}
$("#reloadLog").addEventListener("click", loadLog);

/* ---------- 设置 ---------- */
const MAILER_NAME = { outlook: "Outlook", smtp: "SMTP", dryrun: "模拟发送" };

function fillSettings(s) {
  state.settings = s;
  for (const el of $("#settingsForm").elements) {
    if (!el.name) continue;
    const [a, b] = el.name.split(".");
    const v = b ? s[a][b] : s[a];
    if (el.type === "checkbox") el.checked = !!v; else el.value = v ?? "";
  }
  $("#mailerBadge").textContent = MAILER_NAME[s.mailer] || s.mailer;
  $("#mailerBadge").className = `badge ${s.mailer === "dryrun" ? "badge-dry" : ""}`;
  $("#sendHourText").textContent = s.send_hour;
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
    state.plan = [];
    $("#planTable").innerHTML = `<p class="empty">设置已更改，请重新生成提醒计划</p>`;
    updateSendBtn();
  } catch (err) { $("#settingsStatus").textContent = err.message; }
});

(async function init() {
  try {
    const [settings, defaults] = await Promise.all([api("/api/settings"), api("/api/defaults")]);
    fillSettings(settings);
    $("#optStart").value = defaults.start;
    $("#optEnd").value = defaults.end;
    $("#optMin").value = defaults.raw.min_amount;
    $("#optEos").checked = defaults.raw.include_eos;
    $("#optNoExpand").checked = defaults.raw.include_no_expand;
    $("#optDc").checked = defaults.raw.include_dc_energy;
    document.querySelectorAll("[data-opt]").forEach((c) => { c.checked = !!defaults.plan[c.dataset.opt]; });
  } catch (e) { alert(`无法连接服务：${e.message}`); }
})();
