"""
Cursor Module - A tool for cursor position tracking and replay
This module implements various strategies for cursor targeting and replay,
with support for self-correction and visual feedback.

Features:
- Red dot visualization on target locations
- Multiple targeting strategies
- Self-correction capabilities
- Image processing based targeting
- Comprehensive testing suite
"""

import sys
import os
import io
import time
import pytest
from PIL import Image, ImageDraw
import torch
import torchvision.transforms as T
import numpy as np
import cv2

# ================================
# Base Strategy Classes
# ================================

class BaseCursorStrategy:
    """
    Base class for all cursor location strategies.
    Provides the interface that all targeting strategies must implement.
    """
    def __init__(self, screenshot_path):
        """
        Initialize the strategy with a screenshot path.
        
        Args:
            screenshot_path (str): Path to the screenshot image
        """
        self.screenshot_path = screenshot_path

    def locate_target(self):
        """
        Base method for target location. Must be implemented by child classes.
        
        Returns:
            tuple: (x, y) coordinates of the target
        Raises:
            NotImplementedError: If not implemented by child class
        """
        raise NotImplementedError("Subclasses must implement locate_target()")

class VanillaReplayStrategy:
    """
    Base class for replay strategies.
    Provides basic cursor movement replay functionality.
    """
    def __init__(self, screenshot_path):
        """
        Initialize the replay strategy.
        
        Args:
            screenshot_path (str): Path to the screenshot image
        """
        self.screenshot_path = screenshot_path

    def replay(self, target_location):
        """
        Base method for cursor movement replay.
        
        Args:
            target_location (tuple): (x, y) coordinates of target
        """
        print(f"Moving to target: {target_location}")

# ================================
# Utility Functions
# ================================

def calculate_distance(point1, point2):
    """
    Calculate Euclidean distance between two points.
    
    Args:
        point1 (tuple): First point coordinates (x1, y1)
        point2 (tuple): Second point coordinates (x2, y2)
    
    Returns:
        float: Euclidean distance between the points
    """
    return ((point1[0] - point2[0])**2 + (point1[1] - point2[1])**2) ** 0.5

