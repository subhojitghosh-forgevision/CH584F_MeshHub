# CH584F Mesh Hub: system design

- **Status:** draft for review. Sections 3–5 were approved in chat on 2026-10-03; sections 6–11 are new for review here.
- **Date:** 2026-10-03
- Amended 2026-10-04 after Step 0 spike (spike/REPORT.md): amendments A1–A14.
- **Scope of this document:** the whole system and the feasibility spike (step 0). Each later
  sub-project (firmware, app core, OTA, history/export) gets its own spec and plan.

## 1. Purpose

This is a **product prototype**. An **Android** app acts as the hub for **three WeAct Studio CH584F**
boards. The boards form a Bluetooth mesh and simulate temperature and humidity sensors. The phone
uses a single connection to manage all three boards and to send them custom data. The boards
exchange readings and react to each other.

## 2. Requirements

### 2.1 Stated by the user

| # | Requirement |
|---|---|
| R1 | An Android app (only) is the central hub. It has three separate controls, one panel per board. |
| R2 | The phone sends **commands/settings**, **free-form messages**, and **broadcasts** to all boards. |
| R3 | Each board simulates **temperature and humidity**. |
| R4 | The phone connects to **one gateway board**; the mesh carries traffic to and from the other two. |
| R5 | Mesh goals: **range extension**, **shared readings**, and **board reactions** (threshold rules). Board-to-board free-form messages are not required. |
| R6 | Product features in the first prototype: **secure commissioning**, **OTA updates**, **history + CSV export**, and **rename from the app**. |
| R7 | Commissioning authentication uses **static OOB with a per-board QR label**. |

### 2.2 Confirmed assumptions

| # | Assumption |
|---|---|
| A1 | Free-form messages are short: at most 200 bytes of UTF-8. |
| A2 | Readings arrive every few seconds (default 5 s, configurable from 1 to 3600 s). |
| A3 | Reactions are threshold rules set from the app. |
| A4 | History is stored on the phone only; there is no cloud. |
| A5 | The Android build tools are installed on the development PC, with the user's permission. The user's phone is used for testing. |
| A6 | The user flashes the boards and runs the hardware tests. |

### 2.3 Success criteria

From the phone the user can:

1. securely add three boards by scanning their QR labels;
2. name each board;
3. see live temperature and humidity from all three boards through **one** connection;
4. send a command, a text message, and a broadcast to any or all boards, with delivery feedback for unicast sends;
5. see a threshold rule on one board react to another board's reading;
6. review history charts and export them as CSV;
7. update a board's firmware over the air without losing its network membership.

## 3. Architecture (approved)

### 3.1 Roles

| Element | Role |
|---|---|
| Android app | Mesh **provisioner**, **configuration client**, and **proxy client** (unicast `0x0001`). Holds the network database. |
| Board (×3, identical firmware) | Mesh node with **relay** on and **GATT proxy** on. PB-GATT provisioning is on only while unprovisioned. Friend and LPN are off. One element containing the Config Server, the Health Server, and the **WCH vendor model server** (CID `0x07D7`, model `0x0000`). |
| Gateway | Whichever board the app is currently connected to as proxy (strongest RSSI). Any board can take this role. |

### 3.2 Addresses

| Address | Use |
|---|---|
| `0x0001` | Phone (provisioner) |
| `0x0002`… | Boards, assigned by the app during provisioning |
| `0xC000` "All boards" | Broadcast commands and text. All boards subscribe to it. |
| `0xC001` "Readings" | Every board publishes READING and RULE_EVENT messages here. All boards subscribe to it (for shared readings). The phone adds it to its proxy filter. |

### 3.3 Mapping requirements to mechanisms

| Requirement | Mechanism |
|---|---|
| R1 panels | Unicast vendor messages to each board |
| R2 broadcast | Vendor messages to `0xC000` |
| R4/R5 range extension | Relay on every board; the phone reaches any board through the gateway |
| R5 shared readings | `0xC001` subscription on every board |
| R5 reactions | Rule engine on each board evaluates every READING it receives |

## 4. Data protocol (approved)

### 4.1 Framing

The firmware uses the official WCH vendor model from `EVT/EXAM/BLE/MESH/adv_vendor` without changes:

