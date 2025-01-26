"""This module defines the models used in the OpenAdapt system."""

from collections import OrderedDict
from copy import deepcopy
from itertools import zip_longest
from typing import Any, Type, Union
import copy
import io
import sys
import textwrap

from bs4 import BeautifulSoup
from pynput import keyboard
from PIL import Image, ImageChops
import numpy as np
import sqlalchemy as sa

from openadapt.config import config
from openadapt.custom_logger import logger
from openadapt.drivers import anthropic
from openadapt.db import db
from openadapt.privacy.base import ScrubbingProvider, TextScrubbingMixin
from openadapt.privacy.providers import ScrubProvider
from openadapt.decorators import ForceFloat

EMPTY_VALS = [None, "", [], (), {}]


class Recording(db.Base):
    """Class representing a recording in the database."""

    __tablename__ = "recording"
    _repr_ignore_attrs = ["config"]

    id = sa.Column(sa.Integer, primary_key=True)
    timestamp = sa.Column(ForceFloat)
    monitor_width = sa.Column(sa.Integer)
    monitor_height = sa.Column(sa.Integer)
    double_click_interval_seconds = sa.Column(sa.Numeric(asdecimal=False))
    double_click_distance_pixels = sa.Column(sa.Numeric(asdecimal=False))
    platform = sa.Column(sa.String)
    task_description = sa.Column(sa.String)
    video_start_time = sa.Column(ForceFloat)
    config = sa.Column(sa.JSON)

    original_recording_id = sa.Column(sa.ForeignKey("recording.id"))
    original_recording = sa.orm.relationship(
        "Recording",
        back_populates="copies",
        remote_side=[id],
    )
    copies = sa.orm.relationship(
        "Recording", back_populates="original_recording", cascade="all, delete-orphan"
    )

    action_events = sa.orm.relationship(
        "ActionEvent",
        back_populates="recording",
        order_by="ActionEvent.timestamp",
        cascade="all, delete-orphan",
    )
    screenshots = sa.orm.relationship(
        "Screenshot",
        back_populates="recording",
        order_by="Screenshot.timestamp",
        cascade="all, delete-orphan",
    )
    window_events = sa.orm.relationship(
        "WindowEvent",
        back_populates="recording",
        order_by="WindowEvent.timestamp",
        cascade="all, delete-orphan",
    )
    browser_events = sa.orm.relationship(
        "BrowserEvent",
        back_populates="recording",
        order_by="BrowserEvent.timestamp",
        cascade="all, delete-orphan",
    )
    scrubbed_recordings = sa.orm.relationship(
        "ScrubbedRecording", back_populates="recording", cascade="all, delete-orphan"
    )
    audio_info = sa.orm.relationship(
        "AudioInfo", back_populates="recording", cascade="all, delete-orphan"
    )

    _processed_action_events = None

    @property
    def processed_action_events(self) -> list:
        """Get the processed action events for the recording."""
        from openadapt import events
        from openadapt.db import crud

        if not self._processed_action_events:
            session = crud.get_new_session(read_only=True)
            self._processed_action_events = events.get_events(session, self)
            # Preload screenshots to avoid lazy loading later
            for event in self._processed_action_events:
                event.screenshot
        return self._processed_action_events

    def scrub(self, scrubber: ScrubbingProvider) -> None:
        """Scrub the recording.

        Args:
            scrubber (ScrubbingProvider): The scrubbing provider to use.
        """
        self.task_description = scrubber.scrub_text(self.task_description)


