# Step 0 spike report

- **Date:** 2026-10-04
- **Board:** one WeAct CH584F, `54:6C:50:B5:7A:3E`
- **Firmware:** spike v1, then v2 installed over the mesh. Package: `spike/out/spike_full_v1_plus_v2B.hex`.
- **Phone:** nRF Mesh (Old) for Android.
- **Laptop:** Mesh proxy client in `spike/laptop`.

Every observation, with exact bytes, is in `spike/RESULTS.md`. Findings F1–F3 and notes N1–N3 are defined there.

## Results

| ID | Result | Evidence |
|---|---|---|
| S1 build | PASS | v1 uses 96,664 B of the 152 KB slot and 15,484 B of the 76 KB RAM region. IAP is at `0x4D000` and the ROM library at `0x4E000`–`0x6D6C3`. |
| T1 | PASS | Unprovisioned `0x1827` advertising, UUID `3e7ab5506c54…`, LED blinks once. |
| T2 | PASS (rejected) | Wrong static OOB gives "Provisioning Failed: Prohibited" (failure code `0x00`, not `0x04`). |
| T3 = S2 | PASS | Correct static OOB gives "Configuration Complete" and the LED turns on. Element `0x0004` has 4 models, including vendor `0x07D70000`. |
| T4 | PASS (workaround) | The phone's own app key cannot be bound ("Insufficient Resources", F2). The SDK key, imported as index 1, could be added and bound. |
| T5 = S3 | PASS | WRT (entered as 6-bit `0C`) `01 A4 0400` returns CFM `0xCB` and MSG `CF 8B 84 0400 00`. |
| T6 | PASS | Repeating TID `01` returns only CFM `CB 01`, with no new reply (the duplicate is dropped). |
| T7 = S4 | PARTIAL in nRF Mesh, PASS via laptop | nRF Mesh cannot display unsolicited vendor messages (N2). A laptop proxy client receives a READING to `0xC001` every 5 s through the GATT proxy, with NetMIC and TransMIC verified. |
| T8 = S5 install | PASS | WRT `02 A9 0400` (OTA end): the LED blinks 3 times (v2) and the board still advertises `0x1828` on the same network. |
| T9 | PASS | After the install, ask-status returns `CB 03` and `93 84 0400 00`. The network SEQ continued and was not reset. |
| T10 | PASS | Image info returns size `0x26000` and block `0x1000`. `0xA6` also **erases the update buffer** (A13), so this was safe only because it ran after T8. Chip ID is `0x93` (CH585), which is wrong for a CH584 (`0x92`). |
| T11 | PASS | After a power cycle the board is back on `0x1828` on the same network and returns `CB 05` and `84 84 0400 00`. |
| S6 | API available, untested | `bt_mesh_proxy_set_adv_rsp(u8_t *data, u8_t len)` (scan response, at most 31 bytes) is in `MESH_LIB.h:3262` and in both libraries. No SDK example calls it. |

## Go / no-go

- **Firmware sub-project (step 1, needs S1–S4): GO.** S1, T2 (rejected), T3, T5 and T6 pass. T7 is PARTIAL in nRF Mesh and PASS through a laptop proxy client. Amendments A5 (F2) and A9 (F3) are preconditions.
- **OTA sub-project (step 3, needs S5): GO.** T8–T11 pass. The WCH OTA handler must be hardened first (A13, A14).
  - **Scope:** the spike installed an image that was already in the update buffer, using the end command `0xA9`.
  - **Not exercised:** the block transfer (`0xA7` write, `0xA8` verify) and its throughput over the mesh. That is the first task of the OTA sub-project.

## Proposed spec amendments

