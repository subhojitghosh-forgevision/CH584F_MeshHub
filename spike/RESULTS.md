# Spike results

| ID | Result (PASS/FAIL/PARTIAL) | Observation (exact text/bytes shown by the app) |
|---|---|---|
| S1 build | PASS | node flash/RAM: v1 96,664 B / 15,484 B (152 KB slot, 76 KB RAM region), v2 96,720 B; stack 0x20018000; IAP 2,436 B at 0x4D000 (stack 0x20018000); JumpIAP 4 B = j 0x4d000; ROM lib CH584BLE_ROM_MESH.hex 128,704 B at 0x4E000-0x6D6C3 |
| T1 | PASS | Laptop BLE scan (bleak): 54:6C:50:B5:7A:3E (= chip UID 3E-7A-B5-50-6C-54 reversed) advertises Mesh Provisioning 0x1827, device UUID 3e7ab5506c5400000000000000000000, OOB info 0000, RSSI -52..-69 dBm. LED blinked once at power-up (user). nRF Mesh scan was empty before the reflash: phone-side, re-check with Location on. |
| T2 | PASS | Wrong static OOB FFEEDDCC...1100: invite, capabilities, start, public keys exchanged, then 'Provisioning failed received' - nRF Mesh dialog 'Provisioning Failed: Prohibited' (failed error code 0x00, not the spec's 0x04 Confirmation Failed). Board was available again and provisioned in T3. |
| T3 | PASS (LED + model list to confirm) | 2026-10-04 15:55, after a node reset, user provisioned with the correct static OOB 0011...EEFF. nRF Mesh log: invite, capabilities, start, public keys, 'Waiting for user authentication' (the OOB entry step), confirmation, 'Provisioning random received', provisioning data, 'Provisioning complete received', composition data get/status (segmented, block acks), default TTL get, then 'Configuration Complete - Mesh node has been successfully configured.' Node Configuration (16:11): 'Element: 0x0004 - 4 Models', Network Keys 1; vendor model page shows 'Vendor Model - Model ID: 0x07D70000'. 4 models matches the firmware composition (spike/node/APP/app.c: Config Server, Config Client, Health Server + vendor server 0x07D7/0x0000). Still to confirm: LED ON and the model names. Node unicast address 0x0004, so AAAA = 0400 in T5-T11. (The earlier No-OOB provisioning is finding F1.) |
| T4 | | |
| T5 | | |
| T6 | | |
| T7 | | |
| T8 | | |
| T9 | | |
| T10 | | |
| T11 | | |

## Laptop pre-checks (bleak, 2026-10-04)

| Check | Result | Observation |
|---|---|---|
| GATT services | PASS | 0x1800 GAP, 0x1801 GATT, 0x1827 Mesh Provisioning with Data In 0x2ADB (write-without-response) and Data Out 0x2ADC (notify) |
| Provisioning Capabilities (Invite sent over PB-GATT) | PASS | 03010100010001000000000000: 1 element, algorithms 0x0001 (P-256), no OOB public key, Static OOB AVAILABLE, no output/input OOB |
| Re-advertising after an abandoned provisioning link | PASS | unprovisioned 0x1827 advertising again within ~6 s |
| Unprovisioned advertising after node reset (prov_reset -> prov_enable fix) | PASS | 15:49 not advertising (phone held the proxy link); 15:51:43-15:52:19 provisioned proxy 0x1828 adverts, alternating with gaps (phone reconnecting); 15:52:25 unprovisioned 0x1827, device UUID 3e7ab5506c5400000000000000000000, OOB info 0000, RSSI -49 dBm. Cause: a reset message, by elimination: no bootloader gap (no reflash), and a power cycle keeps provisioning data. The board was then provisioned again at 15:55 (T3). |

## Security finding (2026-10-04)

| ID | Result | Observation |
|---|---|---|
| F1 No-OOB provisioning | FINDING | nRF Mesh provisioned the board with authentication 'No OOB' and configuration completed, although the board offers static OOB. In Mesh 1.0 the provisioner chooses the method; MESH_LIB V1.79 exposes no option to require OOB (bt_mesh_prov has static_val/output/input/oob_pub_key only). Any nearby phone can claim an unprovisioned board. Static OOB still authenticates the board to OUR app (anti-impersonation). |
