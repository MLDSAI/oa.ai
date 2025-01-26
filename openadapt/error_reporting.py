"""Module for error reporting logic."""

from typing import Any

from loguru import logger

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMessageBox, QPushButton
import git
import sentry_sdk
import webbrowser

from openadapt.build_utils import is_running_from_executable
from openadapt.config import PARENT_DIR_PATH, config


def configure_error_reporting() -> None:
    """Configure error reporting."""
    logger.info(f"{config.ERROR_REPORTING_ENABLED=}")
    if not config.ERROR_REPORTING_ENABLED:
        return

    if is_running_from_executable():
        is_reporting_branch = True
    else:
        active_branch_name = git.Repo(PARENT_DIR_PATH).active_branch.name
        logger.info(f"{active_branch_name=}")
        is_reporting_branch = active_branch_name == config.ERROR_REPORTING_BRANCH
        logger.info(f"{is_reporting_branch=}")

    if is_reporting_branch:
        sentry_sdk.init(
            dsn=config.ERROR_REPORTING_DSN,
            traces_sample_rate=1.0,
            before_send=before_send_event,
            ignore_errors=[KeyboardInterrupt],
        )


def show_alert() -> None:
    """Show an alert to the user."""
    # TODO: move to config
    from openadapt.app.tray import ICON_PATH

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowIcon(QIcon(ICON_PATH))
    msg.setText(
        """
        An error has occurred. The development team has been notified.
        Please join the discord server to get help or send an email to
        help@openadapt.ai
        """
    )
    discord_button = QPushButton("Join the discord server")
    discord_button.clicked.connect(
        lambda: webbrowser.open("https://discord.gg/yF527cQbDG")
    )
    msg.addButton(discord_button, QMessageBox.ActionRole)
    msg.addButton(QMessageBox.Ok)
    msg.exec()


def before_send_event(event: Any, hint: Any) -> Any:
    """Handle the event before sending it to Sentry."""
    try:
        show_alert()
    except Exception:
        pass
    return event
