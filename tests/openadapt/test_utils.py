"""Test openadapt.utils."""

from unittest.mock import patch

from openadapt import utils
from openadapt.config import config


def test_get_scale_ratios() -> None:
    """Tests utils.get_scale_ratios."""
    # TODO: pass in action event
    width, height = utils.get_scale_ratios()

    assert isinstance(
        width, (int, float)
    ), f"Expected width to be int or float, got {type(width).__name__}"
    assert isinstance(
        height, (int, float)
    ), f"Expected height to be int or float, got {type(height).__name__}"


def test_posthog_capture() -> None:
    """Tests utils.get_posthog_instance."""
    with patch("posthog.Posthog.capture") as mock_capture:
        with patch("importlib.metadata.version") as mock_version:
            mock_version.return_value = "1.0.0"
            posthog = utils.get_posthog_instance()
            posthog.capture(event="test_event", properties={"test_prop": "test_val"})
            mock_capture.assert_called_once_with(
                event="test_event",
                properties={
                    "test_prop": "test_val",
                    "version": "1.0.0",
                    "is_development": True,
                },
                distinct_id=config.UNIQUE_USER_ID,
            )


def test_take_screenshots() -> None:
    """Tests utils.take_screenshots."""
    screenshots = utils.take_screenshots()

    assert isinstance(screenshots, list), f"Expected list, got {type(screenshots).__name__}"
    for screenshot in screenshots:
        assert isinstance(screenshot, utils.Image.Image), f"Expected PIL.Image, got {type(screenshot).__name__}"
