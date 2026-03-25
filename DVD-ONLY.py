#!/usr/bin/env python3
"""JoPhi's Disc Clouder — DVD Ripper mit eingebettetem VLC."""

import os
import sys

# Auto-restart in conda env if not already there
ENV_NAME = "disc_clouder"
if os.environ.get("CONDA_DEFAULT_ENV") != ENV_NAME:
    argv = " ".join(f'"{a}"' for a in sys.argv)
    os.execvp("conda", ["conda", "run", "--no-capture-output", "-n", ENV_NAME, "python", *sys.argv])

import json
import sys
import re
import subprocess
import time
import threading

import vlc
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QSlider, QProgressBar,
    QTreeWidget, QTreeWidgetItem, QStackedWidget, QTabWidget, QMessageBox,
)
from PyQt6.QtGui import QFont, QPixmap

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_OUTPUT = os.path.expanduser("~/Desktop/filme_sicherungen")
TMP_RIP = "/tmp/disc_clouder_rip"  # extension added per disc type
TMP_THUMB = "/tmp/disc_clouder_thumb.jpg"
DARK_STYLE = """
QMainWindow, QWidget { background: #0d1b2a; color: #e0e0e0; }
QLabel { color: #e0e0e0; }
QPushButton { background: #1b2838; color: white; border: 1px solid #2a4a6b;
              border-radius: 6px; padding: 8px 16px; font-size: 13px; }
QPushButton:hover { background: #2a4a6b; }
QPushButton#ripBtn, QPushButton#queueBtn {
    background: #1db954; color: white; font-weight: bold;
    font-size: 15px; padding: 10px 24px; }
QPushButton#ripBtn:hover, QPushButton#queueBtn:hover { background: #1ed760; }
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
QTreeWidget::item:selected { background: #1a4a7a; }
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
    # ISO 639-1 (2-letter) → ISO 639-2 (3-letter) for lsdvd
    "de": "ger", "en": "eng", "fr": "fre", "it": "ita",
    "es": "spa", "pt": "por", "ja": "jpn", "zh": "chi",
    "ko": "kor", "ru": "rus", "pl": "pol", "hu": "hun",
    "nl": "dut", "sv": "swe", "da": "dan", "no": "nor",
    "fi": "fin", "cs": "cze", "tr": "tur", "ar": "ara",
    "hi": "hin",
}


# ---------------------------------------------------------------------------
# Disc detection
# ---------------------------------------------------------------------------
def find_discs():
    """Find mounted optical discs via diskutil."""
    discs = []
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
        if not mount or not name:
            continue
        mount_point = mount.group(1).strip()
        vol_name = name.group(1).strip()
        discs.append({"mount": mount_point, "name": vol_name, "type": "dvd"})
    return discs


# ---------------------------------------------------------------------------
# VLC title scanning
# ---------------------------------------------------------------------------
def scan_titles(disc, vlc_instance):
    """Scan DVD titles."""
    return _scan_dvd(disc)


def _scan_dvd(disc):
    """Scan DVD titles via lsdvd -x -Oj (JSON, all info including cells)."""
    mount = disc["mount"]
    try:
        result = subprocess.run(
            ["lsdvd", "-x", "-Oj", mount],
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return []

    try:
        data = json.loads(result.stdout)
    except Exception:
        return []

    tracks = []
    for title in data.get("track", []):
        t_num = title.get("ix", 0)
        dur_sec = int(title.get("length", 0))
        if dur_sec < 30:
            continue

        audio_tracks = []
        for i, au in enumerate(title.get("audio", [])):
            lang_raw = au.get("langcode", "")
            lang = LANG_MAP.get(lang_raw, lang_raw)  # 2-letter → 3-letter
            lang_name = au.get("language", "")
            codec = au.get("format", "")
            ch = au.get("channels", 0)
            ch_str = "Stereo" if ch == 2 else f"{ch}ch"
            display = f"{lang_name} ({codec} {ch_str})" if lang_name else f"Track {i+1}"
            audio_tracks.append({
                "id": i,
                "name": display,
                "lang": lang,
            })

        if not audio_tracks:
            continue

        aspect_raw = title.get("aspect", "16/9")
        aspect = "16:9" if "16" in str(aspect_raw) else "4:3"

        tracks.append({
            "idx": t_num,
            "duration": dur_sec,
            "audio": audio_tracks,
            "video_codec": "MPEG-2",
            "playlist": None,
            "dvd_title": t_num,
            "aspect": aspect,
        })

    tracks.sort(key=lambda t: -t["duration"])
    return tracks


# ---------------------------------------------------------------------------
# Rip worker — processes a queue of jobs sequentially
# ---------------------------------------------------------------------------
class RipWorker(QThread):
    progress_rip = pyqtSignal(int, int)
    progress_convert = pyqtSignal(int, int)
    thumbnail = pyqtSignal(str)
    status = pyqtSignal(str)
    job_started = pyqtSignal(int, int, str)   # current_idx, total, name
    job_finished = pyqtSignal(int, str)        # job_idx, output_path
    all_finished = pyqtSignal()
    cancelled = pyqtSignal()
    error = pyqtSignal(int, str)               # job_idx, error_msg

    def __init__(self, queue, disc, output_dir):
        super().__init__()
        self.queue = queue          # list of job dicts
        self.disc = disc
        self.output_dir = output_dir
        self._cancel = False

    def cancel(self):
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
            self._tmp_rip = TMP_RIP + ".ts"

            # Step 1: Disc → temp file
            self.status.emit(f"Rippe: {name}")
            self._rip_start = time.time()
            try:
                self._rip(job)
            except Exception as e:
                if DEBUG: print(f"[RIP] Exception: {e}")
                # Continue to Step 2 regardless — convert whatever was written

            if DEBUG: print(f"[RIP] Step 1 done, cancel={self._cancel}, tmp exists={os.path.exists(self._tmp_rip)}")

            if self._cancel:
                self._cleanup()
                self.cancelled.emit()
                self._say("Queue aborted")
                return

            # Step 2: Convert to MP4 — ALWAYS try if temp file exists
            if os.path.exists(self._tmp_rip):
                self.status.emit(f"Konvertiere: {name}")
                self._convert_start = time.time()
                if DEBUG: print(f"[STEP2] Starting convert: {self._tmp_rip} → {mp4_path}")
                try:
                    self._convert(self._tmp_rip, mp4_path, job=job)
                except Exception as e:
                    if DEBUG: print(f"[CONVERT] Exception: {e}")
                    self.error.emit(i, f"Konvertierung: {e}")
                    self._cleanup()
                    self._say(f"{name} failed")
                    continue
            else:
                if DEBUG: print(f"[ERROR] Temp file not found: {self._tmp_rip}")
                self.error.emit(i, "Rip fehlgeschlagen — keine Datei erstellt")
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
        for f in [getattr(self, '_tmp_rip', TMP_RIP + ".ts"), TMP_THUMB]:
            try:
                os.remove(f)
            except OSError:
                pass

    def _extract_thumb(self, sec):
        """Extract a frame from the growing TS for thumbnail preview."""
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-ss", str(max(0, sec)), "-i", self._tmp_rip,
                 "-frames:v", "1", "-vf", "scale=iw*sar:ih,setsar=1",
                 "-q:v", "5", TMP_THUMB],
                capture_output=True, timeout=5,
            )
            if os.path.exists(TMP_THUMB):
                self.thumbnail.emit(TMP_THUMB)
        except Exception:
            pass

    def _rip(self, job):
        """DVD: Disc → TS via VLC CLI."""
        mount = self.disc["mount"]
        duration = job["duration"]

        # DVD: VLC CLI reads disc, transcodes to H.264+AAC, writes TS
        link = "/tmp/disc_clouder_dvd"
        try:
            os.unlink(link)
        except OSError:
            pass
        os.symlink(mount, link)
        title_num = job.get("dvd_title", 1)
        audio_idx = job.get("audio_idx", 0)
        vlc_args = [
            "/Applications/VLC.app/Contents/MacOS/VLC", "-I", "dummy",
            f"dvdsimple://{link}#{title_num}",
            f":no-sout-all", f":audio-track={audio_idx}",
            f"--run-time={duration}",
            f"--sout=#transcode{{vcodec=h264,acodec=mp4a,ab=192,channels=2}}"
            f":standard{{access=file,mux=ts,dst={self._tmp_rip}}}",
            "vlc://quit",
        ]
        print(f"[RIP-DVD] cmd: {' '.join(vlc_args)}")
        proc = subprocess.Popen(
            vlc_args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        # Monitor progress via ffprobe duration of growing TS
        start = time.time()
        last_pct = -1
        while proc.poll() is None:
            if self._cancel:
                proc.kill()
                proc.wait()
                return
            try:
                probe = subprocess.run(
                    ["ffprobe", "-v", "quiet", "-show_entries",
                     "format=duration", "-of", "csv=p=0", self._tmp_rip],
                    capture_output=True, text=True, timeout=5,
                )
                current_sec = int(float(probe.stdout.strip()))
            except Exception:
                current_sec = 0
            if current_sec > 0 and duration > 0:
                self.progress_rip.emit(current_sec, duration)
                pct = (current_sec * 100) // duration
                if pct != last_pct and current_sec > 5:
                    last_pct = pct
                    self._extract_thumb(current_sec - 2)
                # Kill VLC if we've reached the expected duration
                if current_sec >= duration - 5:
                    proc.kill()
                    proc.wait()
                    break
            time.sleep(2)
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        self.progress_rip.emit(duration, duration)

    def _convert(self, src_path, dst_path, job=None):
        """Convert TS → MP4. DVD TS files already contain
        H.264 + AAC, so this is just a container remux + aspect ratio."""
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

        is_dvd = job and job.get("disc_type") == "dvd"
        cmd = [
            "ffmpeg", "-y", "-i", src_path,
            "-c", "copy",
        ]
        if is_dvd:
            cmd += ["-aspect", job.get("aspect", "16:9")]
        cmd += [
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

    def __init__(self):
        super().__init__()
        self.setWindowTitle("JoPhi's Disc Clouder")
        self.setMinimumSize(1000, 750)
        self.setStyleSheet(DARK_STYLE)

        self.vlc_instance = vlc.Instance("--no-xlib", "--quiet")
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

        QTimer.singleShot(500, self._scan_discs)

        self._last_volumes = set()
        self.disc_poll_timer = QTimer()
        self.disc_poll_timer.setInterval(3000)
        self.disc_poll_timer.timeout.connect(self._check_for_new_disc)
        self.disc_poll_timer.start()

    # =====================================================================
    # UI
    # =====================================================================
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(16, 12, 16, 12)

        # Header (always visible)
        hdr = QHBoxLayout()
        lbl_app = QLabel("JoPhi's Disc Clouder")
        lbl_app.setFont(QFont("Helvetica", 18, QFont.Weight.Bold))
        lbl_app.setStyleSheet("color: #1db954;")
        hdr.addWidget(lbl_app)
        hdr.addStretch()
        self.lbl_disc = QLabel("Keine Disc")
        self.lbl_disc.setFont(QFont("Helvetica", 14, QFont.Weight.Bold))
        hdr.addWidget(self.lbl_disc)
        self.lbl_type = QLabel("")
        self.lbl_type.setStyleSheet(
            "background: #e74c5e; color: white; padding: 2px 10px;"
            "border-radius: 4px; font-weight: bold;"
        )
        hdr.addWidget(self.lbl_type)
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

        # --- View 1: Selection (with Tabs) ---
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

        # Tabs below player
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #1a3a5c; border-radius: 6px;
                               background: #0d1b2a; }
            QTabBar::tab { background: #1b2838; color: #8899aa; padding: 8px 20px;
                           border: 1px solid #1a3a5c; border-bottom: none;
                           border-top-left-radius: 6px; border-top-right-radius: 6px; }
            QTabBar::tab:selected { background: #0d1b2a; color: #4ecdc4;
                                    font-weight: bold; }
        """)
        vs.addWidget(self.tabs, 1)

        # -- Tab 1: Titel --
        tab_titel = QWidget()
        tt = QVBoxLayout(tab_titel)
        tt.setContentsMargins(8, 8, 8, 8)

        self.track_tree = QTreeWidget()
        self.track_tree.setHeaderLabels(["Nr", "Dauer", "Video", "Audio"])
        self.track_tree.setAlternatingRowColors(True)
        self.track_tree.setRootIsDecorated(False)
        self.track_tree.header().setStretchLastSection(True)
        tt.addWidget(self.track_tree)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("Zusatz:"))
        self.edit_suffix = QLineEdit()
        self.edit_suffix.setPlaceholderText("z.B. Extended, SW...")
        add_row.addWidget(self.edit_suffix, 1)
        add_row.addWidget(QLabel("Audio:"))
        self.combo_audio = QComboBox()
        self.combo_audio.setMinimumWidth(200)
        add_row.addWidget(self.combo_audio)
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

        self.lbl_bar1 = QLabel("Disc → TS")
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

        self.lbl_bar2 = QLabel("TS → MP4")
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
        self.btn_scan.clicked.connect(lambda: self._full_reset(eject=False))
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
        self.combo_audio.currentIndexChanged.connect(self._on_audio_changed)

    # =====================================================================
    # Title field tracking
    # =====================================================================
    def _on_title_edited(self, text):
        self._title_set_by_user = True

    # =====================================================================
    # Disc scanning
    # =====================================================================
    def _check_for_new_disc(self):
        if self.rip_worker and self.rip_worker.isRunning():
            return
        try:
            current = set(os.listdir("/Volumes"))
        except OSError:
            return
        if current != self._last_volumes:
            self._last_volumes = current
            self._scan_discs()

    def _scan_discs(self):
        self.lbl_status.setText("Scanne...")
        self.tracks = []
        self.track_tree.clear()

        def _do():
            discs = find_discs()
            if not discs:
                self.scan_done.emit([])
                return
            self.disc = discs[0]
            tracks = scan_titles(self.disc, self.vlc_instance)
            self.scan_done.emit(tracks)

        threading.Thread(target=_do, daemon=True).start()

    def _on_scan_done(self, tracks):
        self.tracks = tracks
        if not self.disc:
            self.lbl_disc.setText("Keine Disc gefunden")
            self.lbl_type.setText("")
            self.lbl_status.setText("")
            return

        self.lbl_disc.setText(self.disc["name"])
        self.lbl_type.setText(self.disc["type"].upper())

        if not self._title_set_by_user:
            self.edit_base_title.setText(
                self.disc["name"].replace("_", " ").title()
            )

        self.track_tree.clear()
        for t in tracks:
            dur = t["duration"]
            dur_str = f"{dur // 60}:{dur % 60:02d}"
            item = QTreeWidgetItem([
                str(t["idx"]),
                dur_str,
                t.get("video_codec", ""),
                f"{len(t['audio'])} Spuren",
            ])
            self.track_tree.addTopLevelItem(item)

        for i in range(4):
            self.track_tree.resizeColumnToContents(i)

        self.vlc_player.set_nsobject(int(self.video_widget.winId()))
        self.vlc_player.audio_set_volume(self.vol_slider.value())

        self.lbl_status.setText(f"{len(tracks)} Titel gefunden")

    # =====================================================================
    # Track selection + Preview
    # =====================================================================
    def _on_track_clicked(self, item, col):
        idx = int(item.text(0))
        track = next((t for t in self.tracks if t["idx"] == idx), None)
        if not track:
            return

        # DVD: open new media with title in URL
        link = "/tmp/disc_clouder_dvd"
        try:
            os.unlink(link)
        except OSError:
            pass
        os.symlink(self.disc["mount"], link)
        media = self.vlc_instance.media_new(f"dvdsimple://{link}#{idx}")
        self.vlc_player.set_media(media)
        self.vlc_player.set_nsobject(int(self.video_widget.winId()))
        self.vlc_player.play()

        time.sleep(0.3)
        self.vlc_player.audio_set_volume(self.vol_slider.value())
        self.pos_timer.start()
        self.btn_play.setText("Pause")

        # Populate audio dropdown
        self.combo_audio.blockSignals(True)
        self.combo_audio.clear()
        for a in track["audio"]:
            self.combo_audio.addItem(a["name"], a["id"])
        self.combo_audio.blockSignals(False)

        self.edit_suffix.clear()

    # =====================================================================
    # Player controls
    # =====================================================================
    def _toggle_play(self):
        state = self.vlc_player.get_state()
        if state == vlc.State.Playing:
            self.vlc_player.pause()
            self.btn_play.setText("Play")
        else:
            self.vlc_player.play()
            self.vlc_player.audio_set_volume(self.vol_slider.value())
            self.btn_play.setText("Pause")
            self.pos_timer.start()

    def _stop_player(self):
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
        self.vlc_player.set_time(int(val * length / 1000))

    def _on_audio_changed(self, index):
        audio_id = self.combo_audio.currentData()
        if audio_id is not None:
            self.vlc_player.audio_set_track(audio_id)

    # =====================================================================
    # Queue management
    # =====================================================================
    def _add_to_queue(self):
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

        audio_idx = self.combo_audio.currentIndex()
        audio_name = self.combo_audio.currentText()
        audio_lang = ""
        if audio_idx < len(track.get("audio", [])):
            audio_lang = track["audio"][audio_idx].get("lang", "")

        job = {
            "title_idx": idx,
            "playlist": track.get("playlist"),
            "audio_idx": audio_idx,
            "audio_name": audio_name,
            "audio_lang": audio_lang,
            "name": name,
            "duration": track["duration"],
            "video_codec": track.get("video_codec", ""),
            "disc_type": self.disc["type"],
            "dvd_title": track.get("dvd_title", idx),
            "aspect": track.get("aspect", "16:9"),
        }
        self.queue.append(job)

        # Add to queue tree
        dur = track["duration"]
        dur_str = f"{dur // 60}:{dur % 60:02d}"
        item = QTreeWidgetItem([name, dur_str, audio_name,
                                track.get("video_codec", "")])
        self.queue_tree.addTopLevelItem(item)

        QMessageBox.information(self, "Queue", f"'{name}' zur Queue hinzugefügt\n({len(self.queue)} in Queue)")
        self.lbl_status.setText(f"'{name}' zur Queue hinzugefügt ({len(self.queue)} in Queue)")

    def _clear_queue(self):
        self.queue.clear()
        self.queue_tree.clear()
        self.lbl_status.setText("Queue geleert")

    # =====================================================================
    # Ripping (Queue)
    # =====================================================================
    def _start_queue(self):
        if not self.queue:
            self.lbl_status.setText("Queue ist leer")
            return
        if not self.disc:
            return

        output_dir = self.edit_output.text().strip() or DEFAULT_OUTPUT

        # Stop preview player and release disc
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
        self._convert_start_time = None

        self.rip_worker = RipWorker(
            queue=list(self.queue),
            disc=self.disc,
            output_dir=output_dir,
        )
        self.rip_worker.progress_rip.connect(self._on_rip_progress)
        self.rip_worker.progress_convert.connect(self._on_convert_progress)
        self.rip_worker.thumbnail.connect(self._on_thumbnail)
        self.rip_worker.status.connect(lambda s: self.lbl_rip_title.setText(s))
        self.rip_worker.job_started.connect(self._on_job_started)
        self.rip_worker.job_finished.connect(self._on_job_finished)
        self.rip_worker.all_finished.connect(self._on_all_finished)
        self.rip_worker.cancelled.connect(self._on_cancelled)
        self.rip_worker.error.connect(self._on_rip_error)
        self.rip_worker.start()

    def _on_job_started(self, idx, total, name):
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
        self.lbl_bar1.setText("Disc → TS")
        self.lbl_bar2.setText("TS → MP4")

    def _on_rip_progress(self, current, total):
        self.bar_rip.setMaximum(total)
        self.bar_rip.setValue(current)

        now = time.time()
        elapsed = now - self._rip_start_time
        self._rip_history.append((now, current))

        if elapsed > 5 and current > 0:
            avg_speed = current / elapsed

            # 30-second recent speed
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

            # Trim old history (keep last 60 seconds)
            self._rip_history = [(t, s) for t, s in self._rip_history if t >= now - 60]

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
        # Update queue tree
        if idx < self.queue_tree.topLevelItemCount():
            item = self.queue_tree.topLevelItem(idx)
            item.setText(0, f"✓ {item.text(0)}")

    def _on_all_finished(self):
        self._full_reset()
        self.lbl_status.setText("Alle Rips fertig!")

    def _on_rip_error(self, idx, msg):
        if idx < self.queue_tree.topLevelItemCount():
            item = self.queue_tree.topLevelItem(idx)
            item.setText(0, f"✗ {item.text(0)}")
        self.lbl_status.setText(f"Fehler bei Rip {idx + 1}: {msg}")

    def _cancel_rip(self):
        if self.rip_worker:
            self.rip_worker.cancel()

    def _on_cancelled(self):
        self._full_reset()
        self.lbl_status.setText("Abgebrochen")

    def _full_reset(self, eject=True):
        """Complete reset — as if the app was freshly started."""

        # 1. Stop timers
        self.pos_timer.stop()
        self.disc_poll_timer.stop()

        # 2. Kill VLC completely and recreate
        try:
            self.vlc_player.stop()
        except Exception:
            pass
        try:
            self.vlc_player.release()
        except Exception:
            pass
        try:
            self.vlc_instance.release()
        except Exception:
            pass
        self.vlc_instance = vlc.Instance("--no-xlib", "--quiet")
        self.vlc_player = self.vlc_instance.media_player_new()

        # 3. Eject disc (optional)
        if eject:
            subprocess.run(["drutil", "eject"], capture_output=True)

        # 4. Delete ALL temp files
        for f in [TMP_RIP + ".ts", TMP_THUMB,
                  "/tmp/disc_clouder_dvd"]:
            try:
                os.remove(f)
            except OSError:
                pass

        # 5. Reset ALL data variables
        self.disc = None
        self.tracks = []
        self.queue = []
        self.rip_worker = None
        self._seeking = False
        self._title_set_by_user = False
        self._rip_start_time = 0
        self._convert_start_time = None
        self._rip_history = []

        # 6. Reset ALL UI to startup state
        self.stack.setCurrentIndex(0)
        self.btn_scan.setVisible(True)
        self.btn_eject.setVisible(True)
        self.lbl_disc.setText("Keine Disc")
        self.lbl_type.setText("")
        self.lbl_status.setText("")
        self.lbl_time.setText("00:00 / 00:00")
        self.btn_play.setText("Play")
        self.track_tree.clear()
        self.queue_tree.clear()
        self.combo_audio.clear()
        self.edit_suffix.clear()
        self.edit_base_title.clear()
        self.lbl_thumb.clear()
        self.seek_slider.setValue(0)
        self.vol_slider.setValue(80)
        self.bar_rip.setValue(0)
        self.bar_convert.setValue(0)
        self.lbl_rip_stats.setText("")
        self.lbl_convert_stats.setText("")
        self.lbl_rip_title.setText("")

        # 7. Restart disc polling and scan — like __init__ does
        self._last_volumes = set()
        self.disc_poll_timer.start()
        QTimer.singleShot(500, self._scan_discs)

    # =====================================================================
    # Eject
    # =====================================================================
    def _eject(self):
        self._full_reset()
        self.lbl_status.setText("Disc ausgeworfen")

    # =====================================================================
    # Cleanup
    # =====================================================================
    def closeEvent(self, event):
        self.vlc_player.stop()
        if self.rip_worker and self.rip_worker.isRunning():
            self.rip_worker.cancel()
        event.accept()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
DEBUG = "--debug" in sys.argv

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Helvetica", 13))
    window = DiscClouder()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
