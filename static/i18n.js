"use strict";
/* 界面中英文切换：以中文原文为键，EN 中为对应英文；带 {参数} 的文本由 t() 填充。
   静态页面元素用 data-i18n（纯文本）或 data-i18n-html（含标签）标记。 */

const EN = {
  // 页面框架
  "过保提醒服务": "Warranty Expiry Reminder",
  "① 导入原始数据": "① Import raw data",
  "② 分析报告": "② Analysis report",
  "③ 上传收件人名单": "③ Upload recipient list",
  "④ 提醒计划与发送": "④ Reminder plan & sending",
  "发送记录": "Send log",
  "设置": "Settings",
  "关闭": "Close",
  "Outlook": "Outlook",
  "SMTP": "SMTP",
  "模拟发送": "Dry run",

  // ① 导入
  "通知模式": "Notification mode",
  "客户通知（发给负责该客户的同事，默认中文）": "Customer notice (to colleagues in charge of the customer, Chinese by default)",
  "渠道续保通知（发给签约客户 / 二代，默认英文）": "Channel renewal notice (to the contracting partner / tier-2 partner, English by default)",
  "只包含非卓越 / 战略 / 核心客户（卓战核客户走客户通知）": "Only non-Premier / Strategic / Core accounts (those go through customer notices)",
  "按签约客户、二代分组排列，收件人填写总代或二代的联系人；同一伙伴的合同合并成一封邮件，不含金额和内部信息，默认英文。":
    "Grouped by contracting partner and tier-2 partner. Fill in the partner contacts; contracts of the same partner (same tier-2) are merged into one email without prices or internal information. English by default.",
  "按客户分类（卓越 > 战略 > 核心 > 价值 > 商业）排列，同一客户相邻；默认中文。":
    "Sorted by account class (Premier > Strategic > Core > Value > Commercial), rows of the same customer kept together. Chinese by default.",
  "筛选参数": "Filters",
  "过保时间从": "Expiry from",
  "到": "to",
  "合同合计目录价大于（美元）": "Contract list price total above (USD)",
  "包含已 EOS 设备（EOS 时间不晚于过保时间）": "Include EOS equipment (EOS date not later than expiry)",
  "包含资产状态为“不再拓展”的设备": "Include assets with status “不再拓展” (no further expansion)",
  "包含产品线“数据中心能源及关键供电”": "Include product line “数据中心能源及关键供电” (DC energy & critical power)",
  "拖入系统导出的原始续保数据": "Drop the raw renewal export from the system",
  "点击选择或拖入 Excel 文件": "Click to choose or drop an Excel file",
  "续保单明细导出表（含“当前合同号”“服务结束”“目录价”等列）": "Renewal detail export (with columns such as 当前合同号, 服务结束, 目录价)",
  "正在处理 {name} …": "Processing {name} …",
  "已处理 <b>{file}</b>：得到 <b>{n}</b> 条需要提醒的合同（过保 {start} ~ {end}，合计目录价 &gt; {min}）。":
    "Processed <b>{file}</b>: <b>{n}</b> contracts need reminders (expiring {start} ~ {end}, list price total &gt; {min}). ",
  "其中 {n} 条已带出上次填写的邮箱。": "{n} of them already have recipients from last time.",
  "查看分析报告 →": "View report →",
  "下载待填写名单 (Excel)": "Download list to fill in (Excel)",
  "修改上面的参数后，可点击": "After changing the filters above,",
  "按新参数重新整理": "re-run with new filters",
  "{n} 条提示": "{n} notice(s)",

  // 筛选过程
  "原始数据行数": "Raw data rows",
  "过保时间不在时间段内": "Expiry outside the period",
  "已 EOS 设备": "EOS equipment",
  "资产状态为不再拓展": "Asset status: no further expansion",
  "数据中心能源及关键供电": "DC energy & critical power",
  "卓越 / 战略 / 核心客户": "Premier / Strategic / Core accounts",
  "缺少合同号或日期": "Missing contract No. or date",
  "按 合同号+过保时间+服务类型 合并后": "After merging by contract No. + expiry + service type",
  "合计目录价未超过 {min}": "List price total not above {min}",
  "最终需要提醒": "Reminders needed",
  "条": "",
  "（已选择包含）": "(included as selected)",

  // ② 报告
  "导出报告 (HTML)": "Export report (HTML)",
  "请先导入数据": "Please import data first",
  "数据：{source} · 统计日期：{date}": "Data: {source} · As of {date}",
  "{file}（原始数据）": "{file} (raw data)",
  "需要提醒": "Reminders",
  "{o} 个代表处 · {c} 个客户": "{o} rep offices · {c} customers",
  "目录价合计": "List price total",
  "按维保类型": "By service type",
  "待填写邮箱": "Recipients missing",
  "筛选过程": "Filtering steps",
  "按过保月份": "By expiry month",
  "按客户分类": "By account class",
  "按代表处": "By rep office",
  "按签约客户（总代）": "By contracting partner",
  "目录价前 10 客户": "Top 10 customers by list price",
  "提醒条数": "Reminders",
  "最早过保": "Earliest expiry",
  "提醒名单": "Reminder list",
  "渠道续保通知名单": "Channel renewal list",
  "（过保目录价 > {min}）": " (list price > {min})",
  "搜索客户 / 签约客户 / 合同 / 代表处": "Search customer / partner / contract / office",
  "待填写": "To fill",
  "（未填写）": "(blank)",
  "过保分析报告": "Warranty Expiry Report",
  "请先在第①步导入原始数据": "Please import the raw data in step ① first",

  // 列名
  "签约客户": "Contracting partner",
  "二代": "Tier-2 partner",
  "代表处": "Rep office",
  "客户分类": "Account class",
  "最终客户": "End customer",
  "合同名称": "Contract name",
  "过保时间": "Expiry",
  "维保类型": "Service type",
  "合同号": "Contract No.",
  "金额": "Amount",
  "邮箱名单": "Recipients",
  "邮件语言": "Email language",
  "产品型号": "Products",
  "内容": "Content",
  "发送": "Sending",
  "收件人": "Recipients",
  "结果": "Result",
  "时间": "Time",
  "客户": "Customer",
  "方式": "Action",
  "定时": "Scheduled",
  "发信": "Mailer",
  "状态": "Status",
  "错误": "Error",

  // ③ 上传
  "怎么填写": "How to fill in",
  "在第②步点击“下载待填写名单”，打开 Excel 的【提醒名单】工作表。Excel 的列名请保持中文，程序按列名识别。":
    "In step ②, click “Download list to fill in” and open the 【提醒名单】 sheet. Keep the Excel column headers in Chinese — the program recognises columns by name.",
  "只填写黄色的 <b>邮箱名单</b> 和 <b>邮件语言</b> 两列，其他列不要改。一行就是一条提醒（合同号 + 过保时间 + 维保类型）。":
    "Only fill in the yellow <b>邮箱名单</b> (recipients) and <b>邮件语言</b> (email language) columns; leave the others unchanged. Each row is one reminder (contract No. + expiry + service type).",
  "同一客户（渠道模式为同一签约客户 / 二代）的行排在一起、底色相同，收件人通常一样，可以整组复制。":
    "Rows of the same customer (in channel mode: the same contracting / tier-2 partner) are together with the same shading — recipients are usually the same, so you can copy them for the whole group.",
  "多个收件人用英文分号 <code>;</code> 分隔，可以填邮箱，也可以填 Outlook 能识别的“姓名 工号”。":
    "Separate multiple recipients with <code>;</code>. Use email addresses or names / employee IDs that Outlook can resolve.",
  "<b>邮件语言</b> 客户通知默认“中文”、渠道通知默认“English”，可下拉切换。":
    "<b>邮件语言</b> defaults to “中文” for customer notices and “English” for channel notices; change it with the drop-down.",
  "留空的行不会发送；不需要提醒的行可以整行删除。保存后在下面上传。":
    "Rows without recipients are not sent; you can also delete rows you don't need. Save and upload below.",
  "以上为示例（Excel 表头为中文）。系统会记住填写过的邮箱和语言，下次下载名单时自动带出。旧版“维保日历数据.xlsx”格式也可以直接上传。":
    "Example above (Excel headers stay in Chinese). Recipients and languages are remembered and pre-filled next time. The old “维保日历数据.xlsx” format can also be uploaded.",
  "上传已填写的名单": "Upload the completed list",
  "点击选择或拖入已填写的 Excel 文件": "Click to choose or drop the completed Excel file",
  "正在读取 {name} …": "Reading {name} …",
  "已读取 <b>{file}</b>：{n} 条提醒，已填写邮箱 <b>{filled}</b> 条。": "Read <b>{file}</b>: {n} reminders, <b>{filled}</b> with recipients.",
  "下一步：提醒计划 →": "Next: reminder plan →",
  "可以在下表直接修改邮箱名单和邮件语言（只对本次发送生效）。同一客户的行底色相同。":
    "You can edit recipients and email language below (for this run only). Rows of the same customer share the same shading.",
  "可以在下表直接修改邮箱名单和邮件语言（只对本次发送生效）。同一签约客户 / 二代的行底色相同。":
    "You can edit recipients and email language below (for this run only). Rows of the same contracting / tier-2 partner share the same shading.",
  "未填写，不会发送": "Empty — will not be sent",

  // ④ 计划
  "提醒频率（可任意组合）": "Reminder frequency (any combination)",
  "过保前 6 个月": "6 months before expiry",
  "过保前 3 个月": "3 months before expiry",
  "过保前 1 个月": "1 month before expiry",
  "立即发送一次": "Send once now",
  "过保当日写入 Outlook 日历并邀请收件人": "Add an Outlook calendar entry on the expiry date and invite recipients",
  "已经过去的提醒节点：": "Reminder dates already passed:",
  "跳过": "Skip",
  "立即补发（多个节点合并为一封）": "Send now (several dates merged into one email)",
  "定时邮件在节点当天 {hour} 点由 Outlook 发出（需开启 Outlook 或使用 Exchange 账号）。渠道通知的节点提前到当月 1 日，同一伙伴同一天的合同合并成一封。已发送/已排定过的节点会自动跳过，可放心重复运行。":
    "Scheduled emails are sent by Outlook at {hour}:00 on the reminder date (Outlook running or an Exchange account required). Channel reminder dates move to the 1st of the month, and a partner's contracts due on the same day are merged into one email. Reminders already sent or scheduled are skipped, so it is safe to run again.",
  "生成提醒计划": "Build reminder plan",
  "隐藏跳过项": "Hide skipped",
  "全选可发送": "Select all sendable",
  "全不选": "Select none",
  "请先上传收件人名单，再生成提醒计划": "Upload the recipient list first, then build the plan",
  "点击“生成提醒计划”": "Click “Build reminder plan”",
  "请先导入数据并上传收件人名单": "Please import data and upload the recipient list first",
  "请至少选择一种提醒频率": "Please choose at least one reminder option",
  "共 {n} 项：立即 {now} · 定时 {defer} · 跳过 {skip}（其中未填收件人 {missing}，之前已发送 {sent}）":
    "{n} items: now {now} · scheduled {defer} · skipped {skip} (no recipients {missing}, sent before {sent})",
  "等 {n} 个合同": "{n} contracts",
  "渠道：{p}": "Partner: {p}",
  "邮件": "Email",
  "日历邀请": "Calendar invite",
  "立即": "Now",
  "定时": "Scheduled",
  "提前6个月提醒": "6-month reminder",
  "提前3个月提醒": "3-month reminder",
  "提前1个月提醒": "1-month reminder",
  "即时提醒": "Immediate reminder",
  "过保当日日历": "Expiry-day calendar",
  "该节点之前已发送": "Already sent before",
  "{days} 天后定时发送": "Scheduled in {days} days",
  "节点日期 {date} 已过": "Reminder date {date} has passed",
  "立即发送": "Send now",
  "立即发送（合并 {n} 个节点）": "Send now ({n} reminder dates merged)",
  "过保日期已过": "Already expired",
  "立即发出日历邀请": "Send calendar invite now",
  "未填写收件人": "No recipients",
  "未填写": "Missing",
  "预览": "Preview",
  "没有可发送的提醒（已隐藏跳过项）": "Nothing to send (skipped items hidden)",
  "没有可发送的提醒": "Nothing to send",
  "✔ 成功": "✔ Sent",
  "模拟成功": "Dry run OK",
  "未发送": "Not sent",
  "✘ 失败": "✘ Failed",
  "之前已发送": "Sent before",
  "发送选中 ({n})": "Send selected ({n})",
  "定时：{time}": "Scheduled: {time}",
  "日程日期：{date}（全天）": "Calendar date: {date} (all day)",
  "收件人：": "To: ",
  "抄送：": "Cc: ",
  "确定通过【{mailer}】发出以下内容吗？\n立即邮件 {now} 封\n定时邮件 {defer} 封\n日历邀请 {cal} 个":
    "Send the following via [{mailer}]?\nImmediate emails: {now}\nScheduled emails: {defer}\nCalendar invites: {cal}",
  "发送中…": "Sending…",
  "完成：成功 {ok} / {n}": "Done: {ok} / {n} succeeded",
  "失败或未发送的项目请查看“结果”列": "See the “Result” column for failed or unsent items",

  // 记录
  "最近 500 条记录（完整记录见 data/send_log.csv）": "Latest 500 records (full log in data/send_log.csv)",
  "刷新": "Refresh",
  "暂无记录": "No records yet",
  "成功": "Sent",
  "模拟": "Dry run",
  "失败": "Failed",

  // 设置
  "发送设置": "Sending settings",
  "发信方式": "Mailer",
  "Outlook 客户端（Windows，支持定时发送和日历邀请）": "Outlook client (Windows; supports scheduling and calendar invites)",
  "SMTP 服务器（不支持定时和日历）": "SMTP server (no scheduling or calendar)",
  "模拟发送（只记录，不真正发信）": "Dry run (log only, nothing is sent)",
  "定时邮件发送时刻（点）": "Scheduled send hour",
  "统一抄送（可选，多个用 ; 分隔）": "Cc for all emails (optional, separate with ;)",
  "模板": "Templates",
  "可用占位符：{office} {customer} {contract_name} {expiry} {service_type} {contract_no} {amount} {amount_fmt} {products} {node_label} {days_left} {days_text}。清空后保存即恢复默认模板。":
    "Placeholders: {office} {customer} {contract_name} {expiry} {service_type} {contract_no} {amount} {amount_fmt} {products} {node_label} {days_left} {days_text}. Clear a field and save to restore the default.",
  "客户通知 · 中文版": "Customer notice · Chinese",
  "客户通知 · 英文版": "Customer notice · English",
  "渠道续保通知 · 英文版（默认）": "Channel renewal notice · English (default)",
  "渠道续保通知 · 中文版": "Channel renewal notice · Chinese",
  "按合作伙伴合并成一封，发给签约客户 / 二代，不含金额和内部联系人、内部链接。额外占位符：{partner_name}（二代，没有时为签约客户）{count}（合同数）{first_expiry}（最早过保日）{contracts_table}（合同列表）{signer} {tier2}":
    "One email per partner, sent to the contracting / tier-2 partner, without prices, internal contacts or internal links. Extra placeholders: {partner_name} (tier-2 partner, or the contracting partner if none) {count} (number of contracts) {first_expiry} (earliest expiry) {contracts_table} (contract list) {signer} {tier2}",
  "邮件标题": "Email subject",
  "日历邀请标题": "Calendar invite subject",
  "邮件正文（HTML）": "Email body (HTML)",
  "SMTP（仅在发信方式为 SMTP 时使用）": "SMTP (only used when the mailer is SMTP)",
  "服务器": "Server",
  "端口": "Port",
  "用户名": "Username",
  "密码": "Password",
  "发件人地址": "Sender address",
  "保存设置": "Save settings",
  "已保存": "Saved",
  "设置已更改，请重新生成提醒计划": "Settings changed — please rebuild the reminder plan",

  // 其他
  "服务器错误 ({status})": "Server error ({status})",
  "请求失败 ({status})": "Request failed ({status})",
  "无法连接服务：{msg}": "Cannot reach the service: {msg}",
};

let LANG = "zh";

function t(key, params) {
  let text = LANG === "en" && key in EN ? EN[key] : key;
  if (params) text = text.replace(/\{(\w+)\}/g, (m, k) => (k in params ? String(params[k]) : m));
  return text;
}

function savedLang() {
  try { return localStorage.getItem("uiLang") === "en" ? "en" : "zh"; } catch { return "zh"; }
}

function setLang(lang) {
  LANG = lang === "en" ? "en" : "zh";
  try { localStorage.setItem("uiLang", LANG); } catch { /* 浏览器禁用存储时忽略 */ }
  document.documentElement.lang = LANG === "en" ? "en" : "zh-CN";
  document.title = t("过保提醒服务");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (!el.dataset.i18nKey) el.dataset.i18nKey = el.textContent.trim();
    el.textContent = t(el.dataset.i18nKey);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    if (!el.dataset.i18nKey) el.dataset.i18nKey = el.innerHTML.trim();
    el.innerHTML = t(el.dataset.i18nKey);
  });
}
