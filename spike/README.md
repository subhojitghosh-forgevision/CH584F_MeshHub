# Step 0 spike (THROWAWAY)

Feasibility checks S1-S6 from docs/specs/2026-10-03-ch584f-mesh-hub-design.md section 11.
Nothing here is production code. The firmware sub-project starts from its own spec and plan.

- assemble_spike.py: copies WCH update-capable mesh projects from the SDK and applies CH584/board/spike edits
- FLASHING.md: how the user flashes the merged spike image
- TESTS.md: hardware test script (nRF Mesh) with result columns
- REPORT.md: go/no-go per check and proposed spec amendments

## Laptop tools (spike/laptop, Windows only)

`mesh_crypto.py` is a minimal Mesh Profile 1.0.1 crypto layer that uses the AES built into Windows (CNG), so it needs nothing beyond bleak. Its known-answer tests run with `cd spike/laptop && python -m unittest test_mesh_crypto`.

`proxy_client.py ADDRESS NETKEY_HEX --cfg-nonce network` connects to a board's Mesh Proxy service once the phone has disconnected. It sets an EXCLUSION proxy filter and decodes the forwarded traffic. Pass `--ask 0xTID` to also send a WRT ask-status. Use `--cfg-nonce network` because WCH boards ignore the spec's proxy nonce (finding F3). The NetKey is a command-line argument; do not commit it.