- **Opcodes** (3-byte vendor opcodes, CID `0x07D7`):
  - `MSG` `0xCF`: unacknowledged
  - `WRT` `0xCC` → `CFM` `0xCB`: acknowledged write (the server confirms with the received TID)
  - `IND` `0xCE` → `ACK` `0xCD`: indication (the client acknowledges)
- **Access payload:** `opcode (3) | TID (1) | application payload`. The server drops duplicates by (TID, source).
  TIDs follow WCH's ranges: **clients (the app) cycle 0–127** (as `vendor_cli_tid_get()` does) and the server cycles 128–191.
  **A `CFM` confirms receipt, not execution:** the server confirms a duplicate without running it and keeps only the last (TID, source) pair, in RAM. The app therefore persists its TID counter per network (or starts each session at a random TID), so that a restart never repeats the last TID. The app drops a board's repeated copies by (source, server TID) within a 3 s window; the window is kept short so that a board's server TID restarting after a reboot is not taken as a duplicate.
- All multi-byte fields are **little-endian**.

The application payload is defined below.

### 4.2 Delivery rules

| Traffic | Opcode | Semantics |
|---|---|---|
| Command or text to **one** board | `WRT` | Acknowledged. The app shows *delivered* (the board confirmed receipt, section 4.1) or *not delivered*. WCH retransmission is used. The firmware passes `WRT` to its own dispatcher in `proto.c`, which has a buffer sized for the RX SDU and per-type length checks. It does not use WCH's `App_trans_model_reveived`, which copies messages without a length check (WCH's example handled only `MSG`). Commands that reset the board (OTA end, factory reset) are never confirmed; the app treats a missing `CFM` for them as expected. |
| Command or text to **all** (`0xC000`) | `MSG` | Best effort: the WCH send is repeated 5 times. The app shows *sent*. Boards **do not reply** to group-addressed requests. |
| READING, RULE_EVENT (to `0xC001`) | `MSG` | Periodic or event-driven; loss is tolerated. Sent once (send count 1), not WCH's default of 5 copies 500 ms apart. |
| INFO, RESULT (reply to a unicast request) | `MSG` | Sent to the requester's address (`ctx->addr`). |

### 4.3 Payload types

| Type | Name | Layout (byte offsets within the application payload) |
|---|---|---|
| `0x01` | READING | `[0]=0x01`, `[1..2]` temperature, int16, 0.01 °C; `[3..4]` humidity, uint16, 0.01 %RH; `[5]` sequence, uint8. **6 bytes**, so it fits an unsegmented access message (3 + 1 + 6 = 10 ≤ 11). |
| `0x02` | INFO | `[0]=0x02`, `[1]` protocol version (=1), `[2..3]` firmware version (major<<8 \| minor), `[4..5]` interval in s, `[6]` LED (0/1), `[7]` rule count, `[8]` name length (0–20), `[9..]` name (UTF-8) |
| `0x10` | COMMAND | `[0]=0x10`, `[1]` command, `[2..]` arguments (see 4.4) |
| `0x11` | RESULT | `[0]=0x11`, `[1]` command, `[2]` status: 0 OK, 1 BAD_ARGS, 2 UNSUPPORTED, 3 STORAGE_ERROR |
| `0x20` | TEXT | `[0]=0x20`, `[1..]` UTF-8, 1–200 bytes. The board stores the last text, logs it on the UART, and blinks the LED twice. |
| `0x30` | RULE_EVENT | `[0]=0x30`, `[1]` rule index, `[2]` state (0 released, 1 triggered), `[3..4]` source address of the reading that caused it |

Unknown types or commands get RESULT UNSUPPORTED (unicast requests only) and are otherwise ignored.

### 4.4 Commands

| Command | Name | Arguments |
|---|---|---|
| `0x01` | LED | `[2]` 0 off, 1 on, 2 toggle, 3 identify (blink for 5 s) |
| `0x02` | SET_INTERVAL | `[2..3]` uint16 seconds, 1–3600 |
| `0x03` | SET_NAME | `[2]` length 1–20, `[3..]` UTF-8 |
| `0x04` | GET_INFO | none; the reply is INFO |
| `0x05` | RULE_SET | `[2]` index 0–3, `[3..4]` source unicast address, `[5]` metric (0 temperature, 1 humidity), `[6]` comparison (0 `>`, 1 `<`), `[7..8]` int16 threshold in 0.01 units, `[9]` action (0 LED off, 1 LED on) |
| `0x06` | RULE_CLEAR | `[2]` index 0–3, or `0xFF` for all |
| `0x07` | READ_NOW | none; the board publishes a READING immediately |
| `0x08` | FACTORY_RESET | `[2]` must be `0xA5`. The board answers RESULT OK, then leaves the network. Its settings are erased; the factory page is kept. |

