#!/usr/bin/env python3
"""JoPhi's Disc Clouder — Blu-ray ONLY Edition (v2)."""

import os, sys, re, ctypes, struct, subprocess, time, threading, glob
from collections import Counter

import vlc
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSlider, QProgressBar, QSpinBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QStackedWidget, QTabWidget, QMessageBox,
)
from PyQt6.QtGui import QFont, QPixmap, QIcon

# ═══════════════════════════════════════════════════════════════════════════
# 1. DISC — constants, MPLS parser, scanning
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_OUTPUT = os.path.expanduser("~/Desktop/filme_sicherungen")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
APP_TMP = os.path.join(APP_DIR, "tmp")
os.makedirs(APP_TMP, exist_ok=True)
TMP_MKV = os.path.join(APP_TMP, "disc_clouder_rip.mkv")
TMP_THUMB = os.path.join(APP_TMP, "disc_clouder_thumb.jpg")
FFMPEG_LOG = os.path.join(APP_TMP, "disc_clouder_ffmpeg.log")
LIBBLURAY_PATH = "/opt/homebrew/lib/libbluray.dylib"

DARK_STYLE = """
QMainWindow, QWidget { background: #0d1b2a; color: #e0e0e0; }
QLabel { color: #e0e0e0; }
QPushButton { background: #1b2838; color: white; border: 1px solid #2a4a6b;
              border-radius: 6px; padding: 8px 16px; font-size: 13px; }
QPushButton:hover { background: #2a4a6b; }
QPushButton#queueBtn { background: #1db954; color: white; font-weight: bold;
    font-size: 15px; padding: 10px 24px; }
QPushButton#queueBtn:hover { background: #1ed760; }
QPushButton#ripBtn { background: #1db954; color: white; font-weight: bold;
    font-size: 15px; padding: 10px 24px; }
QPushButton#ripBtn:hover { background: #1ed760; }
QPushButton#stopBtn { background: #e74c5e; }
QPushButton#ejectBtn { background: #e74c5e; }
QPushButton#clearBtn { background: #e74c5e; font-size: 12px; padding: 6px 12px; }
QLineEdit { background: #1b2838; color: white; border: 1px solid #2a4a6b;
            border-radius: 4px; padding: 6px; }
QTreeWidget { background: #0f2137; color: #e0e0e0; border: 1px solid #1a3a5c;
              border-radius: 6px; alternate-background-color: #132d4a; }
QTreeWidget::item { padding: 10px 4px; border-bottom: 1px solid #1a3a5c; min-height: 32px; }
QTreeWidget::item:selected { background: #8b2035; }
QTreeWidget::header { background: #0a1628; }
QHeaderView::section { background: #0a1628; color: #4ecdc4; border: none;
                       padding: 8px; font-weight: bold; }
QSlider::groove:horizontal { background: #1b2838; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #1db954; width: 14px; height: 14px;
                             margin: -4px 0; border-radius: 7px; }
QSlider::sub-page:horizontal { background: #1db954; border-radius: 3px; }
QProgressBar { background: #1b2838; border: 2px solid #2a4a6b; border-radius: 8px;
               text-align: center; color: white; font-size: 16px; font-weight: bold; }
QProgressBar::chunk { background: #1db954; border-radius: 6px; }
QTabWidget::pane { border: 1px solid #1a3a5c; border-radius: 6px; background: #0d1b2a; }
QTabBar::tab { background: #1b2838; color: #8899aa; padding: 8px 20px;
               border: 1px solid #1a3a5c; border-bottom: none;
               border-top-left-radius: 6px; border-top-right-radius: 6px; }
QTabBar::tab:selected { background: #0d1b2a; color: #4ecdc4; font-weight: bold; }
"""

LANG_MAP = {
    "german": "ger", "deutsch": "ger", "english": "eng",
    "french": "fre", "français": "fre", "italian": "ita",
    "spanish": "spa", "português": "por", "portuguese": "por",
    "japanese": "jpn", "chinese": "chi", "korean": "kor",
    "russian": "rus", "polish": "pol", "hungarian": "hun",
    "dutch": "dut", "swedish": "swe", "danish": "dan",
    "norwegian": "nor", "finnish": "fin", "czech": "cze",
    "turkish": "tur", "arabic": "ara", "hindi": "hin",
}
LANG_NAMES = {
    "deu": "Deutsch", "ger": "Deutsch", "eng": "English",
    "fra": "Français", "fre": "Français", "spa": "Español",
    "ita": "Italiano", "nld": "Nederlands", "dut": "Nederlands",
    "por": "Português", "jpn": "Japanese", "zho": "Chinese",
    "chi": "Chinese", "kor": "Korean", "rus": "Russian",
    "pol": "Polish", "hun": "Hungarian", "swe": "Swedish",
    "dan": "Danish", "nor": "Norwegian", "fin": "Finnish",
    "ces": "Czech", "cze": "Czech", "tur": "Turkish",
    "ara": "Arabic", "hin": "Hindi",
}
AUDIO_STREAM_TYPES = {0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0xA1, 0xA2}
CODEC_NAMES = {
    0x80: "PCM", 0x81: "AC3", 0x82: "DTS", 0x83: "TrueHD",
    0x84: "AC3+", 0x85: "DTS-HD HR", 0x86: "DTS-HD MA",
    0xA1: "AC3 sec", 0xA2: "DTS-HD sec",
}
CH_NAMES = {1: "Mono", 3: "Stereo", 6: "5.1", 12: "7.1"}


# --- MPLS parser ---

