"""Adapter for GPT4-V API.

https://platform.openai.com/docs/guides/vision
"""

from copy import deepcopy
from pprint import pformat
from typing import Any

from PIL import Image
import fire
import requests

from openadapt import cache, utils
from openadapt.config import config
from openadapt.custom_logger import logger
from tokencost import (
    calculate_prompt_cost,
    calculate_completion_cost,
    count_message_tokens,
)


MODEL_NAME = [
    "gpt-4-vision-preview",
    "gpt-4-turbo-2024-04-09",
    "gpt-4o",
][-1]
# TODO XXX: per model
MAX_TOKENS = 4096
# TODO XXX undocumented
MAX_IMAGES = 90

# Track total tokens and cost
total_tokens_used = 0
total_cost = 0.0


def create_payload(
    prompt: str,
    system_prompt: str | None = None,
    images: list[Image.Image] | None = None,
    model: str = MODEL_NAME,
    detail: str = "high",  # "low" or "high"
    max_tokens: int | None = None,
) -> dict:
    """Create payload for prompting.

    Args:
        prompt: the prompt
        system_prompt: the system prompt
        images: list of images
        model: name of OpenAI model
        detail: detail level of images, "low" or "high"
        max_tokens: maximum number of tokens

    Returns:
        dict containing prompt payload
    """
    max_tokens = max_tokens or MAX_TOKENS
    if max_tokens > MAX_TOKENS:
        logger.warning(f"{max_tokens=} {MAX_TOKENS=}")
        max_tokens = MAX_TOKENS

    """Creates the payload for the API request."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        },
    ]

    images = images or []
    for image in images:
        base64_image = utils.image2utf8(image)
        messages[0]["content"].append(
            {
                "type": "image_url",
                "image_url": {
                    "url": base64_image,
                    "detail": detail,
                },
            }
        )

    if system_prompt:
        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_prompt,
                    }
                ],
            }
        ] + messages

    rval = {
        "model": model,
        "messages": messages,
    }
    if max_tokens:
        rval["max_tokens"] = max_tokens
    return rval


@cache.cache()
def get_response(
    payload: dict,
    api_key: str = config.OPENAI_API_KEY,
) -> requests.Response:
    """Sends a request to the OpenAI API and returns the response.

    Args:
        payload: dictionary returned by create_payload
        api_key (str): api key

    Returns:
        response from OpenAI API
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        verify=False,
    )
    result = response.json()
    if "error" in result:
        error = result["error"]
        message = error["message"]
        logger.warning(f"{message=}")
        if "retry" in message:
            return get_response(payload)
        raise Exception(message)
    return result


def calculate_tokens_and_cost(
    result: dict, payload: dict
) -> tuple[int, float, int, float, float]:
    """Calculate the tokens and costs for the API call.

    Args:
        result: The response from the OpenAI API.
        payload: The original request payload.

    Returns:
        A tuple containing:
        - Prompt tokens used
        - Prompt cost
        - Completion tokens used
        - Completion cost
        - Total cost
    """  # noqa: D202

    # Extract text content from payload messages
    def extract_text(messages: list[dict]) -> list[dict]:
        extracted = []
        for message in messages:
            role = message["role"]
            content_list = message["content"]
            text_content = "".join(
                [item["text"] for item in content_list if item["type"] == "text"]
            )
            extracted.append({"role": role, "content": text_content})
        return extracted

    # Extracted messages for token counting
    prompt_messages = extract_text(payload["messages"])
    completion_text = result["choices"][0]["message"]["content"]

    # Calculate tokens and costs
    prompt_tokens = count_message_tokens(prompt_messages, model=payload["model"])
    completion_tokens = count_message_tokens(
        [{"role": "assistant", "content": completion_text}], model=payload["model"]
    )

    prompt_cost = calculate_prompt_cost(prompt_messages, model=payload["model"])
    completion_cost = calculate_completion_cost(completion_text, model=payload["model"])

    total_cost = prompt_cost + completion_cost
    return prompt_tokens, prompt_cost, completion_tokens, completion_cost, total_cost


