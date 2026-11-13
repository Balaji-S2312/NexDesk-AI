# Standard Operating Procedure: Corporate VPN Troubleshooting (GlobalProtect & OpenVPN)
Document ID: SOP-NET-014
Revision: 3.2
Classification: Internal IT Knowledge Base — DEMONSTRATION DOCUMENT ONLY
Author: NexDesk IT Infrastructure & Network Engineering Group

---

## 1. Scope & Objective
This runbook provides tier-1 and tier-2 operational guidance for diagnosing and resolving remote employee connectivity issues with corporate Virtual Private Network (VPN) gateways across corporate laptops running Windows 11, macOS, and Linux.

---

## 2. Common Symptoms & Root Causes
- **Symptom 1: "Authentication Failed / SAML SSO Loop"**
  - *Root Cause:* Cached browser credentials expired in local credential store, MFA token desynchronization, or Okta session timeout.
- **Symptom 2: "Gateway Timeout (504) / Connection Failed"**
  - *Root Cause:* Regional gateway congestion (vpn-east.nexdesk.ai), stale local DNS cache, or ISP UDP port 4500/500 packet throttling.
- **Symptom 3: "Connected but No Internal Intranet Access (Split Tunneling Failure)"**
  - *Root Cause:* Virtual network adapter metric conflict, stale routing table, or IPv6 leakage.

---

## 3. Tier-1 Employee Self-Service Troubleshooting Steps

### Step 1: Clear Local DNS Cache and Flush Adapter
Open Windows Terminal or PowerShell as Administrator and execute:
```powershell
ipconfig /flushdns
ipconfig /registerdns
netsh winsock reset
```
On macOS / Linux:
```bash
sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```
Reboot the laptop to reset the virtual network interface.

### Step 2: Clear VPN Client Authentication Cache
1. Open the **GlobalProtect** or **OpenVPN Client** taskbar menu.
2. Select **Settings > General > Sign Out**.
3. Clear default browser cookies for `okta.nexdesk.ai` and `sso.nexdesk.ai`.
4. Re-launch the client and authenticate with your corporate SSO credentials and 2FA Push.

### Step 3: Switch Regional Gateway
If `vpn-primary.nexdesk.ai` is unresponsive:
1. In GlobalProtect settings, select **Portal / Gateway**.
2. Switch portal to the alternate secondary gateway:
   - Primary: `vpn-east.nexdesk.ai`
   - Secondary: `vpn-west.nexdesk.ai`
   - Disaster Recovery: `vpn-emea.nexdesk.ai`
3. Click **Connect**.

---

## 4. Tier-2 Escalation Protocol
If troubleshooting fails:
1. Open an IT incident via NexDesk AI portal (`/ai-support`).
2. Provide the local client IP, router public IP (`curl ifconfig.me`), and client export logs (`gp-troubleshoot.log`).
3. Routing: Incidents with verified gateway timeouts or SAML errors must be assigned to **Network Support** with **P2 High** priority if business productivity is blocked.
