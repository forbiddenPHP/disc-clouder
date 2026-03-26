# JoPhi's Disc Clouder

> A private vibe-coding project — built to learn macOS multimedia, Blu-ray internals, and PyQt6. Made interactively with AI.

Rips DVDs and Blu-rays to MP4 on macOS (Apple Silicon).

| App | File |
|-----|------|
| Blu-ray | `BLURAY-ONLY.py` |
| DVD | `DVD-ONLY.py` |

## Setup

```bash
chmod +x install-me.sh && ./install-me.sh
```

## Run

```bash
python BLURAY-ONLY.py
python DVD-ONLY.py
```

## What it does

- VLC preview player — watch before you rip
- Multi-audio selection (❤️ = primary)
- Queue — rip multiple titles in sequence
- Live thumbnails during rip
- Hardware encoding (Apple VideoToolbox)
- Trouble Mode — copies BD-50 to SSD first, then rips (for cheap drives)
- Configurable BD-50 read speed (default: 2x)
- Announces completion via `say`

## Disclaimer

This is for **unprotected** discs only. The following are **not** included:

- KEYDB.cfg, libaacs, libbdplus, BD+ VM/Convtab — Blu-ray decryption
- libdvdcss — DVD decryption

Your jurisdiction, your responsibility.

## Advanced

`install.zip` (password: `secret`) contains `install.sh` — use it instead of `install-me.sh` if you have legally obtained decryption libraries. By entering the password, you confirm to all rights holders that you have the legal right to do so.

## License

MIT — see [LICENSE](LICENSE)