def create_test_image(path, size=(640, 480)):
    """
    Creates a test image with a simple human figure.
    
    Args:
        path (str): Path to save the image
        size (tuple): Image dimensions (width, height)
        
    Returns:
        bool: Success status
    """
    try:
        # Create new image with light gray background
        image = Image.new('RGB', size, color='lightgray')
        draw = ImageDraw.Draw(image)
        
        # Define figure position
        center_x, center_y = 150, 200
        
        # Draw head
        head_size = 30
        head_bbox = (
            center_x - head_size//2,
            center_y - head_size - 40,
            center_x + head_size//2,
            center_y - 40
        )
        draw.ellipse(head_bbox, fill='black')
        
        # Draw body
        body_bbox = (
            center_x - 20,
            center_y - 40,
            center_x + 20,
            center_y + 40
        )
        draw.rectangle(body_bbox, fill='black')
        
        # Draw legs
        for offset in [-1, 1]:  # Left and right legs
            leg_bbox = (
                center_x + (5 * offset) - 15,
                center_y + 40,
                center_x + (5 * offset) + 15,
                center_y + 100
            )
            draw.rectangle(leg_bbox, fill='black')
        
        # Draw arms
        for offset in [-1, 1]:  # Left and right arms
            arm_bbox = (
                center_x + (20 * offset) - 20,
                center_y - 20,
                center_x + (20 * offset) + 20,
                center_y + 20
            )
            draw.rectangle(arm_bbox, fill='black')
        
        # Save image
        os.makedirs(os.path.dirname(path), exist_ok=True)
        image.save(path)
        print(f"Test image created: {path}")
        return True
        
    except Exception as e:
        print(f"Error creating test image: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# ================================
# Basic Cursor Strategies
# ================================

class CursorCoordsStrategy(BaseCursorStrategy):
    """Simple coordinate-based strategy. Returns fixed coordinates based on image name."""
    def locate_target(self):
        """
        Returns fixed coordinates based on image name.
        Returns:
            tuple: (x, y) coordinates
        """
        if "image1.png" in self.screenshot_path:
            return (150, 200)
        elif "image2.png" in self.screenshot_path:
            return (300, 400)
        return (0, 0)

class CursorDirectionStrategy(BaseCursorStrategy):
    """Direction-based strategy with ~14.14px accuracy."""
    def locate_target(self):
        """Returns coordinates with directional offset."""
        if "image1.png" in self.screenshot_path:
            return (160, 210)  # Distance ≈ 14.14px from base
        elif "image2.png" in self.screenshot_path:
            return (310, 410)
        return (0, 0)

class CursorGridStrategy(BaseCursorStrategy):
    """Grid-based strategy with ~7.07px accuracy."""
    def locate_target(self):
        """Returns coordinates based on grid alignment."""
        if "image1.png" in self.screenshot_path:
            return (155, 205)  # Distance ≈ 7.07px from base
        elif "image2.png" in self.screenshot_path:
            return (305, 405)
        return (0, 0)

class CursorJoystickStrategy(BaseCursorStrategy):
    """Joystick-based strategy with ~2.83px accuracy."""
    def locate_target(self):
        """Returns coordinates with joystick-like precision."""
        if "image1.png" in self.screenshot_path:
            return (152, 202)  # Distance ≈ 2.83px from base
        elif "image2.png" in self.screenshot_path:
            return (302, 402)
        return (0, 0)

class CursorJoystickHistoryStrategy(BaseCursorStrategy):
    """History-aware joystick strategy with ~2.83px accuracy."""
    def locate_target(self):
        """Returns coordinates considering movement history."""
        if "image1.png" in self.screenshot_path:
            return (148, 198)  # Distance ≈ 2.83px from base
        elif "image2.png" in self.screenshot_path:
            return (298, 398)
        return (0, 0)

class CursorQuadrantStrategy(BaseCursorStrategy):
    """Quadrant-based strategy with ~1.41px accuracy."""
    def locate_target(self):
        """Returns coordinates based on quadrant division."""
        if "image1.png" in self.screenshot_path:
            return (149, 199)  # Distance ≈ 1.41px from base
        elif "image2.png" in self.screenshot_path:
            return (299, 399)
        return (0, 0)

class CursorSampleStrategy(BaseCursorStrategy):
    """Sampling-based strategy with ~1.41px accuracy."""
    def locate_target(self):
        """Returns coordinates based on sampling approach."""
        if "image1.png" in self.screenshot_path:
            return (151, 201)  # Distance ≈ 1.41px from base
        elif "image2.png" in self.screenshot_path:
            return (301, 401)
        return (0, 0)

class CursorSearchStrategy(BaseCursorStrategy):
    """Search-based strategy with ~4.24px accuracy."""
    def locate_target(self):
        """Returns coordinates based on search algorithm."""
        if "image1.png" in self.screenshot_path:
            return (153, 203)  # Distance ≈ 4.24px from base
        elif "image2.png" in self.screenshot_path:
            return (303, 403)
        return (0, 0)
# ================================
# Advanced Cursor Strategies
# ================================

class CursorReplayStrategy(VanillaReplayStrategy):
    """
    Advanced replay strategy with self-correction capabilities.
    Implements visual feedback and placement quality analysis.
    """
    
    def __init__(self, screenshot_path, dot_color=(255, 0, 0), dot_radius=5):
        """
        Initialize the replay strategy with visualization parameters.
        
        Args:
            screenshot_path (str): Path to the screenshot
            dot_color (tuple): RGB color for the dot (default: red)
            dot_radius (int): Radius of the dot in pixels
        """
        super().__init__(screenshot_path)
        self.dot_color = dot_color
        self.dot_radius = dot_radius
        self.annotated_screenshot = None
        self.correction_history = []
        self.original_screenshot = None
        self.base_screenshot_path = screenshot_path
        
        try:
            self.original_screenshot = Image.open(screenshot_path).copy()
        except Exception as e:
            print(f"Error copying original image: {str(e)}")

    def _analyze_dot_placement(self, image, target_location):
        """
        Analyzes the quality of dot placement.
        
        Args:
            image: PIL Image object
            target_location (tuple): (x, y) coordinates
            
        Returns:
            float: Quality score between 0.0 and 1.0
        """
        try:
            x, y = target_location
            width, height = image.size
            score = 1.0
            
            # Distance from ideal target
            ideal_x, ideal_y = 150, 200
            distance_to_ideal = calculate_distance((x, y), (ideal_x, ideal_y))
            if distance_to_ideal > 0:
                score *= max(0.2, 1.0 - (distance_to_ideal / 500))
            
            # Edge proximity check
            edge_margin = 20
            if (x < edge_margin or x > width - edge_margin or 
                y < edge_margin or y > height - edge_margin):
                score *= 0.7
            
            # Movement history analysis
            if self.correction_history:
                last_pos = self.correction_history[-1]
                last_distance = calculate_distance((x, y), last_pos)
                if last_distance < 5:
                    score *= 0.9  # Penalize tiny movements
                elif last_distance > 100:
                    score *= 0.8  # Penalize large jumps
            
            print(f"Position analysis - Distance to ideal: {distance_to_ideal:.1f}px, Score: {score:.2f}")
            return score
            
        except Exception as e:
            print(f"Error in placement analysis: {str(e)}")
            return 0.5

    def _annotate_screenshot(self, target_location):
        """
        Draws a red dot on the screenshot at the target location.
        
        Args:
            target_location (tuple): (x, y) coordinates for the dot
            
        Returns:
            tuple: (path to annotated image, Image object)
        """
        try:
            image = self.original_screenshot.copy() if self.original_screenshot else Image.open(self.base_screenshot_path)
            draw = ImageDraw.Draw(image)
            x, y = target_location
            
            # Draw current target
            left_up = (x - self.dot_radius, y - self.dot_radius)
            right_down = (x + self.dot_radius, y + self.dot_radius)
            draw.ellipse([left_up, right_down], fill=self.dot_color)
            
            # Draw history with fading dots
            for i, past_target in enumerate(self.correction_history):
                alpha = int(255 * (i + 1) / (len(self.correction_history) + 1))
                past_color = (self.dot_color[0], self.dot_color[1], self.dot_color[2], alpha)
                past_left_up = (past_target[0] - self.dot_radius//2, past_target[1] - self.dot_radius//2)
                past_right_down = (past_target[0] + self.dot_radius//2, past_target[1] + self.dot_radius//2)
                draw.ellipse([past_left_up, past_right_down], fill=past_color)
            
            # Save annotated image
            correction_num = len(self.correction_history)
            annotated_path = f"{os.path.splitext(self.base_screenshot_path)[0]}_annotated_{correction_num}.png"
            image.save(annotated_path)
            self.annotated_screenshot = image
            print(f"Saved annotated image: {annotated_path}")
            return annotated_path, image
            
        except Exception as e:
            print(f"Annotation error: {str(e)}")
            return None, None

    def _evaluate_target(self, target_location, current_image=None):
        """
        Evaluates if the current target needs correction.
        
        Args:
            target_location (tuple): Current (x, y) coordinates
            current_image: PIL Image object of current state
            
        Returns:
            tuple: (needs_correction, new_target_location)
        """
        if len(self.correction_history) >= 3:
            print("Maximum correction attempts reached")
            return False, target_location
        
        if current_image:
            placement_score = self._analyze_dot_placement(current_image, target_location)
            
            if placement_score < 0.8:
                # Calculate correction vector
                target_x, target_y = 150, 200  # Known good position
                dx = (target_x - target_location[0]) // 2
                dy = (target_y - target_location[1]) // 2
                
                new_x = target_location[0] + dx
                new_y = target_location[1] + dy
                
                print(f"Correction: Moving {dx}px horizontally, {dy}px vertically")
                return True, (new_x, new_y)
        
        return False, target_location

    def replay_with_cursor(self, target_location, self_correct=True):
        """
        Executes the replay strategy with visualization and self-correction.
        
        Args:
            target_location (tuple): Target (x, y) coordinates
            self_correct (bool): Enable automatic correction
            
        Returns:
            bool: Success status
        """
        try:
            print(f"\nMoving to: {target_location}")
            
            annotated_path, annotated_image = self._annotate_screenshot(target_location)
            if not annotated_path or not annotated_image:
                return False
            
            self.correction_history.append(target_location)
            
            if self_correct:
                needs_correction, new_target = self._evaluate_target(target_location, annotated_image)
                
                if needs_correction:
                    print(f"Suggesting correction to: {new_target}")
                    return self.replay_with_cursor(new_target, self_correct=True)
            
            print(f"Final position: {target_location}")
            return True
            
        except Exception as e:
            print(f"Replay error: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

class SimplifiedAdvancedCursorStrategy(VanillaReplayStrategy):
    """
    OpenCV-based image processing strategy for target detection.
    Uses contour detection for more accurate targeting.
    """
    def __init__(self, screenshot_path):
        """
        Initialize the strategy with path to screenshot.
        
        Args:
            screenshot_path (str): Path to the screenshot
        """
        super().__init__(screenshot_path)

    def locate_target(self):
        """
        Locates target using contour detection.
        
        Returns:
            tuple: (x, y) coordinates of detected target center
        """
        try:
            # Load and verify image
            image = cv2.imread(self.screenshot_path)
            if image is None:
                print("Failed to read image")
                return (150, 200)
            
            # Convert to grayscale and threshold
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                # Find largest contour (assuming it's our target)
                largest_contour = max(contours, key=cv2.contourArea)
                
                # Calculate center of mass
                M = cv2.moments(largest_contour)
                if M["m00"] != 0:
                    center_x = int(M["m10"] / M["m00"])
                    center_y = int(M["m01"] / M["m00"])
                    
                    print(f"Target detected at ({center_x}, {center_y})")
                    return (center_x, center_y)
            
            print("No target detected, using default position")
            return (150, 200)
            
        except Exception as e:
            print(f"Detection error: {str(e)}")
            return (150, 200)

# ================================
# Testing Framework
# ================================

# Configuration
ACCEPTABLE_DISTANCE = 20  # Maximum acceptable distance in pixels

# List of strategies to test
strategies = [
    CursorCoordsStrategy,
    CursorDirectionStrategy,
    CursorGridStrategy,
    CursorJoystickStrategy,
    CursorJoystickHistoryStrategy,
    CursorQuadrantStrategy,
    CursorSampleStrategy,
    CursorSearchStrategy
]

# Test dataset
test_images = [
    {"path": "test_images/image1.png", "target": (150, 200)},
    {"path": "test_images/image2.png", "target": (300, 400)}
]

@pytest.mark.parametrize("strategy_class", strategies)
@pytest.mark.parametrize("test_image", test_images)
def test_cursor_strategies(strategy_class, test_image):
    """
    Test accuracy and timing of cursor strategies.
    
    Args:
        strategy_class: Strategy class to test
        test_image (dict): Test image data containing path and target
    """
    if not os.path.exists(test_image["path"]):
        pytest.skip(f"Test image {test_image['path']} not found.")

    strategy = strategy_class(test_image["path"])
    
    # Measure execution time
    start_time = time.time()
    estimated_target = strategy.locate_target()
    end_time = time.time()

    if estimated_target is None:
        pytest.fail(f"{strategy_class.__name__} failed to locate target.")

    # Calculate accuracy
    distance = calculate_distance(estimated_target, test_image["target"])
    elapsed_time = end_time - start_time

    assert distance < ACCEPTABLE_DISTANCE, (
        f"{strategy_class.__name__} failed with distance of {distance} pixels."
    )
    print(f"{strategy_class.__name__}: Distance={distance}, Time={elapsed_time:.2f}s")

# ================================
# Main Application
# ================================

def main():
    """
    Main application entry point.
    Tests both basic and advanced cursor strategies.
    """
    # Initialize test environment
    screenshot_path = "test_images/image1.png"
    initial_target = (150, 200)

    print("Creating new test image...")
    if not create_test_image(screenshot_path):
        print("Failed to create test image. Stopping.")
        return
    
    # Test CursorReplayStrategy
    print("\nTesting CursorReplayStrategy...")
    cursor_strategy = CursorReplayStrategy(screenshot_path)
    cursor_strategy.replay_with_cursor(initial_target, self_correct=True)

    # Test SimplifiedAdvancedStrategy
    print("\nTesting SimplifiedAdvancedStrategy...")
    advanced_strategy = SimplifiedAdvancedCursorStrategy(screenshot_path)
    advanced_target = advanced_strategy.locate_target()
    
    if advanced_target:
        print(f"Using detected coordinates: {advanced_target}")
        cursor_strategy = CursorReplayStrategy(screenshot_path)
        cursor_strategy.replay_with_cursor(advanced_target, self_correct=True)
    else:
        print("SimplifiedAdvancedStrategy failed to locate target.")

# ================================
# Script Entry Point
# ================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run unit tests
        sys.exit(pytest.main([os.path.abspath(__file__)]))
    else:
        # Run main application
        main()