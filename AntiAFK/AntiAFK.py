import win32gui
import win32con
import win32api
import random
import sys
import os
import subprocess
import pywintypes
import keyboard
from pynput.keyboard import Key, Controller as KeybController
from pynput.mouse import Listener as MouseListener
from PyQt5.QtWidgets import QTextEdit, QSpacerItem, QSizePolicy, QGridLayout, QLineEdit, QMessageBox, QComboBox, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDesktopWidget, QGroupBox, QCheckBox, QSpinBox
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QPoint, QTimer, QObject, Qt, QCoreApplication, pyqtSignal, QThread, pyqtSlot
from winotify import Notification
from Widgets import Screensaver, CollapsibleBox, ListDialog
from Utils import ExceptionHandler, Timer, SingleshotTimer, get_res, ICON_PATH
from pyqtconfig import ConfigManager
from functools import partial

def _get_CollapsibleBox(self):
    return self.isChecked()

def _set_CollapsibleBox(self, val):
    self.setChecked(val)

def _event_CollapsibleBox(self):
    return self.stateChanged

HOOKS = {
    CollapsibleBox: (_get_CollapsibleBox, _set_CollapsibleBox, _event_CollapsibleBox)
}

class AntiAFK(QObject):
    update_timer_label = pyqtSignal(str)
    show_error_message = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, config, winid):
        super().__init__()
        self.config = config
        self.winid = winid
        self.hwnds = []
        self.notopmost = False
        self.keyboard_controller = KeybController()
        self.notification_shown = False

        self.timer = Timer()
        self.timer.timeout.connect(self.handle_timeout)
        self.timer.finished.connect(self.main)

        self.init_variables()

    def init_variables(self):
        names = self.config.get("window_text")
        self.window_names = [name.strip() for name in names.split(",")]

        keys = ['w', 'a', 's', 'd', 'space', 'left', 'up', 'down', 'right']
        self.allowed_key_codes = [keyboard.key_to_scan_codes(key)[0] for key in keys]

        minutes = self.config.get("interval_min")
        seconds = self.config.get("interval_sec")
        self.interval = (minutes * 60) + seconds

        self.block_input = self.config.get("block_input")
        self.transparent_window = self.config.get("transparent_window")

    @pyqtSlot(int)
    def handle_timeout(self, seconds):
        self.update_label(seconds)
        if not self.notification_shown and seconds <= 4:
            self.show_notification(
                "The windows will open in a few seconds\n"
                "Don't click or press keys"
            )
            self.notification_shown = True

    def main(self):
        self.hwnds = self.collect_hwnds(self.window_names)
        if self.hwnds:
            self.set_label("Activity")
            self.perform_activity(self.hwnds)
        else:
            self.set_label("No windows")
            self.time_sleep(1, on_finished=self.main)

    def start_timer(self, time_sec=None):
        if time_sec is None:
            time_sec = self.interval
        self.notification_shown = False
        self.timer.start(time_sec)

    def stop_timer(self):
        self.timer.stop()
        self.disconnect_timer()
        if hasattr(self, "singleshot_timer"):
            self.singleshot_timer.stop()
        
    def disconnect_timer(self):
        signals = [self.timer.timeout, self.timer.finished]
        if any(self.timer.receivers(signal) > 0 for signal in signals):
            self.timer.disconnect()

    def perform_activity(self, handles):
        window = win32gui.GetForegroundWindow()
        # Assign a value if the focus is not on the Anti-AFK program
        self.previous_hwnd = window if window != self.winid else None

        for handle in handles:
            activity_delay = self.config.get("activity_delay")
            activity_type = self.config.get("activity_type")
            window_state = win32gui.GetWindowPlacement(handle)[1]

            def activity():
                self.keypressing(activity_type)
                self.hide_window(handle, window_state)

            response = self.show_window(handle, window_state)
            if response is not False:
                self.time_sleep(activity_delay, on_finished=activity)
                
        self.start_timer()

    def time_sleep(self, delay_sec: float, on_finished=None):
        """
        Create delays without freezing GUI
        It's just like QTimer.singleShot but slot is optional
        and it will wait for the timer to complete before continuing
        """
        delay = round(delay_sec * 1000)
        self.singleshot_timer = SingleshotTimer()

        if on_finished:
            self.singleshot_timer.finished.connect(on_finished)
        self.singleshot_timer.start(delay)
        
        while self.singleshot_timer.is_active():
            QCoreApplication.processEvents()
            QThread.msleep(5) #preventing a lot of CPU usage

    def collect_hwnds(self, names):
        handles = []
        maximized_allowed = self.config.get("maximized_windows")

        def callback(handle, _):
            if handle:
                window_name = win32gui.GetWindowText(handle)
                window_placement = win32gui.GetWindowPlacement(handle)[1]

                if window_name in names and (window_placement == 2 or maximized_allowed):
                    handles.append(handle)

        win32gui.EnumWindows(callback, None)
        print('Handles: ', handles)
        return handles

    def set_key_blocking(self, block):
        key_codes = [i for i in range(1, 150) if i not in self.allowed_key_codes]
        for key in key_codes:
            try:
                if block:
                    keyboard.block_key(i)
                else:
                    keyboard.unblock_key(i)
            except:
                pass

    def reset_window_transparency(self, handle=None):
        if handle:
            self.set_window_transparency(handle, 255)
        elif self.hwnds:
            for handle in self.hwnds:
                self.set_window_transparency(handle, 255)

    def set_mouse_blocking(self, block):
        if block:
            self.mouse_listener = MouseListener(suppress=True)
            self.mouse_listener.start()
        else:
            if hasattr(self, "mouse_listener") and self.mouse_listener.is_alive():
                self.mouse_listener.stop()
                del self.mouse_listener

    def apply_activity_settings(self, handle):
        if self.block_input:
            self.set_mouse_blocking(True)
            self.set_key_blocking(True)
        
        if self.transparent_window:
            self.set_window_transparency(handle, 0)

    def cancel_activity_settings(self, handle=None, anyway=False):
        if self.transparent_window or anyway:
            self.reset_window_transparency(handle)

        if self.block_input or anyway:
            self.set_mouse_blocking(False)
            self.set_key_blocking(False)

    def show_window(self, handle, initial_state):
        self.apply_activity_settings(handle)

        if self.notopmost: 
            self.set_window_pos(handle, win32con.HWND_NOTOPMOST)
        else:
            self.set_window_pos(handle, win32con.HWND_TOPMOST) #Set window on top
            self.set_window_pos(handle, win32con.HWND_NOTOPMOST) #but not overlap all other windows

        # If the window display fails, try again after 30 seconds
        def cancel():
            self.hide_window(handle, initial_state)
            self.cancel_activity_settings(handle)
            self.start_timer(30)

        # If there was a maximized state then set foreground
        if initial_state == 1: 
            try:
                win32gui.SetForegroundWindow(handle)
            except:
                cancel()
                return False
        else:
            win32gui.ShowWindow(handle, win32con.SW_NORMAL)
            if win32gui.GetForegroundWindow() != handle:
                cancel()
                return False

    def hide_window(self, handle, initial_state):
        hide_maximized = self.config.get("hide_maximized_windows")

        if initial_state == 2: #if there was a minimized state then minimize
            win32gui.ShowWindow(handle, win32con.SW_MINIMIZE)
        elif hide_maximized:
            self.set_window_pos(handle, win32con.HWND_BOTTOM)
            
        # Set previous window foreground if the target window was maximized
        # because in this case, focus is not returned to the window
        # Disabled due to unpredictable situations that may occur

        # if initial_state == 1 and self.previous_hwnd:
        #     try:
        #         win32gui.SetForegroundWindow(self.previous_hwnd)
        #     except:
        #         pass

        self.cancel_activity_settings(handle)

    def keypressing(self, activity_type):
        duration = random.uniform(0.3, 0.6)
        arrow_key = random.choice([Key.left, Key.right])
        wasd_key = random.choice(["w", "a", "s", "d"])
        random_key = random.choice([Key.space, arrow_key, wasd_key])

        activity_task = {
            1: [partial(self.keyboard_press, Key.space, duration)],
            2: [partial(self.keyboard_press, arrow_key, duration)],
            3: [
                partial(self.keyboard_press, Key.space, duration),
                partial(self.keyboard_press, wasd_key, duration)
            ],
            4: [partial(self.keyboard_press, wasd_key, duration)],
            5: [partial(self.keyboard_press, random_key, duration)]
        }

        task = activity_task[activity_type]

        for command in task:
            command()

    def set_window_transparency(self, handle, bAlpha):
        try:
            style = win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(handle, win32con.GWL_EXSTYLE, style | win32con.WS_EX_LAYERED)
            win32gui.SetLayeredWindowAttributes(handle, win32api.RGB(0,0,0), bAlpha, win32con.LWA_ALPHA)
        except Exception as e:
            print("Can't set window transparency: ", e)

    def set_window_pos(self, handle, flag):
        try:
            win32gui.SetWindowPos(handle, flag, 0, 0, 0, 0, win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        except pywintypes.error as e:
            #Access Denied Error
            if e.args[0] == 5:
                self.stop_timer()
                self.show_error_message.emit(
                    "It looks like your target window is running as administrator.\n"
                    "You will need to restart Anti-AFK with elevated rights."
                )
                self.finished.emit()
            #Invalid window handle
            elif e.args[0] == 1400:
                pass 
            else:
                raise

    def set_all_windows_notopmost(self):
        for handle in self.hwnds:
            self.set_window_pos(handle, win32con.HWND_NOTOPMOST)

    def keyboard_press(self, key, duration):
        self.keyboard_controller.press(key)
        self.time_sleep(duration)
        self.keyboard_controller.release(key)

    def show_notification(self, message):
        if self.config.get("notification"):
            toast = Notification(
                         app_id="Anti-AFK",
                         title="Notifier",
                         msg=message,
                         icon=ICON_PATH)
            toast.show()

    def update_label(self, seconds):
        formatted_time = self.timer.format_seconds(seconds)
        self.update_timer_label.emit(f"Timer: {formatted_time}")

    def set_label(self, text):
        self.update_timer_label.emit(text)

class ProcessKiller(QObject):
    save_settings = pyqtSignal()
    update_timer_label = pyqtSignal(str)
    stop_program = pyqtSignal()
    finished = pyqtSignal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.timer = Timer()

        self.init_variables()

    def init_variables(self):
        hours = self.config.get("kill_delay_hours")
        minutes = self.config.get("kill_delay_minutes")
        self.kill_delay = hours * 3600 + minutes * 60

        names = self.config.get("process_names")
        self.process_names = [name.strip() for name in names.split(",")]

    @pyqtSlot(int, str)
    def update_label(self, seconds_left, description):
        formatted_time = self.timer.format_seconds(seconds_left)
        self.update_timer_label.emit(f"{description}: {formatted_time}")

    def run_timer(self, sec, description, on_finished):
        self.stop_timer()
        self.timer.timeout.connect(lambda remaining_time: self.update_label(remaining_time, description))
        self.timer.finished.connect(on_finished)
        self.timer.start(sec)
    
    def disconnect_timer(self):
        signals = [self.timer.timeout, self.timer.finished]
        if any(self.timer.receivers(signal) > 0 for signal in signals):
            self.timer.disconnect()

    def stop_timer(self):
        self.timer.stop()
        self.disconnect_timer()

    def reset_label(self):
        self.update_timer_label.emit("")

    def run_command(self, command: str, args: list):
        try:
            subprocess.run([command] + args)
        except Exception as e:
            print(f"An error occurred: {e}")

    def run_kill_sequence(self):
        self.run_timer(self.kill_delay, "Kill Timer", self.kill_process)

    def kill_process(self):
        #Roblox Client: RobloxPlayerBeta.exe
        #Roblox Win store: Windows10Universal.exe
        for name in self.process_names:
            self.run_command("taskkill", ["/im", name, "/t", "/f"])  
        self.stop_program.emit()

        if self.config.get("shutdown"):
            seconds_left = 300
            self.save_settings.emit()
            self.show_shutdown_notification(seconds_left)
            self.run_timer(seconds_left, "Shutdown Timer", self.shutdown)
        else:
            #self.reset_label()
            self.finished.emit()

    def shutdown(self):
        self.run_command("shutdown", ["/s", "/t", "0"])

    def show_shutdown_notification(self, seconds_left):
        message = (
            f"PC will be shutted down in {round(seconds_left/60)} minutes if you do not cancel.\n"
            "All unsaved data will be lost!"
        )

        toast = Notification(
                     app_id="Anti-AFK",
                     title="Shutdown Warning",
                     msg=message,
                     icon=get_res("warning.png"),
                     duration="long")
        toast.show()

class Controller(QObject):
    start_kill_timer = pyqtSignal(object)
    stop_kill_timer = pyqtSignal()
    start_program = pyqtSignal(object, int)
    stop_program = pyqtSignal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self.anti_afk_thread = None
        self.process_killer_thread = None

        self.start_program.connect(self.start_anti_afk)
        self.stop_program.connect(self.stop_anti_afk)
        self.start_kill_timer.connect(self.start_process_killer)
        self.stop_kill_timer.connect(self.stop_process_killer)

    @pyqtSlot(object)
    def start_process_killer(self, config):
        self.process_killer_thread = QThread()
        self.process_killer = ProcessKiller(config)
        self.process_killer.moveToThread(self.process_killer_thread)
        self.process_killer.update_timer_label.connect(self.parent.kill_timer_label.setText)
        self.process_killer.save_settings.connect(self.parent.save_settings)
        self.process_killer.stop_program.connect(self.stop_anti_afk)
        self.process_killer.finished.connect(self.stop_process_killer)
        self.process_killer_thread.started.connect(self.parent.on_enable_kill_timer)
        self.process_killer_thread.started.connect(self.process_killer.run_kill_sequence)
        self.process_killer_thread.finished.connect(self.parent.on_disable_kill_timer)
        self.process_killer_thread.finished.connect(self.process_killer_thread.deleteLater)
        self.process_killer_thread.destroyed.connect(self.on_process_killer_destroyed)
        self.process_killer_thread.start()

    @pyqtSlot()
    def stop_process_killer(self):
        if self.process_killer_thread and self.process_killer_thread.isRunning():
            self.process_killer.stop_timer()
            self.process_killer_thread.quit()
            self.process_killer_thread.wait()
            #self.process_killer.reset_label()
            self.process_killer.deleteLater()

    @pyqtSlot(object, int)
    def start_anti_afk(self, config, winid):
        self.anti_afk_thread = QThread()
        self.anti_afk = AntiAFK(config, winid)
        self.anti_afk.moveToThread(self.anti_afk_thread)
        self.anti_afk.update_timer_label.connect(self.parent.timer_label.setText)
        self.anti_afk.show_error_message.connect(self.parent.show_error_message)
        self.anti_afk.finished.connect(self.stop_anti_afk)
        self.anti_afk_thread.started.connect(self.parent.on_enable_anti_afk)
        self.anti_afk_thread.started.connect(self.anti_afk.main)
        self.anti_afk_thread.finished.connect(self.parent.on_disable_anti_afk)
        self.anti_afk_thread.finished.connect(self.anti_afk_thread.deleteLater)
        self.anti_afk_thread.destroyed.connect(self.on_anti_afk_destroyed)
        self.anti_afk_thread.start()

    @pyqtSlot()
    def stop_anti_afk(self):
        if self.anti_afk_thread and self.anti_afk_thread.isRunning():
            self.anti_afk.stop_timer()
            self.anti_afk.cancel_activity_settings(anyway=True)
            #self.anti_afk.set_all_windows_notopmost()
            self.anti_afk_thread.quit()
            self.anti_afk_thread.wait()
            #self.anti_afk.reset_label()
            self.anti_afk.deleteLater()

    def on_anti_afk_destroyed(self):
        if self.anti_afk_thread is not None:
            self.anti_afk_thread = None

    def on_process_killer_destroyed(self):
        if self.process_killer_thread is not None:
            self.process_killer_thread = None

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        sys.excepthook = self.log_uncaught_exceptions

        self.activity_type_map = {
            'Jump': 1,
            'Camera movement': 2,
            'Jump + Walk': 3,
            'Walk': 4,
            'Random': 5
        }

        # Initialize the GUI
        self.setWindowTitle("Anti-AFK")
        self.setWindowIcon(QIcon(ICON_PATH))
        self.init_ui()
        self.centering()
        self.init_settings()

        # Initialize the variables
        self.controller = Controller(self)
        self.screensaver = Screensaver()

        self.start_button.clicked.connect(self.start_program)
        self.stop_button.clicked.connect(self.stop_program)
        self.start_kill_button.clicked.connect(self.start_kill_timer)
        self.stop_kill_button.clicked.connect(self.stop_kill_timer)
        self.open_screensaver_button.clicked.connect(lambda: self.screensaver.showFullScreen())
        self.open_screensaver_button.clicked.connect(lambda: self.set_notopmost_positioning(True))
        self.screensaver.closed.connect(lambda: self.set_notopmost_positioning(False))
        self.maximized_windows_checkbox.stateChanged.connect(self.on_maximized_windows_state_changed)

    def init_ui(self):
        self.timer_label = QLabel("Stopped")
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setFont(QFont('Arial', 18))
        self.timer_label.setStyleSheet("color: red")

        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        
        self.window_names_textbox = QLineEdit("Roblox")

        self.window_names_expand_button = QPushButton("...")
        self.window_names_expand_button.clicked.connect(
            lambda: self.open_list_dialog(
                self.window_names_textbox,
                title="Window text"
            )
        )
        self.window_names_expand_button.setMaximumWidth(25)

        self.interval_minutes_spinbox = QSpinBox()
        self.interval_minutes_spinbox.setRange(0, 59)
        self.interval_minutes_spinbox.setValue(18)

        self.interval_seconds_spinbox = QSpinBox()
        self.interval_seconds_spinbox.setRange(0, 59)
        self.interval_seconds_spinbox.setValue(0)

        self.activity_type_box = QComboBox()
        self.activity_type_box.addItems(self.activity_type_map.keys())

        self.activity_delay_spinbox = QSpinBox()
        self.activity_delay_spinbox.setRange(1, 59)
        self.activity_delay_spinbox.setValue(2)

        self.notification_checkbox = QCheckBox("Notification of windows opening")
        self.maximized_windows_checkbox = QCheckBox("Maximized windows")
        self.hide_maximized_checkbox = QCheckBox("Hide")
        self.hide_maximized_checkbox.setEnabled(False)

        self.open_screensaver_button = QPushButton("Open screensaver [Night farm]")

        self.block_input_checkbox = QCheckBox("Block input (mouse, keyboard)")
        self.transparent_window_checkbox = QCheckBox("Make target window transparent")

        margin_spacer = QSpacerItem(10, 10, QSizePolicy.Fixed, QSizePolicy.Fixed)
        small_margin_spacer = QSpacerItem(5, 5, QSizePolicy.Fixed, QSizePolicy.Fixed)

        #---Kill Options-----------------
        self.kill_timer_label = QLabel("Stopped")
        self.kill_timer_label.setAlignment(Qt.AlignCenter)
        self.kill_timer_label.setFont(QFont('Arial', 14))
        self.kill_timer_label.setStyleSheet("color: red")

        self.kill_process_names_textbox = QLineEdit(
            "RobloxPlayerBeta.exe, "
            "Windows10Universal.exe"
        )

        self.kill_process_names_expand_button = QPushButton("...")
        self.kill_process_names_expand_button.clicked.connect(
            lambda: self.open_list_dialog(
                self.kill_process_names_textbox, 
                title="Process names"
            )
        )
        self.kill_process_names_expand_button.setMaximumWidth(25)

        self.kill_delay_hours_spinbox = QSpinBox()
        self.kill_delay_hours_spinbox.setRange(0, 999)
        self.kill_delay_hours_spinbox.setValue(0)

        self.kill_delay_minutes_spinbox = QSpinBox()
        self.kill_delay_minutes_spinbox.setRange(1, 59)
        self.kill_delay_minutes_spinbox.setValue(30)

        self.shutdown_checkbox = QCheckBox("Turn off the PC")

        self.start_kill_button = QPushButton("Start")
        self.start_kill_button.setFocusPolicy(Qt.NoFocus)

        self.stop_kill_button = QPushButton("Stop")
        self.stop_kill_button.setEnabled(False)
        self.stop_kill_button.setFocusPolicy(Qt.NoFocus)

        grid_kill_buttons = QGridLayout()
        grid_kill_buttons.addWidget(self.start_kill_button, 0, 0)
        grid_kill_buttons.addWidget(self.stop_kill_button, 0, 1)

        grid_kill_options = QGridLayout()
        grid_kill_options.addWidget(self.kill_timer_label, 0, 0, 1, 5)
        grid_kill_options.addItem(small_margin_spacer, 1, 0)

        grid_kill_options.addWidget(QLabel("Process names: "), 2, 0)
        grid_kill_options.addWidget(self.kill_process_names_textbox, 2, 1, 1, 3)
        grid_kill_options.addWidget(self.kill_process_names_expand_button, 2, 4)

        grid_kill_options.addWidget(QLabel("Kill after"), 3, 0)
        grid_kill_options.addWidget(self.kill_delay_hours_spinbox, 3, 1)
        grid_kill_options.addWidget(QLabel("h"), 3, 2)
        grid_kill_options.addWidget(self.kill_delay_minutes_spinbox, 3, 3)
        grid_kill_options.addWidget(QLabel("m"), 3, 4)

        grid_kill_options.addWidget(self.shutdown_checkbox, 4, 0, 1, 4)
        grid_kill_options.addLayout(grid_kill_buttons, 5, 0, 1, 5, Qt.AlignCenter)

        self.kill_options_box = CollapsibleBox("Delayed Kill Options")
        self.kill_options_box.setContentLayout(grid_kill_options)
        #------------------------------------------------------------
        grid_main_buttons = QGridLayout()
        grid_main_buttons.addWidget(self.start_button, 0, 0)
        grid_main_buttons.addWidget(self.stop_button, 0, 1)

        grid_layout = QGridLayout()
        grid_layout.addWidget(QLabel("Window text: "), 0, 0)
        grid_layout.addWidget(self.window_names_textbox, 0, 1, 1, 3)
        grid_layout.addWidget(self.window_names_expand_button, 0, 4)

        grid_layout.addWidget(QLabel("Interval: "), 1, 0)
        grid_layout.addWidget(self.interval_minutes_spinbox, 1, 1)
        grid_layout.addWidget(QLabel("min"), 1, 2)
        grid_layout.addWidget(self.interval_seconds_spinbox, 1, 3)
        grid_layout.addWidget(QLabel("sec"), 1, 4)

        grid_layout.addWidget(QLabel("Activity type: "), 2, 0)
        grid_layout.addWidget(self.activity_type_box, 2, 1, 1, 4)

        grid_layout.addWidget(QLabel("Activity delay:"), 3, 0)
        grid_layout.addWidget(self.activity_delay_spinbox, 3, 1)
        grid_layout.addWidget(QLabel("sec"), 3, 2)

        grid_layout.addWidget(self.notification_checkbox, 4, 0, 1, 4)
        grid_layout.addWidget(self.maximized_windows_checkbox, 5, 0, 1, 2)
        grid_layout.addWidget(self.hide_maximized_checkbox, 5, 2, 1, 4)


        grid_during_activity = QGridLayout()
        label = QLabel("• During activity...")
        label.setFont(QFont('Arial', 10))
        grid_during_activity.addWidget(label, 1, 0)
        grid_during_activity.addWidget(self.block_input_checkbox, 2, 0)
        grid_during_activity.addWidget(self.transparent_window_checkbox, 3, 0)

        container_layout = QGridLayout()
        container_layout.addItem(margin_spacer, 0, 0) #left margin
        container_layout.addLayout(grid_layout, 0, 1)
        container_layout.addItem(margin_spacer, 1, 0) #spacing
        container_layout.addItem(margin_spacer, 2, 0) #left margin
        container_layout.addLayout(grid_during_activity, 2, 1)
        container_layout.addLayout(grid_main_buttons, 3, 0, 1, 2, Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.timer_label)
        layout.addSpacing(10)
        layout.addLayout(container_layout)
        layout.addWidget(self.open_screensaver_button)
        layout.addWidget(self.kill_options_box)

        for widget in (
            self.interval_minutes_spinbox,
            self.interval_seconds_spinbox,
            self.kill_delay_hours_spinbox,
            self.kill_delay_minutes_spinbox
        ):
            widget.setFixedWidth(45)

        layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        #self.setMaximumSize(self.size())

    def init_settings(self):
        self.config = ConfigManager(filename="config.json")

        self.config.set_defaults({
            "position": []
        })

        for key, hook in HOOKS.items():
            self.config.add_hooks(key, hook)

        handlers = {
            "window_text": self.window_names_textbox,
            "interval_min": self.interval_minutes_spinbox,
            "interval_sec": self.interval_seconds_spinbox,
            "activity_delay": self.activity_delay_spinbox,
            "notification": self.notification_checkbox,
            "maximized_windows": self.maximized_windows_checkbox,
            "hide_maximized_windows": self.hide_maximized_checkbox,
            "block_input": self.block_input_checkbox,
            "transparent_window": self.transparent_window_checkbox,

            "process_names": self.kill_process_names_textbox,
            "kill_delay_hours": self.kill_delay_hours_spinbox,
            "kill_delay_minutes": self.kill_delay_minutes_spinbox,
            "shutdown": self.shutdown_checkbox,

            "expanded_kill_options": self.kill_options_box
        }

        self.config.add_handlers(handlers)
        self.config.add_handler(
            "activity_type", self.activity_type_box, mapper=self.activity_type_map
        )

        self.load_settings()

    def load_settings(self):
        config_values = self.config.config
        if config_values:
            for k, v in config_values.items():
                self.config.set(k, v) #update widgets values

            pos = self.config.get("position")
            if pos:
                self.move(QPoint(*pos))

        self.on_maximized_windows_state_changed() #update checkbox

    def save_settings(self):
        point = window.pos()
        self.config.set("position", [point.x(), point.y()])
        self.config.save()

    def get_text(self, widget):
        if isinstance(widget, QLineEdit):
            return widget.text()

    def set_text(self, widget, new_text):
        if isinstance(widget, QLineEdit):
            widget.setText(new_text)

    def open_list_dialog(self, text_widget, title=""):
        self.setDisabled(True)
        icon = QIcon(get_res("list.png"))
        text = self.get_text(text_widget)

        list_dialog = ListDialog(text, title=title, parent=self)
        list_dialog.setWindowIcon(icon)

        if list_dialog.exec():
            self.set_text(text_widget, list_dialog.text_list)

        list_dialog.deleteLater()
        self.setDisabled(False)

    def popup_widget_centering(self, widget):
        position = self.pos()
        center_position = QPoint(
            int(position.x() + (self.width() // 2 - widget.width() // 2)),
            int(position.y() + (self.height() // 2 - widget.height() // 2))
        )
        widget.move(center_position)

    @pyqtSlot(bool)
    def set_notopmost_positioning(self, value):
        if hasattr(self.controller, "anti_afk"):
            self.controller.anti_afk.notopmost = value

    def log_uncaught_exceptions(self, ex_cls, ex, tb):
        self.stop_program()
        self.screensaver.close()
        exception_handler = ExceptionHandler(ex_cls, ex, tb)
        exception_handler.show_error_message.connect(self.show_unexpected_error_message)
        exception_handler.main()

    @pyqtSlot(str)
    def show_error_message(self, text):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(text)
        msg_box.exec_()

    @pyqtSlot(str, str)
    def show_unexpected_error_message(self, short_text, text):
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText(
            "An unexpected error has occured:\n"
            f"{short_text}\n"
            "Details have been saved in the crash_reports folder."
        )
        msg_box.setDetailedText(text)
        msg_box.exec_()

        #Quit after window closes
        self.save_settings()
        QCoreApplication.quit()

    @pyqtSlot()
    def on_maximized_windows_state_changed(self):
        if self.maximized_windows_checkbox.isChecked():
            self.hide_maximized_checkbox.setEnabled(True)
        else:
            self.hide_maximized_checkbox.setEnabled(False)

    @pyqtSlot()
    def start_kill_timer(self):
        self.controller.start_kill_timer.emit(self.config)

    @pyqtSlot()
    def stop_kill_timer(self):
        self.controller.stop_kill_timer.emit()

    @pyqtSlot()
    def on_disable_kill_timer(self):
        self.kill_timer_label.setText("Stopped")
        self.kill_timer_label.setStyleSheet("color: red")
        self.start_kill_button.setEnabled(True)
        self.stop_kill_button.setEnabled(False)
        for widget in (
            self.kill_delay_hours_spinbox,
            self.kill_delay_minutes_spinbox,
            self.kill_process_names_expand_button,
            self.kill_process_names_textbox
        ):
            widget.setEnabled(True)

    @pyqtSlot()
    def on_enable_kill_timer(self):
        self.kill_timer_label.setStyleSheet("color: black")
        self.start_kill_button.setEnabled(False)
        self.stop_kill_button.setEnabled(True)
        for widget in (
            self.kill_delay_hours_spinbox,
            self.kill_delay_minutes_spinbox,
            self.kill_process_names_expand_button,
            self.kill_process_names_textbox
        ):
            widget.setEnabled(False)

    def centering(self):
        screen = QDesktopWidget().screenGeometry()
        center_point = screen.center()
        self.move(center_point - self.rect().center())

    def closeEvent(self, event):
        self.stop_program()
        self.save_settings()
        event.accept()
        QCoreApplication.quit()

    @pyqtSlot()
    def on_enable_anti_afk(self):
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.timer_label.setStyleSheet("color: black")
        for widget in (
            self.window_names_textbox, 
            self.interval_minutes_spinbox, 
            self.interval_seconds_spinbox,
            self.block_input_checkbox,
            self.transparent_window_checkbox,
            self.window_names_expand_button
        ):
            widget.setEnabled(False)

    @pyqtSlot()
    def on_disable_anti_afk(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.timer_label.setText("Stopped")
        self.timer_label.setStyleSheet("color: red")
        for widget in (
            self.window_names_textbox, 
            self.interval_minutes_spinbox, 
            self.interval_seconds_spinbox,
            self.block_input_checkbox,
            self.transparent_window_checkbox,
            self.window_names_expand_button
        ):
            widget.setEnabled(True)

    @pyqtSlot()
    def start_program(self):
        self.controller.start_program.emit(self.config, int(self.winId()))

    @pyqtSlot()
    def stop_program(self):
        self.controller.stop_program.emit()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())