### 4.5 Rule semantics

- A rule fires when the source board's metric **crosses** the threshold in the stated direction.
- A rule releases when the value returns past the threshold by the hysteresis: **0.5 °C** for temperature, **2 %RH** for humidity.
- Each transition emits RULE_EVENT and applies the action. A manual LED command overrides the LED until the next rule transition.
- Rules are evaluated for every READING received, including the board's own.

### 4.6 Mesh stack settings

| Setting | Value | Reason |
|---|---|---|
| `CONFIG_MESH_UNSEG_LENGTH_DEF` | **7** | SIG standard, required for interoperating with the phone |
| `CONFIG_MESH_RX_SDU_DEF` | **256** | So that a 200-byte TEXT fits (example default is 192) |
| Default TTL | **5** | |

## 5. Commissioning and security (approved)

### 5.1 Factory step (once per board)

A Python script, `factory/make_board.py`, produces a **DataFlash file** for WCHISPTool and a **QR label** for each board. It generates:

- a random 16-byte **device UUID**;
- a random 16-byte **static OOB** value;
- a **serial number** (for example `MH-0001`).

These are written to a **factory page** in DataFlash with a magic number, a format version, and a CRC32.

The QR payload is `MHUB1:<serial>:<UUID hex>:<OOB hex>`. **The label is a secret**: anyone holding it can authenticate that board.

### 5.2 Provisioning

1. The app scans the QR code.
2. The app finds the unprovisioned device advertising **that UUID** (PB-GATT).
3. The app provisions it with ECDH P-256 and **static OOB** authentication.
4. The board receives the NetKey and its unicast address. A per-node **device key** is derived.

A board with no valid factory page **refuses provisioning** and shows the error pattern: three fast LED blinks every 2 s.

**Limit (spike F1):** MESH_LIB V1.79 cannot require OOB, so a provisioner that chooses No OOB is accepted. Static OOB proves the board to our app, but another phone can claim an unprovisioned board. Mitigation: provisioning is open only for 3 minutes after power-up or a BOOT short press, then closed with `bt_mesh_beacon_disable()` and `bt_mesh_proxy_prov_disable()`. A provisioner that already knows the UUID can still reach the board over PB-ADV, so this narrows the risk rather than removing it. It is tested in the firmware sub-project.

### 5.3 Configuration after provisioning (app, Config Client)

1. Add the AppKey.
2. Bind the AppKey to the vendor server.
3. Subscribe to `0xC000` and `0xC001`.
4. Set publication to `0xC001`.
5. Set relay = on, proxy = on, default TTL = 5.

The app tracks which steps have completed and resumes after a failure.

### 5.4 Keys and storage

- The NetKey and AppKey are random per network, generated by the app. **No keys exist in the firmware.** The SDK example's self-configuration (`cfg_local_net_info()`, which adds a published app key at index 1 and binds it to the vendor model's only key slot) is removed (spike F2).
- The gateway link is the mesh proxy, so all traffic is mesh-encrypted. BLE legacy pairing is not used, because the WCH BLE library lacks LE Secure Connections.
- The network database is kept in app-private storage. **Android auto-backup is disabled for it.**
- Network export (JSON) requires an explicit action and shows a warning that the file contains keys.
- Release firmware never prints key material on the UART.

### 5.5 Removal

- **From the app:** Config Node Reset.
- **On the board:** hold BOOT (PB22) for 10 s at runtime. This wipes the provisioning data and settings except the factory page. Holding BOOT at power-up still enters the USB bootloader.

## 6. Board firmware (for review)

### 6.1 Base

The firmware combines three official WCH sources:

- the update-capable (OTA) layout and ROM libraries from `adv_vendor_self_provision_with_peripheral`, `adv_vendor_self_provision_IAP` and `adv_vendor_self_provision_JumpIAP`;
- the proxy and PB-GATT configuration from `adv_proxy`;
- the vendor server from `adv_vendor`.

Board adaptations, as in the earlier projects:

