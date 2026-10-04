# Spike results

| ID | Result (PASS/FAIL/PARTIAL) | Observation (exact text/bytes shown by the app) |
|---|---|---|
| S1 build | PASS | node flash/RAM: v1 96,664 B / 15,484 B (152 KB slot, 76 KB RAM region), v2 96,720 B; stack 0x20018000; IAP 2,436 B at 0x4D000 (stack 0x20018000); JumpIAP 4 B = j 0x4d000; ROM lib CH584BLE_ROM_MESH.hex 128,704 B at 0x4E000-0x6D6C3 |
| T1 | PASS | Laptop BLE scan (bleak): 54:6C:50:B5:7A:3E (= chip UID 3E-7A-B5-50-6C-54 reversed) advertises Mesh Provisioning 0x1827, device UUID 3e7ab5506c5400000000000000000000, OOB info 0000, RSSI -52..-69 dBm. LED blinked once at power-up (user). nRF Mesh scan was empty before the reflash: phone-side, re-check with Location on. |
| T2 | | |
| T3 | | |
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
