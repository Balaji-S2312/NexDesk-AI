"""Reusable HTML and plain-text email templates branded for NexDesk AI."""
from html import escape
from typing import Dict, List, Optional, Tuple


def _base_layout(
    *,
    badge_text: str,
    badge_bg: str,
    badge_fg: str,
    heading: str,
    intro: str,
    rows: List[Tuple[str, str]],
    cta_url: str,
    cta_label: str,
    extra_block_html: str = "",
    extra_block_text: str = "",
    is_verified: bool = True,
) -> Dict[str, str]:
    safe_heading = escape(heading)
    safe_intro = escape(intro)
    safe_cta_url = escape(cta_url, quote=True)
    safe_cta_label = escape(cta_label)
    safe_badge_text = escape(badge_text)

    unverified_banner_html = ""
    unverified_banner_text = ""
    if not is_verified:
        unverified_banner_html = (
            '<div style="margin:0 0 16px;padding:10px 14px;border-radius:8px;'
            'background-color:#fffbeb;border:1px solid #fde68a;color:#92400e;font-size:12px;">'
            "<strong>Unverified Email Notice:</strong> Your corporate email address is currently "
            "marked as unverified in NexDesk AI. Verify your email from Profile or Notification Centre."
            "</div>"
        )
        unverified_banner_text = (
            "[Notice] Your email address is currently marked as unverified in NexDesk AI.\n\n"
        )

    rows_html = "".join(
        f'<tr>'
        f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#64748b;font-size:13px;width:36%;font-weight:600;">{escape(label)}</td>'
        f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;color:#0f172a;font-size:13px;font-weight:500;">{escape(value)}</td>'
        f"</tr>"
        for label, value in rows
    )

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_heading}</title>
</head>
<body style="margin:0;padding:0;background-color:#f8fafc;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="padding:24px 12px;background-color:#f8fafc;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;">
          <tr>
            <td style="padding:20px 24px;background-color:#0f172a;color:#ffffff;">
              <div style="font-size:18px;font-weight:700;letter-spacing:-0.01em;">NexDesk AI</div>
              <div style="font-size:11px;color:#93c5fd;text-transform:uppercase;letter-spacing:0.08em;margin-top:2px;">Enterprise IT Service Management</div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px;">
              <div style="display:inline-block;padding:4px 10px;border-radius:999px;background-color:{badge_bg};color:{badge_fg};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px;">
                {safe_badge_text}
              </div>
              <h1 style="margin:0 0 8px;font-size:20px;line-height:1.3;color:#0f172a;">{safe_heading}</h1>
              <p style="margin:0 0 18px;font-size:14px;line-height:1.55;color:#475569;">{safe_intro}</p>
              {unverified_banner_html}
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e2e8f0;border-radius:10px;border-collapse:collapse;overflow:hidden;margin-bottom:18px;">
                {rows_html}
              </table>
              {extra_block_html}
              <div style="margin:22px 0 8px;">
                <a href="{safe_cta_url}" style="display:inline-block;padding:11px 20px;background-color:#2563eb;color:#ffffff;text-decoration:none;font-size:13px;font-weight:600;border-radius:8px;">
                  {safe_cta_label}
                </a>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding:14px 24px;background-color:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;">
              Sent automatically by NexDesk AI Notification Service. Please do not share confidential credentials via email.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    rows_text = "\n".join(f"- {label}: {value}" for label, value in rows)
    text_body = (
        f"NexDesk AI - {heading}\n\n"
        f"{unverified_banner_text}"
        f"{intro}\n\n"
        f"{rows_text}\n"
        f"{extra_block_text}\n"
        f"View Ticket: {cta_url}\n"
    )
    return {"html": html_body, "text": text_body}


def render_ticket_submission_email(
    *,
    ticket_number: str,
    title: str,
    status_label: str,
    priority_label: str,
    category_label: str,
    created_at_str: str,
    ticket_url: str,
    recipient_name: str,
    is_admin: bool = False,
    requester_name: Optional[str] = None,
    is_verified: bool = True,
) -> Dict[str, str]:
    if is_admin:
        subject = f"[NexDesk AI] New Ticket Created — {ticket_number}"
        heading = f"New Incident Submitted: {ticket_number}"
        intro = f"Hello {recipient_name}, a new support incident has been submitted and requires triage."
        rows = [
            ("Ticket ID", ticket_number),
            ("Title", title),
            ("Employee", requester_name or "Employee"),
            ("Category", category_label),
            ("Priority", priority_label),
            ("Status", status_label),
            ("Submitted At", created_at_str),
        ]
        body = _base_layout(
            badge_text="New Incident Alert",
            badge_bg="#eff6ff",
            badge_fg="#1d4ed8",
            heading=heading,
            intro=intro,
            rows=rows,
            cta_url=ticket_url,
            cta_label="Open Incident in Dashboard",
            is_verified=is_verified,
        )
    else:
        subject = f"[NexDesk AI] Ticket Created Successfully — {ticket_number}"
        heading = f"Ticket Confirmation: {ticket_number}"
        intro = f"Hello {recipient_name}, your IT support request has been registered in NexDesk AI."
        rows = [
            ("Ticket ID", ticket_number),
            ("Title", title),
            ("Current Status", status_label),
            ("Priority", priority_label),
            ("Submitted At", created_at_str),
        ]
        body = _base_layout(
            badge_text="Ticket Submitted",
            badge_bg="#eff6ff",
            badge_fg="#1d4ed8",
            heading=heading,
            intro=intro,
            rows=rows,
            cta_url=ticket_url,
            cta_label="View Ticket Status",
            is_verified=is_verified,
        )
    return {"subject": subject, **body}


