from collections import Counter
import random
from typing import List, Dict, Tuple
import json
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from loguru import logger
import os
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.cluster import KMeans

from openadapt.config import config
from openadapt.drivers import anthropic, openai, google
from openadapt.utils import parse_code_snippet

DRIVER = openai#google
NUM_CURSORS = 2**2
SPREAD_REDUCTION_FACTOR = 0.5
MAX_ITERATIONS = None
MAX_OVERLAP_RATIO = 0.2
CONTRAST_FACTOR = 1
RETRIES_PER_ITERATION = 3
DOWNSAMPLE_FACTOR = 3
CONSENSUS_THRESHOLD = 2
LABEL_SIZE_RATIO = 0.04


def maximally_different_color(image: Image.Image, sample_size: int = 1000, n_clusters: int = 10) -> tuple[int, int, int]:
    """Calculate the RGB color maximally different from every color in a given PIL image."""
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

def generate_cursors(center: dict[str, int], spread: float, width: int, height: int, jitter: float = 0.01) -> list[dict[str, int]]:
    """Generates cursors around a center point within a defined spread, with optional jitter.

    Args:
        center (dict[str, int]): The central point from which cursors are generated.
        spread (float): The spread factor determining the grid size.
        width (int): The width of the image.
        height (int): The height of the image.
        jitter (float): The jitter factor to add randomness to cursor positions.

    Returns:
        list[dict[str, int]]: A list of cursor positions.
    """
    cursors = []
    
    # Calculate grid dimensions
    grid_size = int(np.sqrt(NUM_CURSORS))
    
    # Calculate cell size based on spread
    cell_width = (width * spread) / grid_size
    cell_height = (height * spread) / grid_size
    
    # Calculate top-left corner of the grid
    start_x = center['x'] - (cell_width * (grid_size - 1)) / 2
    start_y = center['y'] - (cell_height * (grid_size - 1)) / 2
    
    for i in range(grid_size):
        for j in range(grid_size):
            x = int(start_x + i * cell_width)
            y = int(start_y + j * cell_height)
            
            # Apply jitter
            x += int((random.random() - 0.5) * cell_width * jitter)
            y += int((random.random() - 0.5) * cell_height * jitter)
            
            # Ensure cursors are within image bounds
            x = max(0, min(width - 1, x))
            y = max(0, min(height - 1, y))
            
            cursors.append({'x': x, 'y': y})
    
    return cursors

def draw_labelled_cursors(
    image: Image.Image,
    cursors: List[Dict[str, int]],
    inner_color: Tuple[int, int, int],
    label_color: Tuple[int, int, int],
    bg_color: Tuple[int, int, int] = (0, 0, 0),
    bg_transparency: float = 0.25,
    labels: List[str] = None,
    padding: int = 10,
) -> Tuple[Image.Image, float]:
    """Draws labelled cursors on the image and computes maximum label overlap ratio.
    
    Args:
        image: The input image on which cursors are to be drawn.
        cursors: A list of dictionaries containing cursor coordinates.
        inner_color: The color of the inner part of the cursor.
        label_color: The color of the label text.
        bg_color: Background color for transparency overlay.
        bg_transparency: Transparency level for the background overlay.
        labels: List of labels to be drawn with the cursors.
        padding: Padding around the labels.

    Returns:
        Tuple of Image with labelled cursors and the maximum overlap ratio.
    """
    image = image.convert("RGBA")
    bg_opacity = int(255 * bg_transparency)
    overlay = Image.new("RGBA", image.size, bg_color + (bg_opacity,))
    draw = ImageDraw.Draw(overlay)
    image = Image.alpha_composite(image, overlay)
    image = image.convert("RGB")

    draw = ImageDraw.Draw(image)
    min_dimension = min(image.size)
    font_size = int(min_dimension * LABEL_SIZE_RATIO)
    font = ImageFont.truetype("Arial.ttf", font_size)

    width, height = image.size

    # Calculate rectangle size based on the largest label
    max_label = max(labels, key=len) if labels else str(len(cursors))
    max_label_bbox = draw.textbbox((0, 0), max_label, font=font)
    max_label_w = max_label_bbox[2] - max_label_bbox[0]
    max_label_h = max_label_bbox[3] - max_label_bbox[1]
    rect_width = max_label_w + padding
    rect_height = max_label_h + padding

    rectangles = []
    for i, coords in enumerate(cursors):
        x, y = coords['x'], coords['y']
        label = labels[i] if labels else str(i + 1)
        
        # Draw rectangle
        rect_x0 = x - rect_width // 2
        rect_y0 = y - rect_height // 2
        rect_x1 = x + rect_width // 2
        rect_y1 = y + rect_height // 2
        draw.rectangle((rect_x0, rect_y0, rect_x1, rect_y1), fill=inner_color)
        
        # Draw label
        label_bbox = draw.textbbox((0, 0), label, font=font)
        label_w = label_bbox[2] - label_bbox[0]
        label_h = label_bbox[3] - label_bbox[1]
        draw.text((x - label_w / 2, y - label_h / 2), label, fill=label_color, font=font)

        rectangles.append((rect_x0, rect_y0, rect_x1, rect_y1))

    # Compute maximum overlap ratio
    max_overlap_ratio = 0.0
    for i, rect1 in enumerate(rectangles):
        for j, rect2 in enumerate(rectangles):
            if i != j:
                overlap_width = max(0, min(rect1[2], rect2[2]) - max(rect1[0], rect2[0]))
                overlap_height = max(0, min(rect1[3], rect2[3]) - max(rect1[1], rect2[1]))
                overlap_area = overlap_width * overlap_height
                rect1_area = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1])
                rect2_area = (rect2[2] - rect2[0]) * (rect2[3] - rect2[1])
                ratio1 = overlap_area / rect1_area if rect1_area > 0 else 0
                ratio2 = overlap_area / rect2_area if rect2_area > 0 else 0
                max_overlap_ratio = max(max_overlap_ratio, ratio1, ratio2)

    return image, max_overlap_ratio


