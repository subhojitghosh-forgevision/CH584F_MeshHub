# MeshHub firmware

Board firmware for the CH584F Mesh Hub (spec: `docs/specs/2026-10-04-step1-firmware-design.md`).

## Layout

| Folder | Content |
|---|---|
| `node/` | The product application. `src/` and `hal/` are ours; WCH SDK parts are linked from `C:\Embedded\WCH\SDK\CH585EVT`. |
| `iap/`, `jumpiap/` | WCH's installer and jump stub, linked from the SDK, with CH584 RAM in `Ld/Link.ld` |
| `projects.py` | The single description of the three projects. It generates their `.project` and `.cproject`. |
| `build.py` | Builds and checks all three images, then packages them with the CH584 ROM library |

## Build

    python firmware/build.py

Output: `firmware/out/meshhub-1.0.hex`. After changing `projects.py`, run `python firmware/projects.py`. The test
`test_projects.py` fails if the committed project files differ from the generator.

## Flash (WCHISPTool v4.0)

**The user flashes, and only with explicit approval.**

1. CH58x → CH584 → USB. Untick **Automatic Download**. Tick **Clear DataFlash**.
2. Object File 1: `firmware/out/meshhub-1.0.hex`. From M2 onwards, also load the board's DataFlash file.
3. Hold BOOT while plugging in USB, then **Download**.

Clear DataFlash removes any provisioning, so delete the old node in nRF Mesh before provisioning it again.

## Check

    python tools/mesh_scan.py 10

M1 boards advertise `UNPROVISIONED 0x1827: device UUID 4d6573684875622d4d312d7465737421` (ASCII `MeshHub-M1-test!`).
