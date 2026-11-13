# Standard Operating Procedure: Corporate Identity & Password Reset
Document ID: SOP-SEC-009
Revision: 4.1
Classification: Internal IT Knowledge Base — DEMONSTRATION DOCUMENT ONLY
Author: NexDesk IT Security & Identity Management Operations

---

## 1. Overview & Policy Requirements
Corporate password policies require a minimum length of 14 characters, containing at least 3 character classes (uppercase, lowercase, numerals, symbols). Passwords expire every 90 days. Passwords cannot match the prior 12 entries.

---

## 2. Self-Service Self-Service Password Reset (SSPR)
1. Navigate to `https://identity.nexdesk.ai/sspr` or access the **NexDesk AI Chat Assistant**.
2. Enter your corporate UPN email (`firstname.lastname@nexdesk.ai`).
3. Complete the multi-factor authentication prompt on your registered mobile authenticator app (Okta Verify or Google Authenticator) or security hardware key (YubiKey 5C).
4. Enter and confirm your new passphrase.
5. Wait 3 minutes for Active Directory (AD) synchronization across Azure AD / Okta connectors.

---

## 3. Account Lockout Remediation
- **Threshold:** 5 consecutive invalid authentication attempts lock the user account for 30 minutes.
- **Immediate Unlock:** Access the self-service portal or request an automated unlock through the NexDesk AI bot by asking: *"My account is locked after typing the wrong password"*.
- **Admin Verification:** If self-service verification fails, contact the IT Service Desk. An engineer will perform an out-of-band video or voice verification before resetting the account password.

---

## 4. Key Escalation Contacts
- Group: **Access Management**
- SLA: P3 (4-hour response, 24-hour resolution under standard 9x5 business hours).
