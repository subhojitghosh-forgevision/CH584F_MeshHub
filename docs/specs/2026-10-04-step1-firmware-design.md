# CH584F Mesh Hub, step 1: board firmware and factory script

- **Status:** draft for review.
- **Date:** 2026-10-04
- **Parent:** `docs/specs/2026-10-03-ch584f-mesh-hub-design.md` (the system spec, amended A1–A14). The parent defines the protocol (section 4), commissioning (section 5) and the base firmware (section 6). This document refines them for step 1 and does not repeat them.
- **Evidence:** `spike/REPORT.md`, `spike/RESULTS.md`.

## 1. Scope

### 1.1 Deliverables

| # | Deliverable |
|---|---|
| D1 | `firmware/`: one product image for all three boards. It is built from our own modules with the WCH SDK linked in, and packaged as a single hex (JumpIAP, application, IAP and the CH584 ROM library). |
| D2 | A **self-test image** that runs the shared test vectors on a board and advertises the result. |
| D3 | `factory/make_board.py`: per-board identity as a WCHISPTool DataFlash file, plus a printable QR label. |
| D4 | `protocol/`: a Python reference of the codec, rules, sensor profiles and storage records, plus `test-vectors.json`. |
| D5 | `tools/mesh_hub.py`: the laptop hub (Mesh proxy client), used to test step 1 without the Android app. |
| D6 | `tools/selftest_read.py`, and `mrs_build.py` support for MounRiver linked resources. |

### 1.2 Not in step 1

- **OTA commands.** `0xA6`–`0xA9` are answered UNSUPPORTED. The OTA flash layout, the IAP and the JumpIAP are in place for step 3.
- **The Android app.** It is step 2.
- **History.** It is step 4.
- **Automatic node configuration.** Boards are configured by hand in nRF Mesh (section 11.3).
- **Physical sensors.** None are fitted. Readings come from the simulation driver (section 6).

### 1.3 Success criteria

Done with three boards, nRF Mesh (Old) and the laptop hub:

1. Each board is provisioned with the static OOB from its label, and a wrong OOB fails.
2. After the provisioning window closes, the board refuses provisioning: it no longer advertises `0x1827`.
3. One proxy connection shows READINGs from all three boards.
4. Each of these reaches its target: every command, a 200-byte TEXT, and a broadcast to `0xC000`.
5. Unicast requests are answered.
6. The demo rules (section 11.4) switch LEDs across the mesh. Hysteresis visibly suppresses chatter.
7. A factory reset (by command or by a 10 s BOOT hold) removes network membership and settings, but keeps the factory page.
8. A captured command replayed after the RPL has been stored is ignored.
9. The board's name appears in the proxy scan response.
10. Every build passes its checks: application ≤ 152 KB, RAM within the 76 KB region, stack top `0x20018000`.
11. The self-test image passes all vectors.

## 2. Decisions taken in brainstorming (2026-10-04)

| # | Decision |
|---|---|
| B1 | Test harness: nRF Mesh for provisioning and configuration, plus the laptop hub (D5). |
| B2 | OTA: layout only, no OTA commands. |
| B3 | Self-test results are sent as a BLE advertisement and read by the laptop. No UART adapter is needed. |
| B4 | QR labels are made with the `segno` library, installed with the user's approval at the start of milestone M2. |
| B5 | Source structure: our own code in `firmware/`, with the WCH SDK linked from `C:\Embedded\WCH\SDK\CH585EVT`. |
| B6 | Sensors are simulated behind a swappable interface, with a different simulation profile per board (section 6). |
| Q1 | A rule starts *released*. The first reading past its threshold fires it. |
| Q2 | SET_NAME, GET_INFO, RULE_SET, RULE_CLEAR and FACTORY_RESET are accepted **unicast only**. LED, SET_INTERVAL, READ_NOW and TEXT are also accepted to `0xC000`. |
| Q3 | Before provisioning, the LED shows status (section 7.4). After provisioning, only commands and rules drive it. |
| Q4 | Replies (INFO, RESULT) are sent 3 times, 500 ms apart. READING and RULE_EVENT are sent once. |
| Q5 | The hub reads keys from an nRF Mesh network export, or from environment variables. Keys are never taken from the command line. |
| Q6 | Firmware version 1.0 (INFO bytes `[2..3]` = `0x0100`). |

