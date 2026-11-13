# Standard Operating Procedure: Corporate Wi-Fi, Ethernet & Office Network Connectivity
Document ID: SOP-NET-002
Revision: 3.4
Classification: Internal IT Knowledge Base — DEMONSTRATION DOCUMENT ONLY
Author: NexDesk Enterprise Networking & Wireless Operations

---

## 1. Supported Corporate Networks
- **SSID: `NexCorp-Secure`**
  - Encryption: WPA3-Enterprise / 802.1X EAP-TLS using corporate machine certificate distributed via MDM.
  - Recommended for: Corporate-managed laptops, tablets, and engineering endpoints.
- **SSID: `NexCorp-Guest`**
  - Captive Portal web authentication with 8-hour session lifetime.
  - Strictly isolated from corporate intranet subnets and internal servers.
- **Wired Ethernet:**
  - 802.1X port security (NAC) is enforced on all physical wall jacks. Connecting an unmanaged switch or unauthorized router will automatically shut down the switchport.

---

## 2. Common Wi-Fi Connectivity Problems & Triage

### Issue 1: "Unable to connect to this network" / Certificate Renewal
1. Check certificate status in Windows Certificate Manager (`certmgr.msc` > Personal > Certificates). Look for `NexDesk Device Intermediate CA`.
2. If expired, connect temporarily to `NexCorp-Guest` and launch Company Portal to sync MDM certificates.
3. Forget the network profile:
   ```cmd
   netsh wlan delete profile name="NexCorp-Secure"
   ```
4. Re-select `NexCorp-Secure` and authenticate.

### Issue 2: IP Address Assignment Failure (169.254.x.x APIPA)
1. Release and renew the DHCP lease:
   ```powershell
   ipconfig /release
   ipconfig /renew
   ```
2. Verify DHCP server response and default gateway reachability:
   ```powershell
   Test-NetConnection -ComputerName 10.100.0.1 -Port 53
   ```

---

## 3. Escalation & Support Assignment
- Group: **Network Support**
- Priority: P2 High for regional floor Wi-Fi degradation; P3 Medium for single-workstation adapter failures.
