# 过保提醒服务

浏览器里完成：**上传过保数据 → 查看分析报告 → 填写收件人名单 → 预览并批量发送提醒邮件**。
由原来的 Tkinter 版“维保提醒邮件生成器 v2.1”改造而来，沿用原有的数据格式、邮件模板和提醒规则。

## 运行（Windows）

1. 安装 Python 3.9+
2. 双击 `启动.bat`（或执行 `pip install -r requirements.txt` 后运行 `python app.py`）
3. 浏览器自动打开 http://127.0.0.1:5000

服务只监听本机，不会被同网段其他电脑访问。

## 使用流程

| 步骤 | 说明 |
| --- | --- |
| ① 导入数据 | 上传 .xlsx / .csv。按表头识别列（必需：过保时间、合同号）；识别不到表头时按旧版“维保日历数据.xlsx”列顺序读取 |
| ② 分析报告 | 总数/金额、已过保、180 天内到期，按紧急程度、未来 12 个月、代表处、维保类型汇总，可筛选明细，可导出 HTML 报告 |
| ③ 收件人名单 | 按代表处填写，或按合同单独指定。优先级：按合同 > Excel 邮箱名单列 > 按代表处。名单保存在本机，下次自动带出 |
| ④ 预览发送 | 逐条显示收件人、提醒日期和发送方式，可预览邮件、勾选后批量发送 |

## 发送规则（与旧版一致）

- 提醒日期 = 过保时间 − 提醒天数（Excel 未填时用设置里的默认值，默认 180 天）
- 提醒日期已到 → 立即发送
- 提醒日期在未来且不超过 300 天 → Outlook 定时发送（`DeferredDeliveryTime`，默认当天 9 点）
- 超过 300 天 → 暂不排定，以后再运行时自动纳入
- **防重复**：成功发送/排定过的提醒记录在 `data/send_log.csv`，再次运行默认不勾选，可以放心定期运行

## 发信方式（在“设置”页切换）

- **Outlook**：调用本机 Outlook 客户端（需 Windows + pywin32），支持定时发送
- **SMTP**：直连邮件服务器，不支持定时，只发送已到提醒日期的邮件
- **模拟发送**：只记录不发信，用于试运行

邮件标题和正文模板可在设置页修改，可用占位符：`{office} {customer} {contract_name} {expiry} {service_type} {contract_no} {amount} {amount_fmt} {remind_date} {days_left}`。

## 本地数据

`data/` 目录（不入库）：`settings.json` 设置、`recipients.json` 收件人名单、`send_log.csv` 发送记录。

## 开发

```bash
pip install -r requirements.txt pytest
python -m pytest -q
```
