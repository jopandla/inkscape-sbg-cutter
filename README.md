# SBG / SKY cutter driver + Inkscape extension

Drive an SBG / SKYCUT "SKY32 Vi"-class film-cutting plotter from your own software, with
arbitrary SVG/DXF geometry instead of the vendor's locked phone app. Everything here was
reverse-engineered from the machine's own firmware and **verified by cutting on real hardware**.

> Interoperability / repair tool for hardware you own. It talks to the device you already
> have; it ships no vendor firmware. See **Legal / scope** below.

## What works

- **Unlock handshake** fully reproduced (the app's `BD:9` / `BD:10` / `BD:12` challenge-response).
- **Job encoding** fully reproduced: the `WSJP`-keyed, digit-substituted `U`/`D` format the
  machine actually cuts (plain HPGL does **not** cut on these machines).
- **Two proven transports** (both no firmware patch):
  - **Bluetooth** serial (the paired `COMx`).
  - **Direct 3.3 V UART** on the mainboard's USART3 ribbon lines at **115200 8N1** — bypasses the
    onboard USB bridge entirely. (The stock USB-B port is dead-ended by a firmware/bridge baud
    mismatch; the UART tap sidesteps it.)

## Pieces

| File | What it is |
|------|------------|
| `sbgcut/sbg_protocol.py` | Pure logic: handshake math + `WSJP` job encoder. No hardware. |
| `sbgcut/sbg_link.py` | pyserial transport + unlock session. |
| `sbgcut/sbgcut.py` + `sbgcut.inx` | **Inkscape extension** (Extensions > Export > Cut on SBG plotter). |
| `cli.py` | Standalone CLI: cut an SVG/DXF (or a test square) with no Inkscape. |
| `tests/test_protocol.py` | Checks the encoder/handshake against live-captured data. |

## Quick start (no Inkscape)

```bash
python cli.py --square 10 --port COM12          # cut a 10x10 mm test square
python cli.py drawing.svg --at 20,30 --port COM12
python cli.py drawing.dxf --at 20,30 --dry      # just print the job
```

## Inkscape extension

Copy `sbgcut/sbgcut.py`, `sbgcut/sbg_protocol.py`, `sbgcut/sbg_link.py` and `sbgcut/sbgcut.inx`
into your Inkscape **user extensions** folder (Edit > Preferences > System > *User extensions*),
restart Inkscape, then **Extensions > Export > Cut on SBG plotter**. Set the serial port, origin,
speed/force, and hit Apply. Use **Dry run** first — it writes the job to a temp file instead of
sending. pyserial ships with Inkscape (it powers the stock Plot extension), so `import serial`
works inside the extension with nothing to install.

## Notes on portability to other units

The handshake keys in `sbg_protocol.py` are **firmware constants, not tied to your serial number**,
so they are identical for every unit on the same firmware version. A *different* firmware version
may use different constants — if your machine doesn't unlock, the four tuples in `sbg_protocol.py`
need re-extracting for that firmware. The `WSJP` key + its digit table are likewise reusable as-is.

## Calibration

Units are 1/40 mm. Origin/orientation depend on how your machine homes — if a cut comes out
mirrored or offset, adjust `--at`, `--flip-y`, and `--bed-h` (CLI) or the Placement tab (Inkscape).
Start every first cut with a pen or no blade.

## Legal / scope

Reverse-engineered for **interoperability** with hardware you own. No vendor firmware is included
or redistributed — only an independent description of the wire protocol and original code. Not
affiliated with or endorsed by the manufacturer; brand names belong to their owners. Provided
as-is, no warranty. Check your local rules before redistributing.
