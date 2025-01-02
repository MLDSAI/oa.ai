import multiprocessing
import atexit

if __name__ == "__main__":
    multiprocessing.freeze_support()

from openadapt.build_utils import redirect_stdout_stderr
from openadapt.error_reporting import configure_error_reporting
from openadapt.custom_logger import logger


def cleanup_multiprocessing_resources():
    """Ensure multiprocessing resources are cleaned up."""
    from multiprocessing.resource_tracker import _resource_tracker
    try:
        _resource_tracker._check_alive()  # Ensure tracker is running
        _resource_tracker._cleanup()  # Attempt cleanup
    except Exception as exc:
        logger.warning(f"Failed to cleanup multiprocessing resources: {exc}")


def run_openadapt() -> None:
    """Run OpenAdapt."""
    with redirect_stdout_stderr():
        try:
            from openadapt.alembic.context_loader import load_alembic_context
            from openadapt.app import tray
            from openadapt.config import print_config

            print_config()
            configure_error_reporting()
            load_alembic_context()
            tray._run()
        except Exception as exc:
            logger.exception(exc)


# Register resource cleanup on exit
atexit.register(cleanup_multiprocessing_resources)

if __name__ == "__main__":
    run_openadapt()
