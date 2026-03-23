#!/bin/bash
# JoPhi's Disc Clouder — macOS Installation
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
for pkg in ffmpeg libdvdcss libaacs libbdplus lsdvd megatools p7zip; do
    brew list "$pkg" &>/dev/null && echo "$pkg: bereits installiert" || brew install "$pkg"
done
for cask in vlc; do
    if brew list --cask "$cask" &>/dev/null || [ -d "/Applications/VLC.app" ]; then
        echo "$cask: bereits installiert"
    else
        brew install --cask "$cask"
    fi
done

# Symlinks für libaacs/libbdplus (VLC sucht in /usr/local/lib/)
echo
echo "--- Symlinks ---"
sudo mkdir -p /usr/local/lib
sudo ln -sf /opt/homebrew/lib/libaacs.dylib /usr/local/lib/libaacs.dylib
sudo ln -sf /opt/homebrew/lib/libbdplus.dylib /usr/local/lib/libbdplus.dylib
echo "Symlinks gesetzt"

# AACS KEYDB
echo
echo "--- AACS Konfiguration ---"
AACS_DIR="$HOME/.config/aacs"
mkdir -p "$AACS_DIR"
if [ ! -f "$AACS_DIR/KEYDB.cfg" ]; then
    echo "Lade KEYDB herunter (deutsch, ~22 MB)..."
    curl -L -o /tmp/keydb_deu.zip "http://fvonline-db.bplaced.net/fv_download.php?lang=deu"
    unzip -o /tmp/keydb_deu.zip -d /tmp/keydb_extract/
    unzip -o /tmp/keydb_deu.zip keydb.cfg -d "$AACS_DIR/"
    mv "$AACS_DIR/keydb.cfg" "$AACS_DIR/KEYDB.cfg"
    echo "KEYDB.cfg installiert ($(du -h "$AACS_DIR/KEYDB.cfg" | cut -f1) entpackt)"
    rm -f /tmp/keydb_deu.zip
else
    echo "KEYDB.cfg vorhanden"
fi

# BD+ VM-Dateien (macOS-Pfade!)
echo
echo "--- BD+ VM-Dateien ---"
BDPLUS_VM="$HOME/Library/Preferences/bdplus/vm0"
if [ ! -d "$BDPLUS_VM" ]; then
    echo "Lade BD+ VM-Dateien herunter..."
    megadl "https://mega.nz/#!MFlTDYiT!I-laau3lrg9OgcAL-1DPk-c9ytxbOCKUj73NBhI8Cr0" --path /tmp/
    mkdir -p "$HOME/Library/Preferences/bdplus"
    unzip -o /tmp/vm0.zip -d "$HOME/Library/Preferences/bdplus/"
    rm -f /tmp/vm0.zip
    echo "VM-Dateien installiert"
else
    echo "VM-Dateien vorhanden"
fi

# BD+ Conversion Tables
echo
echo "--- BD+ Conversion Tables ---"
CONVTAB="$HOME/Library/Caches/bdplus/convtab"
if [ ! -d "$CONVTAB" ] || [ -z "$(ls -A "$CONVTAB" 2>/dev/null)" ]; then
    echo "Lade BD+ Conversion Tables herunter (1.6 GB)..."
    megadl "https://mega.nz/#!Jd1xEQbJ!DRhG9eWLNnrmA5dcwHugnKxmVUpIsT9X-HKuuGjU7n8" --path /tmp/
    mkdir -p "$CONVTAB"
    7z x /tmp/2019-09-29_bdplus_tables.7z -o"$CONVTAB" -y
    rm -f /tmp/2019-09-29_bdplus_tables.7z

    echo "Lade 2022 Update..."
    megadl "https://mega.nz/file/gVsRQQ7Y#JOJwO5woXdz2X73rrvHHBTYCdLposz7aiSVkEX4vChM" --path /tmp/
    7z x /tmp/2022-06-19_bdplus_tables_update.7z -o"$CONVTAB" -y
    rm -f /tmp/2022-06-19_bdplus_tables_update.7z

    echo "Lade 2023 Update..."
    megadl "https://mega.nz/file/AR8DDaib#GgSUMnNGBlVXdJT0BEkNkGm5f4NfodBaQ8SSgFFM4ZA" --path /tmp/
    7z x /tmp/2023-07-28_bdplus_tables_update.7z -o"$CONVTAB" -y
    rm -f /tmp/2023-07-28_bdplus_tables_update.7z

    echo "Conversion Tables installiert"
else
    COUNT=$(ls "$CONVTAB" | wc -l | tr -d ' ')
    echo "Conversion Tables vorhanden: $COUNT Dateien"
fi

# Gepatchte libbdplus (BD+ Generation 4+ Support)
echo
echo "--- libbdplus patchen (BD+ Gen 4+ Support) ---"
read -p "libbdplus patchen für neuere BD+ Discs? [j/N] " PATCH
if [[ "$PATCH" =~ ^[jJyY]$ ]]; then
    cd /tmp
    git clone https://code.videolan.org/videolan/libbdplus.git libbdplus-git 2>/dev/null || true
    cd libbdplus-git
    sed -i '' 's/if (gen > 3) {/if (0 \&\& gen > 3) {/' src/libbdplus/bdsvm/loader.c
    autoreconf -fi
    ./configure --prefix=/opt/homebrew --disable-dependency-tracking
    make -j$(sysctl -n hw.ncpu)
    make install
    cd /tmp && rm -rf libbdplus-git
    echo "libbdplus gepatcht und installiert"
else
    echo "Übersprungen"
fi

echo
echo "=== Installation abgeschlossen ==="
echo "Starte mit: conda run -n disc_clouder python $SCRIPT_DIR/disc_clouder.py"
