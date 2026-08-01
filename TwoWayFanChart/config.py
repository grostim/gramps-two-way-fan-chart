# SPDX-License-Identifier: GPL-3.0-or-later
"""Validated immutable configuration for the Two-Way Fan Chart report."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any

try:
    from .model import GenerationLimits, PaperDimensions
except ImportError:  # Gramps loads add-ons as top-level modules.
    from model import GenerationLimits, PaperDimensions  # type: ignore[no-redef]


class PresetName(StrEnum):
    PUBLICATION = "publication"
    FAMILY = "family"
    COMPACT = "compact"
    CUSTOM = "custom"


class PaperSize(StrEnum):
    A5 = "A5"
    A4 = "A4"
    A3 = "A3"
    A2 = "A2"
    A1 = "A1"
    A0 = "A0"
    LETTER = "Letter"
    LEGAL = "Legal"
    TABLOID = "Tabloid"
    CUSTOM = "Custom"


class Orientation(StrEnum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    AUTOMATIC = "automatic"


class OutputFormat(StrEnum):
    SVG = "svg"
    PDF = "pdf"


class PrivacyMode(StrEnum):
    INCLUDE_ALL = "include_all"
    FULL_NAME_ONLY = "full_name_only"
    SURNAME_ONLY = "surname_only"
    REPLACE_IDENTITY = "replace_identity"
    EXCLUDE = "exclude"
    PUBLICATION_SAFE = "publication_safe"


@dataclass(frozen=True, slots=True)
class ChartConfig:
    """Validated settings consumed by all later report layers."""

    center_family: str = ""
    preset: PresetName = PresetName.PUBLICATION
    ancestor_generations: int = 5
    descendant_generations: int = 3
    paper_size: PaperSize = PaperSize.A0
    orientation: Orientation = Orientation.LANDSCAPE
    margin_mm: float = 12.0
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None
    output_format: OutputFormat = OutputFormat.SVG
    privacy_mode: PrivacyMode = PrivacyMode.INCLUDE_ALL
    background_color: str = "#FAF9F5"
    parent_family_policy: str = "primary"
    descendant_family_policy: str = "all"
    show_portraits: bool = True
    portrait_source: str = "first_image"
    respect_media_crop: bool = True
    portrait_treatment: str = "color"
    include_private: bool = True
    living_people_mode: int = 99
    years_past_death: int = 0

    def __post_init__(self) -> None:
        enum_fields = (
            ("preset", self.preset, PresetName),
            ("paper size", self.paper_size, PaperSize),
            ("orientation", self.orientation, Orientation),
            ("output format", self.output_format, OutputFormat),
            ("privacy mode", self.privacy_mode, PrivacyMode),
        )
        for label, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{label} must be a {enum_type.__name__}")

        choices = {
            "parent_family_policy": {"primary", "biological", "first"},
            "descendant_family_policy": {"all", "primary", "first"},
            "portrait_source": {"first_image", "tagged_portrait", "primary"},
            "portrait_treatment": {"color", "grayscale", "sepia"},
        }
        for field_name, allowed in choices.items():
            if getattr(self, field_name) not in allowed:
                raise ValueError(f"invalid {field_name}")
        if self.living_people_mode not in {0, 1, 2, 3, 99}:
            raise ValueError("invalid living people mode")

        GenerationLimits(self.ancestor_generations, self.descendant_generations)
        if self.margin_mm < 0:
            raise ValueError("paper margin must not be negative")
        if self.paper_size is PaperSize.CUSTOM:
            if self.custom_width_mm is None or self.custom_height_mm is None:
                raise ValueError("custom paper requires width and height")
            PaperDimensions(self.custom_width_mm, self.custom_height_mm)
        elif self.custom_width_mm is not None or self.custom_height_mm is not None:
            raise ValueError("custom paper dimensions require Custom paper size")
        if self.years_past_death < 0:
            raise ValueError("years past death must not be negative")

    def with_changes(self, **changes: Any) -> "ChartConfig":
        """Return a validated custom configuration without mutating this one."""
        changes["preset"] = PresetName.CUSTOM
        return replace(self, **changes)


def build_preset(preset: PresetName) -> ChartConfig:
    """Create one independent configuration for a named product preset."""
    if preset is PresetName.CUSTOM:
        raise ValueError("Custom is a state, not a resettable preset")
    if preset is PresetName.PUBLICATION:
        return ChartConfig(preset=preset)
    if preset is PresetName.FAMILY:
        return ChartConfig(
            preset=preset,
            privacy_mode=PrivacyMode.INCLUDE_ALL,
            living_people_mode=99,
        )
    if preset is PresetName.COMPACT:
        return ChartConfig(
            preset=preset,
            paper_size=PaperSize.A4,
            ancestor_generations=2,
            descendant_generations=1,
        )
    raise ValueError(f"Unknown preset: {preset}")
