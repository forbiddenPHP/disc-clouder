# JoPhi's Disc Clouder

A macOS desktop app for ripping DVDs and Blu-rays to MP4, with an embedded VLC preview player.

Two separate apps, one per disc type:

| App | Datei | Disc-Typ |
|-----|-------|----------|
| Blu-ray Ripper | `BLURAY-ONLY.py` | Blu-ray |
| DVD Ripper | `DVD-ONLY.py` | DVD |

## Features

- **Embedded VLC player** — preview titles before ripping
- **Queue system** — add multiple titles, rip them sequentially
- **Live thumbnails** — see what's being ripped in real time
- **Hardware-accelerated encoding** — uses Apple VideoToolbox (h264_videotoolbox)
- **Multi-Audio selection** — choose multiple audio tracks per title (with primary ❤️)
- **Automatic disc detection** — scans when a new disc is inserted
- **MPLS parsing** — reads audio metadata directly from Blu-ray playlists
- **Retry/Resume** — rip resumes automatically on read errors

## Architecture

| Component | DVD (`DVD-ONLY.py`) | Blu-ray (`BLURAY-ONLY.py`) |
|-----------|-----|---------|
| Scan | lsdvd | VLC API + MPLS + libbluray |
| Preview | VLC (dvdsimple://) | VLC (bluray://) |
| Rip Step 1 | VLC CLI → TS | ffmpeg → MKV |
| Rip Step 2 | ffmpeg TS → MP4 | ffmpeg MKV → MP4 |
| Video | H.264 (VideoToolbox) | copy (H.264) or VideoToolbox (VC-1) |
| Audio | AAC Stereo | AAC Stereo (alle gewählten Spuren) |

## Requirements

- macOS (Apple Silicon or Intel)
- Miniconda or Anaconda
- Homebrew
- An optical disc drive

## Installation

```bash
chmod +x install-me.sh
./install.sh
```

The installer will:
1. Create a conda environment `disc_clouder` with Python 3.12.3
2. Install brew packages: ffmpeg, VLC, lsdvd, p7zip

## Usage

```bash
python BLURAY-ONLY.py
python DVD-ONLY.py
```

## Workflow

1. Insert a disc — the app scans automatically
2. Click a title in the list to preview it
3. Select audio tracks (✓ = included, ❤️ = primary language)
4. Optionally add a suffix (e.g., "Extended", "S01E03")
5. Click "+ Zur Queue"
6. Repeat for more titles
7. Switch to the "Queue" tab
8. Click "Queue starten"
9. Wait — live thumbnails and progress bars show what's happening
10. The app announces completion via macOS `say`

## File Locations

| What | Where |
|------|-------|
| Temp rip files | `/tmp/disc_clouder_rip.*` |
| Output | `~/Desktop/filme_sicherungen/` (configurable) |

## Disclaimer

This software is designed to rip unprotected DVDs and Blu-rays. No decryption libraries, keys, or DRM-bypassing tools are included or distributed.

It is the user's sole responsibility to ensure compliance with applicable copyright laws in their jurisdiction.

## License

MIT License — see [LICENSE](LICENSE)

## Author

Johannes Hinterberger
