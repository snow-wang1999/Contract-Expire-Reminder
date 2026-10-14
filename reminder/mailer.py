"""发信方式：Outlook（本机客户端，支持定时发送）、SMTP、模拟发送。"""
import datetime as dt
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


class MailerError(Exception):
    pass


class DryRunMailer:
    name = "dryrun"
    supports_defer = True

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def send(self, to, cc, subject, body, send_at=None):
        pass


class OutlookMailer:
    """通过本机 Outlook 发送，与旧版程序相同；定时发送使用 DeferredDeliveryTime。"""
    name = "outlook"
    supports_defer = True

    def __enter__(self):
        try:
            import pythoncom
            import win32com.client as win32
        except ImportError as e:
            raise MailerError("未安装 pywin32 或当前不是 Windows，无法使用 Outlook 发送") from e
        pythoncom.CoInitialize()
        self._pythoncom = pythoncom
        try:
            self._outlook = win32.Dispatch("Outlook.Application")
        except Exception as e:
            pythoncom.CoUninitialize()
            raise MailerError(f"无法启动 Outlook：{e}") from e
        return self

    def __exit__(self, *exc):
        self._outlook = None
        self._pythoncom.CoUninitialize()
        return False

    def send(self, to, cc, subject, body, send_at=None):
        mail = self._outlook.CreateItem(0)
        mail.To = ";".join(to)
        if cc:
            mail.CC = ";".join(cc)
        mail.Subject = subject
        mail.Body = body
        if send_at:
            mail.DeferredDeliveryTime = dt.datetime.fromisoformat(send_at)
        mail.Send()


class SmtpMailer:
    name = "smtp"
    supports_defer = False

    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        cfg = self.cfg
        if not cfg.get("host") or not cfg.get("sender"):
            raise MailerError("请先在设置中填写 SMTP 服务器和发件人")
        try:
            if cfg.get("ssl"):
                self._smtp = smtplib.SMTP_SSL(cfg["host"], int(cfg["port"]),
                                              context=ssl.create_default_context(), timeout=30)
            else:
                self._smtp = smtplib.SMTP(cfg["host"], int(cfg["port"]), timeout=30)
                if cfg.get("starttls"):
                    self._smtp.starttls(context=ssl.create_default_context())
            if cfg.get("username"):
                self._smtp.login(cfg["username"], cfg.get("password", ""))
        except (OSError, smtplib.SMTPException) as e:
            raise MailerError(f"连接 SMTP 服务器失败：{e}") from e
        return self

    def __exit__(self, *exc):
        try:
            self._smtp.quit()
        except Exception:
            pass
        return False

    def send(self, to, cc, subject, body, send_at=None):
        if send_at:
            raise MailerError("SMTP 不支持定时发送")
        msg = EmailMessage()
        msg["From"] = self.cfg["sender"]
        msg["To"] = ", ".join(to)
        if cc:
            msg["Cc"] = ", ".join(cc)
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg.set_content(body)
        self._smtp.send_message(msg)


def create(settings):
    kind = settings.get("mailer")
    if kind == "outlook":
        return OutlookMailer()
    if kind == "smtp":
        return SmtpMailer(settings["smtp"])
    return DryRunMailer()
