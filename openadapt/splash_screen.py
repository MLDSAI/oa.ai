"""Modern minimal splash screen for OpenAdapt with improved responsiveness."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar, QSplashScreen


class LoadingScreen(QSplashScreen):
    """A minimal splash screen for."""

    def __init__(self) -> None:
        """Initialize the loading screen."""
        pixmap = QPixmap(400, 100)
        pixmap.fill(QColor(0, 0, 0, 180))

        super().__init__(pixmap)

        self.title_label = QLabel("OpenAdapt", self)
        self.title_label.setGeometry(0, 15, 400, 30)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #FFFFFF;
                font-family: Arial;
                font-size: 20px;
                font-weight: bold;
            }
        """
        )

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setGeometry(50, 55, 300, 6)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.status_label = QLabel(self)
        self.status_label.setGeometry(0, 70, 400, 20)
        self.status_label.setAlignment(Qt.AlignCenter)

        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)

        self.progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: none;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196F3, stop:1 #64B5F6);
                border-radius: 3px;
            }
        """
        )

        self.status_label.setStyleSheet(
            """
            QLabel {
                color: #CCCCCC;
                font-size: 11px;
                font-family: Arial;
            }
        """
        )

    def update_status(self, message: str) -> None:
        """Update the status message displayed on the splash screen."""
        self.status_label.setText(message)
        self.repaint()
        QApplication.processEvents()

    def update_progress(self, value: int) -> None:
        """Update progress value with immediate visual feedback."""
        value = max(0, min(100, value))
        # for smooth progress updates
        QTimer.singleShot(0, lambda: self._do_update(value))

    def _do_update(self, value: int) -> None:
        """Internal method to perform the actual progress update."""
        self.progress_bar.setValue(value)
        self.repaint()
        QApplication.processEvents()

    def show(self) -> None:
        """Show the splash screen."""
        super().show()
        self.raise_()
        QApplication.processEvents()