## 3. Source structure and build

```
firmware/
  node/        MounRiver project (.project/.cproject) and Link.ld
               (application at 0x1000, length 152 KB; RAM 0x20005000, 76 KB)
    src/       our modules (section 4)
    include/
  iap/         WCH IAP main, with CH584 RAM
  jumpiap/     WCH JumpIAP main, with CH584 RAM
  build.py     builds node (product and self-test variants), iap and jumpiap; checks; packages
  out/         (git-ignored) meshhub-1.0.hex, meshhub-selftest-1.0.hex
```

- **Linked from the SDK, unchanged:**
  - StdPeriphDriver, RVMSIS and Startup;
  - the BLE LIB and the ROM library;
  - MESH_LIB;
  - the HAL core (MCU, RTC, SLEEP);
  - WCH's vendor model server (`app_vendor_model_srv.c/.h`).

  Links use the forms WCH's own projects use: `PARENT-n-PROJECT_LOC/...` and absolute `file:/C:/...` URIs.
- **`mrs_build.py`** resolves linked folders and linked files from `.project`. This is new, test-first work, and the existing regression hashes must not change.
- **Board-specific HAL** (WeAct `KEY.c`/`KEY.h`, the LED pin) is ours, under `firmware/node/src/`.
- **`build.py` per image:** `check_image.py` must pass (flash range, `--elf` with stack top `0x20018000`). The packager merges JumpIAP, application, IAP and `CH584BLE_ROM_MESH.hex`, rejects overlaps, and prints the sizes.
- **Mesh stack settings** (parent 4.6): `CONFIG_MESH_UNSEG_LENGTH_DEF` 7, `CONFIG_MESH_RX_SDU_DEF` 256, default TTL 5. Section 7.6 covers RPL storage.
- **Board defines:** `CLK_OSC32K=0`, `DCDC_ENABLE=1` plus `PWR_DCDCCfg(ENABLE)` in `main()`, `HSECap_10p`, `CHIP_ID=ID_CH584`, `BLE_SNV=FALSE`.

## 4. Firmware modules

| Module | Responsibility | Depends on |
|---|---|---|
| `main.c` | Clocks, DC-DC, TMOS and HAL start-up. Starts `board`, `factory`, `settings`, `mesh_node` and `readings`. | all |
| `board.c` | LED on PB6 (active low), and the BOOT button on PB22 (short press; hold for 10 s). LED patterns (section 7.4). | HAL |
| `factory.c` | Reads and validates the factory page (section 5.2). | DataFlash |
| `settings.c` | Name, interval and rules record, A/B pages (section 5.3) | DataFlash, `records` |
| `records.c` *(pure)* | Encodes and decodes the factory and settings records, and computes CRC32 | — |
| `mesh_node.c` | Mesh set-up, composition, provisioning (UUID and static OOB from the factory page), the provisioning window, the proxy scan-response name, factory reset. **No self-configuration and no keys.** | MESH_LIB, `factory`, `board` |
| `vnd_link.c` | Glue to WCH's vendor server. Passes received MSG/WRT to `app` with the source and destination addresses. Owns the send queue (section 7.2). | vendor server |
| `proto.c` *(pure)* | Decodes and validates every payload type and command with exact length checks (256-byte receive buffer). Encodes READING, INFO, RESULT and RULE_EVENT. | — |
| `app.c` | Command handling and the acceptance rules (section 7.1). Replies go through `vnd_link`. | `proto`, `settings`, `rules`, `board`, `readings` |
| `rules.c` *(pure)* | 4 rule slots: threshold crossing, hysteresis, transitions (section 7.3) | — |
| `sensor.h` | Sensor interface (section 6.1) | — |
| `sensor_sim.c` *(pure core)* | Simulation driver: profiles 1–3 (section 6.2) | `sensor.h` |
| `readings.c` | Interval timer. Calls `sensor_read()`, encodes a READING, publishes it, and feeds `rules`. Runs READ_NOW. | `sensor.h`, `proto`, `vnd_link`, `rules` |
| `selftest.c` | Self-test build only. Runs the generated vectors against `proto`, `rules`, `records` and `sensor_sim`, then advertises the result (section 10.2). | the pure modules |

