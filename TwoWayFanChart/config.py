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
    MONOCHROME = "monochrome"
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


class PaletteName(StrEnum):
    MOCKUP = "mockup"
    MONOCHROME = "monochrome"


@dataclass(frozen=True, slots=True)
class ChartConfig:
    """Validated settings consumed by all later report layers."""

    center_family: str = ""
    preset: PresetName = PresetName.PUBLICATION
    ancestor_generations: int = 3
    descendant_generations: int = 2
    paper_size: PaperSize = PaperSize.A2
    orientation: Orientation = Orientation.LANDSCAPE
    margin_mm: float = 12.0
    custom_width_mm: float | None = None
    custom_height_mm: float | None = None
    output_format: OutputFormat = OutputFormat.SVG
    privacy_mode: PrivacyMode = PrivacyMode.PUBLICATION_SAFE
    palette: PaletteName = PaletteName.MOCKUP
    background_color: str = "#FAF9F5"
    show_center_as_couple: bool = True
    include_center_children: bool = True
    parent_family_policy: str = "primary"
    descendant_family_policy: str = "all"
    show_spouses: str = "all"
    child_order: str = "gramps"
    name_format: int = 0
    given_name_strategy: str = "call_then_first"
    name_case: str = "stored"
    date_format: str = "years"
    show_places: bool = False
    place_strategy: str = "locality"
    show_occupation: bool = False
    occupation_strategy: str = "last_dated"
    occupation_maximum: int = 1
    show_sosa: bool = False
    show_daboville: bool = False
    show_residence: bool = False
    show_union: bool = False
    show_portraits: bool = True
    portrait_source: str = "first_image"
    respect_media_crop: bool = True
    portrait_shape: str = "circle"
    portrait_treatment: str = "color"
    missing_portrait: str = "initials"
    portrait_scale: float = 1.0
    fit_one_page: bool = True
    outline_width: float = 1.0
    include_private: bool = False
    living_people_mode: int = 3
    years_past_death: int = 0
    title_mode: str = "automatic"
    custom_title: str = ""
    show_legend: bool = True
    open_after_generation: bool = True
    locale: str = ""
    debug_diagnostics: bool = False

    def __post_init__(self) -> None:
        enum_fields = (
            ("preset", self.preset, PresetName),
            ("paper size", self.paper_size, PaperSize),
            ("orientation", self.orientation, Orientation),
            ("output format", self.output_format, OutputFormat),
            ("privacy mode", self.privacy_mode, PrivacyMode),
            ("palette", self.palette, PaletteName),
        )
        for label, value, enum_type in enum_fields:
            if not isinstance(value, enum_type):
                raise ValueError(f"{label} must be a {enum_type.__name__}")

        choices = {
            "parent_family_policy": {"primary", "biological", "first"},
            "descendant_family_policy": {"all", "primary", "first"},
            "show_spouses": {"none", "first", "all"},
            "child_order": {"gramps", "birth", "name"},
            "given_name_strategy": {
                "complete",
                "first",
                "call_then_first",
                "nickname",
                "call_and_complete",
                "nickname_and_call",
                "gramps",
            },
            "name_case": {"stored", "small_caps", "upper"},
            "date_format": {"years", "short", "full"},
            "place_strategy": {
                "gramps",
                "locality",
                "locality_region",
                "locality_country",
            },
            "occupation_strategy": {
                "first_dated",
                "last_dated",
                "closest_union",
                "distinct",
                "first_nonempty",
            },
            "portrait_source": {"first_image", "tagged_portrait", "primary"},
            "portrait_shape": {"circle", "rounded_square"},
            "portrait_treatment": {"color", "grayscale", "sepia"},
            "missing_portrait": {"initials", "neutral", "gender", "empty"},
            "title_mode": {"automatic", "custom", "none"},
        }
        for field_name, allowed in choices.items():
            if getattr(self, field_name) not in allowed:
                raise ValueError(f"invalid {field_name}")
        if not isinstance(self.name_format, int):
            raise ValueError("name format must be a Gramps format number")
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
        if self.portrait_scale <= 0:
            raise ValueError("portrait scale must be positive")
        if self.outline_width <= 0:
            raise ValueError("outline width must be positive")
        if not 1 <= self.occupation_maximum <= 5:
            raise ValueError("occupation maximum must be between 1 and 5")
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
    if preset is PresetName.MONOCHROME:
        return ChartConfig(
            preset=preset,
            palette=PaletteName.MONOCHROME,
            background_color="#FFFFFF",
            outline_width=1.5,
        )
    if preset is PresetName.COMPACT:
        return ChartConfig(
            preset=preset,
            paper_size=PaperSize.A4,
            ancestor_generations=2,
            descendant_generations=1,
            portrait_scale=0.75,
        )
    raise ValueError(f"Unknown preset: {preset}")