def update_total_usage(
    prompt_tokens: int, completion_tokens: int, api_call_cost: float
) -> None:
    """Update the total token and cost counters.

    Args:
        prompt_tokens: The number of tokens used in the prompt.
        completion_tokens: The number of tokens used in the completion.
        api_call_cost: The total cost of the API call.
    """
    global total_tokens_used, total_cost
    total_tokens_used += prompt_tokens + completion_tokens
    total_cost += float(api_call_cost)  # Convert Decimal to float


def get_completion(payload: dict, dev_mode: bool = False) -> str:
    """Sends a request to the OpenAI API and returns the first message.

    Args:
        payload (dict): dictionary returned by create_payload
        dev_mode (bool): whether to launch a debugger on error

    Returns:
        (str) first message from the response
    """
    try:
        result = get_response(payload)
    except Exception as exc:
        if "retry your request" in str(exc):
            return get_completion(payload)
        elif dev_mode:
            import ipdb

            ipdb.set_trace()
        else:
            raise exc
    logger.info(f"result=\n{pformat(result)}")

    # Calculate tokens and cost
    prompt_tokens, prompt_cost, completion_tokens, completion_cost, api_call_cost = (
        calculate_tokens_and_cost(result, payload)
    )

    # Update total usage
    update_total_usage(prompt_tokens, completion_tokens, api_call_cost)

    # Log the results
    logger.info(
        f"API Call Tokens: {prompt_tokens + completion_tokens}, Total Tokens Used:"
        f" {total_tokens_used}"
    )
    logger.info(f"API Call Cost: ${api_call_cost:.6f}, Total Cost: ${total_cost:.6f}")

    choices = result["choices"]
    choice = choices[0]
    message = choice["message"]
    content = message["content"]
    return content


def log_payload(payload: dict[Any, Any]) -> None:
    """Logs a payload after removing base-64 encoded values recursively."""
    # TODO: detect base64 encoded strings dynamically
    # messages["content"][{"image_url": ...
    # payload["messages"][1]["content"][9]["image_url"]
    payload_copy = deepcopy(payload)
    for message in payload_copy["messages"]:
        for content in message["content"]:
            if "image_url" in content:
                content["image_url"]["url"] = "[REDACTED]"
    logger.info(f"payload=\n{pformat(payload_copy)}")


def prompt(
    prompt: str,
    system_prompt: str | None = None,
    images: list[Image.Image] | None = None,
    max_tokens: int | None = None,
    detail: str = "high",
) -> str:
    """Get prompt completion from OpenAI.

    Args:
        prompt: the prompt
        system_prompt: the system prompt
        images: list of images
        model: name of OpenAI model
        detail: detail level of images, "low" or "high"
        max_tokens: maximum number of tokens

    Returns:
        string containing the first message from the response
    """
    logger.info(f"system_prompt=\n{system_prompt}")
    logger.info(f"prompt=\n{prompt}")
    images = images or []
    logger.info(f"{len(images)=}")
    payload = create_payload(
        prompt,
        system_prompt,
        images,
        max_tokens=max_tokens,
        detail=detail,
    )
    log_payload(payload)
    result = get_completion(payload)
    logger.info(f"result=\n{pformat(result)}")
    return result


def main(text: str, image_path: str | None = None) -> None:
    """Prompt Google Gemini with text and a path to an image."""
    if image_path:
        image = Image.open(image_path)
        # Convert image to RGB if it's RGBA (to remove alpha channel)
        if image.mode in ("RGBA", "LA") or (
            image.mode == "P" and "transparency" in image.info
        ):
            image = image.convert("RGB")
    else:
        image = None

    images = [image] if image else None
    output = prompt(text, images=images)
    logger.info(output)


if __name__ == "__main__":
    fire.Fire(main)
