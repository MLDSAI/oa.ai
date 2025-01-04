from pprint import pformat
from typing import Tuple, List, Dict
import json
import os

from loguru import logger
from PIL import Image, ImageDraw
import matplotlib.pyplot as plt

from openadapt.config import config
from openadapt.drivers import openai, anthropic, google
from openadapt.utils import parse_code_snippet

DRIVER = openai
HISTORY_SIZE = 1

import numpy as np
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans


def maximally_different_color(image: Image.Image, sample_size: int = 1000, n_clusters: int = 10) -> tuple[int, int, int]:
    """Calculate the RGB color maximally different from every color in a given PIL image.

    Args:
        image: The PIL image object.
        sample_size: The number of colors to sample from the image.
        n_clusters: The number of clusters to use for KMeans clustering.

    Returns:
        A tuple representing the RGB color maximally different from all colors in the image.
    """
    img = image.convert('RGB')
    np_img = np.array(img).reshape(-1, 3)
    
    if len(np_img) > sample_size:
        np.random.seed(42)  # For reproducibility
        np.random.shuffle(np_img)
        sampled_colors = np_img[:sample_size]
    else:
        sampled_colors = np_img

    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    kmeans.fit(sampled_colors)
    cluster_centers = kmeans.cluster_centers_

    all_colors = np.array([[r, g, b] for r in range(0, 256, 8) for g in range(0, 256, 8) for b in range(0, 256, 8)])
    distances = cdist(all_colors, cluster_centers, metric='euclidean')
    sum_distances = np.sum(distances, axis=1)
    max_dist_index = np.argmax(sum_distances)

    return tuple(all_colors[max_dist_index].astype(int))

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

def update_coords(coords: Dict[str, int], directions: Dict[str, str], width: int, height: int, iteration: int) -> Dict[str, int]:
    """Update coordinates based on directions and current iteration."""
    if directions.get('x') == 'left':
        coords['x'] -= width // (2 ** iteration)
    elif directions.get('x') == 'right':
        coords['x'] += width // (2 ** iteration)

    if directions.get('y') == 'up':
        coords['y'] -= height // (2 ** iteration)
    elif directions.get('y') == 'down':
        coords['y'] += height // (2 ** iteration)

    return coords

def main():
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = Image.open(image_file_path).convert("RGB")

    width, height = image.size
    coords = {'x': width // 2, 'y': height // 2}
    images = []
    all_coords = []
    exceptions = []
    target = "Cell B3"
    iteration = 1

    color = maximally_different_color(image)
    logger.info(f"{color=}")
    
    while True:
        all_coords.append(dict(coords))
        image_with_dot = draw_concentric_circles(image.copy(), coords, ["red", color], [25, 15, 5])
        image_with_dot.show()
        images.append(image_with_dot)

        prompt = f"The attached image size is {image.size}."

        if all_coords:
            prompt += f" The attached images have red circles at coordinates:"
            for coord in all_coords:
                prompt += f"\n  {coord}"
            prompt += "\n, in the order they are attached."
        prompt += f" Identify the direction to move the last red dot towards the target: {target}. Respond with a single Python dict only: {{ 'x': 'left' | 'right', 'y': 'up' | 'down' }}."
        prompt += f" If the red dot is on the target, respond with an empty dict."
        if exceptions:
            prompt += f"Last time you tried this, your response resulted in the following exception(s): {exceptions}."
        logger.info(f"prompt=\n{prompt}")
        response = DRIVER.prompt(
            prompt=prompt,
            system_prompt="You are an expert GUI interpreter. You are precise and discerning, and you strive for accuracy. You do not make the same mistake twice.",
            images=images or [image],
            detail="high",
        )
        try:
            directions = parse_code_snippet(response)
        except Exception as exc:
            exceptions.append(exc)
            all_coords = all_coords[:-1]
            continue
        else:
            exceptions = []
        
        coords = update_coords(coords, directions, width, height, iteration)
        iteration += 1
        
        if all_coords and all_coords[-1] == coords:
            break
        
        if HISTORY_SIZE:
            all_coords = all_coords[-HISTORY_SIZE:]
            images = images[-HISTORY_SIZE:]

    plt.show()

if __name__ == "__main__":
    main()
