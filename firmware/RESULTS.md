# Step 1 firmware results

| ID | Milestone | Check | Result | Observation |
|---|---|---|---|---|
| M1-1 | M1 | Build checks: node within 0x01000-0x26FFF with stack top 0x20018000; IAP within 0x4D000-0x4DFFF; JumpIAP within 0x00000-0x00FFF; package without overlaps | PASS | 2026-10-04 build (commit 87de77e): jumpiap 4 B at 0x00000 (j 0x4D000); node 87,908 B at 0x01000-0x16763, RAM 14,888 B of 76 KB, stack top 0x20018000; iap 2,436 B at 0x4D000-0x4D983; meshhub-1.0.hex 219,052 B at 0x00000-0x6D6C3 (sha256 d3334b09ed42748c...); 0 compiler warnings; suites tools 27/27, firmware 21/21, spike 12/12 |
| M1-2 | M1 | Boot: one 100 ms LED blink, then off | PASS | 2026-10-04, user: WCHISPTool 'Succeed!' (meshhub-1.0.hex, Clear DataFlash ticked, board 54:6C:50:B5:7A:3E), then after replugging the LED blinked once |
| M1-3 | M1 | Laptop scan: 0x1827 with device UUID 4d6573684875622d4d312d7465737421 | PASS | 23:25:51 watcher, then `python tools/mesh_scan.py 10`: '1 mesh device(s) in 10 s / - 54:6C:50:B5:7A:3E  RSSI -60 dBm / UNPROVISIONED 0x1827: device UUID 4d6573684875622d4d312d7465737421 OOB info 0000' (ASCII MeshHub-M1-test!) |