def render_ticket_assignment_email(
    *,
    ticket_number: str,
    title: str,
    assigned_group: str,
    status_label: str,
    priority_label: str,
    ticket_url: str,
    recipient_name: str,
    is_admin: bool = False,
    is_verified: bool = True,
) -> Dict[str, str]:
    subject = f"[NexDesk AI] Ticket Assigned: {ticket_number}"
    heading = f"Ticket Assigned: {ticket_number}"
    intro = (
        f"Hello {recipient_name}, incident {ticket_number} has been routed to {assigned_group}."
        if is_admin
        else f"Hello {recipient_name}, your ticket has been assigned to an IT support group."
    )
    body = _base_layout(
        badge_text="Ticket Assigned",
        badge_bg="#eef2ff",
        badge_fg="#4338ca",
        heading=heading,
        intro=intro,
        rows=[
            ("Ticket ID", ticket_number),
            ("Title", title),
            ("Assigned Support Group", assigned_group),
            ("Status", status_label),
            ("Priority", priority_label),
        ],
        cta_url=ticket_url,
        cta_label="Open Ticket Details",
        is_verified=is_verified,
    )
    return {"subject": subject, **body}


def render_ticket_status_email(
    *,
    ticket_number: str,
    title: str,
    old_status_label: str,
    new_status_label: str,
    priority_label: str,
    ticket_url: str,
    recipient_name: str,
    is_verified: bool = True,
) -> Dict[str, str]:
    subject = f"[NexDesk AI] Ticket {ticket_number} Status Updated"
    heading = f"Status Updated: {ticket_number}"
    intro = f"Hello {recipient_name}, your support ticket status has changed from {old_status_label} to {new_status_label}."
    body = _base_layout(
        badge_text="Status Updated",
        badge_bg="#f0f9ff",
        badge_fg="#0369a1",
        heading=heading,
        intro=intro,
        rows=[
            ("Ticket ID", ticket_number),
            ("Title", title),
            ("Previous Status", old_status_label),
            ("Latest Status", new_status_label),
            ("Priority", priority_label),
        ],
        cta_url=ticket_url,
        cta_label="Track Ticket Progress",
        is_verified=is_verified,
    )
    return {"subject": subject, **body}


def render_ticket_resolution_email(
    *,
    ticket_number: str,
    title: str,
    status_label: str,
    resolution_notes: str,
    resolved_at_str: str,
    ticket_url: str,
    recipient_name: str,
    is_admin: bool = False,
    is_verified: bool = True,
) -> Dict[str, str]:
    subject = f"[NexDesk AI] Ticket Resolved: {ticket_number}"
    heading = f"Incident Resolved: {ticket_number}"
    intro = (
        f"Hello {recipient_name}, incident {ticket_number} has been marked as resolved."
        if is_admin
        else f"Hello {recipient_name}, your IT support ticket has been resolved. Please review the resolution notes below."
    )
    safe_notes = escape(resolution_notes or "Resolution completed by support team.")
    extra_html = (
        '<div style="padding:14px;border-radius:10px;background-color:#ecfdf5;border:1px solid #a7f3d0;">'
        '<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#065f46;margin-bottom:6px;">Resolution Notes</div>'
        f'<div style="font-size:13px;line-height:1.5;color:#064e3b;white-space:pre-wrap;">{safe_notes}</div>'
        "</div>"
    )
    extra_text = f"\nResolution Notes:\n{resolution_notes or 'Resolution completed by support team.'}\n"
    body = _base_layout(
        badge_text="Ticket Resolved",
        badge_bg="#ecfdf5",
        badge_fg="#047857",
        heading=heading,
        intro=intro,
        rows=[
            ("Ticket ID", ticket_number),
            ("Title", title),
            ("Status", status_label),
            ("Resolved At", resolved_at_str),
        ],
        cta_url=ticket_url,
        cta_label="View Resolution Details",
        extra_block_html=extra_html,
        extra_block_text=extra_text,
        is_verified=is_verified,
    )
    return {"subject": subject, **body}