- RAM sized for the CH584;
- `CLK_OSC32K=0`, `DCDC_ENABLE=1`, plus an explicit `PWR_DCDCCfg(ENABLE)` in `main()` (the define alone does nothing);
- `CHIP_ID` = `ID_CH584` (`0x92`) in `CONFIG.h` (the example reports `ID_CH585`); the image-info high byte uses `CHIP_ID >> 8`;
- without the example's self-configuration (`APP_NODE_EVT` → `cfg_local_net_info()`) and without its custom peripheral (`0xFFE0`);
- `HSECap_10p`;
- WeAct `KEY.c`/`KEY.h`;
- LED on PB6, active low.

Libraries: `CH58xBLE_ROM`, `CH58xMESHROM`, `ISP585`. `LIB_FLASH_BASE_ADDRESSS=0x0004E000`.

### 6.2 Code flash layout (448 KB, WCH OTA scheme)

| Start | Size | Content |
|---|---|---|
| `0x00000` | 4 KB | JumpIAP |
| `0x01000` | 152 KB | **Application.** WCH's comparable image is about 99 KB. |
| `0x27000` | 152 KB | Update buffer |
| `0x4D000` | 4 KB | IAP (installer) |
| `0x4E000` | 136 KB | BLE + mesh ROM library (`CH584BLE_ROM_MESH.hex`) |

The **RAM** region must fit the CH584's 96 KB. WCH's CH585 layout gives the application 108 KB from
`0x20005000`; the CH584 equivalent is about 76 KB. The spike verifies this.

### 6.3 DataFlash usage

| Area | Constraint |
|---|---|
| Mesh settings | First 12 KB (WCH default: 3 × 4 KB sectors from offset 0) |
| OTA ImageFlag | Offset `0x7000` (`OTA_DATAFLASH_ADD`), one page, used by the IAP. BLE SNV, whose default is also `0x7000`, is disabled: no bonding is used. |
| Application settings | One page: name, interval, rules. Versioned record with CRC. |
| Factory page | One page: UUID, OOB, serial. CRC protected and never erased by a factory reset. |

The exact offsets of the last two areas are fixed in the firmware sub-project spec, subject to these constraints.

### 6.4 Modules

| Module | Responsibility |
|---|---|
| `app.c` | Mesh initialisation, provisioning callbacks, static OOB and UUID from the factory page |
| `app_vendor_model_srv.c` | Official WCH vendor server (unchanged) |
| `proto.c` | Pure encode/decode of section 4. No hardware access. |
| `sensors_sim.c` | Bounded random walk: temperature 20.00–35.00 °C, humidity 30.00–80.00 %RH. Seeded from the chip unique ID. Publishes every *interval*. |
| `rules.c` | 4 rules, hysteresis, evaluation, RULE_EVENT |
| `settings.c` | Application settings page |
| `factory.c` | Reads and validates the factory page |
| `board.c` | LED, BOOT long-press factory reset, error blink |
| OTA commands | WCH IAP scheme: commands `0xA6`–`0xA9` from vendor messages, no separate GATT service. WCH's handler is hardened or replaced in the OTA sub-project: length checks, address range limited to the update buffer, unicast only. |

### 6.5 Names

The board name is stored in the settings, reported in INFO, and used as the **GAP device name**.
The library exposes `bt_mesh_proxy_set_adv_rsp()` (scan response, at most 31 bytes; spike S6), so the firmware
also puts the name in the proxy scan response; this is tested in the firmware sub-project. The app always
shows names from INFO.

## 7. OTA (for review)

- **OTA runs over the mesh.** The phone sends WCH's OTA commands (`0xA6` begin, which **erases the update buffer**; `0xA7` write; `0xA8` verify; `0xA9` end) as vendor `WRT` messages through its gateway proxy to any board. No second GATT service is needed (spike T8–T11).
- The image is written to the update buffer and verified. The IAP installs it on reboot. Provisioning data in DataFlash is preserved.
- **Throughput:** the spike installed a pre-loaded image; the block transfer over the mesh is measured first in the OTA sub-project.
- **Install guard:** `0xA9` after `0xA6` without a fully written and verified image would make the IAP install an erased image, because it copies without checks. That board is dead until a USB reflash. The board therefore checks the image length and a CRC before `0xA9` switches the image flag, and the app sends `0xA9` only after a passing verify.
- **Integrity:** WCH's verify (`0xA8`) is a host-driven read-back compare, plus a version check. **Signed images are an open item** (section 13) that a product requires.
- **Initial flashing:** WCHISPTool, with Object Files 1–4 (JumpIAP, application, IAP, ROM library) plus the board's DataFlash file. **Clear DataFlash** is ticked, and the per-board DataFlash file re-writes the factory page.

