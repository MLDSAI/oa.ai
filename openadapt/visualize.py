"""Implements visualization utilities for OpenAdapt."""

from pprint import pformat
from threading import Timer
import html
import os
import string

from bokeh.io import output_file, show
from bokeh.layouts import layout, row
from bokeh.models.widgets import Div

from openadapt.build_utils import redirect_stdout_stderr
from openadapt.custom_logger import logger

with redirect_stdout_stderr():
    from tqdm import tqdm
    import fire

from openadapt import video
from openadapt.config import RECORDING_DIR_PATH, config
from openadapt.db import crud
from openadapt.events import get_events
from openadapt.models import Recording
from openadapt.plotting import display_event
from openadapt.utils import (
    EMPTY,
    compute_diff,
    configure_logging,
    evenly_spaced,
    get_posthog_instance,
    image2utf8,
    row2dict,
    rows2dicts,
    truncate_html,
    take_screenshots,
)

SCRUB = config.SCRUB_ENABLED
posthog = get_posthog_instance()

LOG_LEVEL = "INFO"
MAX_EVENTS = None
MAX_TABLE_CHILDREN = 5
MAX_TABLE_STR_LEN = 1024
PROCESS_EVENTS = True
IMG_WIDTH_PCT = 60


def recursive_len(lst: list, key: str) -> int:
    """Calculate the recursive length of a list based on a key.

    Args:
        lst (list): The list to calculate the length of.
        key: The key to access the sublists.

    Returns:
        int: The recursive length of the list.
    """
    try:
        _len = len(lst)
    except TypeError:
        return 0
    for obj in lst:
        try:
            _len += recursive_len(obj.get(key), key)
        except AttributeError:
            continue
    return _len


def format_key(key: str, value: list) -> str:
    """Format a key and value for display.

    Args:
        key: The key to format.
        value: The value associated with the key.

    Returns:
        str: The formatted key and value.
    """
    if isinstance(value, list):
        return f"{key} ({len(value)}; {recursive_len(value, key)})"
    else:
        return key


def indicate_missing(some: list, every: list, indicator: str) -> list:
    """Indicate missing elements in a list.

    Args:
        some (list): The list with potentially missing elements.
        every (list): The reference list with all elements.
        indicator (str): The indicator to use for missing elements.

    Returns:
        list: The list with indicators for missing elements.
    """
    rval = []
    some_idx = 0
    every_idx = 0
    while some_idx < len(some):
        skipped = False
        while some[some_idx] != every[every_idx]:
            every_idx += 1
            skipped = True
        if skipped:
            rval.append(indicator)
        rval.append(some[some_idx])
        some_idx += 1
        every_idx += 1
    return rval


def dict2html(
    obj: dict,
    max_children: int = MAX_TABLE_CHILDREN,
    max_len: int = MAX_TABLE_STR_LEN,
) -> str:
    """Convert a dictionary to an HTML representation.

    Args:
        obj (dict): The dictionary to convert.
        max_children (int): The maximum number of child elements to display in a table.
        max_len (int): The maximum length of a string value in the HTML representation.

    Returns:
        str: The HTML representation of the dictionary.
    """
    if isinstance(obj, list):
        children = [dict2html(value, max_children) for value in obj]
        if max_children is not None and len(children) > max_children:
            all_children = children
            children = evenly_spaced(children, max_children)
            children = indicate_missing(children, all_children, "...")
        html_str = "\n".join(children)
    elif isinstance(obj, dict):
        rows_html = "\n".join(
            [
                f"""
                <tr>
                    <th>{format_key(key, value)}</th>
                    <td>{dict2html(value, max_children)}</td>
                </tr>
            """
                for key, value in obj.items()
                if value not in EMPTY
            ]
        )
        html_str = f"<table>{rows_html}</table>"
    else:
        html_str = html.escape(str(obj))
        html_str = truncate_html(html_str, max_len)
    return html_str


