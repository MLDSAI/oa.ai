"""Implementation of the system tray icon for OpenAdapt.

usage: `python -m openadapt.app.tray` or `poetry run app`
"""

from functools import partial
from pprint import pformat
import inspect
import multiprocessing
import os
import sys

from loguru import logger
from pyqttoast import Toast, ToastPreset, ToastIcon, ToastPosition, ToastButtonAlignment
from PySide6.QtCore import Qt, QMargins, QSize, QSocketNotifier
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QMenu, QInputDialog, QSystemTrayIcon,
    QDialog, QVBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QDialogButtonBox,
    QWidget,
)

from openadapt.app.cards import quick_record, stop_record
from openadapt.app.dashboard.run import cleanup as cleanup_dashboard
from openadapt.app.dashboard.run import run as run_dashboard
from openadapt.app.main import FPATH, start
from openadapt.build_utils import is_running_from_executable
from openadapt.db.crud import get_all_recordings
from openadapt.extensions.thread import Thread as oaThread
from openadapt.models import Recording
from openadapt.replay import replay
from openadapt.visualize import main as visualize
from openadapt.strategies.base import BaseReplayStrategy
import openadapt.strategies  # Import this to ensure all strategies are registered


ICON_PATH = os.path.join(FPATH, "assets", "logo.png")


