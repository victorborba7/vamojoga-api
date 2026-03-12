import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.core.config import settings

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, html_body: str) -> None:
    """Send an email via Zoho SMTP (TLS on port 587)."""
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, to, msg.as_string())
        logger.info("Email sent to %s", to)
    except Exception:
        logger.exception("Failed to send email to %s", to)
        raise


def send_password_reset_email(to: str, username: str, token: str) -> None:
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    html = f"""\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e5e5e5; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: #1a1a1a; border-radius: 16px; padding: 32px; border: 1px solid #333;">
    <h1 style="color: #a78bfa; font-size: 24px; margin: 0 0 8px;">VamoJoga</h1>
    <p style="color: #999; font-size: 14px; margin: 0 0 24px;">Recuperação de senha</p>
    <p style="font-size: 15px; line-height: 1.6;">
      Olá <strong>{username}</strong>,<br><br>
      Recebemos um pedido para redefinir sua senha. Clique no botão abaixo para criar uma nova senha:
    </p>
    <div style="text-align: center; margin: 28px 0;">
      <a href="{reset_url}" style="display: inline-block; background: #7c3aed; color: #fff; text-decoration: none; padding: 12px 32px; border-radius: 12px; font-size: 15px; font-weight: 600;">
        Redefinir Senha
      </a>
    </div>
    <p style="font-size: 13px; color: #666; line-height: 1.5;">
      Este link expira em <strong>1 hora</strong>.<br>
      Se você não solicitou a redefinição, ignore este e-mail.
    </p>
    <hr style="border: none; border-top: 1px solid #333; margin: 24px 0;">
    <p style="font-size: 11px; color: #555; text-align: center;">
      Se o botão não funcionar, copie e cole este link no navegador:<br>
      <a href="{reset_url}" style="color: #7c3aed; word-break: break-all;">{reset_url}</a>
    </p>
  </div>
</body>
</html>"""
    send_email(to, "Redefinição de Senha — VamoJoga", html)


def send_verification_email(to: str, username: str, token: str) -> None:
    verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    html = f"""\
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f0f; color: #e5e5e5; padding: 40px 20px;">
  <div style="max-width: 480px; margin: 0 auto; background: #1a1a1a; border-radius: 16px; padding: 32px; border: 1px solid #333;">
    <h1 style="color: #a78bfa; font-size: 24px; margin: 0 0 8px;">VamoJoga</h1>
    <p style="color: #999; font-size: 14px; margin: 0 0 24px;">Verificação de e-mail</p>
    <p style="font-size: 15px; line-height: 1.6;">
      Olá <strong>{username}</strong>,<br><br>
      Obrigado por se cadastrar! Clique no botão abaixo para confirmar seu e-mail:
    </p>
    <div style="text-align: center; margin: 28px 0;">
      <a href="{verify_url}" style="display: inline-block; background: #7c3aed; color: #fff; text-decoration: none; padding: 12px 32px; border-radius: 12px; font-size: 15px; font-weight: 600;">
        Confirmar E-mail
      </a>
    </div>
    <p style="font-size: 13px; color: #666; line-height: 1.5;">
      Este link expira em <strong>24 horas</strong>.<br>
      Se você não criou esta conta, ignore este e-mail.
    </p>
    <hr style="border: none; border-top: 1px solid #333; margin: 24px 0;">
    <p style="font-size: 11px; color: #555; text-align: center;">
      Se o botão não funcionar, copie e cole este link no navegador:<br>
      <a href="{verify_url}" style="color: #7c3aed; word-break: break-all;">{verify_url}</a>
    </p>
  </div>
</body>
</html>"""
    send_email(to, "Confirme seu e-mail — VamoJoga", html)
