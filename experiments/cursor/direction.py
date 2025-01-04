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

DRIVER = anthropic
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

def draw_coordinates_and_arrows(
    image: Image.Image,
    all_coords: List[Dict[str, int]],
    inner_color: str,
    border_color: str,
    draw_x: bool = True,
    bg_color: tuple = (0, 0, 0),
    bg_transparency: float = 0.25,
) -> Image.Image:
    """Draw all coordinates and arrows between successive pairs on the image.

    Args:
        image: The PIL image object.
        all_coords: List of dictionaries containing the coordinates.
        border_color: The color of the arrows.
        draw_x: If True, draw a big bold "X" on the last coordinate.
    
    Returns:
        The image with drawn coordinates, arrows, and optionally a big bold "X" on the last coordinate.
    """
    width, height = image.size
    min_dimension = min(width, height)
    
    # Define sizes relative to image dimensions
    dot_radius = int(min_dimension * 0.014)  # Approximately 25 in a 1742 height image
    border_radius = int(min_dimension * 0.017)  # Slightly larger than dot_radius
    arrow_head_size = int(min_dimension * 0.029)  # Approximately 50 in a 1742 height image
    line_width = max(1, int(min_dimension * 0.0023))  # Approximately 4 in a 1742 height image
    x_line_width = max(1, int(min_dimension * 0.0034))  # Approximately 6 in a 1742 height image

    image = image.convert("RGBA")
    bg_opacity = int(255 * bg_transparency)
    overlay = Image.new("RGBA", image.size, bg_color + (bg_opacity,))
    draw = ImageDraw.Draw(overlay)
    image = Image.alpha_composite(image, overlay)
    image = image.convert("RGB")

    draw = ImageDraw.Draw(image)
    
    for i in range(len(all_coords) - 1):
        x1, y1 = all_coords[i]['x'], all_coords[i]['y']
        x2, y2 = all_coords[i+1]['x'], all_coords[i+1]['y']
        
        draw.ellipse((x1 - border_radius, y1 - border_radius, x1 + border_radius, y1 + border_radius), fill=border_color)
        draw.ellipse((x1 - dot_radius, y1 - dot_radius, x1 + dot_radius, y1 + dot_radius), fill=inner_color)
        draw.line((x1, y1, x2, y2), fill=border_color, width=line_width)
        
        # Adjust arrowhead position to point to the exterior of the dot
        angle = np.arctan2(y2 - y1, x2 - x1)
        x2_adjusted = x2 - int(dot_radius * np.cos(angle))
        y2_adjusted = y2 - int(dot_radius * np.sin(angle))
        
        # Draw arrowhead
        draw.polygon([
            (x2_adjusted, y2_adjusted), 
            (x2_adjusted - arrow_head_size * np.cos(angle - np.pi / 6), y2_adjusted - arrow_head_size * np.sin(angle - np.pi / 6)), 
            (x2_adjusted - arrow_head_size * np.cos(angle + np.pi / 6), y2_adjusted - arrow_head_size * np.sin(angle + np.pi / 6))
        ], fill=border_color)
    
    if all_coords:
        x, y = all_coords[-1]['x'], all_coords[-1]['y']
        draw.ellipse((x - border_radius, y - border_radius, x + border_radius, y + border_radius), fill=border_color)
        draw.ellipse((x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius), fill=inner_color)
        
        # Draw a big bold "X" on the last coordinate if draw_x is True
        if draw_x:
            x_size = border_radius * 2  # Size of the X
            
            # Draw the X
            draw.line((x - x_size, y - x_size, x + x_size, y + x_size), fill="black", width=x_line_width)
            draw.line((x - x_size, y + x_size, x + x_size, y - x_size), fill="black", width=x_line_width)

    return image

import random
from typing import Dict, Tuple

def update_coords(coords: Dict[str, int], direction: str, magnitude: str, width: int, height: int, previous_step_size: float) -> Tuple[Dict[str, int], float]:
    """Update coordinates based on a single direction and relative magnitude, with added jitter."""
    if magnitude == 'more':
        new_step_size = min(previous_step_size * 2, 0.25)  # Cap at 0.25
    elif magnitude == 'less':
        new_step_size = max(previous_step_size / 2, 0.01)  # Floor at 0.01
    else:  # 'same'
        new_step_size = previous_step_size

    step = int(min(width, height) * new_step_size)

    # Add jitter
    jitter_range = max(1, int(step * 0.1))  # 10% of step size, minimum 1 pixel
    jitter_x = random.randint(-jitter_range, jitter_range)
    jitter_y = random.randint(-jitter_range, jitter_range)

    direction_map = {
        'left': (-step, 0),
        'right': (step, 0),
        'up': (0, -step),
        'down': (0, step),
        'up-left': (-step, -step),
        'up-right': (step, -step),
        'down-right': (step, step),
        'down-left': (-step, step),
    }
    dx, dy = direction_map.get(direction, (0, 0))
    
    # Apply movement with jitter
    coords['x'] += dx + jitter_x
    coords['y'] += dy + jitter_y

    # Ensure coordinates stay within image boundaries
    coords['x'] = max(0, min(coords['x'], width - 1))
    coords['y'] = max(0, min(coords['y'], height - 1))

    return coords, new_step_size