class SystemTrayIcon:
    """System tray icon for OpenAdapt."""

    recording = False
    app_thread = None
    dashboard_thread = None

    # the actions need to be separated by type
    # or else they will be triggered multiple times
    recording_actions = {"visualize": [], "replay": []}

    def __init__(self) -> None:
        """Initialize the system tray icon."""
        self.app = QApplication([])

        if sys.platform == "darwin":
            # hide Dock icon while allowing focus on dialogs
            # (must come after QApplication())
            from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory,
            )

        self.app.setQuitOnLastWindowClosed(False)

        # currently required for pyqttoast
        # TODO: remove once https://github.com/niklashenning/pyqt-toast/issues/9
        # is addressed
        self.main_window = QMainWindow()
        self.main_window.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        )
        self.main_window.resize(1, 1)  # Minimal size
        self.main_window.move(0, 0)

        self.icon = QIcon(ICON_PATH)

        self.tray = QSystemTrayIcon(self.icon, self.app)
        self.tray.setIcon(self.icon)
        self.tray.setVisible(True)

        self.menu = QMenu()

        self.record_action = QAction("Record")
        self.record_action.triggered.connect(self.on_record_action)
        self.menu.addAction(self.record_action)

        self.visualize_menu = self.menu.addMenu("Visualize")
        self.replay_menu = self.menu.addMenu("Replay")
        self.update_menus()

        # TODO: Remove this action once dashboard is integrated
        self.app_action = QAction("Show App")
        self.app_action.triggered.connect(self.show_app)
        self.menu.addAction(self.app_action)

        self.dashboard_action = QAction("Launch Dashboard")
        self.dashboard_action.triggered.connect(self.launch_dashboard)
        self.menu.addAction(self.dashboard_action)

        self.quit = QAction("Quit")

        def _quit() -> None:
            """Quit the application."""
            if self.dashboard_thread is not None:
                cleanup_dashboard(self.dashboard_thread._return)
            self.app.quit()

        self.quit.triggered.connect(_quit)
        self.menu.addAction(self.quit)

        self.tray.setContextMenu(self.menu)

        self.visualize_proc = None

        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        # Set up QSocketNotifier to monitor the read end of the pipe
        self.notifier = QSocketNotifier(
            self.parent_conn.fileno(), QSocketNotifier.Read,
        )
        self.notifier.activated.connect(lambda: self.handle_recording_signal(
            self.notifier, self.parent_conn,
        ))

        self.show_toast("OpenAdapt is running in the background")


    def handle_recording_signal(
        self,
        notifier: QSocketNotifier,
        conn: multiprocessing.connection.Connection,
    ) -> None:
        """Callback function to handle the signal from the recording process."""
        signal = conn.recv()
        logger.info(f"Received signal: {signal}")

        if signal["type"] == "start":
            self.show_toast("Recording started.")
        elif signal["type"] == "stop":
            self.show_toast("Recording stopped.")

        # Refresh the menus regardless of the type of signal
        self.update_menus()

    def update_menus(self) -> None:
        self.populate_menu(self.visualize_menu, self._visualize, "visualize")
        self.populate_menu(self.replay_menu, self._replay, "replay")

    def on_record_action(self) -> None:
        """Handle click on Record / Stop Recording menu item."""
        if self.recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        task_description, ok = QInputDialog.getText(
            None,
            "New Recording",
            "Briefly describe the task to be recorded:",
        )
        logger.info(f"{task_description=} {ok=}")
        if not ok:
            return
        self.recording = True
        self.record_action.setText("Stop Recording")
        try:
            quick_record(task_description, on_ready=self.child_conn)
        except KeyboardInterrupt:
            self.stop_recording()

    def stop_recording(self):
        self.show_toast("Stopping recording...")
        stop_record()
        self.recording = False
        self.record_action.setText("Record")

    def _visualize(self, recording: Recording) -> None:
        """Visualize a recording.

        Args:
            recording (Recording): The recording to visualize.
        """
        self.show_toast("Starting visualization...")
        try:
            if self.visualize_proc is not None:
                self.visualize_proc.kill()
            self.visualize_proc = multiprocessing.Process(
                target=visualize, args=(recording,)
            )
            self.visualize_proc.start()

        except Exception as e:
            logger.error(e)
            self.show_toast("Visualization failed.")

    def _replay(self, recording: Recording) -> None:
        """Dynamically select and configure a replay strategy."""
        dialog = QDialog()
        dialog.setWindowTitle("Configure Replay Strategy")
        layout = QVBoxLayout(dialog)

        # Strategy selection
        label = QLabel("Select Replay Strategy:")
        combo_box = QComboBox()
        strategies = {
            cls.__name__: cls
            for cls in BaseReplayStrategy.__subclasses__()
            if not cls.__name__.endswith("Mixin") and
            cls.__name__ != "DemoReplayStrategy"
        }
        strategy_names = list(strategies.keys())
        logger.info(f"{strategy_names=}")
        combo_box.addItems(strategy_names)

        # Set default strategy
        default_strategy = "VisualReplayStrategy"
        default_index = combo_box.findText(default_strategy)
        if default_index != -1:  # Ensure the strategy is found in the list
            combo_box.setCurrentIndex(default_index)
        else:
            logger.warning(f"{default_strategy=} not found")

        strategy_label = QLabel()
        layout.addWidget(label)
        layout.addWidget(combo_box)
        layout.addWidget(strategy_label)

        # Container for argument widgets
        args_container = QWidget()
        args_layout = QVBoxLayout(args_container)
        args_container.setLayout(args_layout)
        layout.addWidget(args_container)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        def update_args_inputs():
            # Clear existing widgets
            while args_layout.count():
                widget_to_remove = args_layout.takeAt(0).widget()
                if widget_to_remove is not None:
                    widget_to_remove.setParent(None)
                    widget_to_remove.deleteLater()


            strategy_class = strategies[combo_box.currentText()]

            strategy_label.setText(strategy_class.__doc__)

            sig = inspect.signature(strategy_class.__init__)
            for param in sig.parameters.values():
                if param.name != "self" and param.name != "recording":
                    arg_label = QLabel(f"{param.name.replace('_', ' ').capitalize()}:")

                    # Determine if the parameter is a boolean
                    if param.annotation is bool:
                        # Create a combobox for boolean values
                        arg_input = QComboBox()
                        arg_input.addItems(["True", "False"])
                        # Set default value if exists
                        if param.default is not inspect.Parameter.empty:
                            default_index = 0 if param.default else 1
                            arg_input.setCurrentIndex(default_index)
                    else:
                        # Create a line edit for non-boolean values
                        arg_input = QLineEdit()
                        annotation_str = self.format_annotation(param.annotation)
                        arg_input.setPlaceholderText(annotation_str or "str")
                        # Set default text if there is a default value
                        if param.default is not inspect.Parameter.empty:
                            arg_input.setText(str(param.default))

                    args_layout.addWidget(arg_label)
                    args_layout.addWidget(arg_input)

            args_container.adjustSize()
            dialog.adjustSize()
            dialog.setMinimumSize(0, 0)  # Reset the minimum size to allow shrinking

        combo_box.currentIndexChanged.connect(update_args_inputs)
        update_args_inputs()  # Initial update

        # Show dialog and process the result
        if dialog.exec() == QDialog.Accepted:
            selected_strategy = strategies[combo_box.currentText()]
            sig = inspect.signature(selected_strategy.__init__)
            kwargs = {}
            index = 0
            for param_name, param in sig.parameters.items():
                if param_name in ["self", "recording"]:
                    continue
                widget = args_layout.itemAt(index * 2 + 1).widget()
                if param.annotation is bool:
                    # For boolean, get True/False from the combobox selection
                    value = widget.currentText() == "True"
                else:
                    # Convert the text to the annotated type if possible
                    text = widget.text()
                    try:
                        # Cast text to the parameter's annotated type
                        value = (
                            param.annotation(text)
                            if param.annotation != inspect.Parameter.empty
                            else text
                        )
                    except ValueError as exc:
                        logger.warning(f"{exc=}")
                        value = text
                kwargs[param_name] = value
                index += 1
            kwargs["recording"] = recording
            logger.info(f"kwargs=\n{pformat(kwargs)}")

            self.show_toast("Starting replay with selected strategy...")
            rthread = oaThread(
                target=replay,
                args=(selected_strategy, False, None, recording, None),
                kwargs=kwargs,
                daemon=True,
            )
            rthread.start()
            if rthread.join():
                self.show_toast("Replay finished.")
            else:
                self.show_toast("Replay failed.")

    def format_annotation(self, annotation):
        """Format annotation to a readable string."""
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        elif isinstance(annotation, type):
            return annotation.__name__  # Handle direct type references
        else:
            return str(annotation)  # Handle complex types like Union

    def populate_menu(self, menu: QMenu, action: QAction, action_type: str) -> None:
        """Populate a menu.

        Args:
            menu (QMenu): The menu to populate.
            action (QAction): The action to perform when the menu item is clicked.
            action_type (str): The type of action to perform ["visualize", "replay"]
        """
        recordings = get_all_recordings()
        if len(recordings) == len((self.recording_actions[action_type])):
            return
        else:
            self.recording_actions[action_type] = []
        for idx, recording in enumerate(recordings):
            self.recording_actions[action_type].append(
                QAction(f"{recording.task_description}")
            )
            self.recording_actions[action_type][idx].triggered.connect(
                partial(action, recording)
            )
            menu.addAction(self.recording_actions[action_type][idx])

    def show_app(self) -> None:
        """Show the main application window."""
        if self.app_thread is None or not self.app_thread.is_alive():
            self.app_thread = oaThread(target=start, daemon=True, args=(True,))
            self.app_thread.start()

    def launch_dashboard(self) -> None:
        """Launch the web dashboard."""
        if self.dashboard_thread:
            if is_running_from_executable():
                return
            cleanup_dashboard(self.dashboard_thread._return)
            self.dashboard_thread.join()
        self.dashboard_thread = run_dashboard()
        self.dashboard_thread.start()
        self.dashboard_action.setText("Reload dashboard")

    def run(self) -> None:
        """Run the system tray icon."""
        self.app.exec()

    def show_toast(
        self, 
        message: str, 
        title: str = "OpenAdapt",
        duration: int = 10000,
        icon_path: str = ICON_PATH,
        show_icon: bool = True,
        icon_size: QSize = QSize(32, 32),
        position: ToastPosition = ToastPosition.TOP_RIGHT,
        maximum_on_screen: int = 3,
        spacing: int = 10,
        offset_x: int = 20,
        offset_y: int = 45,
        always_on_main_screen: bool = False,
        show_duration_bar: bool = True,
        preset: ToastPreset = ToastPreset.INFORMATION,
        title_font: QFont = QFont("Arial", 20, QFont.Weight.Bold),
        text_font: QFont = QFont("Arial", 15),
        close_button_alignment: ToastButtonAlignment = ToastButtonAlignment.TOP,
        show_close_button: bool = True,
        fade_in_duration: int = 250,
        fade_out_duration: int = 250,
        reset_duration_on_hover: bool = True,
        border_radius: int = 0,
        background_color: QColor = QColor('#E7F4F9'),
        title_color: QColor = QColor('#000000'),
        text_color: QColor = QColor('#5C5C5C'),
        duration_bar_color: QColor = QColor('#5C5C5C'),
        icon_color: QColor = QColor('#5C5C5C'),
        icon_separator_color: QColor = QColor('#D9D9D9'),
        close_button_icon_color: QColor = QColor('#000000'),
        minimum_width: int = 100,
        maximum_width: int = 350,
        minimum_height: int = 50,
        maximum_height: int = 120,
        fixed_size: QSize = None,
        close_button_icon: QIcon = ToastIcon.CLOSE,
        close_button_icon_size: QSize = QSize(10, 10),
        close_button_size: QSize = QSize(24, 24),
        stay_on_top: bool = True,
        text_section_spacing: int = 8,
        margins: QMargins = QMargins(20, 18, 10, 18),
        icon_margins: QMargins = QMargins(0, 0, 15, 0),
        icon_section_margins: QMargins = QMargins(0, 0, 15, 0),
        text_section_margins: QMargins = QMargins(0, 0, 15, 0),
        close_button_margins: QMargins = QMargins(0, -8, 0, -8),
    ):
        """Show a configurable toast message.

        Args:
            message (str): The main message of the toast.
            title (str): The title of the toast. Defaults to 'OpenAdapt'.
            duration (int): Duration in milliseconds before the toast hides.
                Set to 0 for persistent. Defaults to 10000.
            icon_path (str): Path to the icon image file. Defaults to
                'path/to/icon.png'.
            show_icon (bool): Whether to show the icon. Defaults to True.
            icon_size (QSize): Size of the icon. Defaults to QSize(32, 32).
            position (ToastPosition): Screen position of the toast. Defaults to
                ToastPosition.BOTTOM_RIGHT.
            maximum_on_screen (int): Maximum number of toasts displayed at
                once. Defaults to 3.
            spacing (int): Vertical spacing between toasts. Defaults to 10.
            offset_x (int): Horizontal offset of the toast. Defaults to 20.
            offset_y (int): Vertical offset of the toast. Defaults to 45.
            always_on_main_screen (bool): Whether the toast should always be
                displayed on the main screen. Defaults to False.
            show_duration_bar (bool): Whether to show the duration bar.
                Defaults to True.
            preset (ToastPreset): Preset style to apply to the toast. None
                means no preset is applied.
            title_font (QFont): Font settings for the title. Defaults to bold
                Arial size 20.
            text_font (QFont): Font settings for the text. Defaults to Arial size 15.
            close_button_alignment (ToastButtonAlignment): Alignment of the
                close button. Defaults to ToastButtonAlignment.TOP.
            show_close_button (bool): Whether to show the close button.
                Defaults to True.
            fade_in_duration (int): Duration of the fade-in animation in
                milliseconds. Defaults to 250.
            fade_out_duration (int): Duration of the fade-out animation in
                milliseconds. Defaults to 250.
            reset_duration_on_hover (bool): Whether the duration resets on
                mouse hover. Defaults to True.
            border_radius (int): Radius of the toast's border corners. Defaults to 0.
            background_color (QColor): Background color of the toast. Defaults
                to #E7F4F9.
            title_color (QColor): Color of the title text. Defaults to #000000.
            text_color (QColor): Color of the main text. Defaults to #5C5C5C.
            duration_bar_color (QColor): Color of the duration bar. Defaults to #5C5C5C.
            icon_color (QColor): Color of the icon. Defaults to #5C5C5C.
            icon_separator_color (QColor): Color of the icon separator.
                Defaults to #D9D9D9.
            close_button_icon_color (QColor): Color of the close button icon.
                Defaults to #000000.
            minimum_width (int): Minimum width of the toast. Defaults to 100.
            maximum_width (int): Maximum width of the toast. Defaults to 350.
            minimum_height (int): Minimum height of the toast. Defaults to 50.
            maximum_height (int): Maximum height of the toast. Defaults to 120.
            fixed_size (QSize): Fixed size of the toast. None means not fixed.
                Defaults to None.
            close_button_icon (QIcon): Icon of the close button. Defaults to
                ToastIcon.CLOSE.
            close_button_icon_size (QSize): Size of the close button icon.
                Defaults to QSize(10, 10).
            close_button_size (QSize): Size of the close button. Defaults to
                QSize(24, 24).
            stay_on_top (bool): Whether the toast stays on top even when other
                windows are focused. Defaults to True.
            text_section_spacing (int): Vertical spacing between the title and
                the text. Defaults to 8.
            margins (QMargins): Margins around the whole toast content.
                Defaults to QMargins(20, 18, 10, 18).
            icon_margins (QMargins): Margins around the icon. Defaults to
                QMargins(0, 0, 15, 0).
            icon_section_margins (QMargins): Margins around the icon section.
                Defaults to QMargins(0, 0, 15, 0).
            text_section_margins (QMargins): Margins around the text section.
                Defaults to QMargins(0, 0, 15, 0).
            close_button_margins (QMargins): Margins around the close button.
                Defaults to QMargins(0, -8, 0, -8).

        """
        toast = Toast(self.main_window)
        toast.setDuration(duration)
        toast.setTitle(title)
        toast.setText(message)

        # Apply the preset, if any, which sets various properties
        if preset:
            toast.applyPreset(preset)

        # Only set these if no preset has been applied
        if not preset:
            toast.setBackgroundColor(background_color)
            toast.setCloseButtonIconColor(close_button_icon_color)
            toast.setTitleColor(title_color)
            toast.setTextColor(text_color)
            toast.setDurationBarColor(duration_bar_color)
            toast.setIconColor(icon_color)
            toast.setIconSeparatorColor(icon_separator_color)
            toast.setShowDurationBar(show_duration_bar)

        # Font settings are typically safe to apply regardless of preset
        toast.setTitleFont(title_font)
        toast.setTextFont(text_font)

        # Icon setup
        if show_icon:
            toast.setIcon(QPixmap(icon_path))
            toast.setShowIcon(True)

        # Size settings
        toast.setIconSize(icon_size)
        if fixed_size:
            toast.setFixedSize(fixed_size)
        else:
            toast.setMinimumWidth(minimum_width)
            toast.setMaximumWidth(maximum_width)
            toast.setMinimumHeight(minimum_height)
            toast.setMaximumHeight(maximum_height)

        # Other UI configurations
        toast.setPosition(position)
        toast.setMaximumOnScreen(maximum_on_screen)
        toast.setSpacing(spacing)
        toast.setOffset(offset_x, offset_y)
        toast.setAlwaysOnMainScreen(always_on_main_screen)
        toast.setCloseButtonAlignment(close_button_alignment)
        toast.setShowCloseButton(show_close_button)
        toast.setFadeInDuration(fade_in_duration)
        toast.setFadeOutDuration(fade_out_duration)
        toast.setResetDurationOnHover(reset_duration_on_hover)
        toast.setBorderRadius(border_radius)

        # Close button customization
        toast.setCloseButtonIcon(close_button_icon)
        toast.setCloseButtonIconSize(close_button_icon_size)
        toast.setCloseButtonSize(close_button_size)
        toast.setStayOnTop(stay_on_top)

        # Spacing and margin settings
        toast.setTextSectionSpacing(text_section_spacing)
        toast.setMargins(margins)
        toast.setIconMargins(icon_margins)
        toast.setIconSectionMargins(icon_section_margins)
        toast.setTextSectionMargins(text_section_margins)
        toast.setCloseButtonMargins(close_button_margins)

        # Display the toast
        toast.show()

def _run() -> None:
    tray = SystemTrayIcon()
    tray.run()


if __name__ == "__main__":
    _run()
