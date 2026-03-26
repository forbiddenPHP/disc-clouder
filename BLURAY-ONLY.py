#!/usr/bin/env python3
"""JoPhi's Disc Clouder — Blu-ray ONLY Edition."""

import os
import sys

# Auto-restart in conda env if not already there
# ENV_NAME = "disc_clouder"
# if os.environ.get("CONDA_DEFAULT_ENV") != ENV_NAME:
#     os.execvp("conda", ["conda", "run", "--no-capture-output", "-n", ENV_NAME, "python", *sys.argv])

import re
import ctypes
import struct
import subprocess
import time
import threading

import vlc
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSlider, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QStackedWidget, QTabWidget, QMessageBox,
    QRadioButton, QButtonGroup,
)
from PyQt6.QtGui import QFont, QPixmap

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT = os.path.expanduser("~/Desktop/filme_sicherungen")
TMP_MKV = "/tmp/disc_clouder_rip.mkv"
TMP_THUMB = "/tmp/disc_clouder_thumb.jpg"
LIBBLURAY_PATH = "/opt/homebrew/lib/libbluray.dylib"
DEBUG = "--debug" in sys.argv

DARK_STYLE = """
QMainWindow, QWidget { background: #0d1b2a; color: #e0e0e0; }
QLabel { color: #e0e0e0; }
QPushButton { background: #1b2838; color: white; border: 1px solid #2a4a6b;
              border-radius: 6px; padding: 8px 16px; font-size: 13px; }
QPushButton:hover { background: #2a4a6b; }
QPushButton#queueBtn {
    background: #1db954; color: white; font-weight: bold;
    font-size: 15px; padding: 10px 24px; }
QPushButton#queueBtn:hover { background: #1ed760; }
QPushButton#ripBtn {
    background: #1db954; color: white; font-weight: bold;
    font-size: 15px; padding: 10px 24px; }
QPushButton#ripBtn:hover { background: #1ed760; }
QPushButton#stopBtn { background: #e74c5e; }
QPushButton#ejectBtn { background: #e74c5e; }
QPushButton#clearBtn { background: #e74c5e; font-size: 12px; padding: 6px 12px; }
QLineEdit { background: #1b2838; color: white; border: 1px solid #2a4a6b;
            border-radius: 4px; padding: 6px; }
QComboBox { background: #1b2838; color: white; border: 1px solid #2a4a6b;
            border-radius: 4px; padding: 6px; }
QComboBox QAbstractItemView { background: #1b2838; color: white; }
QTreeWidget { background: #0f2137; color: #e0e0e0; border: 1px solid #1a3a5c;
              border-radius: 6px; alternate-background-color: #132d4a; }
QTreeWidget::item { padding: 10px 4px; border-bottom: 1px solid #1a3a5c;
                    min-height: 32px; }
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
QTabWidget::pane { border: 1px solid #1a3a5c; border-radius: 6px;
                   background: #0d1b2a; }
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


# ---------------------------------------------------------------------------
# MPLS parser — read audio languages per playlist
# ---------------------------------------------------------------------------
AUDIO_STREAM_TYPES = {0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0xA1, 0xA2}
CODEC_NAMES = {
    0x80: "PCM", 0x81: "AC3", 0x82: "DTS", 0x83: "TrueHD",
    0x84: "AC3+", 0x85: "DTS-HD HR", 0x86: "DTS-HD MA",
    0xA1: "AC3 sec", 0xA2: "DTS-HD sec",
}
CH_NAMES = {1: "Mono", 3: "Stereo", 6: "5.1", 12: "7.1"}

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


def parse_mpls_audio(mpls_path):
    """Parse audio streams from an MPLS file. Returns list of dicts with lang, codec, channels."""
    try:
        with open(mpls_path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    if data[:4] != b"MPLS":
        return []

    pl_start = struct.unpack(">I", data[8:12])[0]
    pos = pl_start + 10
    if pos + 2 > len(data):
        return []
    item_len = struct.unpack(">H", data[pos:pos + 2])[0]
    item_data = data[pos + 2:pos + 2 + item_len]

    audio_streams = []
    i = 0
    while i < len(item_data) - 15:
        if (item_data[i] == 0x09 and item_data[i + 1] == 0x01
                and i + 10 < len(item_data) and item_data[i + 10] == 0x05):
            stream_type = item_data[i + 11]
            if stream_type in AUDIO_STREAM_TYPES:
                fmt = item_data[i + 12]
                lang = item_data[i + 13:i + 16].decode("ascii", errors="replace")
                channels = CH_NAMES.get((fmt >> 4) & 0x0F, "?")
                codec = CODEC_NAMES.get(stream_type, "?")
                lang_name = LANG_NAMES.get(lang, lang)
                audio_streams.append({
                    "lang": lang,
                    "lang_name": lang_name,
                    "codec": codec,
                    "channels": channels,
                })
            i += 16
        else:
            i += 1
    return audio_streams


def parse_mpls_duration(mpls_path):
    """Parse total duration from MPLS file in seconds."""
    try:
        with open(mpls_path, "rb") as f:
            data = f.read()
    except OSError:
        return 0
    if data[:4] != b"MPLS":
        return 0

    pl_start = struct.unpack(">I", data[8:12])[0]
    pos = pl_start + 6
    if pos + 4 > len(data):
        return 0
    num_items = struct.unpack(">H", data[pos:pos + 2])[0]
    pos += 4

    total_ticks = 0
    for _ in range(num_items):
        if pos + 2 > len(data):
            break
        item_len = struct.unpack(">H", data[pos:pos + 2])[0]
        item_data = data[pos + 2:pos + 2 + item_len]
        if len(item_data) >= 20:
            in_time = struct.unpack(">I", item_data[12:16])[0]
            out_time = struct.unpack(">I", item_data[16:20])[0]
            total_ticks += (out_time - in_time)
        pos = pos + 2 + item_len

    return total_ticks // 45000


def _parse_mpls_clips(mpls_path):
    """Read clip names + IN/OUT times from MPLS file (for VLC-equivalent filtering)."""
    try:
        with open(mpls_path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    if data[:4] != b"MPLS":
        return []
    pl_start = struct.unpack(">I", data[8:12])[0]
    pos = pl_start + 6
    if pos + 4 > len(data):
        return []
    num_items = struct.unpack(">H", data[pos:pos + 2])[0]
    pos += 4
    clips = []
    for _ in range(num_items):
        if pos + 2 > len(data):
            break
        il = struct.unpack(">H", data[pos:pos + 2])[0]
        item_data = data[pos + 2:pos + 2 + il]
        clip_name = item_data[0:5].decode("ascii", errors="replace")
        # IN/OUT times at offset 12-20 (like _pi_cmp in libbluray)
        in_time = struct.unpack(">I", item_data[12:16])[0] if len(item_data) >= 16 else 0
        out_time = struct.unpack(">I", item_data[16:20])[0] if len(item_data) >= 20 else 0
        clips.append((clip_name, in_time, out_time))
        pos = pos + 2 + il
    return clips


def get_mpls_audio_for_disc(mount_path):
    """Scan MPLS files, filter like VLC (TITLES_RELEVANT, min 60s), return ordered dict."""
    playlist_dir = os.path.join(mount_path, "BDMV", "PLAYLIST")
    if not os.path.isdir(playlist_dir):
        return {}

    # Collect all MPLS > 60s with clips
    all_mpls = {}
    for f in sorted(os.listdir(playlist_dir)):
        if not f.endswith(".mpls"):
            continue
        num = int(f.replace(".mpls", ""))
        path = os.path.join(playlist_dir, f)
        dur = parse_mpls_duration(path)
        if dur < 60:  # Same as VLC: bd_get_titles(bd, 0x03, 60)
            continue
        audio = parse_mpls_audio(path)
        clips = _parse_mpls_clips(path)
        all_mpls[num] = {"duration": dur, "audio": audio, "clips": clips}

    # TITLES_RELEVANT (0x03) = TITLES_FILTER_DUP_TITLE | TITLES_FILTER_DUP_CLIP
    # Exact VLC/libbluray logic from navigation.c:
    #
    # TITLES_FILTER_DUP_CLIP: _filter_repeats(pl, 2)
    #   → reject playlists where any clip appears more than 2 times
    #
    # TITLES_FILTER_DUP_TITLE: _filter_dup() → _pl_cmp()
    #   → reject playlists with identical clip_id + in/out times
    to_remove = set()

    # Step 1: _filter_repeats — remove playlists with repeated clips (>2x)
    for num, info in all_mpls.items():
        clips = info["clips"]
        from collections import Counter
        counts = Counter(clips)
        if any(c > 2 for c in counts.values()):
            to_remove.add(num)

    # Step 2: _filter_dup → _pl_cmp → _pi_cmp
    # Compares clips (name + IN/OUT) AND stream counts (num_audio, num_video, num_pg)
    # Two playlists are duplicates only if ALL of these match
    seen_sigs = []
    for num in sorted(all_mpls.keys()):
        if num in to_remove:
            continue
        info = all_mpls[num]
        # Signature: clips (name+times) + audio stream count
        sig = (tuple(info["clips"]), len(info["audio"]))
        if sig in seen_sigs:
            to_remove.add(num)
        else:
            seen_sigs.append(sig)

    result = {}
    for num in sorted(all_mpls.keys()):
        if num in to_remove:
            continue
        info = all_mpls[num]
        result[num] = {"duration": info["duration"], "audio": info["audio"]}

    return result


# ---------------------------------------------------------------------------
# libbluray ctypes — get playlist numbers per title
# ---------------------------------------------------------------------------
class _BlurayTitleInfo(ctypes.Structure):
    _fields_ = [
        ("idx", ctypes.c_uint32),
        ("playlist", ctypes.c_uint32),
        ("duration", ctypes.c_uint64),
        ("clip_count", ctypes.c_uint32),
        ("angle_count", ctypes.c_uint8),
        ("chapter_count", ctypes.c_uint32),
    ]


def get_playlist_map(mount_path):
    """Return {title_idx: playlist_number} via libbluray."""
    try:
        lib = ctypes.CDLL(LIBBLURAY_PATH)
    except OSError:
        return {}
    lib.bd_open.restype = ctypes.c_void_p
    lib.bd_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    lib.bd_get_titles.restype = ctypes.c_uint32
    lib.bd_get_titles.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint32]
    lib.bd_get_title_info.restype = ctypes.POINTER(_BlurayTitleInfo)
    lib.bd_get_title_info.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    lib.bd_free_title_info.restype = None
    lib.bd_free_title_info.argtypes = [ctypes.POINTER(_BlurayTitleInfo)]
    lib.bd_close.restype = None
    lib.bd_close.argtypes = [ctypes.c_void_p]

    bd = lib.bd_open(mount_path.encode(), None)
    if not bd:
        return {}
    mapping = {}
    n = lib.bd_get_titles(bd, 0x03, 60)
    for i in range(n):
        info = lib.bd_get_title_info(bd, i, 0)
        if info:
            mapping[i] = info.contents.playlist
            lib.bd_free_title_info(info)
    lib.bd_close(bd)
    return mapping


# ---------------------------------------------------------------------------
# Disc detection — Blu-ray only
# ---------------------------------------------------------------------------
def find_disc():
    """Find a mounted Blu-ray disc."""
    print("[FIND_DISC] Searching for Blu-ray disc...")
    for entry in os.listdir("/dev"):
        if not re.match(r"^disk\d+$", entry):
            continue
        try:
            info = subprocess.run(
                ["diskutil", "info", f"/dev/{entry}"],
                capture_output=True, text=True, timeout=5,
            ).stdout
        except Exception:
            continue
        if "Optical" not in info:
            continue
        mount = re.search(r"Mount Point:\s+(.+)", info)
        name = re.search(r"Volume Name:\s+(.+)", info)
        media = re.search(r"Optical Media Type:\s+(.+)", info)
        if not mount or not name:
            continue
        media_type = media.group(1).strip() if media else ""
        if not re.search(r"BD|Blu", media_type, re.I):
            continue
        mount_path = mount.group(1).strip()
        ssif_path = os.path.join(mount_path, "BDMV", "STREAM", "SSIF")
        is_3d = os.path.isdir(ssif_path)
        print(f"[FIND_DISC] 3D check: {ssif_path} → exists={is_3d}")
        disc = {"mount": mount_path, "name": name.group(1).strip(), "is_3d": is_3d}
        print(f"[FIND_DISC] Found: {disc['name']} at {disc['mount']} (3D={is_3d})")
        return disc
    # Fallback: check /Volumes for directories with BDMV structure
    try:
        for vol in os.listdir("/Volumes"):
            vol_path = os.path.join("/Volumes", vol)
            if not os.path.isdir(vol_path):
                continue
            bdmv = os.path.join(vol_path, "BDMV")
            if os.path.isdir(bdmv) and os.path.isdir(os.path.join(bdmv, "PLAYLIST")):
                ssif_path = os.path.join(bdmv, "STREAM", "SSIF")
                is_3d = os.path.isdir(ssif_path)
                print(f"[FIND_DISC] 3D check (fallback): {ssif_path} → exists={is_3d}")
                disc = {"mount": vol_path, "name": vol, "is_3d": is_3d}
                print(f"[FIND_DISC] Found via BDMV fallback: {disc['name']} at {disc['mount']} (3D={is_3d})")
                return disc
    except Exception:
        pass
    print("[FIND_DISC] No Blu-ray disc found")
    return None


# ---------------------------------------------------------------------------
# Scan Blu-ray titles via VLC + libbluray
# ---------------------------------------------------------------------------
def scan_bluray(disc, vlc_instance):
    """Return list of tracks with idx, duration, audio, video_codec, playlist."""
    print(f"[SCAN] Starting scan for {disc['name']} at {disc['mount']}")
    mrl = f"bluray://{disc['mount']}"
    player = vlc_instance.media_player_new()
    media = vlc_instance.media_new(mrl)
    media.add_option("no-bluray-menu")
    player.set_media(media)
    player.audio_set_volume(0)
    player.play()
    print("[SCAN] VLC player started, waiting for playback...")

    # Wait until VLC is actually playing (BD+ init can take minutes)
    for attempt in range(240):  # 120 seconds max
        time.sleep(0.5)
        state = player.get_state()
        if state in (vlc.State.Playing, vlc.State.Paused):
            print(f"[SCAN] VLC playing after {(attempt+1)*0.5:.1f}s")
            break
        if attempt % 20 == 19:
            print(f"[SCAN] Still waiting for playback... ({(attempt+1)*0.5:.0f}s, state={state})")
    else:
        print(f"[SCAN] WARNING: VLC not playing after 120s (state={player.get_state()})")

    # Now get titles — VLC should have them ready
    title_descs = list(player.get_full_title_descriptions() or [])
    if title_descs:
        print(f"[SCAN] Found {len(title_descs)} titles")
    else:
        # One more try after a short wait
        time.sleep(2)
        title_descs = list(player.get_full_title_descriptions() or [])
        if title_descs:
            print(f"[SCAN] Found {len(title_descs)} titles (delayed)")
        else:
            print("[SCAN] WARNING: No titles found")

    # Set first long title so audio tracks load
    for i, td in enumerate(title_descs):
        if td.duration > 60000:
            print(f"[SCAN] Setting title {i} (dur={td.duration//1000}s) for audio scan")
            player.set_title(i)
            break

    # Wait until audio tracks are fully loaded
    audio_descs = []
    for attempt in range(30):
        time.sleep(0.5)
        audio_descs = list(player.audio_get_track_description() or [])
        if len(audio_descs) > 2:
            print(f"[SCAN] Found {len(audio_descs)} VLC audio tracks after {(attempt+1)*0.5:.1f}s")
            break

    # Parse audio tracks
    audio_tracks = []
    for item in audio_descs:
        if isinstance(item, tuple):
            aid, aname = item
        else:
            aid, aname = item.id, item.name
        if aid < 0:
            continue
        if isinstance(aname, bytes):
            aname = aname.decode("utf-8", errors="replace")
        lang_code = ""
        if isinstance(aname, str):
            m = re.search(r"\[(\w+)\]", aname)
            if m:
                lang = m.group(1).lower()
                lang_code = LANG_MAP.get(lang, lang[:3])
        display_name = (
            f"{aname} [{lang_code}]" if lang_code
            else (aname or f"Track {aid}")
        )
        audio_tracks.append({"id": aid, "name": display_name, "lang": lang_code})
    print(f"[SCAN] VLC audio tracks parsed: {len(audio_tracks)}")

    print("[SCAN] Stopping scan player...")
    player.stop()
    player.release()
    print("[SCAN] Scan player released")

    # MPLS DIE EINZIG RICHTIGE METHODE
    print("[SCAN] Reading MPLS audio data...")
    mpls_data = get_mpls_audio_for_disc(disc["mount"])
    mpls_sorted = sorted(mpls_data.items(), key=lambda x: x[0])
    print(f"[SCAN] MPLS filtered: {len(mpls_sorted)} playlists")
    for pl_num, pl_info in mpls_sorted:
        print(f"[SCAN]   MPLS {pl_num:05d}: dur={pl_info['duration']}s, audio={len(pl_info['audio'])}")

    # Zuordnung per Dauer-Matching
    tracks = []
    mpls_used = set()
    for i, td in enumerate(title_descs):
        dur_sec = td.duration // 1000
        if dur_sec < 60:
            continue

        track_audio = []
        matched_pl = None
        for pl_num, pl_info in mpls_sorted:
            if pl_num in mpls_used:
                continue
            if abs(pl_info["duration"] - dur_sec) < 5:
                track_audio = pl_info["audio"]
                mpls_used.add(pl_num)
                matched_pl = pl_num
                break

        print(f"[SCAN] VLC title {i}: dur={dur_sec}s → MPLS {matched_pl}, audio={len(track_audio)}")
        tracks.append({
            "idx": i,
            "duration": dur_sec,
            "audio": track_audio,
            "playlist": matched_pl,
            "video_codec": "?",
        })

    tracks.sort(key=lambda t: -t["duration"])
    print(f"[SCAN] Final track list: {len(tracks)} tracks")
    return tracks


# ---------------------------------------------------------------------------
# Rip Worker — queue of Blu-ray rip jobs
# ---------------------------------------------------------------------------
class RipWorker(QThread):
    progress_rip = pyqtSignal(int, int)       # current_sec, total_sec
    progress_convert = pyqtSignal(int, int)   # current_sec, total_sec
    thumbnail = pyqtSignal(str)               # path to thumbnail jpg
    status = pyqtSignal(str)                  # status text
    job_started = pyqtSignal(int, int, str)   # idx, total, name
    job_finished = pyqtSignal(int, str)       # idx, output_path
    all_finished = pyqtSignal()
    cancelled = pyqtSignal()
    error = pyqtSignal(int, str)              # idx, error_msg

    def __init__(self, queue, mount, output_dir):
        super().__init__()
        self.queue = queue
        self.mount = mount
        self.output_dir = output_dir
        self._cancel = False

    def cancel(self):
        print("[RIP] Cancel requested (worker)")
        self._cancel = True

    def run(self):
        os.makedirs(self.output_dir, exist_ok=True)
        total = len(self.queue)

        for i, job in enumerate(self.queue):
            if self._cancel:
                self._cleanup()
                self.cancelled.emit()
                self._say("Queue aborted")
                return

            name = job["name"]
            self.job_started.emit(i, total, name)
            mp4_path = os.path.join(self.output_dir, f"{name}.mp4")

            # Step 1: ffmpeg Disc → MKV
            self.status.emit(f"Rippe: {name}")
            self._rip_start = time.time()
            try:
                self._rip(job)
            except Exception as e:
                print(f"[RIP] Exception: {e}")

            print(f"[RIP] Step 1 done, cancel={self._cancel}, "
                  f"tmp exists={os.path.exists(TMP_MKV)}")

            if self._cancel:
                self._cleanup()
                self.cancelled.emit()
                self._say("Queue aborted")
                return

            # Step 2: ffmpeg MKV → MP4 — ALWAYS if temp file exists
            if os.path.exists(TMP_MKV):
                self.status.emit(f"Konvertiere: {name}")
                self._convert_start = time.time()
                print(f"[STEP2] Starting convert: {TMP_MKV} → {mp4_path}")
                try:
                    self._convert(TMP_MKV, mp4_path)
                except Exception as e:
                    print(f"[CONVERT] Exception: {e}")
                    self.error.emit(i, f"Konvertierung: {e}")
                    self._cleanup()
                    self._say(f"{name} failed")
                    continue
            else:
                print(f"[ERROR] Temp file not found: {TMP_MKV}")
                self.error.emit(i, "Rip fehlgeschlagen — keine Datei")
                self._say(f"{name} failed")
                continue

            if self._cancel:
                self._cleanup()
                try:
                    os.remove(mp4_path)
                except OSError:
                    pass
                self.cancelled.emit()
                self._say("Queue aborted")
                return

            self._cleanup()
            self.job_finished.emit(i, mp4_path)
            self._say(f"{name} complete")

        self.all_finished.emit()

    def _say(self, text):
        subprocess.run(["say", text], capture_output=True)

    def _cleanup(self):
        for f in [TMP_MKV, TMP_THUMB, "/tmp/disc_clouder_concat.txt"]:
            try:
                os.remove(f)
            except OSError:
                pass
        # Clean up any part files
        import glob
        for f in glob.glob(f"{TMP_MKV}.part*.mkv"):
            try:
                os.remove(f)
            except OSError:
                pass
        try:
            os.remove(TMP_MKV + ".merged.mkv")
        except OSError:
            pass

    def _extract_thumb(self, src_path, sec):
        """Extract a frame from the growing MKV for thumbnail."""
        try:
            # Try fast seek first (works for copy mode)
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(max(0, sec)), "-i", src_path,
                 "-frames:v", "1", "-q:v", "5", TMP_THUMB],
                capture_output=True, timeout=8,
            )
            # If fast seek failed or produced empty file, try slow seek
            if not os.path.exists(TMP_THUMB) or os.path.getsize(TMP_THUMB) == 0:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", src_path,
                     "-ss", str(max(0, sec)),
                     "-frames:v", "1", "-q:v", "5", TMP_THUMB],
                    capture_output=True, timeout=30,
                )
            if os.path.exists(TMP_THUMB) and os.path.getsize(TMP_THUMB) > 0:
                self.thumbnail.emit(TMP_THUMB)
        except Exception:
            pass

    def _rip(self, job):
        """Disc → MKV via ffmpeg — ALL audio tracks in one pass."""
        duration = job["duration"]
        playlist = job.get("playlist")
        video_codec = job.get("video_codec", "?")
        mode_3d = job.get("mode_3d", 0)  # 0=2D, 1=SBS, 2=T/B

        # Video: 3D needs transcode — TODO: not implemented yet
        if mode_3d > 0:
            pass  # TODO: not implemented yet
        if video_codec.lower() in ("h264", "h.264", "h264 3d"):
            v_codec = ["-c:v", "copy"]
        else:
            v_codec = ["-c:v", "h264_videotoolbox", "-q:v", "50"]

        # Audio tracks
        all_audio = job.get("all_audio", [])
        if not all_audio:
            audio_idx = job.get("audio_idx", 0)
            all_audio = [{"idx": audio_idx, "lang": job.get("audio_lang", "und"), "label": "?"}]

        # BD-50 detection: disc > 30GB = dual layer → limit read rate
        is_bd50 = False
        try:
            result = subprocess.run(
                ["diskutil", "info", self.mount],
                capture_output=True, text=True, timeout=5)
            m = re.search(r"Disk Size:\s+(\d[\d.]*)\s+GB", result.stdout)
            if m and float(m.group(1)) > 30:
                is_bd50 = True
                print("[RIP] Dual-layer disc (BD-50) — readrate limited to 2x")
        except Exception:
            pass

        # Build command
        cmd = [
            "ffmpeg", "-y",
            "-err_detect", "ignore_err", "-max_error_rate", "1.0",
        ]
        if is_bd50:
            cmd += ["-readrate", "2"]
        if playlist is not None:
            cmd += ["-playlist", str(playlist)]
        cmd += ["-i", f"bluray://{self.mount}"]
        cmd += ["-map", "0:v:0"]
        # TODO: not implemented yet — 3D stereo3d filters (SBS, T/B, Anaglyph)
        for a in all_audio:
            cmd += ["-map", f"0:a:{a['idx']}"]
        cmd += [*v_codec, "-c:a", "aac", "-ac", "2", "-b:a", "192k"]
        for ai, a in enumerate(all_audio):
            cmd += [f"-metadata:s:a:{ai}", f"language={a['lang']}",
                    f"-metadata:s:a:{ai}", f"title={a['label']}"]
        cmd += ["-progress", "pipe:1", TMP_MKV]

        print(f"[RIP] cmd: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, text=True,
        )

        last_sec = 0
        last_pct = -1
        for line in proc.stdout:
            if self._cancel:
                proc.kill()
                proc.wait()
                return
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    current_sec = int(line.split("=")[1]) // 1_000_000
                    if current_sec > last_sec:
                        last_sec = current_sec
                        self.progress_rip.emit(current_sec, duration)
                        pct = (current_sec * 100) // duration if duration > 0 else 0
                        if pct != last_pct and current_sec > 5:
                            last_pct = pct
                            self._extract_thumb(TMP_MKV, current_sec - 2)
                except ValueError:
                    pass
        proc.wait()
        self.progress_rip.emit(duration, duration)

    def _get_mkv_duration(self, path):
        """Get duration of an MKV file in seconds."""
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", path],
                capture_output=True, text=True, timeout=10,
            )
            return int(float(result.stdout.strip()))
        except Exception:
            return 0


    def _convert(self, src_path, dst_path):
        """MKV → MP4 (copy all streams, just remux)."""
        duration = 0
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", src_path],
                capture_output=True, text=True, timeout=10,
            )
            duration = int(float(probe.stdout.strip()))
        except Exception:
            pass

        cmd = [
            "ffmpeg", "-y", "-i", src_path,
            "-c", "copy",
            "-movflags", "+faststart",
            "-progress", "pipe:1",
            dst_path,
        ]
        print(f"[CONVERT] cmd: {' '.join(cmd)}")

        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL, text=True,
        )
        for line in proc.stdout:
            if self._cancel:
                proc.kill()
                proc.wait()
                return
            line = line.strip()
            if line.startswith("out_time_ms="):
                try:
                    sec = int(line.split("=")[1]) // 1_000_000
                    self.progress_convert.emit(sec, duration)
                except ValueError:
                    pass
        proc.wait()
        self.progress_convert.emit(duration, duration)


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class DiscClouder(QMainWindow):
    scan_done = pyqtSignal(list)
    track_loaded = pyqtSignal(int)  # title idx after background load

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JoPhi's Disc Clouder")
        self.setMinimumSize(1000, 750)
        self.setStyleSheet(DARK_STYLE)

        self.vlc_instance = vlc.Instance("--no-xlib", "--no-bluray-menu", "--quiet", "--no-spu")
        self.vlc_player = self.vlc_instance.media_player_new()

        self.disc = None
        self.tracks = []
        self.queue = []
        self.rip_worker = None
        self._seeking = False
        self._title_set_by_user = False

        self._build_ui()
        self._connect_signals()

        self.pos_timer = QTimer()
        self.pos_timer.setInterval(500)
        self.pos_timer.timeout.connect(self._update_position)

        self._scanning = False
        QTimer.singleShot(500, self._try_scan_or_ask)

    # =====================================================================
    # UI
    # =====================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # Header
        hdr = QHBoxLayout()
        lbl_app = QLabel("JoPhi's Disc Clouder")
        lbl_app.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        lbl_app.setStyleSheet("color: #1db954;")
        hdr.addWidget(lbl_app)
        self.lbl_type = QLabel("")
        self.lbl_type.setStyleSheet(
            "background: #e74c5e; color: white; padding: 2px 10px;"
            "border-radius: 4px; font-weight: bold;"
        )
        hdr.addWidget(self.lbl_type)
        self.lbl_disc = QLabel("Keine Disc")
        self.lbl_disc.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        hdr.addWidget(self.lbl_disc)
        hdr.addStretch()
        hdr.addStretch()
        self.btn_scan = QPushButton("Neu scannen")
        self.btn_eject = QPushButton("Auswerfen")
        self.btn_eject.setObjectName("ejectBtn")
        hdr.addWidget(self.btn_scan)
        hdr.addWidget(self.btn_eject)
        main_layout.addLayout(hdr)

        # Stacked views
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, 1)

        # --- View 1: Selection ---
        view_select = QWidget()
        vs = QVBoxLayout(view_select)
        vs.setContentsMargins(0, 0, 0, 0)
        vs.setSpacing(8)

        title_row = QHBoxLayout()
        title_row.addWidget(QLabel("Titel:"))
        self.edit_base_title = QLineEdit()
        self.edit_base_title.setPlaceholderText("Filmname")
        self.edit_base_title.textEdited.connect(self._on_title_edited)
        title_row.addWidget(self.edit_base_title)
        vs.addLayout(title_row)

        # VLC Player
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background: black;")
        self.video_widget.setMinimumHeight(300)
        vs.addWidget(self.video_widget)

        # Player controls
        ctrl = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_stop_player = QPushButton("Stop")
        self.btn_stop_player.setObjectName("stopBtn")
        ctrl.addWidget(self.btn_play)
        ctrl.addWidget(self.btn_stop_player)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        ctrl.addWidget(self.seek_slider, 1)
        self.lbl_time = QLabel("00:00 / 00:00")
        ctrl.addWidget(self.lbl_time)
        ctrl.addWidget(QLabel("Vol:"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(80)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.valueChanged.connect(
            lambda v: self.vlc_player.audio_set_volume(v)
        )
        ctrl.addWidget(self.vol_slider)
        vs.addLayout(ctrl)

        # Tabs
        self.tabs = QTabWidget()
        vs.addWidget(self.tabs, 1)

        # -- Tab 1: Titel --
        tab_titel = QWidget()
        tt = QVBoxLayout(tab_titel)
        tt.setContentsMargins(8, 8, 8, 8)

        # Track list + Audio list side by side
        track_audio_row = QHBoxLayout()

        self.track_tree = QTreeWidget()
        self.track_tree.setHeaderLabels(["Nr", "Dauer", "Video", "Audio"])
        self.track_tree.setAlternatingRowColors(True)
        self.track_tree.setRootIsDecorated(False)
        self.track_tree.header().setStretchLastSection(True)
        track_audio_row.addWidget(self.track_tree, 2)

        # Audio selection (single select, next to track list)
        audio_col = QVBoxLayout()
        audio_header = QHBoxLayout()
        lbl_audio = QLabel("Audio:")
        lbl_audio.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        audio_header.addWidget(lbl_audio)
        audio_header.addStretch()
        self._3d_group = QButtonGroup(self)
        self._3d_radios = []
        for i, label in enumerate(["2D"]):
            rb = QRadioButton(label)
            rb.setStyleSheet("color: #e74c5e; font-weight: bold;")
            rb.setVisible(False)
            self._3d_group.addButton(rb, i)
            self._3d_radios.append(rb)
            audio_header.addWidget(rb)
        audio_col.addLayout(audio_header)
        self.audio_list = QTreeWidget()
        self.audio_list.setHeaderLabels(["✓", "♥", "Sprache", "Codec", "Kanäle", "Label"])
        self.audio_list.setRootIsDecorated(False)
        self.audio_list.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.audio_list.setMinimumWidth(420)
        self.audio_list.setColumnWidth(0, 30)
        self.audio_list.setColumnWidth(1, 30)
        audio_col.addWidget(self.audio_list)
        track_audio_row.addLayout(audio_col, 1)

        tt.addLayout(track_audio_row)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Zusatz:"))
        self.edit_suffix = QLineEdit()
        self.edit_suffix.setPlaceholderText("z.B. Extended, SW...")
        add_row.addWidget(self.edit_suffix, 1)
        self.btn_add_queue = QPushButton("+ Zur Queue")
        self.btn_add_queue.setObjectName("queueBtn")
        add_row.addWidget(self.btn_add_queue)
        tt.addLayout(add_row)

        self.tabs.addTab(tab_titel, "Titel")

        # -- Tab 2: Queue --
        tab_queue = QWidget()
        tq = QVBoxLayout(tab_queue)
        tq.setContentsMargins(8, 8, 8, 8)

        self.queue_tree = QTreeWidget()
        self.queue_tree.setHeaderLabels(["Name", "Dauer", "Audio", "Video"])
        self.queue_tree.setAlternatingRowColors(True)
        self.queue_tree.setRootIsDecorated(False)
        self.queue_tree.header().setStretchLastSection(True)
        self.queue_tree.setEditTriggers(QTreeWidget.EditTrigger.DoubleClicked)
        self.queue_tree.itemChanged.connect(self._on_queue_item_changed)
        tq.addWidget(self.queue_tree)

        q_row = QHBoxLayout()
        q_row.addWidget(QLabel("Zielordner:"))
        self.edit_output = QLineEdit(DEFAULT_OUTPUT)
        q_row.addWidget(self.edit_output, 1)
        self.btn_clear_queue = QPushButton("Queue leeren")
        self.btn_clear_queue.setObjectName("clearBtn")
        q_row.addWidget(self.btn_clear_queue)
        self.btn_start_queue = QPushButton("Queue starten")
        self.btn_start_queue.setObjectName("ripBtn")
        q_row.addWidget(self.btn_start_queue)
        tq.addLayout(q_row)

        self.tabs.addTab(tab_queue, "Queue")

        self.stack.addWidget(view_select)

        # --- View 2: Rip in progress ---
        view_rip = QWidget()
        vr = QVBoxLayout(view_rip)
        vr.setContentsMargins(0, 10, 0, 10)

        self.lbl_thumb = QLabel()
        self.lbl_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_thumb.setMinimumHeight(300)
        self.lbl_thumb.setStyleSheet("background: black; border-radius: 6px;")
        vr.addWidget(self.lbl_thumb, 1)

        self.lbl_rip_title = QLabel("Rippe...")
        self.lbl_rip_title.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        self.lbl_rip_title.setStyleSheet("color: #1db954;")
        self.lbl_rip_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vr.addWidget(self.lbl_rip_title)

        vr.addSpacing(10)

        self.lbl_bar1 = QLabel("Disc → MKV")
        self.lbl_bar1.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        vr.addWidget(self.lbl_bar1)
        self.bar_rip = QProgressBar()
        self.bar_rip.setMinimumHeight(36)
        vr.addWidget(self.bar_rip)
        self.lbl_rip_stats = QLabel("")
        self.lbl_rip_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_rip_stats.setStyleSheet("color: #8899aa; font-size: 13px;")
        vr.addWidget(self.lbl_rip_stats)

        vr.addSpacing(12)

        self.lbl_bar2 = QLabel("MKV → MP4")
        self.lbl_bar2.setStyleSheet("color: #4ecdc4; font-weight: bold;")
        vr.addWidget(self.lbl_bar2)
        self.bar_convert = QProgressBar()
        self.bar_convert.setMinimumHeight(36)
        vr.addWidget(self.bar_convert)
        self.lbl_convert_stats = QLabel("")
        self.lbl_convert_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_convert_stats.setStyleSheet("color: #8899aa; font-size: 13px;")
        vr.addWidget(self.lbl_convert_stats)

        vr.addSpacing(20)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self.btn_cancel = QPushButton("Abbrechen")
        self.btn_cancel.setObjectName("stopBtn")
        self.btn_cancel.setFixedWidth(200)
        cancel_row.addWidget(self.btn_cancel)
        cancel_row.addStretch()
        vr.addLayout(cancel_row)

        vr.addStretch()
        self.stack.addWidget(view_rip)

        # Status bar
        self.lbl_status = QLabel("")
        main_layout.addWidget(self.lbl_status)

    # =====================================================================
    # Signals
    # =====================================================================
    def _connect_signals(self):
        self.btn_scan.clicked.connect(self._try_scan_or_ask)
        self.btn_eject.clicked.connect(self._eject)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_stop_player.clicked.connect(self._stop_player)
        self.btn_add_queue.clicked.connect(self._add_to_queue)
        self.btn_start_queue.clicked.connect(self._start_queue)
        self.btn_clear_queue.clicked.connect(self._clear_queue)
        self.btn_cancel.clicked.connect(self._cancel_rip)
        self.track_tree.itemClicked.connect(self._on_track_clicked)
        self.seek_slider.sliderPressed.connect(
            lambda: setattr(self, '_seeking', True)
        )
        self.seek_slider.sliderReleased.connect(self._seek_end)
        self.scan_done.connect(self._on_scan_done)
        self.track_loaded.connect(self._on_track_loaded)
        self.audio_list.itemClicked.connect(self._on_audio_clicked)
        self.audio_list.itemDoubleClicked.connect(self._on_audio_dblclick)

    # =====================================================================
    # Title field
    # =====================================================================
    def _on_title_edited(self, text):
        print(f"[UI] Title edited: '{text}'")
        self._title_set_by_user = True

    # =====================================================================
    # Disc scanning
    # =====================================================================
    def _try_scan_or_ask(self):
        """Scan for disc. If none found, ask user."""
        print("[SCAN] Searching for disc...")
        disc = find_disc()
        if disc:
            print(f"[SCAN] Disc found: {disc['name']}")
            self.disc = disc
            self._scanning = True
            self.lbl_status.setText("Scanne...")
            def _do():
                tracks = scan_bluray(disc, self.vlc_instance)
                self.scan_done.emit(tracks)
            threading.Thread(target=_do, daemon=True).start()
        else:
            print("[DIALOG] No disc found — asking user")
            self._show_insert_dialog("No disc found. Please insert a Blu-ray disc.")

    def _show_insert_dialog(self, msg):
        print(f"[DIALOG] {msg}")
        reply = QMessageBox.question(
            self, "Disc Clouder", msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Ok:
            print("[DIALOG] OK clicked — waiting for disc...")
            self.lbl_status.setText("Warte auf Disc...")
            def _wait_for_disc():
                for _ in range(20):  # 10 seconds (20 x 0.5s)
                    time.sleep(0.5)
                    disc = find_disc()
                    if disc:
                        print(f"[DIALOG] Disc found: {disc['name']}")
                        QTimer.singleShot(0, self._try_scan_or_ask)
                        return
                print("[DIALOG] Timeout — no Blu-ray found")
                non_system = [v for v in os.listdir("/Volumes")
                              if v not in ("Macintosh HD", "Macintosh HD - Data")]
                if non_system:
                    msg2 = f"Disc '{non_system[0]}' is not a Blu-ray or could not be recognized."
                else:
                    msg2 = "No disc found. Please insert a Blu-ray disc."
                QTimer.singleShot(0, lambda: self._show_insert_dialog(msg2))
            threading.Thread(target=_wait_for_disc, daemon=True).start()
        else:
            print("[DIALOG] Cancel clicked — waiting for manual scan")
            self.lbl_status.setText("Keine Disc — 'Neu scannen' drücken")

    def _scan_disc(self, reset_title=False):
        if self._scanning:
            print("[SCAN_DISC] Already scanning, skipping")
            return
        self._scanning = True
        print(f"[SCAN_DISC] Starting scan (reset_title={reset_title})")
        self.lbl_status.setText("Scanne...")
        # Stop player in background thread to avoid Main Thread hang
        # (VLC input_Close can deadlock on BD+ discs)
        def _stop():
            try:
                self.vlc_player.stop()
                self.vlc_player.set_media(None)
            except Exception:
                pass
        t = threading.Thread(target=_stop, daemon=True)
        t.start()
        t.join(timeout=3)  # Max 3 seconds, then proceed anyway
        self.tracks = []
        self.track_tree.clear()
        if reset_title:
            self._title_set_by_user = False

        def _do():
            disc = find_disc()
            if not disc:
                self.disc = None
                self.scan_done.emit([])
                return
            self.disc = disc
            tracks = scan_bluray(disc, self.vlc_instance)
            self.scan_done.emit(tracks)

        threading.Thread(target=_do, daemon=True).start()

    def _on_scan_done(self, tracks):
        self._scanning = False
        print(f"[SCAN_DONE] Received {len(tracks)} tracks, disc={self.disc}")
        self.tracks = tracks
        if not self.disc:
            self.lbl_disc.setText("Keine Blu-ray gefunden")
            self.lbl_type.setText("")
            self.lbl_status.setText("")
            self.audio_list.clear()
            self.track_tree.clear()
            return

        self.lbl_disc.setText(self.disc["name"])
        self.lbl_type.setText("BLURAY")

        # 3D disc detection via SSIF directory
        is_3d = self.disc.get("is_3d", False)
        for rb in self._3d_radios:
            rb.setVisible(is_3d)
        self._3d_radios[0].setChecked(True)  # Default: 2D
        if is_3d:
            print(f"[3D] Disc is 3D capable (SSIF found) — TODO: not implemented yet")

        if not self._title_set_by_user:
            self.edit_base_title.setText(
                self.disc["name"].replace("_", " ").title()
            )

        self.track_tree.clear()
        self.audio_list.clear()

        if len(tracks) == 0:
            self.lbl_status.setText(
                f"⚠️ Disc '{self.disc['name']}' erkannt, aber keine Titel lesbar. "
                "Möglicherweise fehlen AACS-Schlüssel (KEYDB.cfg aktualisieren)."
            )
            return

        for t in tracks:
            dur = t["duration"]
            dur_str = f"{dur // 60}:{dur % 60:02d}"
            item = QTreeWidgetItem([
                str(t["idx"]),
                dur_str,
                t.get("video_codec", "?"),
                f"{len(t['audio'])} Spuren",
            ])
            self.track_tree.addTopLevelItem(item)

        for i in range(4):
            self.track_tree.resizeColumnToContents(i)

        # Set up preview player
        print(f"[SCAN_DONE] Setting up preview player for {self.disc['mount']}")
        mrl = f"bluray://{self.disc['mount']}"
        media = self.vlc_instance.media_new(mrl)
        media.add_option("no-bluray-menu")
        self.vlc_player.set_media(media)
        self.vlc_player.set_nsobject(int(self.video_widget.winId()))
        self.vlc_player.audio_set_volume(self.vol_slider.value())
        print("[SCAN_DONE] Preview player ready")

        self.lbl_status.setText(f"{len(tracks)} Titel gefunden")

    # =====================================================================
    # Track selection + Preview
    # =====================================================================
    def _on_track_clicked(self, item, col):
        idx = int(item.text(0))
        track = next((t for t in self.tracks if t["idx"] == idx), None)
        if not track:
            print(f"[TRACK_CLICK] Track idx={idx} not found in tracks list!")
            return

        print(f"[TRACK_CLICK] Clicked track idx={idx}, dur={track['duration']}s, audio={len(track['audio'])}")
        self.vlc_player.play()
        self.pos_timer.start()
        self.btn_play.setText("Pause")

        # Run VLC title switch in background to avoid Main Thread hang
        # (VLC input_Close can deadlock on BD+ discs)
        def _load_title():
            print(f"[LOAD_TITLE] Background: setting title {idx}...")
            time.sleep(0.5)
            self.vlc_player.set_title(idx)
            print(f"[LOAD_TITLE] Title {idx} set")
            time.sleep(0.5)
            self.vlc_player.audio_set_volume(self.vol_slider.value())
            self.vlc_player.video_set_spu(-1)

            # Detect video codec via FourCC
            time.sleep(1)
            media = self.vlc_player.get_media()
            if media:
                media.parse_with_options(vlc.MediaParseFlag.network, 3000)
                time.sleep(1)
                codec_names = {
                    "VC-1": "VC-1", "h264": "H.264", "mpgv": "MPEG-2",
                    "hevc": "HEVC", "av01": "AV1", "WVC1": "VC-1",
                    "H264": "H.264", "HEVC": "HEVC", "AVC1": "H.264",
                    "avc1": "H.264",
                }
                try:
                    for t in media.tracks_get():
                        if t.type == vlc.TrackType.video:
                            fourcc = struct.pack("<I", t.codec).decode("ascii", errors="replace").strip()
                            codec = codec_names.get(fourcc, fourcc)
                            track["video_codec"] = codec
                            print(f"[LOAD_TITLE] Video codec: {codec}")
                            break
                except Exception as e:
                    print(f"[LOAD_TITLE] FourCC error: {e}")

            # VLC audio track IDs are read on demand in _on_audio_clicked
            print("[LOAD_TITLE] Background loading complete")
            self.track_loaded.emit(idx)

        threading.Thread(target=_load_title, daemon=True).start()

        # MPLS DIE EINZIG RICHTIGE METHODE
        # Audio-Spuren aus MPLS (schon beim Scan zugeordnet)
        # Spalte 0: Checkbox (inkludiert), Spalte 1: Herz (Radio, Hauptsprache)
        self.audio_list.clear()
        for i, a in enumerate(track["audio"]):
            default_label = a.get("lang_name", "?")
            ai = QTreeWidgetItem(["", "", a.get("lang_name", "?"), a.get("codec", "?"), a.get("channels", "?"), default_label])
            ai.setData(0, Qt.ItemDataRole.UserRole, a)
            ai.setCheckState(0, Qt.CheckState.Unchecked)
            ai.setText(1, "")  # Herz-Spalte leer
            self.audio_list.addTopLevelItem(ai)
        self.audio_list.setEditTriggers(QTreeWidget.EditTrigger.NoEditTriggers)
        for i in range(6):
            self.audio_list.resizeColumnToContents(i)
        # Update audio count in track tree
        item.setText(3, f"{len(track['audio'])} Spuren")

        self.edit_suffix.clear()

    def _on_track_loaded(self, idx):
        """Update UI after background title load (video codec)."""
        track = next((t for t in self.tracks if t["idx"] == idx), None)
        if not track:
            return
        # Update video codec in track tree
        for i in range(self.track_tree.topLevelItemCount()):
            item = self.track_tree.topLevelItem(i)
            if int(item.text(0)) == idx:
                item.setText(2, track.get("video_codec", "?"))
                break

    # =====================================================================
    # Player controls
    # =====================================================================
    def _toggle_play(self):
        state = self.vlc_player.get_state()
        print(f"[PLAY] Toggle play, state={state}")
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

    def _update_position(self):
        if self._seeking:
            return
        state = self.vlc_player.get_state()
        if state not in (vlc.State.Playing, vlc.State.Paused):
            return
        pos = self.vlc_player.get_time() or 0
        length = self.vlc_player.get_length() or 1
        ps = pos // 1000
        ls = length // 1000
        self.lbl_time.setText(
            f"{ps // 60:02d}:{ps % 60:02d} / {ls // 60:02d}:{ls % 60:02d}"
        )
        if length > 0:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(pos * 1000 / length))
            self.seek_slider.blockSignals(False)

    def _seek_end(self):
        self._seeking = False
        val = self.seek_slider.value()
        length = self.vlc_player.get_length() or 1
        target = int(val * length / 1000)
        print(f"[SEEK] Seeking to {target // 1000}s ({val / 10:.1f}%)")
        self.vlc_player.set_time(target)

    def _on_audio_clicked(self, item, col):
        """
        Spalte 0: Checkbox (inkludiert) — Multi-Select
        Spalte 1: Herz (Hauptsprache) — Radio (genau eine)
        Herz setzt automatisch Checkbox.
        """
        row = self.audio_list.indexOfTopLevelItem(item)
        a_data = item.data(0, Qt.ItemDataRole.UserRole)
        lang = a_data.get('lang') if a_data else '?'

        if col == 1:
            # Herz-Spalte geklickt → Radio-Logik
            # Diese wird ❤️, alle anderen verlieren ❤️
            # Automatisch auch Checkbox setzen
            for i in range(self.audio_list.topLevelItemCount()):
                other = self.audio_list.topLevelItem(i)
                if other == item:
                    other.setText(1, "❤️")
                    other.setCheckState(0, Qt.CheckState.Checked)
                else:
                    other.setText(1, "")
            print(f"[AUDIO] ❤️ Primary set: {lang}")

        elif col == 0:
            # Checkbox-Spalte geklickt — PyQt hat den State schon getoggelt
            is_checked = item.checkState(0) == Qt.CheckState.Checked

            if not is_checked:
                # Unchecked → Herz entfernen
                item.setText(1, "")
                print(f"[AUDIO] Unchecked: {lang}")

                # Wenn das die Hauptsprache war, promote nächste gecheckte
                has_primary = False
                for i in range(self.audio_list.topLevelItemCount()):
                    other = self.audio_list.topLevelItem(i)
                    if other.text(1) == "❤️":
                        has_primary = True
                        break
                if not has_primary:
                    for i in range(self.audio_list.topLevelItemCount()):
                        other = self.audio_list.topLevelItem(i)
                        if other.checkState(0) == Qt.CheckState.Checked:
                            other.setText(1, "❤️")
                            o_data = other.data(0, Qt.ItemDataRole.UserRole)
                            print(f"[AUDIO] ❤️ Auto-promoted: {o_data.get('lang') if o_data else '?'}")
                            break
            else:
                # Checked → wenn keine Hauptsprache existiert, diese wird es
                has_primary = False
                for i in range(self.audio_list.topLevelItemCount()):
                    other = self.audio_list.topLevelItem(i)
                    if other.text(1) == "❤️":
                        has_primary = True
                        break
                if not has_primary:
                    item.setText(1, "❤️")
                    print(f"[AUDIO] ❤️ Auto-primary: {lang}")
                else:
                    print(f"[AUDIO] ✓ Included: {lang}")

        # Switch preview player to clicked audio
        if row >= 0:
            all_tracks = list(self.vlc_player.audio_get_track_description() or [])
            valid = [
                (a[0] if isinstance(a, tuple) else a.id)
                for a in all_tracks
                if (a[0] if isinstance(a, tuple) else a.id) >= 0
            ]
            if row < len(valid):
                self.vlc_player.audio_set_track(valid[row])
                print(f"[AUDIO] Player switched to track {valid[row]}")

    def _on_audio_dblclick(self, item, col):
        if col == 5:  # Label column
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.audio_list.editItem(item, col)
        else:
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    # =====================================================================
    # Queue management
    # =====================================================================
    def _add_to_queue(self):
        print("[QUEUE] Add to queue clicked")
        selected = self.track_tree.currentItem()
        if not selected:
            self.lbl_status.setText("Kein Titel ausgewählt")
            return
        if not self.disc:
            return

        idx = int(selected.text(0))
        track = next((t for t in self.tracks if t["idx"] == idx), None)
        if not track:
            return

        base = self.edit_base_title.text().strip()
        suffix = self.edit_suffix.text().strip()
        name = f"{base} ({suffix})" if suffix else base
        if not name:
            self.lbl_status.setText("Kein Titel angegeben")
            return

        # Get checked audio tracks with 0-based MPLS index (= ffmpeg -map 0:a:N)
        primary_idx = None
        primary_lang = None
        primary_name = None
        secondary_tracks = []
        for i in range(self.audio_list.topLevelItemCount()):
            ai = self.audio_list.topLevelItem(i)
            if ai.checkState(0) == Qt.CheckState.Checked:
                a_data = ai.data(0, Qt.ItemDataRole.UserRole)
                lang = a_data.get("lang", "eng") if a_data else "eng"
                label = ai.text(5).strip() or a_data.get("lang_name", "?") if a_data else "?"
                is_primary = ai.text(1) == "❤️"
                print(f"[QUEUE] Audio idx={i}, lang={lang}, label='{label}': checked=True, primary={is_primary}")
                if is_primary:
                    primary_idx = i
                    primary_lang = lang
                    primary_name = label
                else:
                    secondary_tracks.append({"idx": i, "lang": lang, "name": label})

        if primary_idx is None:
            self.lbl_status.setText("Keine Audio-Spur ausgewählt (❤️ fehlt)")
            return

        all_audio_names = [primary_name] + [s["name"] for s in secondary_tracks]
        audio_display = ", ".join(all_audio_names)

        # Build all_audio: primary first, then secondary — for single-pass ffmpeg
        all_audio = [{"idx": primary_idx, "lang": primary_lang, "label": primary_name}]
        for s in secondary_tracks:
            all_audio.append({"idx": s["idx"], "lang": s["lang"], "label": s["name"]})

        # 3D mode: 0=2D, 1=3D SBS, 2=3D T/B
        mode_3d = self._3d_group.checkedId() if self._3d_radios[0].isVisible() else 0
        mode_3d_names = {0: "2D"}  # TODO: not implemented yet — 3D modes
        job = {
            "title_idx": idx,
            "playlist": track.get("playlist"),
            "all_audio": all_audio,
            "name": name,
            "duration": track["duration"],
            "video_codec": track.get("video_codec", "?"),
            "mode_3d": mode_3d,
        }
        print(f"[QUEUE] Job: name='{name}', idx={idx}, audio={[(a['idx'], a['lang'], a['label']) for a in all_audio]}, dur={track['duration']}s, mode_3d={mode_3d_names.get(mode_3d, '?')}")
        self.queue.append(job)

        dur = track["duration"]
        dur_str = f"{dur // 60}:{dur % 60:02d}"
        item = QTreeWidgetItem([
            name, dur_str, audio_display, track.get("video_codec", ""),
        ])
        # Only Name column (0) is editable
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.queue_tree.addTopLevelItem(item)

        QMessageBox.information(
            self, "Queue",
            f"'{name}' zur Queue hinzugefügt\n({len(self.queue)} in Queue)",
        )
        self.lbl_status.setText(
            f"'{name}' zur Queue hinzugefügt ({len(self.queue)} in Queue)"
        )

    def _on_queue_item_changed(self, item, col):
        """Update job name when user edits the Name column in the queue."""
        if col != 0:
            return
        row = self.queue_tree.indexOfTopLevelItem(item)
        if 0 <= row < len(self.queue):
            old_name = self.queue[row]["name"]
            new_name = item.text(0).strip()
            if new_name and new_name != old_name:
                self.queue[row]["name"] = new_name
                print(f"[QUEUE] Renamed job {row}: '{old_name}' → '{new_name}'")

    def _clear_queue(self):
        print("[QUEUE] Clearing queue")
        self.queue.clear()
        self.queue_tree.clear()
        self.lbl_status.setText("Queue geleert")

    # =====================================================================
    # Ripping
    # =====================================================================
    def _start_queue(self):
        print(f"[RIP_START] Starting queue with {len(self.queue)} jobs")
        if not self.queue:
            self.lbl_status.setText("Queue ist leer")
            return
        if not self.disc:
            print("[RIP_START] No disc — aborting")
            return

        output_dir = self.edit_output.text().strip() or DEFAULT_OUTPUT

        # Stop preview player
        self.vlc_player.stop()
        self.pos_timer.stop()
        self.btn_play.setText("Play")

        # Switch to rip view
        self.stack.setCurrentIndex(1)
        self.bar_rip.setValue(0)
        self.bar_convert.setValue(0)
        self.lbl_thumb.clear()
        self.lbl_thumb.setText("Starte Queue...")
        self.lbl_rip_stats.setText("")
        self.lbl_convert_stats.setText("")
        self.btn_scan.setVisible(False)
        self.btn_eject.setVisible(False)

        self._rip_start_time = time.time()
        self._rip_history = []
        self._convert_start_time = None

        self.rip_worker = RipWorker(
            queue=list(self.queue),
            mount=self.disc["mount"],
            output_dir=output_dir,
        )
        self.rip_worker.progress_rip.connect(self._on_rip_progress)
        self.rip_worker.progress_convert.connect(self._on_convert_progress)
        self.rip_worker.thumbnail.connect(self._on_thumbnail)
        self.rip_worker.status.connect(lambda s: (self.lbl_rip_title.setText(s), self.lbl_status.setText(s)))
        self.rip_worker.job_started.connect(self._on_job_started)
        self.rip_worker.job_finished.connect(self._on_job_finished)
        self.rip_worker.all_finished.connect(self._on_all_finished)
        self.rip_worker.cancelled.connect(self._on_cancelled)
        self.rip_worker.error.connect(self._on_rip_error)
        self.rip_worker.start()

    def _on_job_started(self, idx, total, name):
        print(f"[RIP_JOB] Started job {idx+1}/{total}: '{name}'")
        self.lbl_rip_title.setText(f"Rip {idx + 1}/{total}: {name}")
        self.bar_rip.setValue(0)
        self.bar_convert.setValue(0)
        self.lbl_rip_stats.setText("")
        self.lbl_convert_stats.setText("")
        self.lbl_thumb.clear()
        self.lbl_thumb.setText(f"Starte: {name}")
        self._rip_start_time = time.time()
        self._rip_history = []
        self._convert_start_time = None

    def _on_rip_progress(self, current, total):
        self.bar_rip.setMaximum(total)
        self.bar_rip.setValue(current)

        now = time.time()
        elapsed = now - self._rip_start_time
        self._rip_history.append((now, current))

        if elapsed > 5 and current > 0:
            avg_speed = current / elapsed

            cutoff = now - 30
            recent = [(t, s) for t, s in self._rip_history if t >= cutoff]
            if len(recent) >= 2:
                dt = recent[-1][0] - recent[0][0]
                ds = recent[-1][1] - recent[0][1]
                recent_speed = ds / dt if dt > 0 else avg_speed
            else:
                recent_speed = avg_speed

            remaining = (total - current) / avg_speed if avg_speed > 0 else 0
            el_m, el_s = int(elapsed) // 60, int(elapsed) % 60
            re_m, re_s = int(remaining) // 60, int(remaining) % 60
            self.lbl_rip_stats.setText(
                f"Ø {avg_speed:.1f}x  |  Aktuell {recent_speed:.1f}x  |  "
                f"Vergangen: {el_m}:{el_s:02d}  |  "
                f"Verbleibend: ~{re_m}:{re_s:02d}"
            )

            self._rip_history = [
                (t, s) for t, s in self._rip_history if t >= now - 60
            ]

    def _on_convert_progress(self, current, total):
        self.bar_convert.setMaximum(total)
        self.bar_convert.setValue(current)

        if self._convert_start_time is None:
            self._convert_start_time = time.time()
        elapsed = time.time() - self._convert_start_time
        if elapsed > 2 and current > 0:
            speed = current / elapsed
            remaining = (total - current) / speed if speed > 0 else 0
            el_m, el_s = int(elapsed) // 60, int(elapsed) % 60
            re_m, re_s = int(remaining) // 60, int(remaining) % 60
            self.lbl_convert_stats.setText(
                f"{speed:.1f}x Echtzeit  |  "
                f"Vergangen: {el_m}:{el_s:02d}  |  "
                f"Verbleibend: ~{re_m}:{re_s:02d}"
            )

    def _on_thumbnail(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            scaled = pix.scaled(
                self.lbl_thumb.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.lbl_thumb.setPixmap(scaled)

    def _on_job_finished(self, idx, path):
        print(f"[RIP_JOB] Finished job {idx+1}: {path}")
        if idx < self.queue_tree.topLevelItemCount():
            item = self.queue_tree.topLevelItem(idx)
            item.setText(0, f"✓ {item.text(0)}")

    def _on_all_finished(self):
        print("[RIP] All jobs finished — auto-ejecting disc")
        self._eject()
        self._restore_after_rip()
        self.queue.clear()
        self.queue_tree.clear()
        self.lbl_status.setText("Alle Rips fertig!")

    def _on_rip_error(self, idx, msg):
        print(f"[RIP_ERROR] Job {idx+1}: {msg}")
        if idx < self.queue_tree.topLevelItemCount():
            item = self.queue_tree.topLevelItem(idx)
            item.setText(0, f"✗ {item.text(0)}")
        self.lbl_status.setText(f"Fehler bei Rip {idx + 1}: {msg}")

    def _cancel_rip(self):
        print("[RIP] Cancel requested")
        if self.rip_worker:
            self.rip_worker.cancel()

    def _on_cancelled(self):
        print("[RIP] Cancelled")
        self._restore_after_rip()
        self.queue.clear()
        self.queue_tree.clear()
        self.lbl_status.setText("Abgebrochen")

    def _restore_after_rip(self):
        print("[RESTORE] Restoring after rip")
        self.stack.setCurrentIndex(0)
        self.tabs.setCurrentIndex(0)  # Switch to Titel tab
        self.lbl_thumb.clear()
        self.btn_scan.setVisible(True)
        self.btn_eject.setVisible(True)
        self._title_set_by_user = False
        self._scan_disc()

    # =====================================================================
    # Eject
    # =====================================================================
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
        self.queue.clear()
        self.queue_tree.clear()
        self._title_set_by_user = False
        self.edit_base_title.clear()
        self.lbl_disc.setText("Keine Disc — bitte einlegen")
        self.lbl_type.setText("")
        self.lbl_status.setText("Disc ausgeworfen")

    # =====================================================================
    # Cleanup
    # =====================================================================
    def closeEvent(self, event):
        print("[EXIT] Closing app")
        if self.rip_worker and self.rip_worker.isRunning():
            print("[EXIT] Cancelling running rip")
        self.vlc_player.stop()
        self.vlc_player.set_media(None)
        if self.rip_worker and self.rip_worker.isRunning():
            self.rip_worker.cancel()
        event.accept()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("[APP] Starting JoPhi's Disc Clouder")
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica", 13))
    window = DiscClouder()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
