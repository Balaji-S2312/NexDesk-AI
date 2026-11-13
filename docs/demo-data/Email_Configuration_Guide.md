# Standard Operating Procedure: Corporate Email & Calendar Configuration (Exchange / Outlook / Mobile)
Document ID: SOP-EML-008
Revision: 3.0
Classification: Internal IT Knowledge Base — DEMONSTRATION DOCUMENT ONLY
Author: NexDesk Unified Communications & Collaboration Group

---

## 1. Supported Clients & Protocols
- **Desktop:** Microsoft 365 Outlook for Windows (v2402+), Outlook for Mac (v16.84+), or Outlook on the Web (`https://outlook.office.com`).
- **Mobile:** Microsoft Outlook for iOS and Android with Microsoft Authenticator / Intune Company Portal installed.
- **Protocols:** Modern Exchange Web Services (EWS) / Microsoft Graph with OAuth 2.0. Legacy POP3 and IMAP4 are disabled by corporate tenant security policy.

---

## 2. Desktop Outlook Profile Repair
If Outlook freezes upon opening, prompts repeatedly for credentials, or fails to synchronize calendar invites:
1. Close Outlook completely (`taskkill /F /IM outlook.exe`).
2. Start Outlook in Safe Mode: press `Win + R`, type `outlook.exe /safe`, and click **OK**.
3. If safe mode succeeds, disable third-party COM Add-ins under **File > Options > Add-ins > COM Add-ins > Go**.
4. Rebuild the offline data cache (`.ost` file):
   - Navigate to `%LOCALAPPDATA%\Microsoft\Outlook`
   - Rename `your_email@nexdesk.ai.ost` to `your_email@nexdesk.ai.ost.old`
   - Restart Outlook to force a fresh mailbox sync from Exchange Online.

---

## 3. Mobile Configuration & Intune Enrollment
1. Install **Microsoft Outlook** and **Company Portal** from Google Play Store or Apple App Store.
2. Sign in with your work email (`@nexdesk.ai`).
3. Approve Intune App Protection policies and set an application PIN (min 6 digits).
4. Do not attempt native iOS Mail or Gmail app synchronization without corporate MDM approval.

---

## 4. Escalation
- Group: **Software Support**
- Priority: P3 Medium (or P2 High for executive and VIP mailbox interruptions).
