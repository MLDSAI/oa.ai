"""Adapter for prompting foundation models."""

from typing import Type

from PIL import Image

from openadapt.custom_logger import logger
from openadapt.drivers import anthropic, google, openai

# Define a list of drivers in the order they should be tried
DRIVER_ORDER: list[Type] = [openai, google, anthropic]


def prompt(
    text: str,
    images: list[Image.Image] | None = None,
    system_prompt: str | None = None,
) -> str:
    """Attempt to fetch a prompt completion from various services in order of priority.

    Args:
        text: The main text prompt.
        images: list of images to include in the prompt.
        system_prompt: An optional system-level prompt.

    Returns:
        The result from the first successful driver.
    """
    text = text.strip()
    for driver in DRIVER_ORDER:
        try:
            logger.info(f"Trying driver: {driver.__name__}")
            return driver.prompt(text, images=images, system_prompt=system_prompt)
        except Exception as e:
            logger.exception(e)
            logger.error(f"Driver {driver.__name__} failed with error: {e}")
            import ipdb

            ipdb.set_trace()
            continue
    raise Exception("All drivers failed to provide a response")


def generate_summary_and_icon(action_dict: dict, window_dict: dict, screenshot: Image.Image) -> tuple[str, str]:
    """Generate a summary and icon for a given action.

    Args:
        action_dict: The action dictionary.
        window_dict: The window dictionary.
        screenshot: The screenshot image.

    Returns:
        A tuple containing the summary and icon.
    """
    summary_prompt = f"Please provide a one sentence summary of the following action: {action_dict}, window: {window_dict}"
    summary = prompt(summary_prompt, images=[screenshot])

    icon_prompt = f"Please provide an icon for the following action: {action_dict}, window: {window_dict}"
    icon = prompt(icon_prompt, images=[screenshot])

    return summary, icon


if __name__ == "__main__":
    # This could be extended to use command-line arguments or other input methods
    print(prompt("Describe the solar system."))