class ActionEvent(db.Base):
    """Class representing an action event in the database."""

    __tablename__ = "action_event"
    _repr_ignore_attrs = ["reducer_names"]

    _segment_description_separator = ";"

    id = sa.Column(sa.Integer, primary_key=True)
    name = sa.Column(sa.String)
    timestamp = sa.Column(ForceFloat)
    recording_timestamp = sa.Column(ForceFloat)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    screenshot_timestamp = sa.Column(ForceFloat)
    screenshot_id = sa.Column(sa.ForeignKey("screenshot.id"))
    window_event_timestamp = sa.Column(ForceFloat)
    window_event_id = sa.Column(sa.ForeignKey("window_event.id"))
    browser_event_timestamp = sa.Column(ForceFloat)
    browser_event_id = sa.Column(sa.ForeignKey("browser_event.id"))
    mouse_x = sa.Column(sa.Numeric(asdecimal=False))
    mouse_y = sa.Column(sa.Numeric(asdecimal=False))
    mouse_dx = sa.Column(sa.Numeric(asdecimal=False))
    mouse_dy = sa.Column(sa.Numeric(asdecimal=False))
    active_segment_description = sa.Column(sa.String)
    _available_segment_descriptions = sa.Column(
        "available_segment_descriptions",
        sa.String,
    )
    mouse_button_name = sa.Column(sa.String)
    mouse_pressed = sa.Column(sa.Boolean)
    key_name = sa.Column(sa.String)
    key_char = sa.Column(sa.String)
    key_vk = sa.Column(sa.String)
    canonical_key_name = sa.Column(sa.String)
    canonical_key_char = sa.Column(sa.String)
    canonical_key_vk = sa.Column(sa.String)
    parent_id = sa.Column(sa.Integer, sa.ForeignKey("action_event.id"))
    element_state = sa.Column(sa.JSON)
    disabled = sa.Column(sa.Boolean, default=False)

    scrubbed_text = sa.Column(sa.String)
    scrubbed_canonical_text = sa.Column(sa.String)

    def __new__(cls, *args: tuple, **kwargs: dict) -> "ActionEvent":
        """Create a new instance; also called when loading from db."""
        instance = super(ActionEvent, cls).__new__(cls)
        instance.reducer_names = set()
        return instance

    def __init__(self, **kwargs: dict) -> None:
        """Initialize attributes first, then properties."""
        super().__init__()

        # Temporary dictionary to hold property values
        properties = {}

        # Introspect to determine properties
        prop_keys = [
            name
            for name, obj in type(self).__dict__.items()
            if isinstance(obj, property)
        ]

        # Set non-property attributes first
        for key, value in kwargs.items():
            if key in prop_keys:
                properties[key] = value
            else:
                setattr(self, key, value)

        # Now handle properties
        for key, value in properties.items():
            setattr(self, key, value)

    # TODO: rename "available" to "target"
    @property
    def available_segment_descriptions(self) -> list[str]:
        """Gets the available segment descriptions."""
        if self._available_segment_descriptions:
            return self._available_segment_descriptions.split(
                self._segment_description_separator
            )
        else:
            return []

    @available_segment_descriptions.setter
    def available_segment_descriptions(self, value: list[str]) -> None:
        """Sets the available segment descriptions."""
        self._available_segment_descriptions = self._segment_description_separator.join(
            value
        )

    children = sa.orm.relationship("ActionEvent")
    # TODO: replacing the above line with the following two results in an error:
    #     AttributeError: 'list' object has no attribute '_sa_instance_state'
    # children = sa.orm.relationship(
    #     "ActionEvent", remote_side=[id], back_populates="parent"
    # )
    # parent = sa.orm.relationship(
    #     "ActionEvent", remote_side=[parent_id], back_populates="children"
    # )  # noqa: E501

    recording = sa.orm.relationship("Recording", back_populates="action_events")
    screenshot = sa.orm.relationship("Screenshot", back_populates="action_event")
    window_event = sa.orm.relationship("WindowEvent", back_populates="action_events")
    browser_event = sa.orm.relationship("BrowserEvent", back_populates="action_events")

    # TODO: playback_timestamp / original_timestamp

    def _key(
        self, key_name: str, key_char: str, key_vk: str
    ) -> keyboard.Key | keyboard.KeyCode | str | None:
        """Helper method to determine the key attribute based on available data."""
        if key_name:
            key = keyboard.Key[key_name]
        elif key_char:
            key = key_char
        elif key_vk:
            # TODO: verify this is correct
            key = keyboard.KeyCode.from_vk(int(key_vk))
        else:
            key = None
        return key

    @property
    def key(self) -> keyboard.Key | keyboard.KeyCode | str | None:
        """Get the key associated with the action event."""
        logger.trace(f"{self.name=} {self.key_name=} {self.key_char=} {self.key_vk=}")
        return self._key(
            self.key_name,
            self.key_char,
            self.key_vk,
        )

    @property
    def canonical_key(self) -> keyboard.Key | keyboard.KeyCode | str | None:
        """Get the canonical key associated with the action event."""
        logger.trace(
            f"{self.name=} "
            f"{self.canonical_key_name=} "
            f"{self.canonical_key_char=} "
            f"{self.canonical_key_vk=}"
        )
        return self._key(
            self.canonical_key_name,
            self.canonical_key_char,
            self.canonical_key_vk,
        )

    def _text(
        self,
        canonical: bool = False,
        name_prefix: str = config.ACTION_TEXT_NAME_PREFIX,
        name_suffix: str = config.ACTION_TEXT_NAME_SUFFIX,
    ) -> str | None:
        """Helper method to generate the text representation of the action event."""
        sep = config.ACTION_TEXT_SEP
        if self.children:
            parts = [
                child.canonical_text if canonical else child.text
                for child in [child for child in self.children if child.name == "press"]
            ]
            if any(parts):
                # str is necessary for canonical=True named keys
                # e.g. canonical(<esc>) == <53> (darwin)
                text = sep.join([str(part) for part in parts])
            else:
                text = None
        else:
            if canonical:
                key_attr = self.canonical_key
                key_name_attr = self.canonical_key_name
            else:
                key_attr = self.key
                key_name_attr = self.key_name
            if key_name_attr:
                text = f"{name_prefix}{key_attr}{name_suffix}".replace(
                    "Key.",
                    "",
                )
            else:
                text = key_attr
        return str(text) if text else ""

    @property
    def text(self) -> str:
        """Get the text representation of the action event."""
        if self.scrubbed_text:
            return self.scrubbed_text
        return self._text()

    @text.setter
    def text(self, value: str) -> None:
        """Validate the text property. Useful for ActionModel(**action_dict)."""
        if not value == self.text:
            logger.warning(f"{value=} did not match {self.text=}")
            # if self.text:
            #    import ipdb; ipdb.set_trace()
            #    foo = 1

    @property
    def canonical_text(self) -> str:
        """Get the canonical text representation of the action event."""
        if self.scrubbed_canonical_text:
            return self.scrubbed_canonical_text
        return self._text(canonical=True)

    @canonical_text.setter
    def canonical_text(self, value: str) -> None:
        """Validate canonical_text property. Useful for ActionModel(**action_dict)."""
        if not value == self.canonical_text:
            logger.warning(f"{value=} did not match {self.canonical_text=}")

    @property
    def raw_text(self) -> str:
        """Return a string containing the raw action text (without separators)."""
        return "".join(self.text.split(config.ACTION_TEXT_SEP))

    def __str__(self) -> str:
        """Return a string representation of the action event."""
        attr_names = [
            "name",
            "mouse_x",
            "mouse_y",
            "mouse_dx",
            "mouse_dy",
            "mouse_button_name",
            "mouse_pressed",
            "text",
            "element_state",
        ]
        attrs = [getattr(self, attr_name) for attr_name in attr_names]
        attrs = [int(attr) if isinstance(attr, float) else attr for attr in attrs]
        attrs = [
            f"{attr_name}=`{attr}`"
            for attr_name, attr in zip(attr_names, attrs)
            if attr
        ]
        rval = " ".join(attrs)
        return rval

    @classmethod
    def from_children(cls: Type["ActionEvent"], children_dicts: list) -> "ActionEvent":
        """Create an ActionEvent instance from a list of child event dictionaries.

        Args:
            children_dicts (list): List of dictionaries representing child events.

        Returns:
            ActionEvent: An instance of ActionEvent with the specified child events.
        """
        children = [ActionEvent(**child_dict) for child_dict in children_dicts]
        return ActionEvent(children=children)

    @classmethod
    def from_dict(
        cls: Type["ActionEvent"],
        action_dict: dict,
        handle_separator_variations: bool = True,
    ) -> "ActionEvent":
        """Get an ActionEvent from a dict.

        See tests.openadapt.test_models::test_action_from_dict for behavior details.

        Args:
            action_dict (dict): A dictionary representing the action.
            handle_separator_variations (bool): Whether to attempt to handle variations
                in the key separator string (OpenAI sometimes returns "...><..." instead
                of " "...>-<...".

        Returns:
            (ActionEvent) The ActionEvent.
        """
        sep = config.ACTION_TEXT_SEP
        children = []
        if "text" in action_dict:
            name_prefix = config.ACTION_TEXT_NAME_PREFIX
            name_suffix = config.ACTION_TEXT_NAME_SUFFIX
            text = action_dict["text"]

            # Check if the text contains named keys (starting with the name prefix)
            # TODO: support sequences of the form <cmd>-a-<cmd>
            contains_named_keys = text.startswith(name_prefix) and text.endswith(
                name_suffix
            )

            if contains_named_keys:
                # Handle named keys, potentially with separator variations
                release_events = []
                default_sep = "".join([name_suffix, sep, name_prefix])
                key_seps = [default_sep]
                if handle_separator_variations:
                    variation_seps = ["".join([name_suffix, name_prefix])]
                    key_seps += variation_seps

                prefix_len = len(name_prefix)
                suffix_len = len(name_suffix)

                key_names = utils.split_by_separators(
                    text[prefix_len:-suffix_len],
                    key_seps,
                )
                canonical_key_names = utils.split_by_separators(
                    action_dict.get("canonical_text", "")[prefix_len:-suffix_len],
                    key_seps,
                )

                # Process each key name and canonical key name found
                for key_name, canonical_key_name in zip_longest(
                    key_names,
                    canonical_key_names,
                ):
                    press, release = cls._create_key_events(
                        key_name, canonical_key_name
                    )
                    children.append(press)
                    release_events.append(release)
                children += release_events[::-1]
            else:
                # Handle mixed sequences of named keys and regular characters
                split_text = text.split(sep)
                for part in split_text:
                    if part.startswith(name_prefix) and part.endswith(name_suffix):
                        # It's a named key
                        key_name = part[len(name_prefix) : -len(name_suffix)]
                        press, release = cls._create_key_events(key_name=key_name)
                    else:
                        # It's a character
                        press, release = cls._create_key_events(key_char=part)
                    children.append(press)
                    children.append(release)

        rval = ActionEvent(**action_dict, children=children)
        return rval

    @classmethod
    def _create_key_events(
        cls: Type["ActionEvent"],
        key_name: str | None = None,
        canonical_key_name: str | None = None,
        key_char: str | None = None,
        canonical_key_char: str | None = None,
    ) -> list["ActionEvent"]:
        # This helper function creates press and release events for a given key_name
        # TODO: remove canonical?
        press_event = cls(
            name="press",
            key_name=key_name,
            # canonical_key_name=canonical_key_name,
            key_char=key_char,
            # canonical_key_char=canonical_key_char,
        )
        release_event = cls(
            name="release",
            key_name=key_name,
            # canonical_key_name=canonical_key_name,
            key_char=key_char,
            # canonical_key_char=canonical_key_char,
        )
        return press_event, release_event

    def scrub(self, scrubber: ScrubbingProvider) -> None:
        """Scrub the action event."""
        self.scrubbed_text = scrubber.scrub_text(self.text, is_separated=True)
        self.scrubbed_canonical_text = scrubber.scrub_text(
            self.canonical_text, is_separated=True
        )
        self.key_char = scrubber.scrub_text(self.key_char)
        self.canonical_key_char = scrubber.scrub_text(self.canonical_key_char)
        self.key_vk = scrubber.scrub_text(self.key_vk)

    def to_prompt_dict(self) -> dict[str, Any]:
        """Convert into a dict, excluding properties not necessary for prompting.

        Returns:
            dictionary containing relevant properties from the ActionEvent.
        """
        action_dict = deepcopy(
            {
                key: val
                for key, val in utils.row2dict(self, follow=False).items()
                if val not in EMPTY_VALS
                and not key.endswith("timestamp")
                and not key.endswith("id")
                and key not in ["reducer_names"]
                # and not isinstance(getattr(models.ActionEvent, key), property)
            }
        )
        if self.active_segment_description:
            for key in ("mouse_x", "mouse_y", "mouse_dx", "mouse_dy"):
                if key in action_dict:
                    del action_dict[key]
        # TODO XXX: add target_segment_description?

        # Manually add properties to the dictionary
        if self.available_segment_descriptions:
            action_dict["available_segment_descriptions"] = (
                self.available_segment_descriptions
            )

        # TODO:
        """
        if self.active_browser_element:
            action_dict["active_browser_element"] = str(self.active_browser_element)
        if self.available_browser_elements:
            # TODO XXX: available browser_elements contains raw HTML. We need to
            # prompt to convert into descriptions.
            action_dict["available_browser_elements"] = str(
                self.available_browser_elements
            )
        """
        return action_dict

    @property
    def next_event(self) -> Union["ActionEvent", None]:
        """Get the next ActionEvent chronologically in the same recording.

        Returns:
            ActionEvent | None: The next ActionEvent, or None if this is the last event.
        """
        if not self.recording or not self.recording.action_events:
            return None

        current_index = self.recording.action_events.index(self)
        if current_index < len(self.recording.action_events) - 1:
            return self.recording.action_events[current_index + 1]

        return None

    def prompt_for_description(self, return_image: bool = False) -> str:
        """Use the Anthropic API to describe what is happening in the action event.

        Args:
            return_image (bool): Whether to return the image sent to the model.

        Returns:
            str: The description of the action event.
        """
        from openadapt.plotting import display_event

        image = display_event(
            self,
            marker_width_pct=0.05,
            marker_height_pct=0.05,
            darken_outside=0.7,
            display_text=False,
            marker_fill_transparency=0,
            dim_outside_window=False,
        )

        if self.text:
            description = f"Type '{self.raw_text}'"
        else:
            prompt = (
                "What user interface element is contained in the highlighted circle "
                "of the image?"
            )
            # TODO: disambiguate
            system_prompt = textwrap.dedent(
                """
                Briefly describe the user interface element in the screenshot at the
                highlighted location.
                For example:
                - "OK button"
                - "URL bar"
                - "Down arrow"
                DO NOT DESCRIBE ANYTHING OUTSIDE THE HIGHLIGHTED AREA.
                Do not append anything like "is contained within the highlighted circle
                in the calculator interface." Just name the user interface element.
            """
            )

            logger.info(f"system_prompt=\n{system_prompt}")
            logger.info(f"prompt=\n{prompt}")

            # Call the Anthropic API
            element = anthropic.prompt(
                prompt=prompt,
                system_prompt=system_prompt,
                images=[image],
            )

            if self.name == "move":
                description = f"Move mouse to '{element}'"
            elif self.name == "scroll":
                # TODO: "scroll to", dx/dy
                description = f"Scroll mouse on '{element}'"
            elif "click" in self.name:
                description = (
                    f"{self.mouse_button_name.capitalize()} {self.name} '{element}'"
                )
            else:
                raise ValueError(f"Unhandled {self.name=} {self}")

        if return_image:
            return description, image
        else:
            return description


