# XXX this won't work because context is lost

import os
from collections import deque

from loguru import logger
from PIL import Image

from openadapt.config import config
from openadapt.drivers import openai, anthropic, google
from openadapt.utils import parse_code_snippet

DRIVER = openai  # anthropic

def prompt_model(driver, prompt, image):
    return driver.prompt(
        prompt=prompt,
        system_prompt="You are an expert GUI interpreter. You are precise and discerning, and you strive for accuracy. You do not make the same mistake twice.",
        images=[image]
    )

def get_quadrant(driver, image, target_element):
    prompt = f"The target element is {target_element}. In which quadrant of the image is the target element located: top-left, top-right, bottom-left, or bottom-right? You can also say 'stop' when the target element is in the center of the image. You may reason in natural language, but you should include exactly one code block containing a python dict to structure your final response. The dict should have a single key: 'instruction', whose value is either 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'stop', or 'unknown'. If you don't see the target element, say 'unknown'. DO NOT MAKE ANY ASSUMPTIONS, IF YOU DON'T SEE THE ELEMENT THEN SAY UNKNOWN!!! IF THE TARGET ELEMENT IS IN THE CENTER OF THE IMAGE, SAY STOP!!!"
    response = prompt_model(driver, prompt, image)
    response_dict = parse_code_snippet(response)
    quadrant = response_dict["instruction"]
    return quadrant

def crop_image(image, quadrant):
    width, height = image.size
    if quadrant == "top-left":
        return image.crop((0, 0, width // 2, height // 2))
    elif quadrant == "top-right":
        return image.crop((width // 2, 0, width, height // 2))
    elif quadrant == "bottom-left":
        return image.crop((0, height // 2, width // 2, height))
    elif quadrant == "bottom-right":
        return image.crop((width // 2, height // 2, width, height))
    else:
        return image

def locate_element(driver, image, target_element):
    image_history = deque([(image, ["top-left", "top-right", "bottom-left", "bottom-right"])])
    iterations = 0
    max_iterations = 20  # Increased to allow for backtracking

    while iterations < max_iterations and image_history:
        current_image, available_quadrants = image_history[-1]
        current_image.show()  # Display the current image

        quadrant = get_quadrant(driver, current_image, target_element)
        logger.info(f"{quadrant=}")
        input()
        
        if quadrant == "stop":
            logger.info(f"Element located after {iterations} iterations.")
            return current_image

        if quadrant == "unknown":
            logger.info("Unknown response, discarding current image and trying next quadrant from previous image")
            image_history.pop()  # Discard the current image
            if not image_history:
                logger.warning("No more images in history")
                break
            continue  # Go back to the start of the loop with the previous image

        if quadrant not in available_quadrants:
            logger.warning(f"Unexpected quadrant {quadrant}, trying next available quadrant")
            if not available_quadrants:
                logger.info("No more quadrants to try, backtracking...")
                image_history.pop()
                continue
            quadrant = available_quadrants[0]

        available_quadrants.remove(quadrant)
        new_image = crop_image(current_image, quadrant)
        image_history.append((new_image, ["top-left", "top-right", "bottom-left", "bottom-right"]))
        iterations += 1

    logger.warning("Max iterations reached or no more images to process")
    return image_history[-1][0] if image_history else image  # Return the last processed image or the original if all discarded

def main():
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = Image.open(image_file_path)
    target_element = "Cell A1"
    
    result_image = locate_element(DRIVER, image, target_element)
    result_image.show()  # Display the final result

if __name__ == "__main__":
    main()