A *pure* module touches no hardware and no globals outside its arguments. Pure modules are pinned by `test-vectors.json` (section 10.1).

## 5. Storage

### 5.1 DataFlash map (32 KB; erase unit 256 B)

| Offset | Size | Content |
|---|---|---|
| `0x0000` | 12 KB | WCH mesh storage (3 × 4 KB sectors, `CONFIG_MESH_NVS_ADDR_DEF` 0) |
| `0x3000` | 256 B | **Factory page.** Written only by WCHISPTool, from the board's DataFlash file. |
| `0x4000` | 256 B | Settings page A |
| `0x4100` | 256 B | Settings page B |
| `0x7000` | 256 B | OTA ImageFlag (IAP). BLE SNV is disabled. |

Everything else is unused and left erased (`0xFF`).

### 5.2 Factory page (64 bytes used; little-endian)

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | Magic `"MHF1"` |
| 4 | 1 | Format version = 1 |
| 5 | 1 | Simulation profile: 1–3, or 0 for none |
| 6 | 2 | Reserved, `0xFFFF` |
| 8 | 16 | Device UUID (RFC 4122 version 4) |
| 24 | 16 | Static OOB |
| 40 | 1 | Serial length, 1–16 |
| 41 | 16 | Serial, ASCII, zero-padded |
| 57 | 3 | Reserved, `0xFF` |
| 60 | 4 | CRC32 (IEEE 802.3, the same as Python `zlib.crc32`) over bytes 0–59 |

If the page is missing or invalid, the board shows the error pattern, keeps provisioning closed, and does not publish.

### 5.3 Settings record (one 256-byte page; little-endian)

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | Magic `"MHS1"` |
| 4 | 1 | Version = 1 |
| 5 | 1 | Name length, 0–20 |
| 6 | 2 | Interval in seconds, 1–3600 |
| 8 | 4 | Sequence number |
| 12 | 20 | Name, UTF-8, zero-padded |
| 32 | 32 | 4 rule slots × 8 bytes: used (1), source address (2), metric (1), comparison (1), threshold int16 (2), action (1) |
| 64 | 4 | CRC32 over bytes 0–63 |

**Write:** erase the page that holds the older or invalid record, then write the new record with sequence number + 1. **Read:** take the valid page with the higher sequence number. If neither page is valid, use the defaults: empty name (the serial is shown instead), interval 5 s, no rules.

A power loss during a write therefore keeps the previous settings.

## 6. Sensors

### 6.1 Interface (`sensor.h`)

```c
typedef struct { int16_t temp_c100; uint16_t rh_100; } sensor_sample_t;   /* 0.01 °C, 0.01 %RH */
typedef enum { SENSOR_OK, SENSOR_NOT_READY, SENSOR_ERROR } sensor_status_t;
typedef struct { uint8_t profile; uint32_t seed; } sensor_config_t;
void            sensor_init(const sensor_config_t *cfg);
sensor_status_t sensor_read(sensor_sample_t *out);
```