class WindowEvent(db.Base):
    """Class representing a window event in the database."""

    __tablename__ = "window_event"

    id = sa.Column(sa.Integer, primary_key=True)
    recording_timestamp = sa.Column(ForceFloat)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    timestamp = sa.Column(ForceFloat)
    state = sa.Column(sa.JSON)
    title = sa.Column(sa.String)
    left = sa.Column(sa.Integer)
    top = sa.Column(sa.Integer)
    width = sa.Column(sa.Integer)
    height = sa.Column(sa.Integer)
    window_id = sa.Column(sa.String)

    recording = sa.orm.relationship("Recording", back_populates="window_events")
    action_events = sa.orm.relationship("ActionEvent", back_populates="window_event")

    @classmethod
    def get_active_window_event(
        cls: "WindowEvent",
        # TODO: rename to include_a11y_data
        include_window_data: bool = True,
    ) -> "WindowEvent":
        """Get the active window event.

        Args:
            include_window_data (bool): whether to include a11y data.

        Returns:
            (WindowEvent) the active window event.
        """
        from openadapt import window

        return WindowEvent(**window.get_active_window_data(include_window_data))

    def scrub(self, scrubber: ScrubbingProvider | TextScrubbingMixin) -> None:
        """Scrub the window event."""
        self.title = scrubber.scrub_text(self.title)
        if self.state is not None:
            self.state = scrubber.scrub_dict(self.state)

    def to_prompt_dict(
        self,
        include_data: bool = True,
        add_centroid: bool = True,
        remove_bbox: bool = False,
    ) -> dict[str, Any]:
        """Convert into a dict, excluding properties not necessary for prompting.

        Args:
            include_data (bool): Whether to retain the "data" property of the .state
                attribute (contains operating system accessibility API data).

        Returns:
            dictionary containing relevant properties from the WindowEvent.
        """
        window_dict = deepcopy(
            {
                key: val
                for key, val in utils.row2dict(self, follow=False).items()
                if val not in EMPTY_VALS
                and not key.endswith("timestamp")
                and not key.endswith("id")
                # and not isinstance(getattr(models.WindowEvent, key), property)
            }
        )

        if add_centroid:
            left = window_dict["left"]
            top = window_dict["top"]
            width = window_dict["width"]
            height = window_dict["height"]

            # Compute the centroid of the bounding box
            centroid_x = left + width / 2
            centroid_y = top + height / 2

            # Add centroid in the prompt dict { "centroid": }
            window_dict["centroid"] = {
                "x": centroid_x,
                "y": centroid_y,
            }

        if remove_bbox:
            window_dict.pop("left")
            window_dict.pop("top")
            window_dict.pop("width")
            window_dict.pop("height")

        if "state" in window_dict:
            if include_data:
                key_suffixes = [
                    "value",
                    "h",
                    "w",
                    "x",
                    "y",
                    "description",
                    "title",
                    "help",
                ]
                if sys.platform != "darwin":
                    logger.warning(
                        "key_suffixes have not yet been defined on {sys.platform=}."
                        "You can help by uncommenting the lines below and pasting "
                        "the contents of the window_dict into a new GitHub Issue."
                    )
                    # from pprint import pformat
                    # logger.info(f"window_dict=\n{pformat(window_dict)}")
                    # import ipdb; ipdb.set_trace()
                window_state = window_dict["state"]
                window_state["data"] = utils.clean_dict(
                    utils.filter_keys(
                        window_state["data"],
                        key_suffixes,
                    )
                )
            else:
                window_dict["state"].pop("data")
            window_dict["state"].pop("meta")
        return window_dict