def parse_mpls_audio(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return []
    if data[:4] != b"MPLS":
        return []
    pl_start = struct.unpack(">I", data[8:12])[0]
    pos = pl_start + 10
    if pos + 2 > len(data):
        return []
    item_len = struct.unpack(">H", data[pos:pos+2])[0]
    item_data = data[pos+2:pos+2+item_len]
    audio = []
    i = 0
    while i < len(item_data) - 15:
        if item_data[i] == 0x09 and item_data[i+1] == 0x01 \
                and i+10 < len(item_data) and item_data[i+10] == 0x05:
            st = item_data[i+11]
            if st in AUDIO_STREAM_TYPES:
                fmt = item_data[i+12]
                lang = item_data[i+13:i+16].decode("ascii", errors="replace")
                audio.append({
                    "lang": lang,
                    "lang_name": LANG_NAMES.get(lang, lang),
                    "codec": CODEC_NAMES.get(st, "?"),
                    "channels": CH_NAMES.get((fmt >> 4) & 0x0F, "?"),
                })
            i += 16
        else:
            i += 1
    return audio


def parse_mpls_duration(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return 0
    if data[:4] != b"MPLS":
        return 0
    pl_start = struct.unpack(">I", data[8:12])[0]
    pos = pl_start + 6
    if pos + 4 > len(data):
        return 0
    num_items = struct.unpack(">H", data[pos:pos+2])[0]
    pos += 4
    total = 0
    for _ in range(num_items):
        if pos + 2 > len(data):
            break
        il = struct.unpack(">H", data[pos:pos+2])[0]
        item = data[pos+2:pos+2+il]
        if len(item) >= 20:
            total += struct.unpack(">I", item[16:20])[0] - struct.unpack(">I", item[12:16])[0]
        pos += 2 + il
    return total // 45000


def _parse_mpls_clips(path):
    try:
        data = open(path, "rb").read()
    except OSError:
        return []
    if data[:4] != b"MPLS":
        return []
    pl_start = struct.unpack(">I", data[8:12])[0]
    pos = pl_start + 6
    if pos + 4 > len(data):
        return []
    num_items = struct.unpack(">H", data[pos:pos+2])[0]
    pos += 4
    clips = []
    for _ in range(num_items):
        if pos + 2 > len(data):
            break
        il = struct.unpack(">H", data[pos:pos+2])[0]
        item = data[pos+2:pos+2+il]
        name = item[0:5].decode("ascii", errors="replace")
        in_t = struct.unpack(">I", item[12:16])[0] if len(item) >= 16 else 0
        out_t = struct.unpack(">I", item[16:20])[0] if len(item) >= 20 else 0
        clips.append((name, in_t, out_t))
        pos += 2 + il
    return clips


def get_mpls_audio_for_disc(mount):
    """Scan MPLS, filter like VLC (TITLES_RELEVANT 0x03, min 60s)."""
    pl_dir = os.path.join(mount, "BDMV", "PLAYLIST")
    if not os.path.isdir(pl_dir):
        return {}
    all_mpls = {}
    for f in sorted(os.listdir(pl_dir)):
        if not f.endswith(".mpls"):
            continue
        num = int(f.replace(".mpls", ""))
        p = os.path.join(pl_dir, f)
        dur = parse_mpls_duration(p)
        if dur < 60:
            continue
        all_mpls[num] = {"duration": dur, "audio": parse_mpls_audio(p), "clips": _parse_mpls_clips(p)}

    remove = set()
    # Filter 1: repeated clips (>2x)
    for num, info in all_mpls.items():
        if any(c > 2 for c in Counter(info["clips"]).values()):
            remove.add(num)
    # Filter 2: duplicate playlists (same clips + audio count)
    seen = []
    for num in sorted(all_mpls):
        if num in remove:
            continue
        sig = (tuple(all_mpls[num]["clips"]), len(all_mpls[num]["audio"]))
        if sig in seen:
            remove.add(num)
        else:
            seen.append(sig)

    return {n: {"duration": all_mpls[n]["duration"], "audio": all_mpls[n]["audio"]}
            for n in sorted(all_mpls) if n not in remove}


# --- Disc detection ---

def find_disc():
    """Find Blu-ray disc via /Volumes."""
    print("[FIND_DISC] Searching for Blu-ray disc...")
    try:
        for vol in os.listdir("/Volumes"):
            if vol in ("Macintosh HD", "Macintosh HD - Data"):
                continue
            vp = os.path.join("/Volumes", vol)
            bdmv = os.path.join(vp, "BDMV")
            if os.path.isdir(bdmv) and os.path.isdir(os.path.join(bdmv, "PLAYLIST")):
                ssif = os.path.join(bdmv, "STREAM", "SSIF")
                is_3d = os.path.isdir(ssif)
                print(f"[FIND_DISC] Found: {vol} at {vp} (3D={is_3d})")
                return {"mount": vp, "name": vol, "is_3d": is_3d}
    except OSError:
        pass
    print("[FIND_DISC] No Blu-ray disc found")
    return None


# --- libbluray playlist map ---

class _BDTitleInfo(ctypes.Structure):
    _fields_ = [("idx", ctypes.c_uint32), ("playlist", ctypes.c_uint32),
                ("duration", ctypes.c_uint64), ("clip_count", ctypes.c_uint32),
                ("angle_count", ctypes.c_uint8), ("chapter_count", ctypes.c_uint32)]


def _get_playlist_map(mount):
    """Return {title_idx: playlist_number} via libbluray."""
    try:
        lib = ctypes.CDLL(LIBBLURAY_PATH)
    except OSError:
        return {}
    lib.bd_open.restype = ctypes.c_void_p
    lib.bd_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.bd_get_titles.restype = ctypes.c_uint32
    lib.bd_get_titles.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint32]
    lib.bd_get_title_info.restype = ctypes.POINTER(_BDTitleInfo)
    lib.bd_get_title_info.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    lib.bd_free_title_info.restype = None
    lib.bd_free_title_info.argtypes = [ctypes.POINTER(_BDTitleInfo)]
    lib.bd_close.restype = None
    lib.bd_close.argtypes = [ctypes.c_void_p]
    bd = lib.bd_open(mount.encode(), None)
    if not bd:
        return {}
    m = {}
    for i in range(lib.bd_get_titles(bd, 0x03, 60)):
        info = lib.bd_get_title_info(bd, i, 0)
        if info:
            m[i] = info.contents.playlist
            lib.bd_free_title_info(info)
    lib.bd_close(bd)
    return m


# --- Scan ---

def scan(disc, vlc_instance):
    """Scan disc: VLC for titles, libbluray for playlist map, MPLS for audio."""
    print(f"[SCAN] Starting scan for {disc['name']}")

    # VLC: get title list
    mrl = f"bluray://{disc['mount']}"
    player = vlc_instance.media_player_new()
    media = vlc_instance.media_new(mrl)
    media.add_option("no-bluray-menu")
    player.set_media(media)
    player.audio_set_volume(0)
    player.play()
    print("[SCAN] VLC player started, waiting for playback...")

    for attempt in range(240):
        time.sleep(0.5)
        state = player.get_state()
        if state in (vlc.State.Playing, vlc.State.Paused):
            print(f"[SCAN] VLC playing after {(attempt+1)*0.5:.1f}s")
            break
        if attempt % 20 == 19:
            print(f"[SCAN] Still waiting... ({(attempt+1)*0.5:.0f}s, state={state})")
    else:
        print(f"[SCAN] WARNING: VLC not playing after 120s (state={player.get_state()})")

    title_descs = list(player.get_full_title_descriptions() or [])
    if not title_descs:
        time.sleep(2)
        title_descs = list(player.get_full_title_descriptions() or [])
    print(f"[SCAN] Found {len(title_descs)} titles")

    player.stop()
    player.release()
    print("[SCAN] Scan player released")

    # libbluray: exact title→playlist mapping
    playlist_map = _get_playlist_map(disc["mount"])
    print(f"[SCAN] Playlist map: {len(playlist_map)} entries")

    # MPLS: audio data + VLC-style filter
    mpls_data = get_mpls_audio_for_disc(disc["mount"])
    print(f"[SCAN] MPLS filtered: {len(mpls_data)} playlists")
    for pl, info in sorted(mpls_data.items()):
        print(f"[SCAN]   MPLS {pl:05d}: dur={info['duration']}s, audio={len(info['audio'])}")

    # Build track list: VLC title → playlist → MPLS audio
    tracks = []
    mpls_used = set()
    for i, td in enumerate(title_descs):
        dur = td.duration // 1000
        if dur < 60:
            continue
        pl_num = playlist_map.get(i)
        audio = []
        if pl_num is not None and pl_num in mpls_data:
            audio = mpls_data[pl_num]["audio"]
            mpls_used.add(pl_num)
        elif pl_num is None:
            # Fallback: duration matching
            for pn, pi in sorted(mpls_data.items()):
                if pn not in mpls_used and abs(pi["duration"] - dur) < 5:
                    audio = pi["audio"]
                    pl_num = pn
                    mpls_used.add(pn)
                    break
        print(f"[SCAN] Title {i}: dur={dur}s → playlist {pl_num}, audio={len(audio)}")
        tracks.append({"idx": i, "duration": dur, "audio": audio,
                        "playlist": pl_num, "video_codec": "?"})

    # Sort: most audio tracks first, then longest
    tracks.sort(key=lambda t: (-len(t["audio"]), -t["duration"]))
    print(f"[SCAN] Final: {len(tracks)} tracks")
    return tracks


# ═══════════════════════════════════════════════════════════════════════════
# 2. RIP — ffmpeg worker
# ═══════════════════════════════════════════════════════════════════════════

class RipWorker(QThread):
    progress_rip = pyqtSignal(int, int)
    progress_convert = pyqtSignal(int, int)
    thumbnail = pyqtSignal(str)
    status = pyqtSignal(str)
    job_started = pyqtSignal(int, int, str)
    job_finished = pyqtSignal(int, str)
    all_finished = pyqtSignal()
    cancelled = pyqtSignal()
    error = pyqtSignal(int, str)

    def __init__(self, queue, mount, output_dir, readrate=2, trouble_mode=False, sudo_pw=None):
        super().__init__()
        self.queue = queue
        self.mount = mount
        self.output_dir = output_dir
        self.readrate = readrate
        self.trouble_mode = trouble_mode
        self.sudo_pw = sudo_pw
        self._cancel = False

    def cancel(self):
        print("[RIP] Cancel requested")
        self._cancel = True

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        total = len(self.queue)

        for i, job in enumerate(self.queue):
            if self._cancel:
                break

            name = job["name"]
            mp4_path = os.path.join(self.output_dir, f"{name}.mp4")
            self.job_started.emit(i, total, name)
            self.status.emit(f"Rippe: {name}")

            # Step 1: Disc → MKV
            try:
                self._rip(job)
            except Exception as e:
                print(f"[RIP] Exception: {e}")

            if self._cancel:
                break

            # Step 2: MKV → MP4
            if os.path.exists(TMP_MKV):
                self.status.emit(f"Konvertiere: {name}")
                try:
                    self._convert(TMP_MKV, mp4_path)
                except Exception as e:
                    print(f"[CONVERT] Exception: {e}")
                    self.error.emit(i, str(e))
                    self._cleanup()
                    subprocess.run(["say", f"{name} failed"], capture_output=True)
                    continue
            else:
                self.error.emit(i, "Rip fehlgeschlagen — keine Datei")
                subprocess.run(["say", f"{name} failed"], capture_output=True)
                continue

            if self._cancel:
                try: os.remove(mp4_path)
                except OSError: pass
                break

            self._cleanup()
            self.job_finished.emit(i, mp4_path)
            subprocess.run(["say", f"{name} complete"], capture_output=True)

        if self._cancel:
            self._cleanup()
            self.cancelled.emit()
            subprocess.run(["say", "Queue aborted"], capture_output=True)
        else:
            self.all_finished.emit()

    def _cleanup(self):
        for f in [TMP_MKV, TMP_THUMB]:
            try: os.remove(f)
            except OSError: pass

    def _rip(self, job):
        dur = job["duration"]
        playlist = job.get("playlist")
        video_codec = job.get("video_codec", "?")
        all_audio = job.get("all_audio", [])

        # Manual trouble mode
        if self.trouble_mode:
            print("[RIP] Manual TROUBLE MODE activated")
            self.status.emit("TROUBLE MODE — Kopiere Disc...")
            self._trouble_mode(job)
            return

        v_codec = ["-c:v", "copy"] if video_codec.lower() in ("h264", "h.264") \
            else ["-c:v", "h264_videotoolbox", "-q:v", "50"]

        # BD-50 detection (single diskutil call)
        is_bd50 = False
        is_virtual = False
        try:
            r = subprocess.run(["diskutil", "info", self.mount],
                               capture_output=True, text=True, timeout=5)
            m = re.search(r"Disk Size:\s+(\d[\d.]*)\s+GB", r.stdout)
            if m and float(m.group(1)) > 30:
                is_bd50 = True
            is_virtual = "Virtual:                   Yes" in r.stdout
        except Exception:
            pass

        cmd = ["ffmpeg", "-y", "-err_detect", "ignore_err", "-max_error_rate", "1.0"]
        if is_bd50 and not is_virtual:
            rate = self.readrate
            if rate > 0:
                cmd += ["-readrate", str(rate)]
                print(f"[RIP] Dual-layer (BD-50) — readrate {rate}x")
            else:
                print("[RIP] Dual-layer (BD-50) — Max speed")
        elif is_bd50:
            print("[RIP] Dual-layer (BD-50) on disk image — no readrate limit")
        if playlist is not None:
            cmd += ["-playlist", str(playlist)]
        cmd += ["-i", f"bluray://{self.mount}", "-map", "0:v:0"]
        for a in all_audio:
            cmd += ["-map", f"0:a:{a['idx']}"]
        cmd += [*v_codec, "-c:a", "aac", "-ac", "2", "-b:a", "192k"]
        for ai, a in enumerate(all_audio):
            cmd += [f"-metadata:s:a:{ai}", f"language={a['lang']}",
                    f"-metadata:s:a:{ai}", f"title={a['label']}"]
        cmd += ["-progress", "pipe:1", TMP_MKV]
        print(f"[RIP] cmd: {' '.join(cmd)}")

        log = open(FFMPEG_LOG, "w")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log,
                                stdin=subprocess.DEVNULL, text=True)
        last_sec, last_pct = 0, -1
        last_size, stall_since = 0, time.time()
        for line in proc.stdout:
            if self._cancel:
                proc.kill(); proc.wait(); log.close()
                return
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    sec = int(line.split("=")[1]) // 1_000_000
                    if sec > last_sec:
                        last_sec = sec
                        self.progress_rip.emit(sec, dur)
                        pct = (sec * 100) // dur if dur > 0 else 0
                        if pct != last_pct and sec > 5:
                            last_pct = pct
                            self._thumb(sec - 2)
                except ValueError:
                    pass
            # Filesize watchdog
            try:
                sz = os.path.getsize(TMP_MKV)
                if sz != last_size:
                    last_size, stall_since = sz, time.time()
                elif time.time() - stall_since > 10:
                    print(f"[WATCHDOG] Stall detected — switching to TROUBLE MODE")
                    proc.kill(); proc.wait(); log.close()
                    self.status.emit("TROUBLE MODE — Kopiere Disc...")
                    self._trouble_mode(job)
                    return
            except OSError:
                pass
        proc.wait()
        log.close()
        # Log ffmpeg errors
        try:
            err = open(FFMPEG_LOG).read()
            if err:
                print(f"[RIP] ffmpeg stderr (last 2000):\n{err[-2000:]}")
        except OSError:
            pass
        self.progress_rip.emit(dur, dur)

    def _thumb(self, sec):
        try:
            subprocess.run(["ffmpeg", "-y", "-ss", str(max(0, sec)), "-i", TMP_MKV,
                            "-frames:v", "1", "-q:v", "5", TMP_THUMB],
                           capture_output=True, timeout=8)
            if os.path.exists(TMP_THUMB) and os.path.getsize(TMP_THUMB) > 0:
                self.thumbnail.emit(TMP_THUMB)
        except Exception:
            pass

    def _trouble_mode(self, job):
        """dd disc to ISO, mount, re-rip from image."""
        print("[TROUBLE] Starting dd...")
        icon_path = os.path.join(APP_DIR, "assets", "bluray-only.png")
        if os.path.exists(icon_path):
            self.thumbnail.emit(icon_path)
        iso_path = os.path.join(APP_TMP, "disc_image.iso")
        # Find device
        r = subprocess.run(["diskutil", "info", self.mount], capture_output=True, text=True, timeout=5)
        dev_match = re.search(r"Device Node:\s+(/dev/disk\d+)", r.stdout)
        if not dev_match:
            print("[TROUBLE] Cannot find device node")
            return
        dev = dev_match.group(1)
        # Unmount (keep device)
        subprocess.run(["diskutil", "unmountDisk", dev], capture_output=True)
        # Get disc size for progress
        size_match = re.search(r"Disk Size:\s+(\d[\d.]*)\s+GB", r.stdout)
        total_bytes = int(float(size_match.group(1)) * 1e9) if size_match else 0
        # dd with sudo (password from main thread dialog)
        print(f"[TROUBLE] dd {dev} → {iso_path} ({total_bytes // 1_000_000_000} GB)")
        dd_proc = subprocess.Popen(
            ["sudo", "-S", "dd", f"if={dev}", f"of={iso_path}", "bs=1m"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        dd_proc.stdin.write(f"{self.sudo_pw}\n".encode())
        dd_proc.stdin.flush()
        # Monitor dd progress via file size
        while dd_proc.poll() is None:
            time.sleep(2)
            if self._cancel:
                dd_proc.kill(); dd_proc.wait()
                print("[TROUBLE] Cancelled")
                return
            try:
                sz = os.path.getsize(iso_path)
                if total_bytes > 0:
                    pct = int(sz * 100 / total_bytes)
                    self.status.emit(f"TROUBLE MODE — Kopiere Disc... {pct}%")
                    print(f"[TROUBLE] dd progress: {pct}% ({sz // 1_000_000} MB)")
            except OSError:
                pass
        dd_proc.wait()
        print(f"[TROUBLE] dd done: {os.path.getsize(iso_path)} bytes")
        # Eject original disc
        subprocess.run(["drutil", "eject"], capture_output=True)
        print("[TROUBLE] Original disc ejected")
        # Mount ISO
        r = subprocess.run(["hdiutil", "attach", iso_path], capture_output=True, text=True)
        mount_match = re.search(r"(/Volumes/.+)$", r.stdout.strip(), re.MULTILINE)
        if not mount_match:
            print("[TROUBLE] Cannot mount ISO")
            return
        new_mount = mount_match.group(1).strip()
        print(f"[TROUBLE] ISO mounted at {new_mount}")
        # Update mount and re-rip
        old_mount = self.mount
        self.mount = new_mount
        self.status.emit("TROUBLE MODE — Rippe von Image...")
        self.trouble_mode = False  # Prevent recursion
        # Clean failed temp file
        try:
            os.remove(TMP_MKV)
        except OSError:
            pass
        self._rip(job)
        # Cleanup
        subprocess.run(["hdiutil", "detach", new_mount], capture_output=True)
        try:
            os.remove(iso_path)
        except OSError:
            pass
        print("[TROUBLE] ISO unmounted and deleted")
        self.mount = old_mount

    def _convert(self, src, dst):
        dur = 0
        try:
            r = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                "-of", "csv=p=0", src], capture_output=True, text=True, timeout=10)
            dur = int(float(r.stdout.strip()))
        except Exception:
            pass
        cmd = ["ffmpeg", "-y", "-i", src, "-map", "0", "-c", "copy", "-movflags", "+faststart",
               "-progress", "pipe:1", dst]
        print(f"[CONVERT] cmd: {' '.join(cmd)}")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL, text=True)
        for line in proc.stdout:
            if self._cancel:
                proc.kill(); proc.wait(); return
            if line.strip().startswith("out_time_ms="):
                try:
                    self.progress_convert.emit(int(line.split("=")[1]) // 1_000_000, dur)
                except ValueError:
                    pass
        proc.wait()
        self.progress_convert.emit(dur, dur)


# ═══════════════════════════════════════════════════════════════════════════
# 3. GUI — main window
# ═══════════════════════════════════════════════════════════════════════════

class DiscClouder(QMainWindow):
    scan_done = pyqtSignal(list)
    codec_ready = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JoPhi's Disc Clouder")
        self.setMinimumSize(1000, 750)
        self.setStyleSheet(DARK_STYLE)
        icon = os.path.join(APP_DIR, "assets", "bluray-only.png")
        if os.path.exists(icon):
            self.setWindowIcon(QIcon(icon))

        self.vlc_instance = vlc.Instance("--no-xlib", "--no-bluray-menu", "--quiet", "--no-spu")
        self.vlc_player = self.vlc_instance.media_player_new()
        self.disc = None
        self.tracks = []
        self.queue = []
        self.rip_worker = None
        self._seeking = False
        self._scanning = False
        self._title_edited = False
        self._loading = False

        self._build_ui()
        self.scan_done.connect(self._on_scan_done)
        self.codec_ready.connect(self._codec_detected)

        self.pos_timer = QTimer()
        self.pos_timer.setInterval(500)
        self.pos_timer.timeout.connect(self._update_pos)

        QTimer.singleShot(500, self._scan)

    # --- UI ---
    def _build_ui(self):
        c = QWidget()
        self.setCentralWidget(c)
        ml = QVBoxLayout(c)
        ml.setSpacing(8)
        ml.setContentsMargins(16, 12, 16, 12)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("JoPhi's Disc Clouder")
        lbl.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        lbl.setStyleSheet("color: #1db954;")
        hdr.addWidget(lbl)
        self.lbl_type = QLabel("")
        self.lbl_type.setStyleSheet("background: #e74c5e; color: white; padding: 2px 10px;"
                                    "border-radius: 4px; font-weight: bold;")
        hdr.addWidget(self.lbl_type)
        self.lbl_disc = QLabel("Keine Disc")
        self.lbl_disc.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        hdr.addWidget(self.lbl_disc)
        hdr.addStretch()
        self.btn_scan = QPushButton("Neu scannen")
        self.btn_scan.clicked.connect(self._scan)
        self.btn_eject = QPushButton("Auswerfen")
        self.btn_eject.setObjectName("ejectBtn")
        self.btn_eject.clicked.connect(self._eject)
        hdr.addWidget(self.btn_scan)
        hdr.addWidget(self.btn_eject)
        ml.addLayout(hdr)

        # Stacked views
        self.stack = QStackedWidget()
        ml.addWidget(self.stack, 1)

        # View 1: Selection
        v1 = QWidget()
        v1l = QVBoxLayout(v1)
        v1l.setContentsMargins(0, 0, 0, 0)
        v1l.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(QLabel("Titel:"))
        self.edit_title = QLineEdit()
        self.edit_title.setPlaceholderText("Filmname")
        self.edit_title.textEdited.connect(lambda: setattr(self, '_title_edited', True))
        row.addWidget(self.edit_title)
        v1l.addLayout(row)

        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background: black;")
        self.video_widget.setMinimumHeight(300)
        v1l.addWidget(self.video_widget)

        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("stopBtn")
        self.btn_stop.clicked.connect(self._stop_player)
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_stop)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, '_seeking', True))
        self.seek_slider.sliderReleased.connect(self._seek_end)
        ctrl.addWidget(self.seek_slider, 1)
        self.lbl_time = QLabel("00:00 / 00:00")
        ctrl.addWidget(self.lbl_time)
        ctrl.addWidget(QLabel("Vol:"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.valueChanged.connect(lambda v: self.vlc_player.audio_set_volume(v))
        ctrl.addWidget(self.vol_slider)
        v1l.addLayout(ctrl)

        self.tabs = QTabWidget()
        v1l.addWidget(self.tabs, 1)

        # Tab: Titel
        t1 = QWidget()
        t1l = QVBoxLayout(t1)
        t1l.setContentsMargins(8, 8, 8, 8)
        ta_row = QHBoxLayout()

        self.track_tree = QTreeWidget()
        self.track_tree.setHeaderLabels(["Nr", "Dauer", "Video", "Audio"])
        self.track_tree.setAlternatingRowColors(True)
        self.track_tree.setRootIsDecorated(False)
        self.track_tree.header().setStretchLastSection(True)
        self.track_tree.itemClicked.connect(self._on_track_clicked)
        ta_row.addWidget(self.track_tree, 2)

        acol = QVBoxLayout()
        albl = QLabel("Audio:")
        albl.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        acol.addWidget(albl)
        self.audio_list = QTreeWidget()
        self.audio_list.setHeaderLabels(["✓", "♥", "Sprache", "Codec", "Kanäle", "Label"])
        self.audio_list.setRootIsDecorated(False)
        self.audio_list.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.audio_list.setMinimumWidth(420)
        self.audio_list.setColumnWidth(0, 30)
        self.audio_list.setColumnWidth(1, 30)
        self.audio_list.itemClicked.connect(self._on_audio_clicked)
        self.audio_list.itemDoubleClicked.connect(self._on_audio_dblclick)
        acol.addWidget(self.audio_list)
        ta_row.addLayout(acol, 1)
        t1l.addLayout(ta_row)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Zusatz:"))
        self.edit_suffix = QLineEdit()
        self.edit_suffix.setPlaceholderText("z.B. Extended, SW...")
        add_row.addWidget(self.edit_suffix, 1)
        self.btn_queue = QPushButton("+ Zur Queue")
        self.btn_queue.setObjectName("queueBtn")
        self.btn_queue.clicked.connect(self._add_to_queue)
        add_row.addWidget(self.btn_queue)
        t1l.addLayout(add_row)
        self.tabs.addTab(t1, "Titel")

        # Tab: Queue
        t2 = QWidget()
        t2l = QVBoxLayout(t2)
        t2l.setContentsMargins(8, 8, 8, 8)
        self.queue_tree = QTreeWidget()
        self.queue_tree.setHeaderLabels(["Name", "Dauer", "Audio", "Video"])
        self.queue_tree.setAlternatingRowColors(True)
        self.queue_tree.setRootIsDecorated(False)
        self.queue_tree.header().setStretchLastSection(True)
        self.queue_tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked)
        self.queue_tree.itemChanged.connect(self._on_queue_changed)
        t2l.addWidget(self.queue_tree)

        bd50_row = QHBoxLayout()
        bd50_row.addWidget(QLabel("BD-50 Speed:"))
        self.spin_readrate = QSpinBox()
        self.spin_readrate.setRange(0, 10)
        self.spin_readrate.setValue(2)
        self.spin_readrate.setSpecialValueText("Max")
        self.spin_readrate.setFixedWidth(70)
        bd50_row.addWidget(self.spin_readrate)
        self.chk_trouble = QCheckBox("Trouble Mode")
        self.chk_trouble.setChecked(True)
        bd50_row.addWidget(self.chk_trouble)
        bd50_row.addStretch()
        t2l.addLayout(bd50_row)

        qrow = QHBoxLayout()
        qrow.addWidget(QLabel("Zielordner:"))
        self.edit_output = QLineEdit(DEFAULT_OUTPUT)
        qrow.addWidget(self.edit_output, 1)
        btn_clear = QPushButton("Queue leeren")
        btn_clear.setObjectName("clearBtn")
        btn_clear.clicked.connect(lambda: (self.queue.clear(), self.queue_tree.clear(),
                                           self.lbl_status.setText("Queue geleert")))
        qrow.addWidget(btn_clear)
        self.btn_start = QPushButton("Queue starten")
        self.btn_start.setObjectName("ripBtn")
        self.btn_start.clicked.connect(self._start_queue)
        qrow.addWidget(self.btn_start)
        t2l.addLayout(qrow)
        self.tabs.addTab(t2, "Queue")
        self.stack.addWidget(v1)

        # View 2: Rip progress
        v2 = QWidget()
        v2l = QVBoxLayout(v2)
        v2l.setContentsMargins(0, 10, 0, 10)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setMinimumHeight(300)
        self.lbl_thumb.setStyleSheet("background: black; border-radius: 6px;")
        v2l.addWidget(self.lbl_thumb, 1)

        self.lbl_rip_title = QLabel("Rippe...")
        self.lbl_rip_title.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        self.lbl_rip_title.setStyleSheet("color: #1db954;")
        self.lbl_rip_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v2l.addWidget(self.lbl_rip_title)
        v2l.addSpacing(10)

        self.lbl_bar1 = QLabel("Disc → MKV")
        self.lbl_bar1.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        v2l.addWidget(self.lbl_bar1)
        self.bar_rip = QProgressBar()
        self.bar_rip.setMinimumHeight(36)
        v2l.addWidget(self.bar_rip)
        self.lbl_rip_stats = QLabel("")
        self.lbl_rip_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_rip_stats.setStyleSheet("color: #8899aa; font-size: 13px;")
        v2l.addWidget(self.lbl_rip_stats)
        v2l.addSpacing(12)

        self.lbl_bar2 = QLabel("MKV → MP4")
        self.lbl_bar2.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        v2l.addWidget(self.lbl_bar2)
        self.bar_convert = QProgressBar()
        self.bar_convert.setMinimumHeight(36)
        v2l.addWidget(self.bar_convert)
        self.lbl_conv_stats = QLabel("")
        self.lbl_conv_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_conv_stats.setStyleSheet("color: #8899aa; font-size: 13px;")
        v2l.addWidget(self.lbl_conv_stats)
        v2l.addSpacing(20)

        cr = QHBoxLayout()
        cr.addStretch()
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setObjectName("stopBtn")
        self.btn_cancel.setFixedWidth(200)
        self.btn_cancel.clicked.connect(self._cancel_rip)
        cr.addWidget(self.btn_cancel)
        cr.addStretch()
        v2l.addLayout(cr)
        v2l.addStretch()
        self.stack.addWidget(v2)

        self.lbl_status = QLabel("")
        ml.addWidget(self.lbl_status)

    # --- Scan (ONE function) ---
    def _scan(self):
        if self._scanning:
            print("[SCAN] Already scanning, skipping")
            return
        print("[SCAN] _scan() called")
        disc = find_disc()
        if disc:
            self._scanning = True
            self.disc = disc
            self.lbl_status.setText("Scanne...")
            def _do():
                tracks = scan(disc, self.vlc_instance)
                self.scan_done.emit(tracks)
            threading.Thread(target=_do, daemon=True).start()
        else:
            reply = QMessageBox.question(
                self, "Disc Clouder", "No disc found. Please insert a Blu-ray disc.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Ok:
                print("[SCAN] OK — waiting for disc...")
                self.lbl_status.setText("Warte auf Disc...")
                def _wait():
                    for _ in range(20):
                        time.sleep(0.5)
                        if find_disc():
                            QTimer.singleShot(0, self._scan)
                            return
                    # Timeout
                    vols = [v for v in os.listdir("/Volumes")
                            if v not in ("Macintosh HD", "Macintosh HD - Data")]
                    msg = (f"Disc '{vols[0]}' is not a Blu-ray or could not be recognized."
                           if vols else "No disc found. Please insert a Blu-ray disc.")
                    QTimer.singleShot(0, lambda: self._show_retry(msg))
                threading.Thread(target=_wait, daemon=True).start()
            else:
                print("[SCAN] Cancel — manual scan needed")
                self.lbl_status.setText("Keine Disc — 'Neu scannen' drücken")

    def _show_retry(self, msg):
        reply = QMessageBox.question(
            self, "Disc Clouder", msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if reply == QMessageBox.StandardButton.Ok:
            self._scan()
        else:
            self.lbl_status.setText("Keine Disc — 'Neu scannen' drücken")

    def _on_scan_done(self, tracks):
        self._scanning = False
        self.tracks = tracks
        print(f"[SCAN_DONE] {len(tracks)} tracks, disc={self.disc}")

        if not self.disc:
            self.lbl_disc.setText("Keine Blu-ray gefunden")
            self.lbl_type.setText("")
            self.lbl_status.setText("")
            self.track_tree.clear()
            self.audio_list.clear()
            return

        self.lbl_disc.setText(self.disc["name"])
        self.lbl_type.setText("BLURAY")
        if not self._title_edited:
            self.edit_title.setText(self.disc["name"].replace("_", " ").title())

        self.track_tree.clear()
        self.audio_list.clear()
        if not tracks:
            self.lbl_status.setText(f"Disc '{self.disc['name']}' erkannt, aber keine Titel lesbar.")
            return

        for t in tracks:
            d = t["duration"]
            QTreeWidgetItem(self.track_tree, [str(t["idx"]), f"{d//60}:{d%60:02d}",
                                               t.get("video_codec", "?"),
                                               f"{len(t['audio'])} Spuren"])
        for i in range(4):
            self.track_tree.resizeColumnToContents(i)

        self.vlc_player.set_nsobject(int(self.video_widget.winId()))
        self.lbl_status.setText(f"{len(tracks)} Titel gefunden")
        print("[SCAN_DONE] Ready (waiting for track click)")

    # --- Track click ---
    def _on_track_clicked(self, item, col):
        idx = int(item.text(0))
        track = next((t for t in self.tracks if t["idx"] == idx), None)
        if not track:
            return
        print(f"[TRACK] Clicked idx={idx}, dur={track['duration']}s, audio={len(track['audio'])}")

        # Set media with title option, then play
        mrl = f"bluray://{self.disc['mount']}"
        media = self.vlc_instance.media_new(mrl)
        media.add_option("no-bluray-menu")
        media.add_option(f":title={idx}")
        self.vlc_player.set_media(media)
        self.vlc_player.audio_set_volume(self.vol_slider.value())
        self.vlc_player.video_set_spu(-1)
        self.vlc_player.play()
        self.pos_timer.start()
        self.btn_play.setText("Pause")
        self.btn_queue.setEnabled(False)
        self.btn_queue.setText("Ermittle Codec...")
        print(f"[TRACK] Playing title {idx}")

        # Detect video codec after VLC starts playing
        def _detect_codec():
            # Wait until VLC is actually playing
            for _ in range(20):
                time.sleep(0.5)
                if self.vlc_player.get_state() == vlc.State.Playing:
                    break
            media = self.vlc_player.get_media()
            if media:
                codecs = {"h264": "H.264", "H264": "H.264", "avc1": "H.264", "AVC1": "H.264",
                          "hevc": "HEVC", "HEVC": "HEVC", "mpgv": "MPEG-2",
                          "VC-1": "VC-1", "WVC1": "VC-1", "av01": "AV1"}
                try:
                    for t in media.tracks_get():
                        if t.type == vlc.TrackType.video:
                            fc = struct.pack("<I", t.codec).decode("ascii", errors="replace").strip()
                            track["video_codec"] = codecs.get(fc, fc)
                            print(f"[TRACK] Video codec: {track['video_codec']}")
                            for j in range(self.track_tree.topLevelItemCount()):
                                ti = self.track_tree.topLevelItem(j)
                                if int(ti.text(0)) == idx:
                                    ti.setText(2, track["video_codec"])
                            break
                except Exception:
                    pass
            self.codec_ready.emit(track.get("video_codec", "?"))
        threading.Thread(target=_detect_codec, daemon=True).start()

        # Audio list from MPLS
        self.audio_list.clear()
        for a in track["audio"]:
            ai = QTreeWidgetItem(["", "", a.get("lang_name", "?"), a.get("codec", "?"),
                                  a.get("channels", "?"), a.get("lang_name", "?")])
            ai.setData(0, Qt.ItemDataRole.UserRole, a)
            ai.setCheckState(0, Qt.CheckState.Unchecked)
            self.audio_list.addTopLevelItem(ai)
        self.audio_list.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        for i in range(6):
            self.audio_list.resizeColumnToContents(i)
        item.setText(3, f"{len(track['audio'])} Spuren")
        self.edit_suffix.clear()

    def _codec_detected(self, codec):
        self.btn_queue.setEnabled(True)
        self.btn_queue.setText("+ Zur Queue")
        self.lbl_status.setText(f"Video: {codec}")

    # --- Player controls ---
    def _toggle_play(self):
        state = self.vlc_player.get_state()
        print(f"[PLAY] state={state}")
        if state == vlc.State.Playing:
            self.vlc_player.pause()
            self.btn_play.setText("Play")
        else:
            self.vlc_player.play()
            self.vlc_player.audio_set_volume(self.vol_slider.value())
            self.btn_play.setText("Pause")
            self.pos_timer.start()

    def _stop_player(self):
        print("[STOP] Stopping player")
        self.vlc_player.stop()
        self.pos_timer.stop()
        self.btn_play.setText("Play")
        self.lbl_time.setText("00:00 / 00:00")
        self.seek_slider.setValue(0)

    def _update_pos(self):
        if self._seeking:
            return
        state = self.vlc_player.get_state()
        if state not in (vlc.State.Playing, vlc.State.Paused):
            return
        pos = self.vlc_player.get_time() or 0
        length = self.vlc_player.get_length() or 1
        ps, ls = pos // 1000, length // 1000
        self.lbl_time.setText(f"{ps//60:02d}:{ps%60:02d} / {ls//60:02d}:{ls%60:02d}")
        if length > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(pos * 1000 / length))
            self.seek_slider.blockSignals(False)

    def _seek_end(self):
        self._seeking = False
        val = self.seek_slider.value()
        length = self.vlc_player.get_length() or 1
        target = int(val * length / 1000)
        print(f"[SEEK] Seeking to {target//1000}s ({val/10:.1f}%)")
        self.vlc_player.set_time(target)

    # --- Audio click ---
    def _on_audio_clicked(self, item, col):
        row = self.audio_list.indexOfTopLevelItem(item)
        a = item.data(0, Qt.ItemDataRole.UserRole)
        lang = a.get("lang", "?") if a else "?"

        if col == 1:  # Heart (primary)
            for i in range(self.audio_list.topLevelItemCount()):
                o = self.audio_list.topLevelItem(i)
                if o == item:
                    o.setText(1, "❤️")
                    o.setCheckState(0, Qt.CheckState.Checked)
                else:
                    o.setText(1, "")
            print(f"[AUDIO] ❤️ Primary: {lang}")
        elif col == 0:  # Checkbox
            checked = item.checkState(0) == Qt.CheckState.Checked
            if not checked:
                item.setText(1, "")
                print(f"[AUDIO] Unchecked: {lang}")
                # Auto-promote next checked
                if not any(self.audio_list.topLevelItem(i).text(1) == "❤️"
                           for i in range(self.audio_list.topLevelItemCount())):
                    for i in range(self.audio_list.topLevelItemCount()):
                        o = self.audio_list.topLevelItem(i)
                        if o.checkState(0) == Qt.CheckState.Checked:
                            o.setText(1, "❤️")
                            od = o.data(0, Qt.ItemDataRole.UserRole)
                            print(f"[AUDIO] ❤️ Auto-promoted: {od.get('lang') if od else '?'}")
                            break
            else:
                if not any(self.audio_list.topLevelItem(i).text(1) == "❤️"
                           for i in range(self.audio_list.topLevelItemCount())):
                    item.setText(1, "❤️")
                    print(f"[AUDIO] ❤️ Auto-primary: {lang}")
                else:
                    print(f"[AUDIO] ✓ Included: {lang}")

        # Switch preview audio (index-based)
        if row >= 0:
            valid = [(x[0] if isinstance(x, tuple) else x.id)
                     for x in (self.vlc_player.audio_get_track_description() or [])
                     if (x[0] if isinstance(x, tuple) else x.id) >= 0]
            if row < len(valid):
                self.vlc_player.audio_set_track(valid[row])
                print(f"[AUDIO] Player → track {valid[row]}")

    def _on_audio_dblclick(self, item, col):
        if col == 5:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.audio_list.editItem(item, col)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    # --- Queue ---
    def _add_to_queue(self):
        print("[QUEUE] Add clicked")
        sel = self.track_tree.currentItem()
        if not sel or not self.disc:
            self.lbl_status.setText("Kein Titel ausgewählt")
            return
        idx = int(sel.text(0))
        track = next((t for t in self.tracks if t["idx"] == idx), None)
        if not track:
            return

        base = self.edit_title.text().strip()
        suffix = self.edit_suffix.text().strip()
        name = f"{base} ({suffix})" if suffix else base
        if not name:
            self.lbl_status.setText("Kein Titel angegeben")
            return

        primary_idx = None
        all_audio = []
        # Get VLC track IDs for correct ffmpeg stream mapping
        valid = [(x[0] if isinstance(x, tuple) else x.id)
                 for x in (self.vlc_player.audio_get_track_description() or [])
                 if (x[0] if isinstance(x, tuple) else x.id) >= 0]
        for i in range(self.audio_list.topLevelItemCount()):
            ai = self.audio_list.topLevelItem(i)
            if ai.checkState(0) != Qt.CheckState.Checked:
                continue
            ad = ai.data(0, Qt.ItemDataRole.UserRole)
            lang = ad.get("lang", "und") if ad else "und"
            label = ai.text(5).strip() or (ad.get("lang_name", "?") if ad else "?")
            is_pri = ai.text(1) == "❤️"
            ffmpeg_idx = valid[i] - 0x1100 if i < len(valid) else i
            print(f"[QUEUE] Audio row={i}, ffmpeg_idx={ffmpeg_idx}, lang={lang}, label='{label}', primary={is_pri}")
            if is_pri:
                primary_idx = i
                all_audio.insert(0, {"idx": ffmpeg_idx, "lang": lang, "label": label})
            else:
                all_audio.append({"idx": ffmpeg_idx, "lang": lang, "label": label})

        if primary_idx is None:
            self.lbl_status.setText("Keine Audio-Spur ausgewählt (❤️)")
            return

        job = {"title_idx": idx, "playlist": track.get("playlist"),
               "all_audio": all_audio, "name": name, "duration": track["duration"],
               "video_codec": track.get("video_codec", "?")}
        print(f"[QUEUE] Job: '{name}', playlist={job['playlist']}, "
              f"audio={[(a['idx'], a['lang']) for a in all_audio]}")
        self.queue.append(job)

        d = track["duration"]
        qi = QTreeWidgetItem([name, f"{d//60}:{d%60:02d}",
                              ", ".join(a["label"] for a in all_audio),
                              track.get("video_codec", "?")])
        qi.setFlags(qi.flags() | Qt.ItemFlag.ItemIsEditable)
        self.queue_tree.addTopLevelItem(qi)
        self.lbl_status.setText(f"'{name}' zur Queue ({len(self.queue)})")
        QMessageBox.information(self, "Queue", f"'{name}' zur Queue hinzugefügt\n({len(self.queue)} in Queue)")

    def _on_queue_changed(self, item, col):
        if col != 0:
            return
        row = self.queue_tree.indexOfTopLevelItem(item)
        if 0 <= row < len(self.queue):
            new = item.text(0).strip()
            if new:
                print(f"[QUEUE] Renamed: '{self.queue[row]['name']}' → '{new}'")
                self.queue[row]["name"] = new

    # --- Ripping ---
    def _start_queue(self):
        if not self.queue or not self.disc:
            self.lbl_status.setText("Queue ist leer" if not self.queue else "Keine Disc")
            return
        print(f"[RIP] Starting queue ({len(self.queue)} jobs)")

        # Stop VLC, release media
        self.vlc_player.stop()
        self.vlc_player.set_media(None)
        self.pos_timer.stop()
        self.btn_play.setText("Play")

        self.stack.setCurrentIndex(1)
        self.bar_rip.setValue(0)
        self.bar_convert.setValue(0)
        self.lbl_thumb.clear()
        self.lbl_rip_stats.setText("")
        self.lbl_conv_stats.setText("")
        self.btn_scan.setVisible(False)
        self.btn_eject.setVisible(False)

        self._rip_start = time.time()
        self._rip_history = []
        self._conv_start = None

        sudo_pw = None
        if self.chk_trouble.isChecked():
            from PyQt6.QtWidgets import QInputDialog
            while True:
                pw, ok = QInputDialog.getText(self, "Disc Clouder",
                    "Trouble Mode requires 'sudo' to copy the disc.\nPlease enter your administrator password:",
                    QLineEdit.EchoMode.Password)
                if not ok:
                    self.lbl_status.setText("Abgebrochen")
                    self.stack.setCurrentIndex(0)
                    self.btn_scan.setVisible(True)
                    self.btn_eject.setVisible(True)
                    return
                # Verify password
                r = subprocess.run(["sudo", "-S", "echo", "ok"],
                    input=f"{pw}\n", capture_output=True, text=True, timeout=5)
                if r.stdout.strip() == "ok":
                    break
                QMessageBox.warning(self, "Disc Clouder", "Wrong password. Please try again.")
            sudo_pw = pw

        self.rip_worker = RipWorker(list(self.queue), self.disc["mount"],
                                    self.edit_output.text().strip() or DEFAULT_OUTPUT,
                                    readrate=self.spin_readrate.value(),
                                    trouble_mode=self.chk_trouble.isChecked(),
                                    sudo_pw=sudo_pw)
        self.rip_worker.progress_rip.connect(self._on_rip_progress)
        self.rip_worker.progress_convert.connect(self._on_conv_progress)
        self.rip_worker.thumbnail.connect(self._on_thumb)
        self.rip_worker.status.connect(lambda s: (self.lbl_rip_title.setText(s),
                                                  self.lbl_status.setText(s)))
        self.rip_worker.job_started.connect(self._on_job_start)
        self.rip_worker.job_finished.connect(self._on_job_done)
        self.rip_worker.all_finished.connect(self._on_all_done)
        self.rip_worker.cancelled.connect(self._on_cancelled)
        self.rip_worker.error.connect(self._on_rip_error)
        self.rip_worker.start()

    def _on_job_start(self, idx, total, name):
        print(f"[RIP] Job {idx+1}/{total}: '{name}'")
        self.lbl_rip_title.setText(f"Rip {idx+1}/{total}: {name}")
        self.lbl_status.setText(f"Rippe: {name}")
        self.bar_rip.setValue(0)
        self.bar_convert.setValue(0)
        self.lbl_rip_stats.setText("")
        self.lbl_conv_stats.setText("")
        self.lbl_thumb.clear()
        self._rip_start = time.time()
        self._rip_history = []
        self._conv_start = None

    def _on_rip_progress(self, cur, total):
        self.bar_rip.setMaximum(total)
        self.bar_rip.setValue(cur)
        now = time.time()
        elapsed = now - self._rip_start
        self._rip_history.append((now, cur))
        if elapsed > 5 and cur > 0:
            avg = cur / elapsed
            cutoff = now - 30
            recent = [(t, s) for t, s in self._rip_history if t >= cutoff]
            rspeed = ((recent[-1][1] - recent[0][1]) / (recent[-1][0] - recent[0][0])
                      if len(recent) >= 2 and recent[-1][0] != recent[0][0] else avg)
            rem = (total - cur) / avg if avg > 0 else 0
            self.lbl_rip_stats.setText(
                f"Ø {avg:.1f}x | Aktuell {rspeed:.1f}x | "
                f"Vergangen: {int(elapsed)//60}:{int(elapsed)%60:02d} | "
                f"Verbleibend: ~{int(rem)//60}:{int(rem)%60:02d}")
            self._rip_history = [(t, s) for t, s in self._rip_history if t >= now - 60]

    def _on_conv_progress(self, cur, total):
        self.bar_convert.setMaximum(total)
        self.bar_convert.setValue(cur)
        if self._conv_start is None:
            self._conv_start = time.time()
        el = time.time() - self._conv_start
        if el > 2 and cur > 0:
            sp = cur / el
            rem = (total - cur) / sp if sp > 0 else 0
            self.lbl_conv_stats.setText(
                f"{sp:.1f}x | Vergangen: {int(el)//60}:{int(el)%60:02d} | "
                f"Verbleibend: ~{int(rem)//60}:{int(rem)%60:02d}")

    def _on_thumb(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            self.lbl_thumb.setPixmap(pix.scaled(
                self.lbl_thumb.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def _on_job_done(self, idx, path):
        print(f"[RIP] Done {idx+1}: {path}")
        if idx < self.queue_tree.topLevelItemCount():
            self.queue_tree.topLevelItem(idx).setText(0, f"✓ {self.queue_tree.topLevelItem(idx).text(0)}")

    def _on_all_done(self):
        print("[RIP] All done — ejecting")
        self._eject()
        self._restore()

    def _on_rip_error(self, idx, msg):
        print(f"[RIP] Error {idx+1}: {msg}")
        self.lbl_status.setText(f"Fehler: {msg}")

    def _cancel_rip(self):
        print("[RIP] Cancel")
        if self.rip_worker:
            self.rip_worker.cancel()

    def _on_cancelled(self):
        print("[RIP] Cancelled")
        self._restore()

    def _restore(self):
        print("[RESTORE] Resetting")
        self.stack.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)
        self.lbl_thumb.clear()
        self.btn_scan.setVisible(True)
        self.btn_eject.setVisible(True)
        self.queue.clear()
        self.queue_tree.clear()
        self._title_edited = False
        self.lbl_status.setText("Fertig")

    # --- Eject ---
    def _eject(self):
        print("[EJECT] Ejecting disc")
        self.vlc_player.stop()
        self.vlc_player.set_media(None)
        time.sleep(0.5)
        subprocess.run(["drutil", "eject"], capture_output=True)
        self.disc = None
        self.tracks = []
        self.track_tree.clear()
        self.audio_list.clear()
        self._title_edited = False
        self.edit_title.clear()
        self.lbl_disc.setText("Keine Disc")
        self.lbl_type.setText("")
        self.lbl_status.setText("Disc ausgeworfen")

    # --- Close ---
    def closeEvent(self, event):
        print("[EXIT] Closing")
        self.vlc_player.stop()
        self.vlc_player.set_media(None)
        if self.rip_worker and self.rip_worker.isRunning():
            self.rip_worker.cancel()
        event.accept()


# ═══════════════════════════════════════════════════════════════════════════
# 4. MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    print("[APP] Starting JoPhi's Disc Clouder v2")
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica", 13))
    icon_path = os.path.join(APP_DIR, "assets", "bluray-only.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        # macOS Dock icon
        try:
            from Foundation import NSBundle
            bundle = NSBundle.mainBundle()
            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
            info["CFBundleName"] = "Disc Clouder"
        except ImportError:
            pass
        try:
            from AppKit import NSApplication, NSImage
            ns_app = NSApplication.sharedApplication()
            ns_icon = NSImage.alloc().initByReferencingFile_(icon_path)
            ns_app.setApplicationIconImage_(ns_icon)
        except ImportError:
            pass
    w = DiscClouder()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
