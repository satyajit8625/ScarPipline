# 👑 ScarTools — Studio Admin License Guide

> **CONFIDENTIAL — ADMIN & LEAD TD ONLY**  
> Keep this folder (`admin_tools/`) on the lead/admin machine only. Never distribute to artists.

---

## ⚡ Quick 3-Step Licensing Workflow

### Step 1: Artist Gets Machine HWID
When an artist opens ScarTools in Maya without an active license, the **Activation Dialog** opens automatically displaying their **Hardware ID** (e.g. `HW-8F924B11`).  
*The artist sends you their **Username** and **HWID**.*

---

### Step 2: Admin Generates the License Key
Open a terminal in the `admin_tools/` folder and run the generator:

#### Option A: Interactive Wizard (Easiest)
```bash
python generate_studio_license.py
```
*Prompts you step-by-step for Username, Machine HWID, and Expiry Days.*

#### Option B: Fast 1-Line Commands
- **Permanent In-House Seat (Perpetual):**
  ```bash
  python generate_studio_license.py --user john.doe --hwid HW-8F924B11 --perpetual
  ```
- **Time-Limited Contractor Lease (Days):**
  ```bash
  python generate_studio_license.py --user jane.smith --hwid HW-7F1188EE --days 30
  ```
- **Short Evaluation / Testing Seat (Hours or Minutes):**
  ```bash
  # 2 Hours lease:
  python generate_studio_license.py --user test.artist --hwid HW-8F924B11 --hours 2

  # 30 Minutes lease (or --duration 30m):
  python generate_studio_license.py --user test.artist --hwid HW-8F924B11 --minutes 30
  ```

---

### Step 3: Artist Activates in Maya
Send the generated `SCAR-XXXX...` key back to the artist.  
The artist pastes the key into Maya's **Activation Dialog** and clicks **Activate License**.

---

## 📋 Managing Seats & Enforcement (`manage_licenses.py`)

Every generated key is automatically logged in `studio_licenses_registry.json`.

### 🛡️ Two Levels of Enforcement: Revoke vs Delete

| Level | Action | What Happens on Artist Workstation | Command |
| :--- | :--- | :--- | :--- |
| **Soft Lock** | **Revoke** | Locks the tool UI and prompts for license reactivation. Installed files remain on disk. | `python manage_licenses.py --revoke-user <user>` |
| **Hard Kill-Switch** | **Delete / Purge** | **Permanently deletes and wipes** all local ScarTools files, modules, shelves, and licenses from the artist's computer. | `python manage_licenses.py --delete-user <user>` |

---

### 💻 Quick Command Cheat Sheet

| Task | Command |
| :--- | :--- |
| **View all issued seats** | `python manage_licenses.py --list` |
| **Revoke seat (Soft Lock)** | `python manage_licenses.py --revoke-user john.doe` |
| **Revoke by Machine HWID** | `python manage_licenses.py --revoke-hwid HW-8F924B11` |
| **Delete & Wipe PC (Kill-Switch)** | `python manage_licenses.py --delete-user contractor.rig` |
| **Delete & Wipe by HWID** | `python manage_licenses.py --delete-hwid HW-B2D94411` |
| **Reinstate seat back to Active** | `python manage_licenses.py --reinstate-user john.doe` |
| **Inspect local PC license** | `python manage_licenses.py --local` |
| **Deactivate license on local PC** | `python manage_licenses.py --deactivate-local` |
| **Export seat audit to CSV** | `python manage_licenses.py --export-csv studio_audit.csv` |
| **Sync updates to GitHub Cloud** | `python sync_cloud_licenses.py` |

---

## 🌐 Worldwide GitHub Cloud License Sync (`sync_cloud_licenses.py`)

To control remote artists working from home across different networks or cities:
1. Run any management command (e.g. `python manage_licenses.py --delete-user <user>`).
2. Run:
   ```bash
   python sync_cloud_licenses.py
   ```
3. The license registry is pushed to `https://github.com/satyajit8625/scartools-licenses`.
4. Remote artists' Maya sessions query the public GitHub raw endpoint and execute the kill-switch worldwide in **under 1 second**.

---

## 🔒 Security Rules & Anti-Tamper Defense

1. **Single-Seat Hardware Lock (HWID)**: Each key is cryptographically bound to the physical motherboard and CPU of that exact machine. Keys cannot be copied to other laptops or PCs.
2. **Out-of-Process Firewall Bypass Probe**: Maya probes the cloud registry outside of `maya.exe` via Windows system utilities, defeating attempts to block the kill-switch via outbound Windows Firewall rules on Maya.
3. **15-Day Mandatory Online Heartbeat**:
   - If an artist disconnects from the internet or blocks Maya to evade revocation, the workstation is granted an offline grace period.
   - If the machine remains offline for longer than the heartbeat limit, the suite automatically **locks down and permanently shreds all local tool files offline**.
4. **Real-Time Remote Wipe (Zero-Fill Kill-Switch)**:
   - When an admin deletes a user, Maya overwrites all files with `0-byte` data before deletion, unloads the module, deletes shelves, and disables the machine.
5. **Anti-Clock Rollback Trap**: Detects if an artist sets their system clock backwards in time and immediately disables the suite.