class BrowserEvent(db.Base):
    """Class representing a browser event in the database."""

    __tablename__ = "browser_event"

    id = sa.Column(sa.Integer, primary_key=True)
    recording_timestamp = sa.Column(ForceFloat)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    message = sa.Column(sa.JSON)
    timestamp = sa.Column(ForceFloat)

    recording = sa.orm.relationship("Recording", back_populates="browser_events")
    action_events = sa.orm.relationship("ActionEvent", back_populates="browser_event")

    def __str__(self) -> str:
        """Returns a truncated string representation without modifying original data."""
        # Create a copy of the message to avoid modifying the original
        message_copy = copy.deepcopy(self.message)

        # Truncate the visibleHTMLString in the copied message if it exists
        if "visibleHTMLString" in message_copy:
            message_copy["visibleHTMLString"] = utils.truncate_html(
                message_copy["visibleHTMLString"], max_len=100
            )

        # Get all attributes except 'message'
        attributes = {
            attr: getattr(self, attr)
            for attr in self.__mapper__.columns.keys()
            if attr != "message"
        }

        # Construct the string representation dynamically
        base_repr = ", ".join(f"{key}={value}" for key, value in attributes.items())

        # Return the complete representation including the truncated message
        return f"BrowserEvent({base_repr}, message={message_copy})"

    def parse(self) -> tuple[BeautifulSoup, BeautifulSoup | None]:
        """Parses the visible HTML and optionally extracts the target element.

        This method processes the browser event to parse the visible HTML and,
        if the event has a targetId, extracts the target HTML element.

        Returns:
            A tuple containing:
            - BeautifulSoup: The parsed soup of the visible HTML.
            - BeautifulSoup | None: The target HTML element if the event type is
                "click"; otherwise, None.

        Raises:
            AssertionError: If the necessary data is missing.
        """
        message = self.message

        visible_html_string = message.get("visibleHTMLString")
        assert visible_html_string, "Cannot parse without visibleHTMLstring"

        # Parse the visible HTML using BeautifulSoup
        soup = utils.parse_html(visible_html_string)

        target_element = None

        # Fetch the target element using its data-id
        target_id = message.get("targetId")
        if target_id:
            target_element = soup.find(attrs={"data-id": target_id})
            assert target_element, f"No target element found for targetId: {target_id}"

        return soup, target_element

    # # TODO: implement
    # @classmethod
    # def get_active_browser_event(
    #     cls: "BrowserEvent",
    # ) -> "BrowserEvent":