- Exactly one driver is linked, selected by the build option `SENSOR_DRIVER` (step 1: `sim`).
- Nothing outside `readings.c` calls the driver. The READING format, group publishing, rules and the hub depend only on `sensor_sample_t`.
- A later real driver, for example `sensor_sht3x.c`, implements the same two functions. A real driver ignores `profile`.
- If `sensor_read()` does not return OK, that interval publishes nothing and an error counter is incremented. The protocol is unchanged.

### 6.2 Simulation profiles

- **Time and seed.** Values are a pure function of (profile, seed, t), where t = seconds since boot from the TMOS system clock. The interval only changes how often the function is sampled.
- **Seed.** The seed is a CRC32 of the 8-byte chip unique ID (`GET_UNIQUE_ID`).
- **Noise.** Noise is xorshift32(seed XOR t), scaled to the stated amplitude.
- **Bounds.** All results are clamped to 20.00–35.00 °C and 30.00–80.00 %RH.
- **Default profile.** `make_board.py` sets the profile; the default is 1, 2, 3 by serial order. Profile 0 ("none") makes `sensor_sim` use profile 1.

| Profile | Temperature | Humidity | Purpose |
|---|---|---|---|
| 1 Wave | Triangle wave 20.00 → 30.00 → 20.00 °C, period 120 s; noise ±0.05 | Triangle wave 40 → 60 %RH, period 300 s | Clean crossings of a 25 °C rule, about once a minute each way |
| 2 Near threshold | 25.00 °C, noise ±0.40, so the value keeps crossing a 25.00 °C threshold but never falls below 24.50. Once every 90 s it dips: a linear ramp to 23.00 °C over 10 s, then back over 10 s. | 50 %RH, noise ±1 | Hysteresis: a `> 25.00` rule triggers once and **stays triggered through the noise** (no chatter). Each dip releases it once, and the return triggers it once. |
| 3 Humidity steps | 22.00 °C, noise ±0.20 | Square wave 35 ↔ 65 %RH, half-period 30 s, 5 s linear ramps; noise ±0.5 | Humidity rules and the 2 %RH hysteresis |

Each profile's exact formula is written once in `protocol/sensor_profiles.py`, and `sensor_sim.c` implements it identically. Vectors at chosen (profile, seed, t) points pin the two together (section 10.1).

## 7. Node behaviour

### 7.1 Message handling and acceptance (refines parent 4.2–4.4)

| Request | To own unicast | To `0xC000` |
|---|---|---|
| COMMAND LED, SET_INTERVAL, READ_NOW | Execute; RESULT | Execute; no reply |
| COMMAND SET_NAME, GET_INFO, RULE_SET, RULE_CLEAR, FACTORY_RESET | Execute; RESULT, or INFO for GET_INFO | Ignore |
| TEXT (1–200 bytes) | Store the last text, blink twice, log on UART; RESULT OK | Same; no reply |
| A READING arriving on `0xC001` | — | Feed `rules`. Ignored if its source is this board's own address, because the board already evaluated it locally. |
| An unknown type, an unknown command, or `0xA6`–`0xA9` | RESULT UNSUPPORTED | Ignore |
| A bad length or bad arguments | RESULT BAD_ARGS | Ignore |

- **Replies.** Replies go to the requester's address. RESULT byte `[1]` is the command byte for COMMAND requests, and the payload type byte for TEXT and for unknown types. A `CFM` from WCH's server means "received" (parent A12); only RESULT/INFO means "done".
- **FACTORY_RESET.** The board sends RESULT OK, waits for the reply copies to finish (about 1.5 s), then resets (section 7.5).

### 7.2 Sending

- **READING and RULE_EVENT** are published once, to the vendor model's configured publication address (`0xC001` after configuration). Until a publication address is configured, nothing is published.
- **INFO and RESULT** are sent 3 times, 500 ms apart.
- **Send queue (depth 4).** `vnd_link` starts the next message only when the previous message's copies are finished, so a later message never cancels an earlier message's repeats (spike M5).
  - When the queue is full, a new READING replaces a queued READING, or else it is dropped and counted.
  - A reply is never dropped while a READING holds a slot.

  The "finished" signal is WCH's send state if it can be observed (verified in M4); otherwise it is a timer of copies × period.

