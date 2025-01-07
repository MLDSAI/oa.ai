"""Entrypoint for OpenAdapt."""

import multiprocessing
import sys

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication

from openadapt.build_utils import redirect_stdout_stderr
from openadapt.custom_logger import logger
from openadapt.splash_screen import LoadingScreen


class LoadingManager(QObject):
    """Manages the loading stages and progress updates."""

    progress_updated = Signal(int, str)
    loading_complete = Signal()

    def __init__(self, splash_screen: LoadingScreen, app: QApplication) -> None:
        """Initializes the main application entry point.

        Args:
            splash_screen: The splash screen to be displayed during startup.
            app: The main application instance.
        """
        super().__init__()
        self.splash = splash_screen
        self.app = app
        self.progress_updated.connect(self._update_progress)

    def _update_progress(self, value: int, message: str) -> None:
        """Update progress bar and process events."""
        self.splash.update_progress(value)
        self.splash.update_status(message)
        self.app.processEvents()
        logger.debug(f"Progress: {value}% - {message}")

    def start_loading_sequence(self) -> None:
        """Execute the loading sequence with visible progress updates."""
        # Initial setup - 0%
        self.progress_updated.emit(0, "Initializing...")

        # Configuration - 20%
        try:
            self.progress_updated.emit(20, "Loading configuration...")

            from openadapt.config import print_config

            print_config()
        except Exception as e:
            logger.error(f"Configuration error: {e}")
            return False

        # Error reporting setup - 40%
        try:
            self.progress_updated.emit(40, "Configuring error reporting...")

            from openadapt.error_reporting import configure_error_reporting

            configure_error_reporting()
        except Exception as e:
            logger.error(f"Error reporting setup failed: {e}")
            return False

        # Database context - 60%
        try:
            self.progress_updated.emit(60, "Loading database context...")

            from openadapt.alembic.context_loader import load_alembic_context

            load_alembic_context()
        except Exception as e:
            logger.error(f"Database context loading failed: {e}")
            return False

        # System tray setup - 80%
        try:
            self.progress_updated.emit(80, "Setting up system tray...")

            from openadapt.app import tray

            tray_instance = tray.SystemTrayIcon(app=self.app)

        except Exception as e:
            logger.error(f"System tray setup failed: {e}")
            return False

        # Final setup - 90%
        self.progress_updated.emit(90, "Finalizing setup...")

        return tray_instance


def run_openadapt() -> None:
    """Run OpenAdapt with improved progress visibility."""
    with redirect_stdout_stderr():
        try:
            app = QApplication(sys.argv)

            # Create and show splash screen
            splash = LoadingScreen()
            splash.show()

            # Initialize loading manager
            loading_manager = LoadingManager(splash, app)

            # Start loading sequence
            tray_instance = loading_manager.start_loading_sequence()
            if not tray_instance:
                raise Exception("Loading sequence failed")

            def on_dashboard_ready() -> None:
                logger.info("Dashboard ready - closing splash screen")
                loading_manager.progress_updated.emit(100, "Ready!")

                # Use QTimer for smooth transition
                QTimer.singleShot(
                    500,
                    lambda: (
                        logger.info("Hiding splash screen"),
                        splash.hide(),
                        splash.deleteLater(),
                        (
                            tray_instance.dashboard_monitor.stop()
                            if hasattr(tray_instance, "dashboard_monitor")
                            else None
                        ),
                    ),
                )

            # Connect dashboard monitor signals
            if hasattr(tray_instance, "dashboard_monitor"):

                def on_dashboard_ready_wrapper() -> None:
                    """Wrapper function that logs a debug message.

                    calls the on_dashboard_ready function.

                    Returns:
                        None
                    """
                    logger.debug("Dashboard ready wrapper called")
                    on_dashboard_ready()

                try:
                    tray_instance.dashboard_monitor.ready.connect(
                        on_dashboard_ready_wrapper, Qt.ConnectionType.AutoConnection
                    )
                    logger.debug("Signal handler connected")

                    if (
                        not hasattr(tray_instance.dashboard_monitor, "monitor_thread")
                        or not tray_instance.dashboard_monitor.monitor_thread.isRunning()  # noqa: E501
                    ):
                        logger.debug(
                            "Dashboard appears to be already ready, "
                            "calling handler directly"
                        )
                        on_dashboard_ready_wrapper()

                except Exception as e:
                    logger.error(f"Failed to connect signal: {str(e)}")

            app.exec()

        except Exception as exc:
            logger.exception(exc)
            if "splash" in locals():
                splash.hide()
            sys.exit(1)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_openadapt()