class FrameCache:
    """Provide a caching mechanism for video frames to minimize IO operations.

    This class maintains a nested dictionary to store video frames by video
    filename and their respective timestamps. It offers functionalities to get
    frames from the cache or load them if they are not available in the cache.

    Attributes:
        capacity (int): The maximum number of frames that can be stored per video.
            If set to 0, the capacity is considered infinite.
        frames (dict): A nested dictionary to store frames by video filename and
            timestamp.
    """

    ENABLED = True

    def __init__(self, capacity: int = 0) -> None:
        """Initialize a new FrameCache instance with specified capacity.

        Args:
            capacity (int): The maximum number of frames to cache per video file.
        """
        self.capacity = capacity
        # Nested dictionary to store frames by video filename and timestamp
        self.frames = {}

    def get_frame(self, video_file_path: str, timestamp: float) -> Image.Image:
        """Retrieve a frame by video file path and timestamp from the cache.

        If the frame is not available in the cache, it logs a warning and loads
        the frame into the cache before returning it.

        Args:
            video_file_path (str): The path to the video file.
            timestamp (float): The timestamp of the frame in the video.

        Returns:
            Image.Image: The requested video frame.
        """
        # Check if the frame is cached
        if not (
            video_file_path in self.frames and timestamp in self.frames[video_file_path]
        ):
            # Issue a warning if the frame needs to be loaded without prior caching
            logger.warning(
                f"Frame at timestamp {timestamp} from {video_file_path} was not "
                "pre-cached. Loading it now, but consider using cache_frames to load "
                "batches."
            )
            # Load the frame since it wasn't cached
            self.cache_frames(video_file_path, [timestamp])
        return self.frames[video_file_path][timestamp]

    def cache_frames(self, video_file_path: str, timestamps: list[float]) -> None:
        """Cache multiple frames from a video file at specified timestamps.

        This method checks which frames are not already cached and loads them.
        It respects the capacity limit of the cache, potentially evicting the oldest
        cached frame to make room for new ones if the capacity is exceeded.

        Args:
            video_file_path (str): The path to the video file.
            timestamps (list[float]): A list of timestamps of frames to cache.

        Returns:
            None
        """
        # avoid circular import
        from openadapt import video

        # Ensure the dictionary for this video file is initialized
        if video_file_path not in self.frames:
            self.frames[video_file_path] = OrderedDict()

        # Load only the frames that have not been loaded yet
        uncached_timestamps = [
            t for t in timestamps if t not in self.frames[video_file_path]
        ]
        frames = video.extract_frames(video_file_path, uncached_timestamps)
        # Add loaded frames to cache, respecting capacity if not infinite
        for timestamp, frame in zip(uncached_timestamps, frames):
            if self.capacity > 0 and len(self.frames[video_file_path]) >= self.capacity:
                # Remove oldest frame if capacity is exceeded
                self.frames[video_file_path].popitem(last=False)
            self.frames[video_file_path][timestamp] = frame


