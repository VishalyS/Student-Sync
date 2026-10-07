import os
import sys
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Load .env
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
if os.path.exists(env_path):
    load_dotenv(env_path)
load_dotenv()

def run_smtp_verification():
    print("======================================================================")
    print("STUDENT SYNC — SAFE SMTP VERIFICATION & TEST EMAIL")
    print("======================================================================\n")

    sender_email = (os.getenv("SMTP_USER") or "").strip()
    raw_password = (os.getenv("SMTP_PASSWORD") or "").strip().strip('"').strip("'")
    password = raw_password.replace(" ", "")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    admin_email = (os.getenv("ADMIN_EMAIL") or "studentsync12@gmail.com").strip()

    print("1. [Environment & Credentials Check]")
    print(f"   - SMTP Server: {smtp_server}:{smtp_port}")
    print(f"   - SMTP User: {sender_email if sender_email else 'NOT CONFIGURED'}")
    print(f"   - Admin Target: {admin_email}")
    print(f"   - App Password Configured: {'YES (********)' if password else 'NO'}")

    if not sender_email or not password:
        print("\n[FAIL] SMTP_USER or SMTP_PASSWORD is not set in backend/.env.")
        return False

    print("\n2. [SMTP Handshake & STARTTLS Authentication]")
    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=15) as server:
            server.set_debuglevel(0)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, password)
            print("   [SUCCESS] SMTP STARTTLS Authentication Successful!")

            # 3. Safe Test Email Delivery (ONLY to Admin email, never to student addresses)
            print(f"\n3. [Safe Email Delivery Test -> {admin_email}]")
            test_subject = "Student Sync SMTP Test"
            test_body = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin: 0; padding: 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
              <div style="max-width: 520px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 12px; padding: 28px;">
                <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: #34d399; font-weight: 600; margin-bottom: 6px;">
                  System Diagnostic • Verified
                </div>
                <h2 style="color: #ffffff; font-size: 20px; margin-top: 0; margin-bottom: 12px;">Student Sync SMTP Test</h2>
                <p style="color: #9ca3af; font-size: 14px; line-height: 1.6; margin-bottom: 16px;">
                  This is a test email verifying that SMTP authentication and email delivery are operational on Student Sync.
                </p>
                <div style="padding: 12px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin-bottom: 20px;">
                  <strong>Status:</strong> Connected & Authenticated via Google SMTP (Port 587 / STARTTLS)<br/>
                  <strong>Sender:</strong> {sender_email}<br/>
                  <strong>Recipient:</strong> {admin_email}
                </div>
                <div style="border-top: 1px solid #1c202e; padding-top: 14px; font-size: 11px; color: #6b7280; text-align: center;">
                  © 2026 Student Sync | All rights reserved.
                </div>
              </div>
            </body>
            </html>
            """

            msg = MIMEText(test_body, 'html')
            msg['Subject'] = test_subject
            msg['From'] = sender_email
            msg['To'] = admin_email

            server.sendmail(sender_email, admin_email, msg.as_string())
            print(f"   [SUCCESS] Safe test email sent to {admin_email}!")
            print("   Email delivery confirmed with zero impact on student data.")
            return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"   [FAIL] SMTP Authentication failed (535): {e}")
        return False
    except Exception as e:
        print(f"   [FAIL] SMTP Delivery failed: {e}")
        return False

if __name__ == "__main__":
    success = run_smtp_verification()
    sys.exit(0 if success else 1)
