# Spike hardware tests (nRF Mesh for Android)

Static OOB (correct): 00112233445566778899AABBCCDDEEFF
Static OOB (WRONG, for the negative test): FFEEDDCCBBAA99887766554433221100
Node address: whatever nRF Mesh assigns (usually 0x0002). Below, AAAA = that address little-endian (0x0002 -> 0200).
LED: blinks N times at power-up (N = firmware version), then OFF = unprovisioned, ON = provisioned.
Vendor model: company 0x07D7, model 0x0000. WRT opcode byte = 0xCC, MSG = 0xCF, ACK = 0xCD.
If the app asks for a 6-bit opcode instead of the full byte, use 0x0C for WRT. Record which form the app wanted.
Parameters = TID byte + payload. Use a NEW TID (01, 02, 03 ...) for every message unless a step says otherwise.

| ID | Step | Expected |
|---|---|---|
| T1 | Power the board. Open nRF Mesh, add node, scan. | Board listed as unprovisioned; LED blinked once at power-up, then stays OFF (not provisioned) |
| T2 | Provision it choosing Static OOB, enter the WRONG value | Provisioning FAILS (confirmation error); board stays unprovisioned |
| T3 (S2) | Provision again with the CORRECT static OOB | Provisioning succeeds; the board LED turns ON and stays on; node shows Config Server, Health Server, Vendor model 0x07D7/0x0000 |
| T4 | Add the network App Key to the node; bind it to the vendor model 0x0000 | Both succeed |
| T5 (S3) | Vendor model: send WRT (0xCC), params 01 A4 AAAA (ask status) | App shows ACK (0xCD) with param 01; then a MSG (0xCF) whose params are: server TID (0x80-0xBF), 84, AAAA, 00 |
| T6 | Send the SAME message again with TID 01 | ACK arrives again but NO new 84 reply (duplicate dropped) |
| T7 (S4) | Add group 0xC001 to the proxy filter (Network or Proxy settings) and wait 15 s | MSG (0xCF) every 5 s: TID, 01, temp lo, temp hi, 88, 13, seq (temperature 20.00-30.00 C, humidity 0x1388 = 50.00 %) |
| T8 (S5 install) | Send WRT, params 02 A9 AAAA (OTA end) | NO ACK is expected (the board resets inside the handler before acknowledging; the app may show a timeout); the LED then blinks THREE times (version 2 installed by the IAP) and then stays ON (still provisioned) |
| T9 | Reconnect if needed; send WRT, params 03 A4 AAAA | 84 reply again: still provisioned after the install |
| T10 (S5 path) | Send WRT, params 04 A6 AAAA (image info) | MSG with params: TID, 86, AAAA, 00 60 02 00 (image size 0x26000), block size (2 bytes), chip id (2 bytes), 00 |
| T11 | Unplug and replug the board | LED blinks three times, then stays ON; node still answers T9-style ask status (use TID 05) |