# for use in Screenshot.image
frame_cache = FrameCache()


class Screenshot(db.Base):
    """Class representing a screenshot in the database."""

    __tablename__ = "screenshot"

    id = sa.Column(sa.Integer, primary_key=True)
    recording_timestamp = sa.Column(ForceFloat)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    timestamp = sa.Column(ForceFloat)
    png_data = sa.Column(sa.LargeBinary)
    png_diff_data = sa.Column(sa.LargeBinary, nullable=True)
    png_diff_mask_data = sa.Column(sa.LargeBinary, nullable=True)
    # cropped_png_data = sa.Column(sa.LargeBinary, nullable=True)

    recording = sa.orm.relationship("Recording", back_populates="screenshots")
    action_event = sa.orm.relationship("ActionEvent", back_populates="screenshot")

    def __init__(
        self,
        *args: tuple,
        image: Image.Image | None = None,
        **kwargs: dict,
    ) -> None:
        """Initialize."""
        super().__init__(*args, **kwargs)
        self.initialize_instance_attributes()
        self._image = image

    def scrub(self, scrubber: ScrubbingProvider) -> None:
        """Scrub the screenshot."""

        def save_scrubbed_image(image: Image, setattr_name: str) -> None:
            """Save the scrubbed image."""
            scrubbed_image = scrubber.scrub_image(image)
            setattr(self, setattr_name, self.convert_png_to_binary(scrubbed_image))

        save_scrubbed_image(self.image, "png_data")
        if self.png_diff_data:
            save_scrubbed_image(self.diff, "png_diff_data")
        if self.png_diff_mask_data:
            save_scrubbed_image(self.diff_mask, "png_diff_mask_data")

    @sa.orm.reconstructor
    def initialize_instance_attributes(self) -> None:
        """Initialize attributes for both new and loaded objects."""
        # TODO: convert to png_data on save
        # TODO: replace prev with prev_timestamp?
        self.prev = None
        self._image = None
        self._cropped_image = None
        self._diff = None
        self._diff_mask = None
        self._base64 = None

    @property
    def image(self) -> Image.Image:
        """Get the image associated with the screenshot."""
        if not self._image:
            if self.png_data:
                self._image = self.convert_binary_to_png(self.png_data)
            else:
                # avoid circular import
                from openadapt import video

                video_file_path = video.get_video_file_path(self.recording_timestamp)
                if FrameCache.ENABLED:
                    if video_file_path not in frame_cache.frames:
                        screenshot_timestamps = [
                            screenshot.timestamp - self.recording.video_start_time
                            for screenshot in self.recording.screenshots
                        ]
                        frame_cache.cache_frames(video_file_path, screenshot_timestamps)
                    self._image = frame_cache.get_frame(
                        video_file_path,
                        self.timestamp - self.recording.video_start_time,
                    )
                else:
                    self._image = video.extract_frames(
                        video_file_path,
                        [self.timestamp - self.recording.video_start_time],
                    )[0]
        return self._image

    @property
    def cropped_image(self) -> Image.Image:
        """Return screenshot image cropped to corresponding action's active window."""
        if not self._cropped_image:
            # if events have been merged, the last event will be the parent, e.g.
            #   ipdb> [(action.name, action.timestamp) for action in self.action_event]
            #   [('move', 1714142176.1630979), ('click', 1714142174.4848516),
            #   ('singleclick', 1714142174.4537418)]
            # TODO: verify (e.g. assert)
            # TODO: rename action_event -> action_events?
            action_event = self.action_event[-1]
            self._cropped_image = self.crop_active_window(action_event)
            # TODO: save?
            # self.cropped_png_data = self.convert_png_to_binary(self._cropped_image)
        return self._cropped_image

    @property
    def base64(self) -> str:
        """Return data URI of JPEG encoded base64."""
        if not self._base64:
            self._base64 = utils.image2utf8(self.image)
        return self._base64

    @property
    def diff(self) -> Image.Image:
        """Get the difference between the current and previous screenshot."""
        if self.png_diff_data:
            return self.convert_binary_to_png(self.png_diff_data)

        assert self.prev, "Attempted to compute diff before setting prev"
        self._diff = ImageChops.difference(self.image, self.prev.image)
        return self._diff

    @property
    def diff_mask(self) -> Image.Image:
        """Get the difference mask between the current and previous screenshot."""
        if self.png_diff_mask_data:
            return self.convert_binary_to_png(self.png_diff_mask_data)

        if self.diff:
            self._diff_mask = self.diff.convert("1")
        return self._diff_mask

    @property
    def array(self) -> np.ndarray:
        """Get the NumPy array representation of the image."""
        return np.array(self.image)

    @classmethod
    def take_screenshot(cls: "Screenshot") -> "Screenshot":
        """Capture a screenshot."""
        image = utils.take_screenshot()
        screenshot = Screenshot(image=image)
        return screenshot

    def crop_active_window(self, action_event: ActionEvent) -> None:
        """Crop the screenshot to the active window defined by the action event."""
        window_event = action_event.window_event
        width_ratio, height_ratio = utils.get_scale_ratios(action_event)

        x0 = window_event.left * width_ratio
        y0 = window_event.top * height_ratio
        x1 = x0 + window_event.width * width_ratio
        y1 = y0 + window_event.height * height_ratio

        box = (x0, y0, x1, y1)
        cropped_image = self._image.crop(box)
        return cropped_image

    def convert_binary_to_png(self, image_binary: bytes) -> Image.Image:
        """Convert a binary image to a PNG image.

        Args:
            image_binary (bytes): The binary image data.

        Returns:
            Image: The PNG image.
        """
        buffer = io.BytesIO(image_binary)
        return Image.open(buffer)

    def convert_png_to_binary(self, image: Image.Image) -> bytes:
        """Convert a PNG image to binary image data.

        Args:
            image (Image): The PNG image.

        Returns:
            bytes: The binary image data.
        """
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()