### 7.3 Rules (refines parent 4.5)

- Each rule watches one source address (which may be the board's own) and one metric.
- The rule state starts **released**. A reading **past the threshold** in the rule's direction **triggers** it (Q1). It **releases** when the value comes back past the threshold by the hysteresis: 0.50 °C, or 2.00 %RH.
- Every transition applies the action (LED on or off) and publishes RULE_EVENT `[0x30, index, state, source]`.
- A manual LED command overrides the LED until the next rule transition.
- RULE_SET resets that rule's state to released. Rules persist in settings; rule states and the LED do not persist.

### 7.4 LED and BOOT button

| State | LED |
|---|---|
| Boot | One 100 ms blink |
| Unprovisioned, provisioning window open | Double blink every 2 s |
| Unprovisioned, window closed | Off |
| No valid factory page | 3 fast blinks every 2 s |
| Provisioned | Commands and rules only. TEXT gives two blinks; LED identify blinks for 5 s, then restores the state. |
| BOOT held for 10 s | 3 fast blinks, then factory reset |

- **BOOT short press** (< 2 s) while unprovisioned reopens the provisioning window.
- **BOOT held at power-up** still enters the USB bootloader (ROM behaviour).

### 7.5 Provisioning, window, reset (mitigation for parent F1)

- **Capabilities.** Provisioning uses the factory page's UUID and static OOB. Capabilities offer static OOB only.
- **The window.** While unprovisioned with a valid factory page, the window opens at power-up and on each BOOT short press, for **180 s**. While it is open, the board sends unprovisioned beacons, PB-GATT advertising, and scans for PB-ADV.
- **Closing the window.** When it closes, the board calls `bt_mesh_beacon_disable()`, `bt_mesh_proxy_prov_disable(0)` and `bt_mesh_scan_disable()`. Whether scanning off also blocks PB-ADV is checked in M2; if not, the residual is recorded.
- **Expiry during provisioning.** If the window expires while a provisioning link is open, the link is allowed to finish.
- **After provisioning:** proxy advertising only (Network ID), relay on, no window.
- **Factory reset** (by command or BOOT hold): `bt_mesh_reset()`, erase both settings pages, reboot. The factory page is never erased.

### 7.6 Mesh identity and security

- **Composition.** One element: Config Server, Health Server, and WCH vendor server (CID `0x07D7`, model `0x0000`). No Config Client. Relay and proxy are on by default; friend and LPN are off.
- **Proxy scan response.** It carries the board name (Complete Local Name; the settings name, or the serial if the name is empty), through `bt_mesh_proxy_set_adv_rsp()`. It is refreshed after SET_NAME. The GAP device name is the same name.
- **No key material** in the source, the images or the UART output. Keys arrive only through provisioning and configuration.
- **RPL storage.** Store the RPL with `CONFIG_MESH_RPL_STORE_RATE` at its minimum, 5 s. M4 measures whether a command captured before a reboot is rejected afterwards. If WCH's `ALLOW_RPL_CYCLE` defeats this, record it as a risk.

## 8. Factory script (`factory/make_board.py`)

```
python factory/make_board.py --serial MH-0001 [--profile 1] [--out factory/out]
```

- **Generated values.** A fresh UUID (`uuid.uuid4`) and a fresh 16-byte static OOB (`secrets.token_bytes`).
- **DataFlash file.** The script builds the factory page with `protocol/records.py` and writes `<serial>.dataflash.bin`. That is the DataFlash image from offset 0 to the end of the factory page: `0xFF` up to `0x3000`, then the page.
- **Label.** `<serial>.label.svg`: a QR code holding `MHUB1:<serial>:<UUID hex>:<OOB hex>`, with serial, profile and the OOB in text. A `labels.html` sheet collects all the labels.
- **Registry.** The script appends to `factory/out/registry.csv`. It refuses a serial that is already in the registry.
- **Git.** `factory/out/` is **git-ignored**: labels and the registry are secrets (parent 5.1).
- **Flashing** each board with WCHISPTool (Clear DataFlash ticked):
  - Object Files: `meshhub-1.0.hex`;
  - DataFlash file: the board's `.dataflash.bin`.

  A reflash clears the provisioning, so the board must be removed in nRF Mesh and provisioned again.

## 9. Laptop hub (`tools/mesh_hub.py`)

- **Code it builds on.** The spike's `mesh_crypto.py` and proxy client move to `tools/`, with the review fixes:
  - an IVI mismatch at IV 0 returns None;
  - empty access payloads are rejected;
  - an independent cross-check of the proxy nonce.
- **Keys.** `--network <nRF Mesh export.json>` (NetKey, AppKey, nodes and names), or the environment variables `MESHHUB_NETKEY`/`MESHHUB_APPKEY`.
- **State.** `tools/.hub_state.json` (git-ignored) persists the hub's unicast address (default `0x7F00`), its SEQ (never reused: on start, SEQ = max(stored + 64, time-based value)) and its TID counter (parent A12).
- **Proxy configuration.** It is sent with the network nonce (parent F3) and sets an EXCLUSION filter.
- **Segmented messages.**
  - *Transmit:* for TEXT up to 200 bytes, unicast segments are re-sent until the Segment Acknowledgment covers them, or until a timeout.
  - *Receive:* the hub reassembles, sends Segment ACKs for unicast, and drops duplicate copies by (source, server TID) within 3 s.
- **Commands.**
  - **Watch:** `watch` shows READINGs (name, address, °C, %RH, sequence), RULE_EVENTs and TEXT.
  - **Queries and settings:** `info <node>`, `led <node|all> on|off|toggle|identify`, `interval <node|all> <s>`, `name <node> <text>`.
  - **Rules:** `rule set <node> <idx> <src> temp|rh '>'|'<' <value> on|off`, `rule clear <node> <idx|all>`.
  - **Other:** `read <node|all>`, `text <node|all> <message>`, `reset <node> --yes`.

  `<node>` is a unicast address or a name from the export. `all` means `0xC000`.

## 10. Testing

### 10.1 Test vectors (single source of truth)

`protocol/test-vectors.json` is generated by `protocol/gen_vectors.py` from the Python reference, and checked by `protocol/test_*.py`. It holds:

- **codec:** valid and invalid payloads for every type and command, with the decoded fields or the expected error;
- **rules:** reading sequences and the expected transitions, including Q1, both hysteresis values, and the near-threshold noise;
- **sensor:** (profile, seed, t) → sample, for each profile, including bounds;
- **records:** factory and settings bytes ↔ fields, and CRC32.

`gen_vectors.py` also writes `firmware/node/src/selftest_vectors.h`. A test checks that the header matches the JSON.

### 10.2 Self-test image

- **Contents.** The product build with `SELFTEST=1`: it runs every vector at boot and skips the mesh.
- **Result advert.** Non-connectable, local name `MHST`, manufacturer data (company `0x07D7`): `[format 1, total uint16, passed uint16, first failing vector id uint16 (0xFFFF if none)]`. The LED is steady on for all-pass and blinks for a failure.
- **Reader.** `tools/selftest_read.py` scans for the advert and prints PASS, or the failing vector's name.

### 10.3 Python tests (run on every task)

- `tools` (including linked resources and the checker);
- `protocol`;
- `factory` (the DataFlash file layout, the label payload, the duplicate-serial refusal);
- `tools/mesh_hub` (crypto known-answer tests, the segmentation round trip, the state file, the duplicate filter).

### 10.4 Hardware checks

Recorded in `firmware/RESULTS.md`, one row per check. These are run by the user, with the laptop, at the end of each milestone (section 12).

## 11. Bring-up procedures

### 11.1 Flash

WCHISPTool → CH58x → CH584 → USB. Tick **Clear DataFlash**. Load the product hex and the board's DataFlash file. The user flashes; every flash needs the user's approval.

### 11.2 Provision

Within 180 s of power-up (or after a BOOT short press), in nRF Mesh: **+** → board → Provision → **Static OOB** → the OOB printed on its label.

### 11.3 Configure (nRF Mesh, per board)

1. Add the network AppKey.
2. Bind it to Vendor Model `0x07D70000`.
3. Subscribe that model to `0xC000` and `0xC001`.
4. Set its publication to `0xC001` (AppKey, TTL 5, period 0).
5. Proxy on; relay stays on by default.

### 11.4 Demo rules for the system test

- **MH-0002:** `rule set MH-0002 0 MH-0001 temp '>' 25.00 on`. Follows board 1's wave.
- **MH-0003:** `rule set MH-0003 0 MH-0002 temp '>' 25.00 on`. The LED stays on through board 2's noise, and goes off and back on once per 90 s dip.
- **MH-0001:** `rule set MH-0001 0 MH-0003 rh '>' 50.00 on`. Follows board 3's humidity steps.

## 12. Milestones

Each milestone gets its own implementation plan (writing-plans), approved before it is executed. A milestone ends with its hardware check recorded in `firmware/RESULTS.md`.

| Milestone | Delivers | Hardware check |
|---|---|---|
| **M1 Skeleton** | `mrs_build` linked resources; `firmware/` project, `build.py` and packaging; a minimal node that boots and advertises unprovisioned with a test UUID | Board shows `0x1827`; build checks pass |
| **M2 Identity** | `records`, `factory`, `settings`, the provisioning window, `make_board.py` (segno install) | The board advertises its label's UUID. Its label OOB provisions and a wrong one fails. After 180 s, no `0x1827` and no PB-ADV. A missing page gives the error pattern. |
| **M3 Protocol core** | `protocol/` reference and vectors; `proto`, `rules`, `records`, `sensor_sim`; self-test image; `selftest_read.py` | All vectors pass on the board |
| **M4 Node and hub** | `vnd_link` queue, `app`, `readings`, rules wiring, LED and BOOT, factory reset, RPL setting, scan-response name; `mesh_hub.py` | Commands, TEXT (200 B), broadcast, readings, RULE_EVENTs, replay after reboot, name in the scan response |
| **M5 System test** | Three boards; configuration checklist; demo rules; every success criterion (1.3) recorded | All rows PASS, or a documented exception |

## 13. Risks and open items

| Risk | Handling |
|---|---|
| WCHISPTool's DataFlash file format and offset are unverified | M2 first: the board must advertise the label's UUID |
| PB-ADV may stay reachable after the window closes | M2 test; record the residual (parent F1) |
| RPL may not be stored as configured (`ALLOW_RPL_CYCLE`, store rate) | M4 replay test; record the result |
| The WCH vendor server exposes no "copies finished" signal | Timer fallback (section 7.2) |
| The hub's segmented transmit with ACKs is new code | Round-trip tests against `mesh_crypto`, plus a 200-byte TEXT on hardware |
| The self-test loop is slow (each run is a reflash) | Batch vectors per milestone. A host C compiler stays an option if the loop gets too slow. |
| RAM: 256-byte receive buffer, send queue, rules | Every build checks RAM within 76 KB |
| Each reflash clears provisioning | Procedure 11.1–11.3. The hub reads names from a fresh nRF Mesh export. |
| The nRF Mesh export contains keys | Git-ignored; passed by path only |
| The F3 proxy nonce for the Android app | Out of scope here; the step 2 spec handles it |
