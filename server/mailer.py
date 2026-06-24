"""
mailer.py — Email utility for the HTTP DMS Server.

Sends OTP password-reset emails via SMTP (STARTTLS on port 587 by default).

Usage:
    from mailer import send_otp_email
    send_otp_email("user@example.com", "482910")

Requirements:
    All settings are read from config.settings:
        SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

    For Gmail, use an App Password:
        https://myaccount.google.com/apppasswords
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("dms.mailer")


def send_otp_email(to_email: str, otp_code: str) -> None:
    """
    Sends a styled OTP password-reset email to the given address.

    Args:
        to_email:  Recipient's email address.
        otp_code:  The 6-digit OTP to include in the email.

    Raises:
        RuntimeError: If SMTP credentials are not configured.
        Exception:    Re-raises SMTP errors after logging them.
    """
    from config import settings

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise RuntimeError(
            "SMTP credentials are not configured. "
            "Set SMTP_USER and SMTP_PASSWORD in your .env file."
        )

    from_addr = settings.SMTP_FROM or settings.SMTP_USER
    subject = "DMS Portal — Your Password Reset OTP"

    # ── Plain-text fallback ──
    text_body = (
        f"Your DMS Portal password reset OTP is: {otp_code}\n\n"
        f"This code expires in {settings.OTP_EXPIRY_MINUTES} minutes.\n"
        f"If you did not request a password reset, please ignore this email."
    )

    # ── HTML body ──
    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DMS Password Reset</title>
</head>
<body style="margin:0;padding:0;background:#0d1117;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="480" cellpadding="0" cellspacing="0"
               style="background:#161b22;border:1px solid #21262d;border-radius:12px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background:linear-gradient(135deg,#1f6feb,#58a6ff);padding:28px 32px;text-align:center;">
              <p style="margin:0;color:#fff;font-size:22px;font-weight:700;letter-spacing:-0.02em;">
                🔐 DMS Portal
              </p>
              <p style="margin:6px 0 0;color:rgba(255,255,255,0.8);font-size:13px;">
                Password Reset Request
              </p>
            </td>
          </tr>

          <!-- Body -->
          <tr>
            <td style="padding:32px;">
              <p style="margin:0 0 16px;color:#e6edf3;font-size:15px;line-height:1.6;">
                We received a request to reset your DMS Portal password.
                Use the OTP below to continue. It expires in
                <strong style="color:#58a6ff;">{settings.OTP_EXPIRY_MINUTES} minutes</strong>.
              </p>

              <!-- OTP Box -->
              <div style="text-align:center;margin:28px 0;">
                <div style="display:inline-block;background:#0d1117;border:2px solid #58a6ff;
                            border-radius:10px;padding:18px 36px;">
                  <p style="margin:0;color:#7d8590;font-size:11px;font-weight:600;
                             text-transform:uppercase;letter-spacing:0.08em;">
                    Your One-Time Password
                  </p>
                  <p style="margin:10px 0 0;color:#58a6ff;font-size:40px;font-weight:700;
                             letter-spacing:0.2em;font-family:'Courier New',monospace;">
                    {otp_code}
                  </p>
                </div>
              </div>

              <p style="margin:0 0 12px;color:#7d8590;font-size:13px;line-height:1.6;">
                If you didn't request this, you can safely ignore this email.
                Your password will not change.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:16px 32px;border-top:1px solid #21262d;text-align:center;">
              <p style="margin:0;color:#7d8590;font-size:12px;">
                DMS — Production Test Management System
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # ── Compose message ──
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"DMS Portal <{from_addr}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # ── Send via STARTTLS ──
    logger.info("Sending OTP email to %s via %s:%d", to_email, settings.SMTP_HOST, settings.SMTP_PORT)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(from_addr, to_email, msg.as_string())
        logger.info("OTP email sent successfully to %s", to_email)
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed for user '%s'. "
            "Check SMTP_USER and SMTP_PASSWORD in .env. "
            "For Gmail, use an App Password.",
            settings.SMTP_USER,
        )
        raise
    except Exception as exc:
        logger.exception("Failed to send OTP email to %s: %s", to_email, exc)
        raise
