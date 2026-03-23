# JoPhi's Disc Clouder

A macOS desktop app for ripping DVDs and Blu-rays to MP4, with an embedded VLC preview player.

## Features

- **DVD and Blu-ray support** — encrypted discs (CSS, AACS, BD+)
- **Embedded VLC player** — preview titles before ripping
- **Queue system** — add multiple titles, rip them sequentially
- **Live thumbnails** — see what's being ripped in real time
- **Hardware-accelerated encoding** — uses Apple VideoToolbox (h264_videotoolbox)
- **Audio selection** — choose language per title
- **Automatic disc detection** — scans when a new disc is inserted

## Architecture

| Component | DVD | Blu-ray |
|-----------|-----|---------|
| Scan | lsdvd | VLC API + libbluray |
| Preview | VLC (dvdsimple://) | VLC (bluray://) |
| Rip Step 1 | VLC CLI → TS | ffmpeg → MKV |
| Rip Step 2 | ffmpeg TS → MP4 | ffmpeg MKV → MP4 |
| Video | H.264 (VideoToolbox) | copy (H.264) or VideoToolbox (VC-1) |
| Audio | AAC Stereo | AAC Stereo |

## Requirements

- macOS (Apple Silicon or Intel)
- Miniconda or Anaconda
- Homebrew
- An optical disc drive

## Installation

```bash
chmod +x install.sh
./install.sh
```

The installer will:
1. Create a conda environment `disc_clouder` with Python 3.12.3
2. Install brew packages: ffmpeg, VLC, libdvdcss, libaacs, libbdplus, lsdvd, megatools, p7zip
3. Create symlinks for libaacs/libbdplus in /usr/local/lib/
4. Download AACS key database (KEYDB.cfg)
5. Download BD+ VM files and conversion tables
6. Optionally patch libbdplus for newer BD+ generations

## Usage

```bash
python disc_clouder.py
```

Or with debug mode (limits rips to 2 minutes for testing):

```bash
python disc_clouder.py --debug
```

The app auto-detects if it's not running in the `disc_clouder` conda environment and restarts itself in it.

## Workflow

1. Insert a disc — the app scans automatically
2. Click a title in the list to preview it
3. Choose audio track from the dropdown
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

This software is designed to rip **unprotected** DVDs and Blu-rays. It is not designed or intended to circumvent copy protection mechanisms (CSS, AACS, BD+). No decryption libraries, keys, or DRM-bypassing tools are included or distributed.

It is the user's sole responsibility to ensure compliance with applicable copyright laws in their jurisdiction.

## License

MIT License — see [LICENSE](LICENSE)

## Author

Johannes Hinterberger
