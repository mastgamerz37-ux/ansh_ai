import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import sys
import threading
import time
import json
import os
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QLineEdit, QGraphicsDropShadowEffect, QSizePolicy
import keyboard

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent

BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"

def _read_full_config() -> dict:
    try:
        return json.loads(API_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

class SmartIslandWindow(QWidget):
    subtitle_signal = pyqtSignal(str)
    state_signal = pyqtSignal(str)
    reconfig_signal = pyqtSignal()
    name_signal = pyqtSignal()
    license_signal = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._muted = False
        self._ready = True
        self._assistant_name = _read_full_config().get("assistant_name", "ANSH") or "ANSH"
        
        self.on_text_command = None
        self.on_remote_clicked = None
        self.on_interrupt = None
        
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.base_width = 150
        self.base_height = 55
        self.expanded_width = 400
        self.expanded_height = 100
        self.is_expanded = False

        self.init_ui()
        self.setup_hotkey()

        self.subtitle_signal.connect(self.show_subtitle)
        self.state_signal.connect(self.update_state)
        self.reconfig_signal.connect(self.prompt_api_key_dialog)
        self.name_signal.connect(self.prompt_name_dialog)
        self.license_signal.connect(self.prompt_license_dialog)
        
        # Idle timer (1 minute)
        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self.hide)
        self.idle_timer.start(60000)

        # Liquid motion timer
        self.liquid_timer = QTimer(self)
        self.liquid_timer.timeout.connect(self.animate_liquid)
        self.liquid_step = 0
        self._current_state = "IDLE"
        self.update_state("IDLE")

        self.enforce_autostart()

    def enforce_autostart(self):
        try:
            import platform
            _OS = platform.system()
            script = str(Path(__file__).resolve().parent / "main.py")
            if _OS == "Windows":
                import winreg
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
                pythonw = Path(sys.executable).parent / "pythonw.exe"
                exe = str(pythonw if pythonw.exists() else sys.executable)
                winreg.SetValueEx(reg, "ANSH_AI", 0, winreg.REG_SZ, f'"{exe}" "{script}"')
                winreg.CloseKey(reg)
            print("[SYS] Auto-start enforced.")
        except Exception as e:
            print(f"[ERR] Auto-start failed: {e}")

    def init_ui(self):
        self.setFixedSize(self.base_width, self.base_height)
        screen = QApplication.primaryScreen().geometry()
        self.x_pos = (screen.width() - self.base_width) // 2
        self.y_pos = 10
        self.move(self.x_pos, self.y_pos)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)

        self.container = QWidget(self)
        self.container.setStyleSheet("""
            QWidget {
                background-color: #000000;
                border-radius: 20px;
                border: 2px solid #333333;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 5)
        self.container.setGraphicsEffect(shadow)

        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(15, 10, 15, 10)
        self.container_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetNoConstraint)

        self.subtitle_label = QLabel(self._assistant_name)
        self.subtitle_label.setStyleSheet("color: white; font-weight: bold; font-family: 'Segoe UI'; font-size: 14px; border: none;")
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.container_layout.addWidget(self.subtitle_label)

        self.input_field = QLineEdit()
        self.input_field.setStyleSheet("""
            QLineEdit {
                background-color: #1c1c1e;
                color: white;
                border: 1px solid #555555;
                border-radius: 10px;
                padding: 5px 10px;
                font-family: 'Segoe UI';
                font-size: 14px;
            }
        """)
        self.input_field.setPlaceholderText("Type a command...")
        self.input_field.hide()
        self.input_field.returnPressed.connect(self.on_submit)
        self.container_layout.addWidget(self.input_field)

        self.layout.addWidget(self.container)

    def setup_hotkey(self):
        try:
            keyboard.add_hotkey('ctrl+shift+a', self.toggle_expand_safe)
        except Exception as e:
            print(f"Failed to bind hotkey: {e}")

    def reset_idle_timer(self):
        self.show()
        self.idle_timer.start(60000)

    def toggle_expand_safe(self):
        QTimer.singleShot(0, self.reset_idle_timer)
        QTimer.singleShot(0, self.toggle_expand)

    def toggle_expand(self):
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def animate_size(self, width, height):
        self.setMinimumSize(0, 0)
        self.setMaximumSize(9999, 9999)
        screen = QApplication.primaryScreen().geometry()
        new_x = (screen.width() - width) // 2
        
        self.size_anim = QPropertyAnimation(self, b"geometry")
        self.size_anim.setDuration(300)
        self.size_anim.setEasingCurve(QEasingCurve.Type.OutExpo)
        self.size_anim.setEndValue(QRect(new_x, self.y_pos, width, height))
        self.size_anim.start()

    def expand(self):
        self.is_expanded = True
        self.subtitle_label.show()
        self.input_field.show()
        self.input_field.setFocus()
        self.animate_size(self.expanded_width + 100, self.expanded_height + 20)

    def collapse(self):
        self.is_expanded = False
        self.input_field.hide()
        self.input_field.clear()
        
        if getattr(self, "_current_state", "IDLE") != "SPEAKING":
            self.subtitle_label.setText(self._assistant_name)
            self.animate_size(self.base_width, self.base_height)
        else:
            self.show_subtitle(self.subtitle_label.text())

    def show_subtitle(self, text):
        self.reset_idle_timer()
        self.subtitle_label.setText(text)
        if not self.subtitle_label.isVisible() and text.strip():
            self.subtitle_label.show()
            
        if getattr(self, "_current_state", "IDLE") == "SPEAKING" and not self.is_expanded:
            if text == self._assistant_name:
                self.animate_size(self.base_width, self.base_height)
            else:
                chars = len(text)
                target_w = min(500, max(200, chars * 10 + 40))
                if chars > 45:
                    target_w = 500
                lines = chars // 45 + 1
                target_h = max(70, 40 + lines * 22)
                self.animate_size(target_w, target_h)

    def animate_liquid(self):
        import math
        self.liquid_step += 1
        t = self.liquid_step * 0.1
        
        x1 = 0.5 + 0.5 * math.sin(t)
        y1 = 0.5 + 0.5 * math.cos(t)
        x2 = 0.5 + 0.5 * math.sin(t + math.pi)
        y2 = 0.5 + 0.5 * math.cos(t + math.pi)
        
        color1 = "rgba(88, 14, 255, 0.85)"
        color2 = "rgba(0, 212, 255, 0.85)"
        r = 20 + 4 * math.sin(t * 2)
        
        self.container.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(spread:pad, x1:{x1:.2f}, y1:{y1:.2f}, x2:{x2:.2f}, y2:{y2:.2f}, stop:0 {color1}, stop:1 {color2});
                border-radius: {r:.1f}px;
                border: 1px solid rgba(255, 255, 255, 40);
            }}
        """)

    def update_state(self, state):
        self.reset_idle_timer()
        self._current_state = state
        if state == "SPEAKING":
            self.liquid_timer.stop()
            self.subtitle_label.show()
            self.container.setStyleSheet("""
                QWidget {
                    background-color: rgba(15, 15, 20, 240);
                    border-radius: 20px;
                    border: 2px solid rgba(0, 212, 255, 150);
                }
            """)
            self.show_subtitle(self.subtitle_label.text())
        else:
            if not self.is_expanded:
                self.subtitle_label.setText(self._assistant_name)
                self.subtitle_label.show()
                self.animate_size(self.base_width, self.base_height)
            self.liquid_timer.start(50)

    def prompt_api_key_dialog(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from memory.config_manager import get_gemini_key, save_api_keys
        cur = get_gemini_key() or ""
        text, ok = QInputDialog.getText(
            None,
            "ANSH AI — API Key Settings",
            "Enter your Google Gemini API Key:\n(Developed by Anshu Dubey)",
            QLineEdit.EchoMode.Password,
            cur,
        )
        if ok and text.strip():
            save_api_keys(text.strip())
            self.show_subtitle("API Key updated successfully.")
            QMessageBox.information(None, "Success", "Gemini API Key saved successfully!")
            return True
        return False

    def prompt_name_dialog(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from memory.config_manager import get_user_name, get_assistant_name, save_assistant_config
        cur_name = get_user_name()
        asst_name = get_assistant_name()
        text, ok = QInputDialog.getText(
            None,
            "ANSH AI — User Name Settings",
            "Enter your name so ANSH can address you properly:",
            QLineEdit.EchoMode.Normal,
            cur_name,
        )
        if ok and text.strip():
            save_assistant_config(asst_name, text.strip())
            self.show_subtitle(f"Hello, {text.strip()}!")
            QMessageBox.information(None, "Success", f"User name updated to: {text.strip()}")
            return True
        return False

    def prompt_license_dialog(self):
        from PyQt6.QtWidgets import QInputDialog, QMessageBox
        from licensing.engine import activate_license, check_license_status
        st = check_license_status()
        prompt_msg = f"{st.message}\n\nEnter Product Key (ANSH-XXXX-XXXX-XXXX-XXXX):"
        text, ok = QInputDialog.getText(
            None,
            "ANSH AI — License Activation",
            prompt_msg,
            QLineEdit.EchoMode.Normal,
        )
        if ok and text.strip():
            success, msg = activate_license(text.strip())
            if success:
                QMessageBox.information(None, "Activation Successful", msg)
                self.show_subtitle("License Activated: Lifetime Access")
                return True
            else:
                QMessageBox.critical(None, "Activation Failed", msg)
                return False
        return False

    def on_submit(self):
        self.reset_idle_timer()
        text = self.input_field.text().strip()
        if not text:
            return

        cmd_lower = text.lower()
        
        # Intercept Developer Query
        if any(w in cmd_lower for w in ("who developed you", "who made you", "developer", "creator", "portfolio", "anshu dubey")):
            import webbrowser
            webbrowser.open("https://devanshu.page.gd")
            self.show_subtitle("Developed by Anshu Dubey. Opening portfolio...")
            self.collapse()
            if self.on_text_command:
                threading.Thread(target=self.on_text_command, args=(text,), daemon=True).start()
            return

        # Intercept Configuration Commands
        if any(w in cmd_lower for w in ("change api key", "set api key", "update api key", "edit api key", "api key")):
            self.collapse()
            QTimer.singleShot(100, self.prompt_api_key_dialog)
            return

        if any(w in cmd_lower for w in ("change name", "set name", "update name", "change my name", "user name")):
            self.collapse()
            QTimer.singleShot(100, self.prompt_name_dialog)
            return

        if any(w in cmd_lower for w in ("license", "activate", "product key", "enter key", "trial")):
            self.collapse()
            QTimer.singleShot(100, self.prompt_license_dialog)
            return

        if any(w in cmd_lower for w in ("check update", "update app", "github update")):
            from updater.github_updater import get_updater
            up = get_updater().check_for_updates()
            if up.get("has_update"):
                self.show_subtitle(f"Update available: v{up['latest_version']}. Opening GitHub...")
                import webbrowser
                webbrowser.open(up.get("url", "https://github.com/devanshu/ANSH-AI"))
            else:
                self.show_subtitle(f"ANSH is up to date (v{up['current_version']}).")
            self.collapse()
            return

        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(text,), daemon=True).start()
        self.collapse()

    def _toggle_mute(self):
        self._muted = not self._muted
        if self._muted:
            self.subtitle_signal.emit("MUTED")
        else:
            self.subtitle_signal.emit("LISTENING")
        self.reset_idle_timer()
        
    def notify_phone_connected(self): pass
    def start_camera_stream(self): pass
    def stop_camera_stream(self): pass


class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app
    def mainloop(self):
        self._app.exec()
    def protocol(self, *_):
        pass

class AnshUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = SmartIslandWindow()
        self._win.show()
        self.root = _RootShim(self._app)
        
        self._log_sig = pyqtSignal(str)
        self._content_sig = pyqtSignal(str, str)
        self._reconfig_sig = pyqtSignal()
        self._camera_sig = pyqtSignal(bytes)

    @property
    def muted(self) -> bool: return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted: self._win._toggle_mute()

    @property
    def current_file(self) -> str | None: return None

    @property
    def on_text_command(self): return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb): self._win.on_text_command = cb

    @property
    def on_remote_clicked(self): return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb): self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self): return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb): self._win.on_interrupt = cb

    def notify_phone_connected(self) -> None: pass

    def set_state(self, state: str):
        self._win.state_signal.emit(state)

    def write_log(self, text: str):
        if text.startswith("ANSH:") or text.startswith("Ansh:"):
            msg = text.split(":", 1)[1].strip()
            self._win.subtitle_signal.emit(msg)

    def check_license(self) -> bool:
        from licensing.engine import check_license_status
        from PyQt6.QtWidgets import QMessageBox
        st = check_license_status()
        if not st.is_valid:
            QMessageBox.warning(
                None,
                "ANSH AI — Trial Expired",
                f"{st.message}\n\nPlease activate with a valid Product Key to continue.",
            )
            return self._win.prompt_license_dialog()
        return True

    def wait_for_api_key(self):
        self.check_license()
        from memory.config_manager import get_gemini_key, get_user_name, save_api_keys, save_assistant_config, get_assistant_name
        from PyQt6.QtWidgets import QInputDialog, QMessageBox

        cur_key = get_gemini_key()
        if not cur_key:
            text, ok = QInputDialog.getText(None, "Welcome to ANSH AI", "First time setup: Enter your Gemini API Key:\n(Developed by Anshu Dubey)", QLineEdit.EchoMode.Password)
            if ok and text.strip():
                save_api_keys(text.strip())
            else:
                QMessageBox.critical(None, "Error", "API Key is required to run ANSH AI.")
                sys.exit(0)

        cur_user = get_user_name()
        if not cur_user:
            text, ok = QInputDialog.getText(None, "Welcome to ANSH AI", "First time setup: What is your name?", QLineEdit.EchoMode.Normal)
            if ok and text.strip():
                save_assistant_config(get_assistant_name(), text.strip())

    def show_content(self, title: str, text: str): pass
    def prompt_reconfig(self):
        self._win.reconfig_signal.emit()

    def prompt_name(self):
        self._win.name_signal.emit()

    def prompt_license(self):
        self._win.license_signal.emit()

    def show_camera_frame(self, img_bytes: bytes): pass
    def start_camera_stream(self) -> None: pass
    def stop_camera_stream(self) -> None: pass

    @property
    def assistant_name(self) -> str: return self._win._assistant_name

    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self):
        if not self.muted: self.set_state("LISTENING")

