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

DRIVER = openai#anthropic
HISTORY_SIZE = 10

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

def draw_coordinates_and_arrows(image: Image.Image, all_coords: List[Dict[str, int]], arrow_color: str = "blue", dot_radius: int = 25) -> Image.Image:
    """Draw all coordinates and arrows between successive pairs on the image.

    Args:
        image: The PIL image object.
        all_coords: List of dictionaries containing the coordinates.
        arrow_color: The color of the arrows.
        dot_radius: The radius of the red dot.
    
    Returns:
        The image with drawn coordinates and arrows.
    """
    draw = ImageDraw.Draw(image)
    border_radius = dot_radius + 5
    arrow_head_size = 50
    
    for i in range(len(all_coords) - 1):
        x1, y1 = all_coords[i]['x'], all_coords[i]['y']
        x2, y2 = all_coords[i+1]['x'], all_coords[i+1]['y']
        
        draw.ellipse((x1 - border_radius, y1 - border_radius, x1 + border_radius, y1 + border_radius), fill=arrow_color)
        draw.ellipse((x1 - dot_radius, y1 - dot_radius, x1 + dot_radius, y1 + dot_radius), fill="red")
        draw.line((x1, y1, x2, y2), fill=arrow_color, width=4)
        
        # Adjust arrowhead position to point to the exterior of the dot
        angle = np.arctan2(y2 - y1, x2 - x1)
        x2_adjusted = x2 - int(dot_radius * np.cos(angle))
        y2_adjusted = y2 - int(dot_radius * np.sin(angle))
        
        # Draw arrowhead
        draw.polygon([
            (x2_adjusted, y2_adjusted), 
            (x2_adjusted - arrow_head_size * np.cos(angle - np.pi / 6), y2_adjusted - arrow_head_size * np.sin(angle - np.pi / 6)), 
            (x2_adjusted - arrow_head_size * np.cos(angle + np.pi / 6), y2_adjusted - arrow_head_size * np.sin(angle + np.pi / 6))
        ], fill=arrow_color)
    
    if all_coords:
        x, y = all_coords[-1]['x'], all_coords[-1]['y']
        draw.ellipse((x - border_radius, y - border_radius, x + border_radius, y + border_radius), fill=arrow_color)
        draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill="red")
    
    return image


def update_coords(coords: Dict[str, int], directions: Dict[str, str], width: int, height: int) -> Dict[str, int]:
    """Update coordinates based on directions and magnitude."""
    for direction, magnitude in directions.items():
        step_size = {
            'large': 0.25,
            'medium': 0.10,
            'small': 0.01
        }[magnitude]
        
        if direction == 'left':
            coords['x'] -= int(width * step_size)
        elif direction == 'right':
            coords['x'] += int(width * step_size)
        elif direction == 'up':
            coords['y'] -= int(height * step_size)
        elif direction == 'down':
            coords['y'] += int(height * step_size)

    return coords

def main():
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = Image.open(image_file_path).convert("RGB")

    width, height = image.size
    coords = {'x': width // 2, 'y': height // 2}
    all_coords = []
    exceptions = []
    placement_history = []
    target = "The center of Cell G1"
    iteration = 1


    # TODO: warn off screen
    # TODO: zoom, other primitives?

    color = maximally_different_color(image)
    logger.info(f"{color=}")
    
    while True:
        all_coords.append(dict(coords))

        prompt = f"Attached are three images: the first ('raw') is an unadultered screenshot, the second ('history') shows previous cursor locations on the screenshot separated by arrows, and the third ('current') shows the current cursor location."

        if all_coords:
            prompt += f" Cursor locations are indicated with red dots surrounded by a border. The history image has cursors at coordinates:"
            for coord in all_coords:
                prompt += f"\n  {coord}"
            prompt += f" The current image has a cursor at coordinates {all_coords[-1]}."
        prompt += f" Identify the magnitude and direction to move the current cursor towards the target: {target}. Respond with a single Python dict of the form {{'target': '<specified target>', 'placement': '<natural language description of the current location of the cursor>', 'left' | 'right' | 'up' | 'down': 'large' | 'medium' | 'small'}}."
        prompt += f" If the current cursor is already at the target, do not specify any directions (but still specify the placement)."
        prompt += " Make sure to surround your code with triple backticks: ```"
        if exceptions:
            prompt += f"Last time you tried this, your response resulted in the following exception(s): {exceptions}."
        logger.info(f"prompt=\n{prompt}")
        history_image = draw_coordinates_and_arrows(image.copy(), all_coords, color)
        history_image.show()
        current_image = draw_coordinates_and_arrows(image.copy(), [all_coords[-1]], color)
        #input()
        response = DRIVER.prompt(
            prompt=prompt,
            system_prompt="You are an expert GUI interpreter. You are precise and discerning, and you strive for accuracy. You do not make the same mistake twice.",
            images=[image, history_image, current_image],
        )
        try:
            directions = parse_code_snippet(response)
        except Exception as exc:
            exceptions.append(exc)
            all_coords = all_coords[:-1]
            continue
        else:
            exceptions = []
        
        target = directions.pop("target")
        placement = directions.pop("placement")
        placement_history.append(placement)
        logger.info(f"{target=} {placement=}")
        coords = update_coords(coords, directions, width, height)
        iteration += 1
        
        if all_coords and all_coords[-1] == coords:
            break
        
        if HISTORY_SIZE:
            all_coords = all_coords[-HISTORY_SIZE:]

    logger.info(f"placement_history=\n{pformat(placement_history)}")

if __name__ == "__main__":
    main()