| # | Spec section | Amendment | Source |
|---|---|---|---|
| A1 | 4.1, 11 (S3) | Opcode pairs: **WRT `0xCC` → CFM `0xCB`** (the server confirms) and **IND `0xCE` → ACK `0xCD`** (the client replies). In S3, "the app receives ACK" becomes "CFM". | T5, T6, `app_vendor_model_srv.c` (N3) |
| A2 | 4.2 | The firmware routes WRT to the command handler. WCH's example passed only MSG; the spike adds the WRT routing. Commands that reset the board (OTA end, factory reset) get **no CFM**, and the app treats that as expected. | T8, plan item 8 |
| A3 | 4.2 | WCH sends every vendor MSG 5 times (`trans_cnt` 5, 500 ms apart). READING and RULE_EVENT use a send count of 1 (loss is tolerated). Broadcast commands keep 5. | N1 |
| A4 | 5.2, 9, 13 | **F1:** the board accepts **No OOB** provisioning, and MESH_LIB V1.79 cannot require OOB. Static OOB proves the board to our app but does not stop another phone from claiming an unprovisioned board. **Mitigation:** provisioning is open only for a window (for example 3 minutes after power-up or a BOOT short press), then closed with `bt_mesh_beacon_disable()` and `bt_mesh_proxy_prov_disable()`. PB-ADV still answers a provisioner that already knows the UUID, so this narrows the risk rather than removing it. Untested. **Section 9:** a wrong OOB arrives as failure code `0x00` "Prohibited", so the app reports any provisioning failure as "wrong label or board refused". | T2, T3, F1 |
| A5 | 5.3, 5.4, 6.1 | **F2:** remove the SDK example's self-configuration. `prov_complete` → `APP_NODE_EVT` → `cfg_local_net_info()` adds the app key `0023456789ABCDEF…` (published in the SDK) at index 1 and binds it to the only vendor-model key slot. Without it, "no keys exist in the firmware" holds and the app's own AppKey binds normally. | T4, F2 |
| A6 | 6.1 | Call `PWR_DCDCCfg(ENABLE)` explicitly in `main()`; `DCDC_ENABLE` alone does nothing. Set `CHIP_ID` to `ID_CH584` (`0x92`) in `CONFIG.h`. Fix the image-info high byte: `(CHIP_ID<<8)&0xFF` should be `>>8`. | Task 3, T10 |
| A7 | 6.3 | DataFlash `0x7000` is the OTA ImageFlag page (`OTA_DATAFLASH_ADD = 0x77000 - FLASH_ROM_MAX_SIZE`), the same address as the BLE SNV default. Reserve `0x7000` for the ImageFlag and disable BLE SNV, since no bonding is used. | Task 1 desk check |
| A8 | 6.4, 7, 11 (S5) | **OTA over the mesh is supported.** WCH's OTA commands `0xA6`–`0xA9` are handled in `App_trans_model_reveived` from any mesh source (T8, T10). In section 7, replace "the phone connects to the target board directly" and "OTA over the mesh is not supported" with: "the phone sends WCH OTA commands as vendor WRT messages through its gateway proxy to any board; throughput is measured in the OTA sub-project". The custom WCH peripheral (`0xFFE0`) and a separate GATT OTA service are not needed; the spike ran without them. In section 6.4, the "OTA service" row becomes "OTA commands in `app.c` (WCH IAP scheme)". In S5, "Both GATT services are visible" no longer applies. | T8–T11 |
| A9 | 8.2 (`mesh/`) | **F3:** MESH_LIB V1.79 encrypts proxy configuration with the **network nonce**, not the Proxy nonce (Mesh Profile 3.8.5.4). The current Nordic library sends with the Proxy nonce, so its proxy-filter requests would be ignored and `0xC001` READINGs would not reach the hub. nRF Mesh (Old) did get a filter status, so its bundled library differs. **The app sub-project tests this first**, then either patches the library to use the network nonce for proxy configuration, or has boards also address READINGs to the hub's unicast address. Separately, unsolicited vendor messages arrive in `MeshStatusCallbacks.onUnknownPduReceived(src, accessPayload)` (N2). | T7, laptop checks, F3 |
| A10 | 6.5 | S6: the API exists, so the firmware sub-project tries putting the name in the proxy scan response. INFO remains the source of truth. | S6 desk check |
| A11 | 13 | **Close:** "CH584 RAM" (S1 PASS), "Nordic ↔ WCH vendor interop" (S3 PASS) and "OTA service alongside proxy" (replaced by OTA over the mesh). **Add:** F1 no-OOB claim, F3 proxy-configuration nonce, and OTA block-transfer throughput. | all |

## Final review additions (approved 2026-10-04 and applied to the spec)

The whole-branch review found three problems that amendments A1–A11 miss.

| # | Spec section | Amendment | Source |
|---|---|---|---|
| A12 | 4.1, 4.2, 8.2 | **A CFM confirms receipt, not execution.** The server confirms a duplicate (same TID and source) without running it, and keeps only the last (TID, source) pair, in RAM. So the app persists its TID counter per network, or starts each session at a random TID, and a restart never repeats the last TID. The app drops the board's repeated copies by (source, server TID) within a 3 s window; the window is short so that a board's server TID restarting after a reboot is not mistaken for a duplicate. | T6, `vendor_message_srv_write` |
| A13 | 7, 13 | **`0xA6` is OTA *begin*:** it erases the whole update buffer before replying (`app.c:1184`). `0xA9` after `0xA6` without a fully written and verified image makes the IAP install an erased image, because it copies without checks (`iap/APP/app_main.c:72-76`). The device is then dead until a USB reflash. The OTA sub-project adds a device-side length and CRC check before `0xA9` switches the image flag, and the app sends `0xA9` only after a passing verify. | T10, code |
| A14 | 4.2, 6.4, 7, 13 | **WCH's `App_trans_model_reveived` is not memory-safe.** It copies the whole message into an 88-byte buffer without a length check (`app.c:1034`), so a message close to the 256-byte RX SDU overwrites the mesh heap. `0xA7`/`0xA8` have no address-range check and can reach the IAP and the ROM library, and OTA commands also act on group-addressed messages. Commands are therefore dispatched by `proto.c`, with a buffer sized for the RX SDU and per-type length checks, and `WRT` is not routed into the WCH handler; this refines A2. The OTA sub-project replaces or hardens the WCH OTA handler (length, address range, unicast only). The integrity claim in section 7 ("WCH's verification step") becomes "a host-driven read-back compare". | code |

## Notes for later testing (nRF Mesh and test tools)

- nRF Mesh takes the **6-bit** vendor opcode (`0C`) and adds `0xC0` itself.
- **Received message** shows only the latest vendor message, and only replies to its own last vendor send (N2).
- App keys must first be created under **Settings → App Keys**.
- Proxy-filter **ADD** stays disabled until a Filter Status arrives.
- The phone needs **Location** turned on to scan.
- `spike/laptop/proxy_client.py ADDRESS NETKEY --cfg-nonce network` reproduces T7 and T9–T11 without a phone (12 crypto known-answer tests). The NetKey goes on the command line only.
