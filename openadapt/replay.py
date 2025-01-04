"""Replay recorded events.

Usage:
    python -m openadapt.replay.py <strategy_name> [--timestamp=<recording_timestamp>]
"""

from time import sleep
import multiprocessing
import multiprocessing.connection
import os

from openadapt.build_utils import redirect_stdout_stderr
from openadapt.custom_logger import logger

with redirect_stdout_stderr():
    import fire

from openadapt import capture as _capture
from openadapt import utils
from openadapt.config import CAPTURE_DIR_PATH, print_config
from openadapt.db import crud
from openadapt.error_reporting import configure_error_reporting
from openadapt.models import Recording
from openadapt.strategies import BaseReplayStrategy


LOG_LEVEL = "INFO"

posthog = utils.get_posthog_instance()


@logger.catch
def replay(
    strategy_name: str,
    capture: bool = False,
    timestamp: str | None = None,
    recording: Recording = None,
    status_pipe: multiprocessing.connection.Connection | None = None,
    **kwargs: dict,
) -> bool:
    """Replay recorded events.

    Args:
        strategy_name (str): Name of the replay strategy to use.
        timestamp (str, optional): Timestamp of the recording to replay.
        recording (Recording, optional): Recording to replay.
        capture (bool, optional): Flag indicating whether to capture the replay.
        status_pipe: A connection to communicate replay status.
        kwargs: Keyword arguments to pass to strategy.

    Returns:
        bool: True if replay was successful, None otherwise.
    """
    utils.configure_logging(logger, LOG_LEVEL)
    print_config()
    configure_error_reporting()
    posthog.capture(event="replay.started", properties={"strategy_name": strategy_name})

    if status_pipe:
        # TODO: move to Strategy?
        status_pipe.send({"type": "replay.started"})

    session = crud.get_new_session(read_only=True)

    if timestamp and recording is None:
        recording = crud.get_recording(session, timestamp)
    elif recording is None:
        recording = crud.get_latest_recording(session)

    logger.debug(f"{recording=}")
    assert recording, "No recording found"

    logger.info(f"{strategy_name=}")

    strategy_class_by_name = utils.get_subclass_by_name(BaseReplayStrategy)
    if strategy_name not in strategy_class_by_name:
        strategy_names = [
            name
            for name in strategy_class_by_name.keys()
            if not name.lower().endswith("mixin")
        ]
        available_strategies = ", ".join(strategy_names)
        raise ValueError(f"Invalid {strategy_name=}; {available_strategies=}")

    strategy_class = strategy_class_by_name[strategy_name]
    logger.info(f"{strategy_class=}")

    strategy = strategy_class(recording, **kwargs)
    logger.info(f"{strategy=}")

    handler = None
    rval = True
    if capture:
        _capture.start(audio=False, camera=False)
        # TODO: handle this more robustly
        sleep(1)
        file_name = f"log-{strategy_name}-{recording.timestamp}.log"
        file_path = os.path.join(CAPTURE_DIR_PATH, file_name)
        os.makedirs(CAPTURE_DIR_PATH, exist_ok=True)
        logger.info(f"{file_path=}")
        handler = logger.add(open(file_path, "w"))
    try:
        strategy.run()
    except Exception as e:
        logger.exception(e)
        rval = False

    if status_pipe:
        status_pipe.send({"type": "replay.stopped"})
    posthog.capture(
        event="replay.stopped",
        properties={"strategy_name": strategy_name, "success": rval},
    )

    if capture:
        sleep(1)
        _capture.stop()
        logger.remove(handler)

    return rval


# Entry point
def start() -> None:
    """Starts the replay."""
    fire.Fire(replay)


if __name__ == "__main__":
    fire.Fire(replay)
