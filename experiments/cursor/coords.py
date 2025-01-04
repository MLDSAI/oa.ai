from pprint import pformat
from typing import Tuple, List, Dict
import json
import os

from PIL import Image, ImageDraw
import matplotlib.pyplot as plt

from openadapt.config import config
from openadapt.drivers import openai, anthropic, google
from openadapt.utils import parse_code_snippet

DRIVER = openai
HISTORY_SIZE = 5

def draw_concentric_circles(image: Image.Image, coords: Dict[str, int], colors: List[str], radii: List[int]) -> Image.Image:
    """Draw concentric circles on the image at the specified coordinates."""
    draw = ImageDraw.Draw(image)
    x, y = coords['x'], coords['y']
    
    for color, radius in zip(colors, radii):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        
    return image

def display_images(images: List[Image.Image]) -> None:
    """Display all images in the same window."""
    fig, axs = plt.subplots(1, len(images), figsize=(15, 5))
    if len(images) == 1:
        axs = [axs]
    for ax, img in zip(axs, images):
        ax.imshow(img)
        ax.axis('off')
    plt.show(block=False)

def main():
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = Image.open(image_file_path).convert("RGB")
    images = []
    all_coords = []
    exceptions = []
    target = "Cell B3"
    
    while True:
        prompt = f"The attached image size is {image.size}."

        if all_coords:
            prompt += f" The images have red circles at coordinates:"
            for coord in all_coords:
                coord.pop('direction', None)
                prompt += f"\n  {coord}"
            prompt += "\n, in the order they are attached."
        prompt += f" Locate the pixel coordinates of the target: {target}. Respond with a Python dict only: {{ 'x': int, 'y': int, 'direction': '<natural language description of your intended direction to move the last circle>' }}."
        if all_coords:
            prompt += "To move the circle to the right, increase the 'x' coordinate, and decrease it to move to the left. To move the circle down, increase the 'y' coordinate, and decrease it to move up."
        #if all_coords:
            #prompt += " If the red dot is in the correct location in the last image I gave you, respond with the last pair of coordinates I gave you. Otherwise, consider the images and corresponding coordinate locations I gave you to provide an accurate location of the target."
            #prompt += f" IT IS IMPERATIVE THAT IF THE RED DOT IS ALREADY IN THE TARGET, YOU DO NOT PROVIDE UPDATED COORDINATES, BUT RE-USE THE CORRECT ONES. Remember, the target is {target}. IF THE RED DOT IS **NOT** ALREADY IN THE TARGET, YOU MUST PROVIDE UPDATED COORDINATES."
        if exceptions:
            prompt += f"Last time you tried this, your response resulted in the following exception(s): {exceptions}."
        print(prompt)
        response = DRIVER.prompt(
            prompt=prompt,
            system_prompt="You are an expert GUI interpreter. You are precise and discerning, and you strive for accuracy. You do not make the same mistake twice.",
            images=images or [image],
            detail="high",
        )
        try:
            coords = parse_code_snippet(response)
        except Exception as exc:
            exceptions.append(exc)
            continue
        else:
            exceptions = []
        last_coords = all_coords[-1] if all_coords else None
        print(f"{coords=} {last_coords=}")
        if last_coords == coords:
            break
        all_coords.append(coords)
        image_with_dot = draw_concentric_circles(image.copy(), coords, ["red", "yellow"], [25, 15, 5])
        image_with_dot.show()
        images.append(image_with_dot)

        if HISTORY_SIZE:
            all_coords = all_coords[-HISTORY_SIZE:]
            images = images[-HISTORY_SIZE:]

    #display_images(images)
    plt.show()

if __name__ == "__main__":
    main()