@logger.catch
def main(
    recording: Recording = None,
    recording_id: int = None,
    diff_video: bool = False,
    cleanup: bool = True,
    browser: str = None,
) -> bool:
    """Visualize a recording.

    Args:
        recording (Recording, optional): The recording to visualize.
        recording_id (int, optional): The ID of the recording to visualize.
        diff_video (bool): Whether to diff Screenshots against video frames.
        cleanup (bool): Whether to remove the HTML file after it is displayed.
        browser (str, optional): Command to open the browser executable.

    Returns:
        bool: True if visualization was successful, None otherwise.
    """
    configure_logging(logger, LOG_LEVEL)

    assert not all([recording, recording_id]), "Only one may be specified."

    posthog.capture(
        event="visualize.started", properties={"recording_id": recording_id}
    )

    session = crud.get_new_session(read_only=True)

    if recording_id:
        recording = crud.get_recording_by_id(session, recording_id)
    elif recording is None:
        recording = crud.get_latest_recording(session)

    if recording is None:
        logger.error("No recording found")
        return False

    if SCRUB:
        from openadapt.privacy.providers.presidio import PresidioScrubbingProvider

        scrub = PresidioScrubbingProvider()
        scrub.scrub_text(recording.task_description)
    logger.info(f"{recording=}")
    logger.info(f"{diff_video=}")

    session = crud.get_new_session(read_only=True)
    audio_info = row2dict(crud.get_audio_info(session, recording))
    if audio_info:
        del audio_info["flac_data"]
    # TODO XXX: display audio_info

    if diff_video:
        assert recording.config[
            "RECORD_VIDEO"
        ], "Can't diff video against images because video was not saved."
        assert recording.config[
            "RECORD_IMAGES"
        ], "Can't diff video against images because images were not saved."

    meta = {}
    action_events = get_events(session, recording, process=PROCESS_EVENTS, meta=meta)
    event_dicts = rows2dicts(action_events)

    if SCRUB:
        event_dicts = scrub.scrub_list_dicts(event_dicts)
    logger.info(f"event_dicts=\n{pformat(event_dicts)}")

    recording_dict = row2dict(recording)
    if SCRUB:
        recording_dict = scrub.scrub_dict(recording_dict)

    CSS = string.Template(
        """
        table {
            outline: 1px solid black;
        }
        table th {
            vertical-align: top;
        }
        .screenshot img {
            display: none;
            width: ${IMG_WIDTH_PCT}vw;
        }
        .screenshot img:nth-child(1) {
            display: block;
        }

        .screenshot:hover img:nth-child(1) {
            display: none;
        }
        .screenshot:hover img:nth-child(2) {
            display: block;
        }
        .screenshot:hover img:nth-child(3) {
            display: none;
        }

        .screenshot:active img:nth-child(1) {
            display: none;
        }
        .screenshot:active img:nth-child(2) {
            display: none;
        }
        .screenshot:active img:nth-child(3) {
            display: block;
        }
    """
    ).substitute(
        IMG_WIDTH_PCT=IMG_WIDTH_PCT,
    )

    rows = [
        row(
            Div(
                text=f"<style>{CSS}</style>",
            ),
        ),
        row(
            Div(
                text=f"{dict2html(recording_dict)}",
            ),
        ),
        row(
            Div(
                text=f"{dict2html(meta)}",
                width_policy="max",
            ),
        ),
    ]
    logger.info(f"{len(action_events)=}")

    if diff_video:
        video_file_path = video.get_video_file_path(recording.timestamp)
        timestamps = [
            action_event.screenshot.timestamp - recording.video_start_time
            for action_event in action_events
        ]
        frames = video.extract_frames(video_file_path, timestamps)

    num_events = (
        min(MAX_EVENTS, len(action_events))
        if MAX_EVENTS is not None
        else len(action_events)
    )
    with redirect_stdout_stderr():
        with tqdm(
            total=num_events,
            desc="Preparing HTML",
            unit="event",
            colour="green",
            dynamic_ncols=True,
        ) as progress:
            for idx, action_event in enumerate(action_events):
                if idx == MAX_EVENTS:
                    break

                try:
                    image = display_event(action_event)
                except TypeError as exc:
                    # https://github.com/moses-palmer/pynput/issues/481
                    logger.warning(exc)
                    continue

                if image:
                    if diff_video:
                        frame_image = frames[idx]
                        diff_image = compute_diff(
                            frame_image, action_event.screenshot.image
                        )

                        # TODO: rename
                        diff = frame_image
                        mask = diff_image
                    else:
                        diff = display_event(action_event, diff=True)
                        mask = action_event.screenshot.diff_mask

                    if SCRUB:
                        image = scrub.scrub_image(image)
                        diff = scrub.scrub_image(diff)
                        mask = scrub.scrub_image(mask)

                    image_utf8 = image2utf8(image)
                    diff_utf8 = image2utf8(diff)
                    mask_utf8 = image2utf8(mask)
                    width, height = image.size
                else:
                    # TODO: display a placeholder image
                    image_utf8 = ""
                    diff_utf8 = ""
                    mask_utf8 = ""
                    width = 0
                    height = 1

                action_event_dict = row2dict(action_event)
                window_event_dict = row2dict(action_event.window_event)
                browser_event_dict = row2dict(action_event.browser_event)

                if SCRUB:
                    action_event_dict = scrub.scrub_dict(action_event_dict)
                    window_event_dict = scrub.scrub_dict(window_event_dict)
                    browser_event_dict = scrub.scrub_dict(browser_event_dict)

                rows.append(
                    [
                        row(
                            Div(
                                text=f"""
                                <div class="screenshot">
                                    <img
                                        src="{image_utf8}"
                                        style="
                                            aspect-ratio: {width}/{height};
                                        "
                                    >
                                    <img
                                        src="{diff_utf8}"
                                        style="
                                            aspect-ratio: {width}/{height};
                                        "
                                    >
                                    <img
                                        src="{mask_utf8}"
                                        style="
                                            aspect-ratio: {width}/{height};
                                        "
                                    >
                                </div>
                                <table>
                                    {dict2html(window_event_dict , None)}
                                </table>
                                <table>
                                    {dict2html(browser_event_dict , None)}
                                </table>
                            """,
                            ),
                            Div(
                                text=f"""
                                <table>
                                    {dict2html(action_event_dict)}
                                </table>
                            """
                            ),
                        ),
                    ]
                )

                progress.update()

            progress.close()

    # Visualize BrowserEvents
    rows.append([row(Div(text="<h2>Browser Events</h2>"))])
    browser_events = crud.get_browser_events(session, recording)
    with redirect_stdout_stderr():
        with tqdm(
            total=len(browser_events),
            desc="Preparing HTML (browser events)",
            unit="event",
            colour="green",
            dynamic_ncols=True,
        ) as progress:
            for idx, browser_event in enumerate(browser_events):
                browser_event_dict = row2dict(browser_event)
                rows.append(
                    [
                        row(
                            Div(
                                text=f"""
                                <table>
                                    {dict2html(browser_event_dict)}
                                </table>
                            """
                            ),
                        ),
                    ]
                )

                progress.update()

            progress.close()

    # Display screenshots from all monitors
    screenshots = take_screenshots()
    for idx, screenshot in enumerate(screenshots):
        screenshot_utf8 = image2utf8(screenshot)
        width, height = screenshot.size
        rows.append(
            row(
                Div(
                    text=f"""
                    <div class="screenshot">
                        <img
                            src="{screenshot_utf8}"
                            style="
                                aspect-ratio: {width}/{height};
                            "
                        >
                    </div>
                """,
                ),
            )
        )

    title = f"recording-{recording.id}"

    fname_out = RECORDING_DIR_PATH / f"recording-{recording.id}.html"
    logger.info(f"{fname_out=}")
    os.makedirs(RECORDING_DIR_PATH, exist_ok=True)
    output_file(fname_out, title=title)

    result = show(layout(rows))  # noqa: F841

    if browser:
        import subprocess

        logger.info(f"Opening browser with command: {browser}")
        subprocess.run([browser, f"file://{fname_out}"], check=True)

    def _cleanup() -> None:
        os.remove(fname_out)
        removed = not os.path.exists(fname_out)
        logger.info(f"{removed=}")

    if cleanup:
        Timer(1, _cleanup).start()
    posthog.capture(
        event="visualize.completed", properties={"recording_id": recording.id}
    )
    return True


if __name__ == "__main__":
    fire.Fire(main)