## 8. Android app (for review)

### 8.1 Stack

- Kotlin, Jetpack Compose, MVVM.
- **nordicsemi/Android-nRF-Mesh-Library** (BSD-3-Clause) for provisioning, configuration, proxy and vendor messages.
- **nordicsemi/Android-BLE-Library** (BSD-3-Clause) for OTA.
- **Room** (AndroidX, Apache-2.0) for storage.
- **Vico** (Apache-2.0) for charts.
- **zxing-android-embedded** (Apache-2.0) for QR scanning.

minSdk is 26 unless a library requires more. targetSdk is the latest stable. Permissions: `BLUETOOTH_SCAN`
and `BLUETOOTH_CONNECT` (Android 12+), location for scanning on Android 11 and older, and `CAMERA`.

### 8.2 Packages

| Package | Responsibility |
|---|---|
| `mesh/` | Create and load the network; provision with QR static OOB; resumable configuration; choose the gateway (strongest proxy) and auto-reconnect; proxy filter {`0x0001`, `0xC001`}: WCH nodes accept proxy configuration only with the network nonce (spike F3), so test the chosen Nordic library version first, then patch it or have boards also send READINGs to the hub's unicast address; unsolicited vendor messages are read in `onUnknownPduReceived(src, accessPayload)`; WCH vendor send/receive and TID management (persisted counter, 3 s duplicate window) |
| `protocol/` | Kotlin codec for section 4. Must pass the **same test-vector file** as `proto.c`. |
| `data/` | Room entities: boards, readings, rules, events. History retention is 30 days. |
| `ota/` | WCH OTA protocol |
| `ui/` | Screens (8.3) |

### 8.3 Screens

| Screen | Contents |
|---|---|
| **Home** | Current gateway. **Three board panels**, each with name, live temperature/humidity, last seen or stale, an LED toggle, and quick actions. |
| **Board detail** | Send text, set interval, rename, rules editor, info, OTA, remove |
| **Broadcast** | Command or text to all boards |
| **History** | Per-board charts, time range, **CSV export** through the share sheet |
| **Network** | Add a board (QR scan), gateway status, network export (with warning) |

The app collects data only while it is open. A background service is out of scope.

## 9. Error handling (for review)

| Situation | Behaviour |
|---|---|
| Unicast `WRT` without `CFM` | *Not delivered*, with a Retry button. No silent queue. |
| No READING for 3 × the interval | The panel is marked **stale** |
| Gateway lost | Auto-reconnect to the next strongest proxy. The UI shows the new gateway. |
| Provisioning or configuration fails | A specific message (bad QR, UUID not found, timeout). Configuration resumes from the failed step. A wrong OOB arrives as Provisioning Failed code `0x00` "Prohibited" (not `0x04`), so any provisioning failure is reported as "wrong label or board refused". |
| Bad command arguments, or a storage failure | RESULT BAD_ARGS or STORAGE_ERROR |
| OTA fails | The board keeps running its old image. The app offers a retry. |

## 10. Testing (for review)

| Level | Method |
|---|---|
| Protocol | `protocol/test-vectors.json` is the single source of truth. Kotlin unit tests run on the PC. The C codec is tested by a **self-test firmware build** that runs the same vectors on a board and prints PASS/FAIL over the UART, because no host C compiler is installed. |
| Firmware | Every build checks flash ≤ 152 KB and RAM within the CH584 region. Self-test build for `proto.c`, `rules.c`, `sensors_sim.c` bounds. |
| App | JVM unit tests: codec, stale detection, CSV export, rule-form validation. Compose UI tests for the Home panels. |
| System | A written end-to-end checklist derived from the success criteria (2.3), run with three boards and the user's phone. |

## 11. Step 0: feasibility spike (for review)

**Status:** done 2026-10-04. Results and go/no-go: `spike/REPORT.md`.