class AudioInfo(db.Base):
    """Class representing the audio from a recording in the database."""

    __tablename__ = "audio_info"

    id = sa.Column(sa.Integer, primary_key=True)
    timestamp = sa.Column(ForceFloat)
    flac_data = sa.Column(sa.LargeBinary)
    transcribed_text = sa.Column(sa.String)
    recording_timestamp = sa.Column(ForceFloat)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    sample_rate = sa.Column(sa.Integer)
    words_with_timestamps = sa.Column(sa.Text)

    recording = sa.orm.relationship("Recording", back_populates="audio_info")


class PerformanceStat(db.Base):
    """Class representing a performance statistic in the database."""

    __tablename__ = "performance_stat"

    id = sa.Column(sa.Integer, primary_key=True)
    recording_timestamp = sa.Column(ForceFloat)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    event_type = sa.Column(sa.String)
    start_time = sa.Column(sa.Integer)
    end_time = sa.Column(sa.Integer)
    window_id = sa.Column(sa.String)


class MemoryStat(db.Base):
    """Class representing a memory usage statistic in the database."""

    __tablename__ = "memory_stat"

    id = sa.Column(sa.Integer, primary_key=True)
    recording_timestamp = sa.Column(sa.Integer)
    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    memory_usage_bytes = sa.Column(ForceFloat)
    timestamp = sa.Column(ForceFloat)


