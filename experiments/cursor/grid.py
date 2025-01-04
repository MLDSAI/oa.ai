from typing import Tuple, List
import os

from loguru import logger
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

from openadapt.config import config
from openadapt.drivers import anthropic, openai, google
from openadapt.utils import parse_code_snippet

# Constants
DOWNSAMPLE_FACTOR = 2
GRID_SIZE = 25  # Adjust based on desired grid size
DRIVER = openai
DO_CORRECTIONS = True

def load_and_downsample_image(image_file_path: str, downsample_factor: int) -> Image.Image:
    """Load and downsample the image."""
    image = Image.open(image_file_path).convert("RGB")
    original_width, original_height = image.size
    new_width = original_width // downsample_factor
    new_height = original_height // downsample_factor
    downsampled_image = image.resize((new_width, new_height), Image.LANCZOS)
    return downsampled_image

def dim_image(image: Image.Image) -> Image.Image:
    """Dim the image by reducing brightness to 50%."""
    enhancer = ImageEnhance.Brightness(image)
    return enhancer.enhance(0.5)

def add_grid_labels(image: Image.Image, grid_size: int) -> Image.Image:
    """Add grid labels to the image on all four sides."""
    width, height = image.size
    grid_image = Image.new('RGB', (width + 100, height + 100), 'red')
    grid_image.paste(image, (50, 50))
    draw = ImageDraw.Draw(grid_image)

    max_font_size = min((height // grid_size) // 2, (width // grid_size) // 2)
    font_size = max_font_size
    font = ImageFont.truetype("Arial.ttf", font_size)

    while True:
        fits = True
        for i in range(grid_size):
            text_size = draw.textbbox((0, 0), str(i + 1), font=font)[2:]
            if text_size[0] > width // grid_size or text_size[1] > height // grid_size:
                fits = False
                break
        if fits:
            break
        font_size -= 1
        font = ImageFont.truetype("Arial.ttf", font_size)
        if font_size <= 0:
            raise ValueError("Cannot find a suitable font size that fits within the grid cells")

    cell_width = width / grid_size
    cell_height = height / grid_size

    for i in range(grid_size):
        # Left side labels
        draw.text((25, 50 + int(i * cell_height + cell_height / 2) - font_size // 2), str(i + 1), fill='white', font=font)
        # Top side labels
        draw.text((50 + int(i * cell_width + cell_width / 2) - font_size // 2, 25), str(i + 1), fill='white', font=font)
        # Right side labels
        draw.text((width + 75, 50 + int(i * cell_height + cell_height / 2) - font_size // 2), str(i + 1), fill='white', font=font)
        # Bottom side labels
        draw.text((50 + int(i * cell_width + cell_width / 2) - font_size // 2, height + 75), str(i + 1), fill='white', font=font)

    overlay = Image.new('RGBA', grid_image.size, (255, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for i in range(grid_size + 1):
        # Horizontal lines
        overlay_draw.line([(50, 50 + int(i * cell_height)), (50 + width, 50 + int(i * cell_height))], fill=(255, 255, 255, 128), width=3)
        # Vertical lines
        overlay_draw.line([(50 + int(i * cell_width), 50), (50 + int(i * cell_width), 50 + height)], fill=(255, 255, 255, 128), width=3)

    grid_image = Image.alpha_composite(grid_image.convert('RGBA'), overlay)
    return grid_image.convert('RGB')

def get_cell_coordinates(grid_size: int, target_cell: Tuple[int, int], image_size: Tuple[int, int]) -> Tuple[int, int]:
    """Get the coordinates of a cell in the grid."""
    row, col = target_cell
    cell_width = image_size[0] / grid_size
    cell_height = image_size[1] / grid_size
    x = int((col - 0.5) * cell_width)
    y = int((row - 0.5) * cell_height)
    return x, y

def draw_target_coordinates(image: Image.Image, coordinates: List[Tuple[int, int]]) -> Image.Image:
    """Draw the target coordinates on the image."""
    image = image.copy()
    label_offset = 50
    draw = ImageDraw.Draw(image)
    for coordinate in coordinates:
        adjusted_coordinates = (coordinate[0] + label_offset, coordinate[1] + label_offset)
        draw.ellipse((adjusted_coordinates[0] - 5, adjusted_coordinates[1] - 5, adjusted_coordinates[0] + 5, adjusted_coordinates[1] + 5), fill='red', outline='red')
    return image

def undim_target_cells(image: Image.Image, coordinates: List[Tuple[int, int]], grid_size: int) -> Image.Image:
    """Undim the target cells on the image and highlight them in red."""
    image = image.copy()
    width, height = image.size
    cell_width = (width - 100) / grid_size
    cell_height = (height - 100) / grid_size
    label_offset = 50

    for coordinate in coordinates:
        row, col = coordinate
        x1 = int((col - 1) * cell_width) + label_offset
        y1 = int((row - 1) * cell_height) + label_offset
        x2 = int(x1 + cell_width)
        y2 = int(y1 + cell_height)
        box = (x1, y1, x2, y2)
        cropped_section = image.crop(box)
        enhancer = ImageEnhance.Brightness(cropped_section)
        brightened_section = enhancer.enhance(2.0)  # Increase brightness to undim

        # Create a red overlay
        red_overlay = Image.new('RGBA', brightened_section.size, (255, 0, 0, 128))  # Semi-transparent red

        # Combine the brightened section with the red overlay
        highlighted_section = Image.alpha_composite(brightened_section.convert('RGBA'), red_overlay)

        image.paste(highlighted_section, box)

    return image

def main(target: str):
    """Main function to process the image and identify target cells."""
    image_file_path = os.path.join(config.ROOT_DIR_PATH, "../tests/assets/excel.png")
    image = load_and_downsample_image(image_file_path, DOWNSAMPLE_FACTOR)
    image = dim_image(image)
    grid_image = add_grid_labels(image, GRID_SIZE)
    grid_image.show()

    coordinates = []
    all_coordinates = []
    grid_image_with_target = None

    while True:
        if DO_CORRECTIONS and coordinates:
            correction_prompt = f"""
- Previously, someone specified these cells: {coordinates}. These cells have been highlighted in red.
- There may be an error. Please correct or confirm the previous assessment.
- In your analysis, include the position of the target relative to these previously specified cells.
- In your reasoning, describe how many cells to move in each direction to reach the target."""
        else:
            correction_prompt = "\n"

        prompt = f"""
Attached is an image containing a screenshot over which a grid has been overlaid.
The grid labels are white (255, 255, 255) on a red (255, 0, 0) background.
The grid lines are semi-transparent.
Your task is to identify the coordinates of grid cells containing the target.
The target is: "{target}".

Respond in JSON with the following keys:
{{
    "target": "<the target you are looking for>",
    "analysis": "<natural language description of the location of the target, adjacent elements, and anything else that is relevant to identifying the correct row and column>",
    "reasoning": "<natural language step by step reasoning of how you are determining the grid coordinates of the target>",
    "coordinates": [(<grid row>, <grid col>), (<grid row>, <grid col>), ...],
}}

**Important Instructions**:
- Focus on the overlaid grid for coordinate determination.
- Do not confuse the overlaid grid with any internal grids in the screenshot, such as those in spreadsheets.
- Verify the grid coordinates carefully.{correction_prompt}
- LOOK CAREFULLY AT THE IMAGE to avoid mistakes.
- You must specify all cells containing any part of the target, so that the target is COMPLETELY COVERED.

Wrap your code in triple backticks: ```
"""

        if not DO_CORRECTIONS:
            config.CACHE_ENABLED = False
        response = DRIVER.prompt(
            prompt=prompt,
            system_prompt="You are an expert GUI interpreter. You are precise and accurate.",
            images=[grid_image_with_target or grid_image] if DO_CORRECTIONS else [grid_image],
        )
        result = parse_code_snippet(response)
        coordinates = sorted(result["coordinates"])
        logger.info(f"{coordinates=}")
        coord_list = [get_cell_coordinates(GRID_SIZE, coord, image.size) for coord in coordinates]
        #grid_image_with_target = draw_target_coordinates(grid_image, coord_list)
        grid_image_with_target = undim_target_cells(grid_image, coordinates, GRID_SIZE)
        #grid_image_with_target = draw_target_coordinates(grid_image_with_target, coord_list)

        grid_image_with_target.show()

        if coordinates in all_coordinates:
            break

        all_coordinates.append(coordinates)

if __name__ == "__main__":
    #main("save button")
    main("Spreadsheet cell A1")
    #main("cell containing 'Marketing'")
    #main("font selector")
    #main("zoom slider")
    #main("paste button")
    #main("font size dropdown")
    #main("13-May")
    #main("Engineering")
    #main("Sales")
    #main("Spreadsheet area")
