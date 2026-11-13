"""
Responsive, enterprise-branded HTML and plain-text email templates for Module 12B.
NexDesk AI branding with white/navy/blue/orange styling, clear info cards, and mobile responsiveness.
"""
import html
from typing import Any, Dict, List, Optional

from app.core.config import settings


def _escape(val: Any) -> str:
    return html.escape(str(val) if val is not None else "")


def _base_email_shell(title: str, content_html: str, action_url: Optional[str] = None, action_label: Optional[str] = None) -> str:
    action_button = ""
    if action_url and action_label:
        action_button = f"""
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 28px 0;">
          <tr>
            <td align="center">
              <a href="{_escape(action_url)}" target="_blank" style="background-color: #2563EB; color: #FFFFFF; font-size: 14px; font-weight: 600; text-decoration: none; padding: 12px 28px; border-radius: 8px; display: inline-block; box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);">
                {_escape(action_label)} &rarr;
              </a>
            </td>
          </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_escape(title)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #172033; -webkit-font-smoothing: antialiased;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; padding: 32px 16px;">
    <tr>
      <td align="center">
        <!-- Main Card -->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
          <!-- Header Banner -->
          <tr>
            <td style="background-color: #0F172A; padding: 24px 32px; border-bottom: 3px solid #2563EB;">
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td>
                    <span style="font-size: 20px; font-weight: 800; color: #FFFFFF; letter-spacing: -0.5px;">NexDesk AI</span>
                    <span style="font-size: 11px; font-weight: 700; color: #60A5FA; text-transform: uppercase; letter-spacing: 1px; margin-left: 8px; background-color: rgba(37, 99, 235, 0.2); padding: 3px 8px; border-radius: 6px;">IT Service Desk</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Body Content -->
          <tr>
            <td style="padding: 32px;">
              <h1 style="font-size: 20px; font-weight: 700; color: #0F172A; margin: 0 0 16px 0; line-height: 1.3;">{_escape(title)}</h1>
              {content_html}
              {action_button}
              <p style="font-size: 13px; color: #64748B; margin: 24px 0 0 0; line-height: 1.5;">
                If you did not make this request or believe this is an error, please contact the NexDesk IT Helpdesk immediately.
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #F1F5F9; padding: 20px 32px; border-top: 1px solid #E2E8F0; text-align: center;">
              <p style="font-size: 11px; color: #64748B; margin: 0; line-height: 1.5;">
                &copy; NexDesk AI Enterprise Service Management Platform &bull; Automated System Dispatch
              </p>
              <p style="font-size: 11px; color: #94A3B8; margin: 4px 0 0 0;">
                Sender: {_escape(settings.SMTP_FROM_EMAIL)} &bull; Confidential IT Support Communication
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def render_admin_ticket_creation_email(
    *,
    employee_name: str,
    employee_email: str,
    ticket_id: int,
    ticket_number: str,
    title: str,
    description: str,
    category: str,
    priority_label: str,
    status_label: str,
    created_at: str,
    admin_ticket_url: str,
) -> Dict[str, str]:
    """Generates notification email for the administrator whenever a new ticket is raised."""
    subject = f"[NexDesk AI] New Ticket Created — {ticket_number}"

    content_html = f"""
    <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 16px 0;">
      A verified employee has submitted a new IT incident ticket. Details are provided below:
    </p>

    <!-- Ticket Details Card -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; margin-bottom: 20px;">
      <tr>
        <td style="padding: 18px 20px;">
          <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px; width: 140px;"><strong>Ticket Number:</strong></td>
              <td style="font-size: 13px; color: #0F172A; font-weight: 700; padding-bottom: 8px;">{_escape(ticket_number)} (ID: #{ticket_id})</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Title:</strong></td>
              <td style="font-size: 13px; color: #0F172A; font-weight: 600; padding-bottom: 8px;">{_escape(title)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Employee:</strong></td>
              <td style="font-size: 13px; color: #334155; padding-bottom: 8px;">{_escape(employee_name)} &lt;{_escape(employee_email)}&gt;</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Category:</strong></td>
              <td style="font-size: 13px; color: #334155; padding-bottom: 8px;">{_escape(category)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Priority:</strong></td>
              <td style="font-size: 13px; color: #D97706; font-weight: 700; padding-bottom: 8px;">{_escape(priority_label)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Status:</strong></td>
              <td style="font-size: 13px; color: #2563EB; font-weight: 600; padding-bottom: 8px;">{_escape(status_label)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Created At (UTC):</strong></td>
              <td style="font-size: 13px; color: #334155; padding-bottom: 8px;">{_escape(created_at)}</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>

    <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px 18px; margin-bottom: 20px;">
      <p style="font-size: 11px; font-weight: 700; color: #64748B; text-transform: uppercase; margin: 0 0 6px 0;">Description:</p>
      <p style="font-size: 13px; color: #1E293B; line-height: 1.6; margin: 0; white-space: pre-wrap;">{_escape(description)}</p>
    </div>
    """

    text_body = f"""[NexDesk AI] New Ticket Created — {ticket_number}

Ticket ID: {ticket_number} (#{ticket_id})
Title: {title}
Employee: {employee_name} ({employee_email})
Category: {category}
Priority: {priority_label}
Status: {status_label}
Submitted At: {created_at}

Description:
{description}

Open Administrator Dashboard:
{admin_ticket_url}
"""

    html_body = _base_email_shell(
        title=f"New IT Incident: {ticket_number}",
        content_html=content_html,
        action_url=admin_ticket_url,
        action_label="Open Ticket in Admin Dashboard",
    )

    return {"subject": subject, "html_body": html_body, "text_body": text_body}


def render_employee_ticket_creation_email(
    *,
    employee_name: str,
    ticket_id: int,
    ticket_number: str,
    title: str,
    description: str,
    category: str,
    priority_label: str,
    status_label: str,
    created_at: str,
    ticket_url: str,
) -> Dict[str, str]:
    """Generates confirmation email sent to the employee after submitting a ticket."""
    subject = f"[NexDesk AI] Ticket Created Successfully — {ticket_number}"

    content_html = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6; margin: 0 0 16px 0;">
      Hello <strong>{_escape(employee_name)}</strong>,
    </p>
    <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 20px 0;">
      Your IT support ticket has been received and registered in our service management queue. An IT technician will triage your request according to the designated service level agreement (SLA).
    </p>

    <!-- Ticket Summary Card -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; margin-bottom: 20px;">
      <tr>
        <td style="padding: 18px 20px;">
          <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px; width: 140px;"><strong>Ticket Number:</strong></td>
              <td style="font-size: 13px; color: #0F172A; font-weight: 700; padding-bottom: 8px;">{_escape(ticket_number)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Issue Title:</strong></td>
              <td style="font-size: 13px; color: #0F172A; font-weight: 600; padding-bottom: 8px;">{_escape(title)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Category:</strong></td>
              <td style="font-size: 13px; color: #334155; padding-bottom: 8px;">{_escape(category)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Assigned Priority:</strong></td>
              <td style="font-size: 13px; color: #2563EB; font-weight: 600; padding-bottom: 8px;">{_escape(priority_label)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Current Status:</strong></td>
              <td style="font-size: 13px; color: #059669; font-weight: 600; padding-bottom: 8px;">{_escape(status_label)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Submission Time:</strong></td>
              <td style="font-size: 13px; color: #334155; padding-bottom: 8px;">{_escape(created_at)} UTC</td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
    """

    text_body = f"""Hello {employee_name},

Your IT support ticket has been received:

Ticket ID: {ticket_number}
Title: {title}
Category: {category}
Priority: {priority_label}
Current Status: {status_label}
Submitted At: {created_at} UTC

You can track the progress of your incident here:
{ticket_url}

Regards,
NexDesk AI IT Service Desk
{settings.SMTP_FROM_EMAIL}
"""

    html_body = _base_email_shell(
        title="Support Ticket Confirmed",
        content_html=content_html,
        action_url=ticket_url,
        action_label="View My Ticket Details",
    )

    return {"subject": subject, "html_body": html_body, "text_body": text_body}


def render_ticket_field_update_email(
    *,
    employee_name: str,
    ticket_id: int,
    ticket_number: str,
    field_name: str,
    old_value: str,
    new_value: str,
    assigned_group: Optional[str],
    updated_by_name: str,
    current_status: str,
    resolution_notes: Optional[str],
    updated_at: str,
    ticket_url: str,
) -> Dict[str, str]:
    """Generates email notification when an administrator mutates a ticket field."""
    subject = f"[NexDesk AI] Ticket {ticket_number} {field_name.capitalize()} Updated"

    notes_block = ""
    if resolution_notes:
        notes_block = f"""
        <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 10px; padding: 14px 18px; margin-top: 16px;">
          <p style="font-size: 11px; font-weight: 700; color: #065F46; text-transform: uppercase; margin: 0 0 6px 0;">Resolution Notes:</p>
          <p style="font-size: 13px; color: #064E3B; line-height: 1.5; margin: 0;">{_escape(resolution_notes)}</p>
        </div>
        """

    content_html = f"""
    <p style="font-size: 15px; color: #334155; line-height: 1.6; margin: 0 0 16px 0;">
      Hello <strong>{_escape(employee_name)}</strong>,
    </p>
    <p style="font-size: 14px; color: #334155; line-height: 1.6; margin: 0 0 20px 0;">
      Your support ticket <strong>{_escape(ticket_number)}</strong> has been updated by <strong>{_escape(updated_by_name)}</strong>.
    </p>

    <!-- Change Audit Card -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; margin-bottom: 20px;">
      <tr>
        <td style="padding: 18px 20px;">
          <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px; width: 140px;"><strong>Ticket ID:</strong></td>
              <td style="font-size: 13px; color: #0F172A; font-weight: 700; padding-bottom: 8px;">{_escape(ticket_number)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Field Changed:</strong></td>
              <td style="font-size: 13px; color: #2563EB; font-weight: 700; padding-bottom: 8px;">{_escape(field_name.capitalize())}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Previous Value:</strong></td>
              <td style="font-size: 13px; color: #64748B; text-decoration: line-through; padding-bottom: 8px;">{_escape(old_value)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>New Value:</strong></td>
              <td style="font-size: 13px; color: #059669; font-weight: 700; padding-bottom: 8px;">{_escape(new_value)}</td>
            </tr>
            {f'<tr><td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Assigned Group:</strong></td><td style="font-size: 13px; color: #0F172A; font-weight: 600; padding-bottom: 8px;">{_escape(assigned_group)}</td></tr>' if assigned_group else ''}
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Current Status:</strong></td>
              <td style="font-size: 13px; color: #0F172A; font-weight: 600; padding-bottom: 8px;">{_escape(current_status)}</td>
            </tr>
            <tr>
              <td style="font-size: 12px; color: #64748B; padding-bottom: 8px;"><strong>Updated At:</strong></td>
              <td style="font-size: 13px; color: #334155; padding-bottom: 8px;">{_escape(updated_at)} UTC</td>
            </tr>
          </table>
          {notes_block}
        </td>
      </tr>
    </table>
    """

    text_body = f"""Hello {employee_name},

Your support ticket has been updated:

Ticket ID: {ticket_number}
Field Changed: {field_name.capitalize()}
Previous Value: {old_value}
New Value: {new_value}
Current Status: {current_status}
Updated by: {updated_by_name}
Update timestamp: {updated_at} UTC
{f'Resolution notes: {resolution_notes}' if resolution_notes else ''}

You can open NexDesk AI to view the latest ticket details:
{ticket_url}

Regards,
NexDesk AI IT Service Desk
{settings.SMTP_FROM_EMAIL}
"""

    html_body = _base_email_shell(
        title=f"Ticket {ticket_number} Updated",
        content_html=content_html,
        action_url=ticket_url,
        action_label="View Updated Ticket",
    )

    return {"subject": subject, "html_body": html_body, "text_body": text_body}
