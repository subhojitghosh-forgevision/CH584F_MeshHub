# Spike results

| ID | Result (PASS/FAIL/PARTIAL) | Observation (exact text/bytes shown by the app) |
|---|---|---|
| S1 build | PASS | node flash/RAM: v1 96,664 B / 15,484 B (152 KB slot, 76 KB RAM region), v2 96,720 B; stack 0x20018000; IAP 2,436 B at 0x4D000 (stack 0x20018000); JumpIAP 4 B = j 0x4d000; ROM lib CH584BLE_ROM_MESH.hex 128,704 B at 0x4E000-0x6D6C3 |
| T1 | PASS | Laptop BLE scan (bleak): 54:6C:50:B5:7A:3E (= chip UID 3E-7A-B5-50-6C-54 reversed) advertises Mesh Provisioning 0x1827, device UUID 3e7ab5506c5400000000000000000000, OOB info 0000, RSSI -52..-69 dBm. LED blinked once at power-up (user). nRF Mesh scan was empty before the reflash: phone-side, re-check with Location on. |
| T2 | PASS | Wrong static OOB FFEEDDCC...1100: invite, capabilities, start, public keys exchanged, then 'Provisioning failed received' - nRF Mesh dialog 'Provisioning Failed: Prohibited' (failed error code 0x00, not the spec's 0x04 Confirmation Failed). Board was available again and provisioned in T3. |
| T3 | PASS | 2026-10-04 15:55, after a node reset, user provisioned with the correct static OOB 0011...EEFF. nRF Mesh log: invite, capabilities, start, public keys, 'Waiting for user authentication' (the OOB entry step), confirmation, 'Provisioning random received', provisioning data, 'Provisioning complete received', composition data get/status (segmented, block acks), default TTL get, then 'Configuration Complete - Mesh node has been successfully configured.' Node Configuration (16:11): 'Element: 0x0004 - 4 Models', Network Keys 1; vendor model page shows 'Vendor Model - Model ID: 0x07D70000'. 4 models matches the firmware composition (spike/node/APP/app.c: Config Server, Config Client, Health Server + vendor server 0x07D7/0x0000). LED ON (user, 16:24). Model names not listed one by one; the count and the vendor model ID match. Node unicast address 0x0004, so AAAA = 0400 in T5-T11. (The earlier No-OOB provisioning is finding F1.) |
| T4 | PASS (workaround) | nRF Mesh network had no app key; user created 'Application Key 1' (index 0, 52595AE9...84351). Binding/adding it gave 'AppKey Status: Insufficient Resources' (16:16, shown on the Vendor Model page). Cause (code): the SDK example's prov_complete -> APP_NODE_EVT -> cfg_local_net_info() adds its own app key (index 1) and binds it to the vendor model, whose only bind slot (CONFIG_MESH_MOD_KEY_COUNT_DEF 1) is then full - see F2. Workaround applied: 'Application Key 2' = 0023456789ABCDEF0023456789ABCDEF (index 1) added to the node and bound; the Vendor Model 0x07D70000 page lists it under Bound App Keys (16:24). The phone's own key (index 0) cannot be bound with this firmware (F2). |
| T5 | PASS | 16:31, Acknowledged Message ticked, opcode entered as 6-bit 0C (field shows '0xC0 | 0x0C', so the app wants the 6-bit form; sent as 0xCC), parameters 01A40400 (TID 01, A4 ask status, address 0x0004). 'Received message: CFD7078B84040000' = MSG 0xCF, company 0x07D7, server TID 0x8B (in 0x80-0xBF), 84 status reply, address 0400, status 00. The server's confirm (CFM 0xCB, see T6) was not displayed: the app shows only the latest received message. Reply uses app key index 1 (F2 workaround). |
| T6 | PASS | 16:33, same opcode 0C and parameters 01A40400 sent again: 'Received message: CBD70701' = CFM 0xCB, company 0x07D7, TID 01, and no new 84 reply (a new one would carry server TID 0x8C, as in T5 the reply arrived after the confirm). Matches app_vendor_model_srv.c vendor_message_srv_write: the handler runs only when the (TID, source) pair changes; the confirm is sent every time. Correction: a WRT is answered with CFM 0xCB, not ACK 0xCD (0xCD is the client's reply to the server's IND 0xCE); spec section 4 lists the pairs swapped. |
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
| F2 Hardcoded self-configured app key | FINDING | spike/node/APP/app.c (from the SDK example): after ANY provisioning, prov_complete schedules APP_NODE_EVT and cfg_local_net_info() calls bt_mesh_app_key_set(net_idx, app_idx 0x0001, self_prov_app_key = 0023456789ABCDEF0023456789ABCDEF) and binds it to the vendor model (keys[0] = 1). Effects: (a) the key is public (SDK source) and identical on every board, so anyone holding the NetKey can read and send vendor messages, including the OTA commands 0xA6-0xA9; (b) with one bind slot per model the provisioner's own app key cannot be bound (T4 'Insufficient Resources'); (c) the node publishes READINGs with that key. Product firmware must remove the self-config and let the hub add/bind keys (spec amendment). |
