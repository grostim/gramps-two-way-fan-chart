# SPDX-License-Identifier: GPL-3.0-or-later
"""Small immutable value objects shared by report configuration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .facts import EventFact, VitalDates


class VisibilityState(StrEnum):
    """Maximum real data a later rendering layer may receive."""

    VISIBLE = "visible"
    NAME_ONLY = "name_only"
    MASKED = "masked"
    EXCLUDED = "excluded"


@dataclass(frozen=True, slots=True)
class SurnamePart:
    """Sanitized primitive projection of one structured Gramps surname."""

    surname: str
    prefix: str = ""
    connector: str = ""
    primary: bool = False
    origin_type: int = 0


@dataclass(frozen=True, slots=True)
class PersonViewSeed:
    """Sanitized person data allowed to cross the privacy boundary."""

    position_id: str
    visibility: VisibilityState
    given_name: str
    surname: str
    details: tuple[str, ...]
    media_reference: str | None
    masked_label: str | None = None
    call_name: str = ""
    nick_name: str = ""
    title: str = ""
    suffix: str = ""
    family_nick_name: str = ""
    surname_parts: tuple[SurnamePart, ...] = ()


@dataclass(frozen=True, slots=True)
class InformationLine:
    """One semantic line ordered by degradation priority."""

    kind: str
    text: str
    priority: int


@dataclass(frozen=True, slots=True)
class InformationProfile:
    """Layout-neutral information selected for one chart zone."""

    zone: str
    lines: tuple[InformationLine, ...]


@dataclass(frozen=True, slots=True)
class PersonView:
    """Privacy-safe labels and facts ready for the future scene builder."""

    seed: PersonViewSeed
    full_label: str
    short_label: str
    name_case: str
    vital_dates: "VitalDates"
    information: InformationProfile
    residence: "EventFact | None" = None
    union: "EventFact | None" = None


@dataclass(frozen=True, slots=True)
class GenerationLimits:
    """Validated ancestor/descendant depths for V1."""

    ancestors: int
    descendants: int

    def __post_init__(self) -> None:
        if not 0 <= self.ancestors <= 8:
            raise ValueError("ancestor generation limit must be between 0 and 8")
        if not 0 <= self.descendants <= 5:
            raise ValueError("descendant generation limit must be between 0 and 5")


@dataclass(frozen=True, slots=True)
class PaperDimensions:
    """Physical paper dimensions in millimetres."""

    width_mm: float
    height_mm: float

    def __post_init__(self) -> None:
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError("custom paper dimensions must be positive")


@dataclass(frozen=True, slots=True)
class PersonNode:
    """Minimum stable identity needed by later projections."""

    handle: str
    gramps_id: str


@dataclass(frozen=True, slots=True)
class AncestorSlot:
    """One deterministic position in one of the two ancestor fans."""

    position_id: str
    generation: int
    index: int
    lineage: str
    person: PersonNode | None
    relation: str = "birth"
    repeated: bool = False
    cycle: bool = False

    def __post_init__(self) -> None:
        if self.generation < 1:
            raise ValueError("ancestor generation must be at least 1")
        if self.index < 0:
            raise ValueError("ancestor index must not be negative")
        if self.lineage not in {"a", "b"}:
            raise ValueError("ancestor lineage must be 'a' or 'b'")


@dataclass(frozen=True, slots=True)
class UnionBranch:
    """One recorded family of a descendant."""

    family_handle: str
    spouse_handle: str | None
    child_handles: tuple[str, ...]
    child_relations: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.child_handles) != len(self.child_relations):
            raise ValueError("one relation is required for every union child")


@dataclass(frozen=True, slots=True)
class DescendantBranch:
    """One visible descendant position and its recorded unions."""

    position_id: str
    person: PersonNode
    generation: int
    unions: tuple[UnionBranch, ...]
    children: tuple["DescendantBranch", ...]
    relation: str = "birth"
    cycle: bool = False

    def __post_init__(self) -> None:
        if self.generation < 1:
            raise ValueError("descendant generation must be at least 1")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A stable non-fatal extraction observation."""

    code: str
    message: str
    position_id: str


@dataclass(frozen=True, slots=True)
class ChartGraph:
    """Backend-neutral graph extracted from a Gramps family tree."""

    center_family_handle: str
    center_people: tuple[PersonNode | None, PersonNode | None]
    ancestor_slots: tuple[AncestorSlot, ...]
    descendant_branches: tuple[DescendantBranch, ...]
    diagnostics: tuple[Diagnostic, ...]


# ---------------------------------------------------------------------------
# Scene model — backend-neutral rendering primitives
# ---------------------------------------------------------------------------

_scene_id_counter = 0


def next_scene_id() -> str:
    """Return a unique scene node identifier."""
    global _scene_id_counter
    _scene_id_counter += 1
    return f"node-{_scene_id_counter}"


@dataclass(frozen=True, slots=True)
class ScenePage:
    """Top-level page dimensions for the scene."""

    width_mm: float
    height_mm: float


@dataclass(frozen=True, slots=True)
class SceneSector:
    """An annular sector or pie slice in the fan chart."""

    inner_radius: float
    outer_radius: float
    start_angle: float
    sweep_angle: float
    fill: str = ""
    stroke: str | None = None
    stroke_width: float | None = None
    cx: float = 0.0
    cy: float = 0.0


@dataclass(frozen=True, slots=True)
class SceneCircle:
    """A circle (typically a portrait medallion)."""

    cx: float
    cy: float
    r: float
    fill: str = ""
    stroke: str | None = None
    stroke_width: float | None = None


@dataclass(frozen=True, slots=True)
class SceneImage:
    """An embedded image (portrait or fallback)."""

    cx: float
    cy: float
    r: float
    data_uri: str | None = None
    fallback_text: str = ""


@dataclass(frozen=True, slots=True)
class SceneText:
    """A text label placed at an absolute position."""

    x: float
    y: float
    content: str
    font_size: float
    fill: str = "#141413"
    anchor: str | None = None
    font_weight: str | None = None
    rotation: float | None = None


@dataclass(frozen=True, slots=True)
class ScenePathText:
    """Text placed along an SVG arc path."""

    path: str
    content: str
    font_size: float
    fill: str = "#141413"


@dataclass(frozen=True, slots=True)
class SceneLegend:
    """A legend block positioned on the page."""

    x: float
    y: float
    items: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class SceneRect:
    """A rectangle (background card, border box)."""

    x: float
    y: float
    width: float
    height: float
    fill: str = "#FFFFFF"
    stroke: str = "#D1CFC5"
    stroke_width: float = 0.3
    rx: float = 3.0


@dataclass(frozen=True, slots=True)
class SceneDiagnostic:
    """A rendering diagnostic (density warning, omitted info, etc.)."""

    kind: str
    message: str
    severity: str = "info"


@dataclass(frozen=True, slots=True)
class SceneNode:
    """A group of scene primitives forming a renderable unit."""

    children: tuple[
        ScenePage
        | SceneSector
        | SceneCircle
        | SceneImage
        | SceneText
        | ScenePathText
        | SceneLegend
        | SceneDiagnostic,
        ...,
    ]