def load_and_downsample_image(image_file_path, downsample_factor: int):
    # Open the image and convert to RGB
    image = Image.open(image_file_path).convert("RGB")
    
    # Get the original dimensions
    original_width, original_height = image.size
    
    # Calculate new dimensions (half of the original)
    new_width = original_width // downsample_factor
    new_height = original_height // downsample_factor
    
    # Resize the image to half its original size
    downsampled_image = image.resize((new_width, new_height), Image.LANCZOS)
    
    return downsampled_image

def increase_contrast(image: Image.Image, contrast_factor: float) -> Image.Image:
    """
    Increases the contrast of a PIL image and returns the enhanced image.

    Args:
        image (Image.Image): The input PIL image.
        contrast_factor (float): Factor by which to increase the contrast. 1.0 means no change,
                                 less than 1.0 decreases contrast, greater than 1.0 increases contrast.

    Returns:
        Image.Image: The enhanced PIL image.
    """
    if contrast_factor == 1:
        return image

    # Create an ImageEnhance object for contrast enhancement
    enhancer = ImageEnhance.Contrast(image)
    
    # Apply the contrast enhancement
    enhanced_image = enhancer.enhance(contrast_factor)
    
    return enhanced_image

def main():
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = load_and_downsample_image(image_file_path, DOWNSAMPLE_FACTOR)
    image = increase_contrast(image, CONTRAST_FACTOR)
    width, height = image.size

    inner_color = maximally_different_color(image)
    label_color = (255, 255, 255)
    
    target = "Inside cell C8"  # almost
    target = "Inside cell G5"  # almost
    target = "Inside cell A1"  # almost
    target = "Cell B12"
    target = "Cell E7"
    target = "Save button"
    target = "Cell C3"
    target = "Cell G4"
    target = "Cell A1"
    target = "14-May"
    center = {'x': width // 2, 'y': height // 2}
    spread = 1.0
    iteration = 1

    identified_locations = []
    exceptions = []
    center_history = []
    spread_history = []

    while True:
        if MAX_ITERATIONS and iteration > MAX_ITERATIONS:
            break

        prompt = f"""
Attached is a screenshot that has been dimmed and with {NUM_CURSORS} cursors overlaid.
Each cursor is a rectangle with color {inner_color}, labelled with a number from 1 to {NUM_CURSORS} with color {label_color}.

Your task is to identify the cursor closest to the target: '{target}'.

Respond with a single Python dict of the form:
    {{
        'target': '<target>',
        'target_position': '<natural language description of the target position>',
        'cursor_positions': '<natural language description of the cursor positions relative to the other elements in the image>',
        'closest': '<number of cursor closest to target>',
    }}

Don't make any assumptions about positions of anything. I need you to CAREFULLY ANALYZE THE IMAGE.

Make sure to surround your code with triple backticks: ```
"""
        if exceptions:
            prompt += f"""
Previously when you responded to this prompt, this resulted in the following exceptions:
{{exceptions}}
"""
        logger.info(f"prompt=\n{prompt}")

        votes = []
        center_history.append(center)
        spread_history.append(spread)
        max_overlap_ratio = 0
        while True:
            cursors = generate_cursors(center, spread, width, height)
            cursor_image, overlap_ratio = draw_labelled_cursors(image.copy(), cursors, inner_color, label_color)
            logger.info(f"{overlap_ratio=}")
            max_overlap_ratio = max(overlap_ratio, max_overlap_ratio)
            cursor_image.show()
            response = DRIVER.prompt(
                prompt=prompt,
                system_prompt="You are an expert GUI interpreter. You are precise and accurate.",
                images=[
                    #image,
                    cursor_image,
                ],
            )

            try:
                result = parse_code_snippet(response)
                closest = result['closest']
            except Exception as exc:
                logger.exception(exc)
                exceptions.append(exc)

            if closest is None:
                # try again with previous level
                center = center_history.pop()
                spread = spread_history.pop()
                continue
            votes.append(int(closest))
            most_common = Counter(votes).most_common(1)[0]
            logger.info(f"{votes=} {most_common=}")
            if most_common[1] >= CONSENSUS_THRESHOLD:
                break
        closest_number = most_common[0]
        identified_location = cursors[closest_number - 1]  # Adjust for 0-based indexing
        identified_locations.append(identified_location)
        center = identified_location
        spread *= SPREAD_REDUCTION_FACTOR

        if max_overlap_ratio > MAX_OVERLAP_RATIO:
            break

        iteration += 1

    # Create final image with all identified locations
    final_image = image.copy()
    labels = [str(i) for i in range(1, len(identified_locations) + 1)]
    final_image_with_cursors, _ = draw_labelled_cursors(
        final_image, 
        identified_locations, 
        inner_color, 
        label_color, 
        labels=labels,
    )
    final_image_with_cursors.show()
    final_image_with_cursors.save("final_cursor_locations.png")

    logger.info(f"Final identified locations: {identified_locations}")

if __name__ == "__main__":
    main()
