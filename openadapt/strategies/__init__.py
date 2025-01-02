"""Package containing different replay strategies.

Module: __init__.py
"""

# flake8: noqa

from openadapt.strategies.base import BaseReplayStrategy
from openadapt.strategies.visual_browser import VisualBrowserReplayStrategy

# disabled because importing is expensive
# from openadapt.strategies.demo import DemoReplayStrategy
from openadapt.strategies.naive import NaiveReplayStrategy
from openadapt.strategies.segment import SegmentReplayStrategy
from openadapt.strategies.stateful import StatefulReplayStrategy
from openadapt.strategies.vanilla import VanillaReplayStrategy
from openadapt.strategies.visual import VisualReplayStrategy
from openadapt.strategies.cursor import CursorReplayStrategy

# add more strategies here
