"""Entrypoint for OpenAdapt."""

import multiprocessing
import sys
import requests

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication

from openadapt.build_utils import redirect_stdout_stderr
from openadapt.config import config
from openadapt.custom_logger import logger
from openadapt.splash_screen import LoadingScreen


class LoadingManager(QObject):
    """Manages the loading stages and progress updates."""

    progress_updated = Signal(int, str)
    loading_complete = Signal()

    def __init__(self, splash_screen: LoadingScreen, app: QApplication) -> None:
        """Initialize the loading manager."""
        super().__init__()
        self.splash = splash_screen
        self.app = app
        self.progress_updated.connect(self._update_progress)
        self.loading_complete.connect(self._on_loading_complete)
        self.dashboard_check_attempts = 0
        self.is_ready = False
        self.dashboard_timer = None

    def _update_progress(self, value: int, message: str) -> None:
        """Update progress bar and process events."""
        if not self.is_ready:
            self.splash.update_progress(value)
            self.splash.update_status(message)
            self.app.processEvents()
            logger.debug(f"Progress: {value}% - {message}")

    def _on_loading_complete(self) -> None:
        """Handle completion of loading sequence."""
        self.is_ready = True
        if self.dashboard_timer:
            self.dashboard_timer.stop()
        QTimer.singleShot(500, self.splash.hide)
        QTimer.singleShot(600, self.app.quit)

    def check_dashboard(self) -> None:
        """Check if dashboard is responsive and handle loading completion."""
        try:
            url = f"http://localhost:{config.DASHBOARD_CLIENT_PORT}"
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                self.progress_updated.emit(100, "Ready!")
                self.loading_complete.emit()
                return
        except requests.RequestException:
            pass

    def start_dashboard_monitoring(self) -> None:
        """Start dashboard monitoring using Qt timer."""
        self.dashboard_timer = QTimer(self)
        self.dashboard_timer.timeout.connect(self.check_dashboard)
        self.dashboard_timer.start(100)  # Check every 100ms

    def start_loading_sequence(self) -> bool:
        """Execute the loading sequence with visible progress updates."""
        try:
            # Initial setup - 0%
            self.progress_updated.emit(0, "Initializing...")

            # Configuration - 20%
            self.progress_updated.emit(20, "Loading configuration...")
            from openadapt.config import print_config

            print_config()

            # Error reporting setup - 40%
            self.progress_updated.emit(40, "Configuring error reporting...")
            from openadapt.error_reporting import configure_error_reporting

            configure_error_reporting()

            # Database context - 60%
            self.progress_updated.emit(60, "Loading database context...")
            from openadapt.alembic.context_loader import load_alembic_context

            load_alembic_context()

            # System tray setup - 80%
            self.progress_updated.emit(80, "Starting system tray...")

            return True

        except Exception as e:
            logger.error(f"Loading sequence failed: {e}")
            return False


def run_tray() -> None:
    """Run the openadapt tray."""
    from openadapt.app import tray

    tray._run()


def run_openadapt() -> None:
    """Run OpenAdapt."""
    with redirect_stdout_stderr():
        try:
            app = QApplication(sys.argv)
            splash = LoadingScreen()
            splash.show()

            loading_manager = LoadingManager(splash, app)

            if not loading_manager.start_loading_sequence():
                raise Exception("Loading sequence failed")

            tray_process = multiprocessing.Process(target=run_tray, daemon=False)
            tray_process.start()

            if not tray_process.is_alive():
                raise Exception("Tray process failed to start")

            loading_manager.start_dashboard_monitoring()

            app.exec()

        except Exception as exc:
            logger.exception(exc)
            if "tray_process" in locals() and tray_process and tray_process.is_alive():
                tray_process.terminate()
            sys.exit(1)


if __name__ == "__main__":
    run_openadapt()