class ScrubbedRecording(db.Base):
    """Class representing a scrubbed recording in the database."""

    __tablename__ = "scrubbed_recording"

    id = sa.Column(sa.Integer, primary_key=True)
    timestamp = sa.Column(ForceFloat)

    recording_id = sa.Column(sa.ForeignKey("recording.id"))
    recording = sa.orm.relationship("Recording", back_populates="scrubbed_recordings")

    provider = sa.Column(sa.String)
    scrubbed = sa.Column(sa.Boolean)

    def get_provider_name(self) -> str:
        """Get the name of the scrubbing provider."""
        return ScrubProvider.as_options()[self.provider]

    def asdict(self) -> dict:
        """Return the scrubbed recording as a dictionary."""
        return {
            **super().asdict(),
            "provider": self.get_provider_name(),
            "recording": {
                "task_description": self.recording.task_description,
            },
            "original_recording": {
                "id": self.recording.original_recording_id,
                "task_description": self.recording.original_recording.task_description,
            },
        }


class Replay(db.Base):
    """Class representing a replay in the database."""

    __tablename__ = "replay"

    id = sa.Column(sa.Integer, primary_key=True)
    timestamp = sa.Column(ForceFloat)
    strategy_name = sa.Column(sa.String)
    strategy_args = sa.Column(sa.JSON)
    git_hash = sa.Column(sa.String)


def copy_sa_instance(sa_instance: db.Base, **kwargs: dict) -> db.Base:
    """Copy a SQLAlchemy instance.

    Args:
        sa_instance (Base): The SQLAlchemy instance to copy.
        **kwargs: Additional keyword arguments to pass to the copied instance.

    Returns:
        Base: The copied SQLAlchemy instance.
    """
    sa_instance.id

    table = sa_instance.__table__
    pk_columns = [k for k in table.primary_key.columns.keys()]
    fk_columns = [k.parent.name for k in table.foreign_keys]
    exclude_columns = pk_columns + fk_columns
    data = {
        c: getattr(sa_instance, c)
        for c in table.columns.keys()
        if c not in exclude_columns
    }
    data.update(kwargs)
    clone = sa_instance.__class__(**data)
    return clone


# avoid circular import
from openadapt import utils  # noqa
