#!/bin/bash
# JoPhi's Disc Clouder — macOS Installation (without decryption libraries)
set -e

echo "=== JoPhi's Disc Clouder — macOS Installation ==="
echo

# Check Homebrew
if ! command -v brew &>/dev/null; then
    echo "Homebrew not found. Please install: https://brew.sh"
    exit 1
fi

# Check Conda
if ! command -v conda &>/dev/null; then
    echo "Miniconda not found."
    read -p "Install Miniconda now? [y/N] " INSTALL_CONDA
    if [[ "$INSTALL_CONDA" =~ ^[yY]$ ]]; then
        ARCH=$(uname -m)
        if [ "$ARCH" = "arm64" ]; then
            CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh"
        else
            CONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
        fi
        echo "Downloading Miniconda ($ARCH)..."
        curl -L -o /tmp/miniconda.sh "$CONDA_URL"
        bash /tmp/miniconda.sh -b -p "$HOME/miniconda3"
        rm -f /tmp/miniconda.sh
        eval "$("$HOME/miniconda3/bin/conda" shell.bash hook)"
        conda init zsh bash 2>/dev/null || true
        echo "Miniconda installed. Please restart your shell and run this script again: ./install-me.sh"
        exit 0
    else
        echo "Aborted. Miniconda is required."
        exit 1
    fi
fi

# Conda environment
echo "--- Conda Environment ---"
ENV_NAME="disc_clouder"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if conda env list | grep -q "^${ENV_NAME} "; then
    echo "Conda env '${ENV_NAME}' already exists"
else
    echo "Creating conda env '${ENV_NAME}' with Python 3.12.3..."
    conda create -n "$ENV_NAME" python=3.12.3 -y
fi
echo "Installing Python packages..."
conda run -n "$ENV_NAME" pip install -r "$SCRIPT_DIR/requirements.txt"
echo

# Brew packages (dependencies, NOT ffmpeg — we build that from source)
echo "--- Brew Packages ---"
for pkg in libbluray libx264 libx265 lame opus dav1d libvpx svt-av1 lsdvd p7zip; do
    brew list "$pkg" &>/dev/null && echo "$pkg: already installed" || brew install "$pkg"
done
if brew list --cask vlc &>/dev/null || [ -d "/Applications/VLC.app" ]; then
    echo "vlc: already installed"
else
    brew install --cask vlc
fi

# Build ffmpeg from source (with --enable-libbluray for bluray:// protocol)
echo
echo "--- ffmpeg (from source) ---"
if command -v ffmpeg &>/dev/null && ffmpeg -protocols 2>&1 | grep -q "bluray"; then
    echo "ffmpeg with bluray support already installed"
else
    echo "Building ffmpeg from source with libbluray support..."
    cd /tmp
    git clone https://git.ffmpeg.org/ffmpeg.git ffmpeg-build 2>/dev/null || (cd ffmpeg-build && git pull)
    cd ffmpeg-build
    ./configure \
        --prefix=/opt/homebrew \
        --enable-gpl \
        --enable-libbluray \
        --enable-videotoolbox \
        --enable-audiotoolbox \
        --enable-libx264 \
        --enable-libx265 \
        --enable-libmp3lame \
        --enable-libopus \
        --enable-libdav1d \
        --enable-libvpx \
        --enable-libsvtav1 \
        --enable-neon \
        --extra-cflags=-I/opt/homebrew/include \
        --extra-ldflags=-L/opt/homebrew/lib
    make -j$(sysctl -n hw.ncpu)
    make install
    cd /tmp && rm -rf ffmpeg-build
    echo "ffmpeg built and installed"
fi

# Symlinks for libaacs/libbdplus (if installed later, VLC looks in /usr/local/lib/)
echo
echo "--- Symlinks ---"
sudo mkdir -p /usr/local/lib
sudo ln -sf /opt/homebrew/lib/libaacs.dylib /usr/local/lib/libaacs.dylib
sudo ln -sf /opt/homebrew/lib/libbdplus.dylib /usr/local/lib/libbdplus.dylib
echo "Symlinks created"

echo
echo "=== Installation complete ==="
echo
echo "Note: For encrypted DVDs/Blu-rays you also need:"
echo "  - libdvdcss (DVD decryption)"
echo "  - libaacs + KEYDB.cfg (AACS Blu-ray decryption)"
echo "  - libbdplus + VM/convtab files (BD+ Blu-ray decryption)"
echo "These components are not part of this installation."
echo
echo "Run with:"
echo "  Blu-ray: python $SCRIPT_DIR/BLURAY-ONLY.py"
echo "  DVD:     python $SCRIPT_DIR/DVD-ONLY.py"