def load_and_downsample_image(image_file_path):
    # Open the image and convert to RGB
    image = Image.open(image_file_path).convert("RGB")
    
    # Get the original dimensions
    original_width, original_height = image.size
    
    # Calculate new dimensions (half of the original)
    new_width = original_width // 2
    new_height = original_height // 2
    
    # Resize the image to half its original size
    downsampled_image = image.resize((new_width, new_height), Image.LANCZOS)
    
    return downsampled_image

def main():
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = load_and_downsample_image(image_file_path)

    width, height = image.size
    coords = {'x': width // 2, 'y': height // 2}
    all_coords = []
    exceptions = []
    all_directions = []
    placement_history = []
    target = "Inside cell C8"
    iteration = 1
    previous_step_size = 0.10  # Start with a medium step size

    border_color = maximally_different_color(image)
    inner_color = (255, 0, 0)
    logger.info(f"{inner_color=} {border_color=}")
    
    try:
        while True:
            all_coords.append(dict(coords))

            prompt = f"""
Attached are two images: the first ('raw') is an unadultered
screenshot, the second ('history') shows previous cursor locations overlaid
on the (dimmed) screenshot, separated by arrows. Cursors are circles with color 
{inner_color} surrounded by {border_color}. The latest cursor location is 
indicated by an 'X'. Be careful not to get confused with background GUI elements and the overlaid cursors.
Your task is to identify the direction and magnitude to move the current cursor towards the 
target, which is '{target}'.
Respond with a single Python dict of the form:
    {{
        'target': '<specified target>',
        'placement': '<step by step reasoning for identifying the current location of the cursor>',
        'plan': '<natural language description of your plan for moving the current placement to the target>',
        'direction': 'left' | 'right' | 'up' | 'down' | 'up-left' | 'up-right' | 'down-left' | 'down-right',
        'magnitude': 'more' | 'less' | 'same'
    }}
The 'direction' specifies the direction we need to move the cursor to get it to the target.
The magnitude you specify should be relative to the previous movement, regardless of direction.
If the current cursor is already at the target, do not specify any direction or magnitude (but still specify the placement).
Make sure to surround your code with triple backticks: ```
"""
            if exceptions:
                prompt += f"Last time you tried this, your response resulted in the following exception(s): {exceptions}."
            logger.info(f"prompt=\n{prompt}")
            history_image = draw_coordinates_and_arrows(image.copy(), all_coords[-(HISTORY_SIZE + 1):], inner_color, border_color)
            history_image.show()
            current_image = draw_coordinates_and_arrows(image.copy(), [all_coords[-1]], inner_color, border_color)
            #input()
            response = DRIVER.prompt(
                prompt=prompt,
                system_prompt="You are an expert GUI interpreter. You are precise and accurate.",
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
            
            all_directions.append(directions.copy())
            target = directions.pop("target")
            placement = directions.pop("placement")
            direction = directions.pop("direction", None)
            magnitude = directions.pop("magnitude", None)
            plan = directions.pop("plan", None)
            placement_history.append(placement)
            logger.info(f"{target=} {placement=} {plan=} {direction=} {magnitude=}")
            
            if direction and magnitude:
                coords, previous_step_size = update_coords(coords, direction, magnitude, width, height, previous_step_size)
            iteration += 1
            
            if all_coords and all_coords[-1] == coords:
                break
            
            #if HISTORY_SIZE:
            #    all_coords = all_coords[-HISTORY_SIZE:]
    except Exception as exc:
        logger.exception(exc)
        pass

    full_history_image = draw_coordinates_and_arrows(image.copy(), all_coords, inner_color, border_color)
    full_history_image.show()
    logger.info(f"placement_history=\n{pformat(placement_history)}")
    logger.info(f"all_directions=\n{pformat(all_directions)}")

if __name__ == "__main__":
    main()
