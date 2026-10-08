import os
import re
from datetime import datetime, timezone

try:
    from backend.attendance_calculator import (
        calculate_safe_bunks,
        calculate_required_classes,
        calculate_attendance
    )
except ImportError:
    try:
        from attendance_calculator import (
            calculate_safe_bunks,
            calculate_required_classes,
            calculate_attendance
        )
    except ImportError:
        def calculate_safe_bunks(att, cond, target=75.0):
            try:
                import math
                if cond <= 0 or att <= 0: return 0
                return max(0, int(math.floor(((float(att) - (target/100.0) * float(cond)) / (target/100.0)) + 1e-9)))
            except Exception: return 0
        def calculate_required_classes(att, cond, target=75.0):
            try:
                import math
                if cond <= 0: return 0
                return max(0, int(math.ceil(((target/100.0) * float(cond) - float(att)) / (1 - target/100.0))))
            except Exception: return 0
        def calculate_attendance(att, cond):
            try:
                return round((float(att) / float(cond)) * 100.0, 2) if float(cond) > 0 else 0.0
            except Exception: return 0.0


def _parse_pct(pct_str):
    if not pct_str:
        return None
    try:
        cleaned = re.sub(r'[^0-9.]', '', str(pct_str))
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None


def build_notification_email(notif, student_name, roll_no, recipient_email):
    """
    Constructs a rich, meaningful, and professional HTML notification email
    tailored specifically to the detected academic change category.
    
    Includes:
    - Clear PSG Tech & Student Sync branding
    - Category-specific color theme and badges
    - Detailed change comparison (before vs after)
    - Actionable academic insights (e.g. Safe Bunk calculation or classes needed to hit 75%)
    - Direct dashboard action link
    - Student verification details
    """
    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000').rstrip('/')
    category = (notif.get('category') or notif.get('type') or 'general').lower()
    ntype = (notif.get('type') or 'general').lower()
    title = notif.get('title') or 'Academic Update'
    message = notif.get('message') or notif.get('description') or ''
    source = notif.get('source') or 'Student Sync'
    module = notif.get('module') or 'Academics'
    change_data = notif.get('changeData') or {}

    subject_name = change_data.get('subject') or ''
    course_code = change_data.get('code') or ''

    # Format consistent Subject line
    if subject_name:
        email_subject = f"Student Sync — {title} ({subject_name})"
    else:
        email_subject = f"Student Sync — {title}"

    # Default styling tokens
    accent_color = "#8b5cf6"  # Purple default
    badge_bg = "rgba(139, 92, 246, 0.15)"
    badge_border = "rgba(139, 92, 246, 0.3)"
    badge_text = "#c4b5fd"
    badge_icon = "📢"
    cta_url = f"{frontend_url}/dashboard"
    cta_text = "Open Student Sync Dashboard →"
    insight_html = ""

    # 1. ATTENDANCE NOTIFICATION
    if ntype == 'attendance':
        cta_url = f"{frontend_url}/attendance"
        cta_text = "Open Attendance Dashboard →"
        badge_icon = "📊"
        
        prev_pct = change_data.get('previousValue')
        new_pct = change_data.get('newValue')
        direction = change_data.get('direction', '')
        attended = change_data.get('attended')
        total = change_data.get('total')

        pct_val = _parse_pct(new_pct)
        is_warning = (pct_val is not None and pct_val < 75.0) or direction == 'decreased' or 'Alert' in title

        if is_warning:
            accent_color = "#ef4444"  # Rose / Alert Red
            badge_bg = "rgba(239, 68, 68, 0.15)"
            badge_border = "rgba(239, 68, 68, 0.35)"
            badge_text = "#f87171"
        else:
            accent_color = "#10b981"  # Emerald / Safe Green
            badge_bg = "rgba(16, 185, 129, 0.15)"
            badge_border = "rgba(16, 185, 129, 0.35)"
            badge_text = "#34d399"

        # Construct meaningful academic insight based on attended / total or percentage
        if attended is not None and total is not None:
            try:
                att_i = int(attended)
                tot_i = int(total)
                if pct_val is not None and pct_val < 75.0:
                    needed = calculate_required_classes(att_i, tot_i, 75.0)
                    insight_html = f"""
                    <div style="background-color: #201317; border: 1px solid #7f1d1d; border-radius: 8px; padding: 14px; margin-top: 16px;">
                      <div style="font-size: 12px; font-weight: 700; color: #f87171; margin-bottom: 4px;">
                        ⚠️ Attendance Below PSG Tech 75% Threshold
                      </div>
                      <div style="font-size: 13px; color: #fca5a5; line-height: 1.5;">
                        Your attendance is currently <strong>{new_pct}</strong>. PSG Tech regulations require at least <strong>75%</strong> to qualify for examinations without condonation.
                      </div>
                      <div style="font-size: 12px; font-weight: 600; color: #ffffff; margin-top: 8px; padding-top: 8px; border-top: 1px solid #3b1820;">
                        🎯 Action Plan: You must attend the next <strong>{needed} consecutive class(es)</strong> without absence to restore your attendance to 75%.
                      </div>
                    </div>
                    """
                else:
                    safe = calculate_safe_bunks(att_i, tot_i, 75.0)
                    insight_html = f"""
                    <div style="background-color: #0d1f18; border: 1px solid #065f46; border-radius: 8px; padding: 14px; margin-top: 16px;">
                      <div style="font-size: 12px; font-weight: 700; color: #34d399; margin-bottom: 4px;">
                        ✅ Safe Attendance Zone (≥ 75%)
                      </div>
                      <div style="font-size: 13px; color: #a7f3d0; line-height: 1.5;">
                        Your attendance is currently <strong>{new_pct}</strong> ({att_i} attended out of {tot_i} classes conducted).
                      </div>
                      <div style="font-size: 12px; font-weight: 600; color: #ffffff; margin-top: 8px; padding-top: 8px; border-top: 1px solid #0f3d2e;">
                        🛡️ Safe Margin: You can safely miss up to <strong>{safe} upcoming class(es)</strong> while maintaining ≥ 75% attendance (safe bunks remaining: {safe}).
                      </div>
                    </div>
                    """
            except Exception:
                pass

        if not insight_html and pct_val is not None:
            if pct_val < 75.0:
                insight_html = f"""
                <div style="background-color: #201317; border: 1px solid #7f1d1d; border-radius: 8px; padding: 14px; margin-top: 16px;">
                  <div style="font-size: 12px; font-weight: 700; color: #f87171; margin-bottom: 4px;">
                    ⚠️ Attendance Below PSG Tech 75% Threshold
                  </div>
                  <div style="font-size: 13px; color: #fca5a5; line-height: 1.5;">
                    Your attendance is currently <strong>{new_pct}</strong>. PSG Tech regulations require at least <strong>75%</strong> to qualify for examinations without condonation.
                  </div>
                </div>
                """
            else:
                insight_html = f"""
                <div style="background-color: #0d1f18; border: 1px solid #065f46; border-radius: 8px; padding: 14px; margin-top: 16px;">
                  <div style="font-size: 12px; font-weight: 700; color: #34d399; margin-bottom: 4px;">
                    ✅ Safe Attendance Zone (≥ 75%)
                  </div>
                  <div style="font-size: 13px; color: #a7f3d0; line-height: 1.5;">
                    Your attendance is currently <strong>{new_pct}</strong>, meeting the PSG Tech academic requirement.
                  </div>
                </div>
                """

    # 2. CONTINUOUS ASSESSMENT / MARKS NOTIFICATION
    elif ntype == 'marks':
        accent_color = "#a855f7"  # Violet
        badge_bg = "rgba(168, 85, 247, 0.15)"
        badge_border = "rgba(168, 85, 247, 0.35)"
        badge_text = "#d8b4fe"
        badge_icon = "📝"
        cta_url = f"{frontend_url}/grades"
        cta_text = "View Internal Marks & Analysis →"

        test_name = change_data.get('test', 'Assessment')
        prev_mark = change_data.get('previousValue', '')
        new_mark = change_data.get('newValue', '')

        insight_html = f"""
        <div style="background-color: #171529; border: 1px solid #4c1d95; border-radius: 8px; padding: 14px; margin-top: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #c084fc; margin-bottom: 4px;">
            📝 Continuous Assessment Recorded
          </div>
          <div style="font-size: 13px; color: #ddd6fe; line-height: 1.5;">
            {subject_name} {test_name} marks have been officially recorded on StudZone 1.
          </div>
        </div>
        """

    # 3. SEMESTER RESULTS & CGPA
    elif ntype in ['results', 'cgpa']:
        accent_color = "#3b82f6"  # Blue
        badge_bg = "rgba(59, 130, 246, 0.15)"
        badge_border = "rgba(59, 130, 246, 0.35)"
        badge_text = "#93c5fd"
        badge_icon = "📈"
        cta_url = f"{frontend_url}/grades"
        cta_text = "View Semester Results & CGPA →"

        insight_html = f"""
        <div style="background-color: #111a2e; border: 1px solid #1e3a8a; border-radius: 8px; padding: 14px; margin-top: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #60a5fa; margin-bottom: 4px;">
            🎓 Academic Record Updated
          </div>
          <div style="font-size: 13px; color: #bfdbfe; line-height: 1.5;">
            Your semester evaluation record has been updated on StudZone 2.
          </div>
        </div>
        """

    # 4. EXAM TIMETABLE
    elif ntype == 'timetable':
        accent_color = "#f59e0b"  # Amber
        badge_bg = "rgba(245, 158, 11, 0.15)"
        badge_border = "rgba(245, 158, 11, 0.35)"
        badge_text = "#fbbf24"
        badge_icon = "📅"
        cta_url = f"{frontend_url}/schedule"
        cta_text = "View Exam Schedule →"

        exam_date = change_data.get('examDate') or change_data.get('newDate') or ''
        timing = change_data.get('timing') or change_data.get('newTiming') or ''
        session = change_data.get('session') or ''

        details_extra = ""
        if exam_date:
            details_extra += f"<div>Date: <strong style='color:#ffffff;'>{exam_date}</strong></div>"
        if session or timing:
            details_extra += f"<div>Session: <strong style='color:#ffffff;'>{session} {('(' + timing + ')') if timing else ''}</strong></div>"

        insight_html = f"""
        <div style="background-color: #211c13; border: 1px solid #78350f; border-radius: 8px; padding: 14px; margin-top: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #fbbf24; margin-bottom: 4px;">
            📅 Examination Schedule Notification
          </div>
          <div style="font-size: 13px; color: #fde68a; line-height: 1.5;">
            {details_extra}
          </div>
        </div>
        """

    # 5. SEATING ARRANGEMENT
    elif ntype == 'seating':
        accent_color = "#14b8a6"  # Teal
        badge_bg = "rgba(20, 184, 166, 0.15)"
        badge_border = "rgba(20, 184, 166, 0.35)"
        badge_text = "#5eead4"
        badge_icon = "🪑"
        cta_url = f"{frontend_url}/schedule"
        cta_text = "View Seating Arrangement →"

        hall = change_data.get('hall', '')
        seat = change_data.get('seat', '')

        insight_html = f"""
        <div style="background-color: #0e201f; border: 1px solid #134e4a; border-radius: 8px; padding: 14px; margin-top: 16px;">
          <div style="font-size: 12px; font-weight: 700; color: #5eead4; margin-bottom: 4px;">
            🪑 Exam Hall & Seat Allocation
          </div>
          <div style="font-size: 13px; color: #99f6e4; line-height: 1.5;">
            Hall: <strong style="color: #ffffff;">{hall or 'Allocated'}</strong> • Seat: <strong style="color: #ffffff;">{seat or 'Allocated'}</strong>
          </div>
        </div>
        """

    # 6. FEES & DUES
    elif ntype == 'fees':
        accent_color = "#f97316"  # Orange
        badge_bg = "rgba(249, 115, 22, 0.15)"
        badge_border = "rgba(249, 115, 22, 0.35)"
        badge_text = "#fdba74"
        badge_icon = "💳"
        cta_url = f"{frontend_url}/services"
        cta_text = "View Academic Accounts →"

    # Assemble Details Table
    details_rows = []
    if subject_name:
        code_tag = f" <span style='font-family: monospace; color: #9ca3af;'>({course_code})</span>" if course_code else ""
        details_rows.append(f"""
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af; width: 35%;">Subject</td>
            <td style="padding: 10px 14px; color: #ffffff; font-weight: 600;">{subject_name}{code_tag}</td>
          </tr>
        """)

    prev_val = change_data.get('previousValue')
    new_val = change_data.get('newValue')
    if prev_val is not None and new_val is not None and prev_val != new_val:
        details_rows.append(f"""
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">Update Transition</td>
            <td style="padding: 10px 14px; color: #ffffff;">
              <span style="color: #9ca3af; text-decoration: line-through;">{prev_val}</span>
              <span style="margin: 0 8px; color: #c4b5fd;">→</span>
              <strong style="color: {accent_color};">{new_val}</strong>
            </td>
          </tr>
        """)
    elif new_val is not None:
        details_rows.append(f"""
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">Current Value</td>
            <td style="padding: 10px 14px; color: {accent_color}; font-weight: 600;">{new_val}</td>
          </tr>
        """)

    if ntype == 'attendance' and change_data.get('attended') is not None and change_data.get('total') is not None:
        details_rows.append(f"""
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">Classes Status</td>
            <td style="padding: 10px 14px; color: #ffffff;">
              <strong>{change_data.get('attended')}</strong> attended / <strong>{change_data.get('total')}</strong> conducted
            </td>
          </tr>
        """)

    if ntype == 'marks' and change_data.get('test'):
        details_rows.append(f"""
          <tr style="border-bottom: 1px solid #222738;">
            <td style="padding: 10px 14px; color: #9ca3af;">Assessment</td>
            <td style="padding: 10px 14px; color: #ffffff; font-weight: 600;">{change_data.get('test')}</td>
          </tr>
        """)

    details_table_html = ""
    if details_rows:
        details_table_html = f"""
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; color: #d1d5db; margin-top: 16px; margin-bottom: 16px; background-color: #181c2b; border-radius: 8px; border: 1px solid #222738; overflow: hidden;">
          {''.join(details_rows)}
        </table>
        """

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{email_subject}</title>
</head>
<body style="margin: 0; padding: 24px 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0d13; color: #f3f4f6;">
  <div style="max-width: 540px; margin: 0 auto; background-color: #131620; border: 1px solid #232738; border-radius: 14px; padding: 28px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);">
    
    <!-- Top Header & Source Badge -->
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
      <div style="display: inline-block; padding: 4px 10px; border-radius: 20px; background-color: {badge_bg}; border: 1px solid {badge_border}; font-size: 11px; font-weight: 700; color: {badge_text}; text-transform: uppercase; letter-spacing: 0.05em;">
        {badge_icon} {source} • {module}
      </div>
    </div>

    <!-- Notification Title -->
    <h1 style="color: #ffffff; font-size: 20px; font-weight: 700; margin-top: 0; margin-bottom: 10px; line-height: 1.3;">
      {title}
    </h1>

    <!-- Message Summary -->
    <p style="color: #e5e7eb; font-size: 14px; line-height: 1.6; margin-top: 0; margin-bottom: 16px;">
      {message}
    </p>

    <!-- Specific Details Table -->
    {details_table_html}

    <!-- Actionable Academic Insight -->
    {insight_html}

    <!-- Call to Action Button -->
    <div style="text-align: center; margin-top: 24px; margin-bottom: 24px;">
      <a href="{cta_url}" style="display: inline-block; padding: 12px 24px; background-color: {accent_color}; color: #ffffff; text-decoration: none; font-size: 13px; font-weight: 600; border-radius: 8px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);">
        {cta_text}
      </a>
    </div>

    <!-- Student Context Box -->
    <div style="padding: 12px 14px; border-radius: 8px; background-color: #181c2b; border: 1px solid #222738; font-size: 12px; color: #9ca3af; margin-bottom: 20px;">
      <div style="margin-bottom: 4px;">Student: <strong style="color: #ffffff;">{student_name}</strong> (<span style="font-family: monospace; color: #c4b5fd;">{roll_no}</span>)</div>
      <div>Sent to: <span style="font-family: monospace; color: #93c5fd;">{recipient_email}</span></div>
    </div>

    <!-- Footer -->
    <div style="border-top: 1px solid #1c202e; padding-top: 16px; font-size: 11px; color: #6b7280; text-align: center; line-height: 1.5;">
      © 2026 Student Sync | PSG College of Technology<br/>
      You received this automated notification because this account is registered with Student Sync.
    </div>

  </div>
</body>
</html>
"""
    return email_subject, html_body
