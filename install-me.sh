#!/bin/bash
# JoPhi's Disc Clouder — macOS Installation (ohne Entschlüsselungs-Bibliotheken)
set -e

echo "=== JoPhi's Disc Clouder — macOS Installation ==="
echo

# Homebrew prüfen
if ! command -v brew &>/dev/null; then
    echo "Homebrew nicht gefunden. Bitte installieren: https://brew.sh"
    exit 1
fi

# Conda prüfen
if ! command -v conda &>/dev/null; then
    echo "Conda nicht gefunden. Bitte Miniconda installieren: https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

# Conda Environment erstellen
echo "--- Conda Environment ---"
ENV_NAME="disc_clouder"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Conda env '${ENV_NAME}' existiert bereits"
else
    echo "Erstelle Conda env '${ENV_NAME}' mit Python 3.12.3..."
    conda create -n "$ENV_NAME" python=3.12.3 -y
fi
echo "Installiere Python-Pakete in Conda env..."
conda run -n "$ENV_NAME" pip install -r "$SCRIPT_DIR/requirements.txt"
echo

# Brew-Pakete
echo "--- Brew-Pakete ---"
for pkg in ffmpeg lsdvd p7zip; do
    brew list "$pkg" &>/dev/null && echo "$pkg: bereits installiert" || brew install "$pkg"
done
if brew list --cask vlc &>/dev/null || [ -d "/Applications/VLC.app" ]; then
    echo "vlc: bereits installiert"
else
    brew install --cask vlc
fi

echo
echo "=== Installation abgeschlossen ==="
echo
echo "Hinweis: Für verschlüsselte DVDs/Blu-rays werden zusätzlich benötigt:"
echo "  - libdvdcss (DVD-Entschlüsselung)"
echo "  - libaacs + KEYDB.cfg (AACS Blu-ray-Entschlüsselung)"
echo "  - libbdplus + VM/Convtab-Dateien (BD+ Blu-ray-Entschlüsselung)"
echo "Diese Komponenten sind nicht Teil dieser Installation."
echo
echo "Starte mit: python $SCRIPT_DIR/disc_clouder.py"
