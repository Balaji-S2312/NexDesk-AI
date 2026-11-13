# Standard Operating Procedure: Corporate Laptop Maintenance & Hardware Health
Document ID: SOP-HDW-021
Revision: 2.5
Classification: Internal IT Knowledge Base — DEMONSTRATION DOCUMENT ONLY
Author: NexDesk Hardware Support & Endpoint Operations

---

## 1. Scope
Applies to standard-issue company endpoints (Dell Latitude/Precision, Lenovo ThinkPad X1, Apple MacBook Pro M2/M3) distributed to all personnel.

---

## 2. Power, Battery & Thermal Management
- **Thermal Throttling & Fan Noise:**
  - Keep cooling vents clear of soft surfaces (beds, blankets). Use a flat desk surface or laptop riser.
  - Run the onboard hardware diagnostics utility (Dell SupportAssist or Apple Diagnostics by holding `D` at boot).
  - Clean external vent grills with compressed air canisters every 90 days.
- **Battery Calibration & Longevity:**
  - Avoid leaving the device plugged into a 100W dock indefinitely; enable "Primarily AC Use" battery profile in Dell Command | Power Manager or macOS Optimized Battery Charging.
  - If battery health falls below 75% capacity, schedule a battery replacement through `/my-tickets`.

---

## 3. Peripheral & Docking Station Troubleshooting
- **Dock Flickering / External Monitors Disconnecting:**
  1. Power-drain the docking station: disconnect the USB-C / Thunderbolt host cable and power adapter.
  2. Hold the dock power button down for 30 seconds to release residual capacitance.
  3. Reconnect the AC power brick first, then connect the host laptop cable.
  4. Verify that video cables are rated DisplayPort 1.4 or HDMI 2.1 certified.

---

## 4. Hardware Replacement & Repair Workflow
- Report physical damage, swollen battery, or screen artifacting immediately.
- Assigned Group: **Hardware Support**
- Priority: P2 High if work-halting; P3 Medium if peripheral or cosmetic.