- **Throwaway code, one board.** The phone side uses the existing **nRF Mesh** app, which is built on the same Nordic library, so no app needs to be built for the spike.
- **Output:** a short report giving go/no-go for each item, plus any amendments to this spec.

| ID | Check | Pass criterion |
|---|---|---|
| S1 | ROM-library OTA layout builds for the CH584 | Links with the application ≤ 152 KB and RAM within 96 KB |
| S2 | Static OOB provisioning | nRF Mesh provisions the board using the static OOB value |
| S3 | Vendor message interop | nRF Mesh vendor-model control sends `WRT` (`0xCC`, CID `0x07D7`) with a TID. The board handles it and the app receives `CFM` (`0xCB`). |
| S4 | Readings to the phone | A board `MSG` to `0xC001` is visible in nRF Mesh through the proxy |
| S5 | OTA over the mesh | A test image is installed by vendor command and the board keeps its provisioning. |
| S6 | Name in advertising (nice to have) | The device name appears in the proxy scan response |

## 12. Delivery plan

| Step | Sub-project | Depends on |
|---|---|---|
| 0 | Spike (section 11) | none |
| 1 | Board firmware + factory script | Spike S1–S4 |
| 2 | Android app core: commissioning, gateway, panels, commands, text, broadcast, rename, rules | 1 |
| 3 | OTA end to end | Spike S5, then 1 and 2 |
| 4 | History + CSV export | 2 |

Each sub-project has its own spec, plan and approval.

**Environment:**

- Firmware tools are installed: MounRiver Studio 2 GCC12 and WCHISPTool v4.0.
- The app needs the Android SDK command-line tools, JDK 17 and Gradle (about 2–5 GB). These are installed with permission at the start of step 2.

## 13. Open items and risks

| Item | Status |
|---|---|
| Vendor Company ID | The prototype uses WCH's `0x07D7` model. A product must decide whether to keep WCH's model or register its own CID. |
| Key Refresh (evicting removed or stolen boards) | Designed for, not in the first prototype. WCH library support is unverified. |
| Signed OTA images | Not in WCH's scheme. Required for a product, after the prototype. |
| CH584 RAM in the ROM-library layout | Closed: spike S1 PASS (15.5 KB of the 76 KB region) |
| Nordic library ↔ WCH vendor model interop | Closed: spike S3 PASS (`WRT` → `CFM`) |
| OTA over the mesh | Install and provisioning retention closed (spike T8–T11); block-transfer throughput open (OTA sub-project) |
| OTA install of an erased or partial image (`0xA6` erases; the IAP copies without checks) | Device-side length and CRC check before `0xA9` (section 7), OTA sub-project |
| WCH command/OTA handler memory safety (unbounded copy into 88 bytes; no OTA address-range or unicast checks) | Commands go through `proto.c` (section 4.2); the OTA handler is hardened or replaced in the OTA sub-project |
| No-OOB claim of unprovisioned boards (spike F1) | The library cannot require OOB; provisioning-window mitigation (section 5.2), tested in the firmware sub-project |
| Proxy configuration nonce (spike F3) | WCH uses the network nonce; resolved in the app sub-project (section 8.2) |
| BLE LE Secure Connections absent in the WCH BLE library | Mitigated: security relies on mesh provisioning, not BLE pairing |
| Hardware behaviour (radio range, relay timing) | Verified only during system testing |

## 14. References

- SDK: `CH585EVT.ZIP` from WeActStudio.WCH-BLE-Core (EVT list 2025.05, `CH585_BLE_LIB_V1.4`, `MESH_LIB_V1.79`), extracted to `C:\Embedded\WCH\SDK\CH585EVT`.
- WCH manuals in `EVT/EXAM/BLE/MESH`: *沁恒低功耗蓝牙MESH软件开发参考手册* V1.1 (§9.1, p.39: proxy example with nRF_mesh) and *沁恒MESH APP管理配网应用手册* V1.1 (OTA layout, DataFlash advice). Also *WCH蓝牙空中升级（BLE OTA）.PDF*.
- CH584/CH585 datasheet `CH585DS1.PDF`: the CH584 has 96 KB RAM; debug pins PB14 (TIO) and PB15 (TCK).
- Earlier verified work: `C:\Embedded\WCH\projects\CH584F_Mesh_Relay_LED` and `CH584F_Mesh_Controller` (GCC12 build flags, CH584 96 KB adaptation, LED PB6).
