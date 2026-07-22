# SPDX-License-Identifier: GPL-3.0-or-later
"""Privacy-first portrait media selection for the report."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from gramps.gen.utils.file import media_path_full
from PIL import Image, ImageOps


_PORTRAIT_STRATEGIES = {"first_image", "tagged_portrait", "primary"}
_TRUE_MARKERS = {"1", "yes", "true", "oui"}
_FALLBACK_MODES = {"initials", "neutral", "gender", "empty"}
_TREATMENTS = {"color", "grayscale", "sepia"}
_ASSET_DIR = Path(__file__).with_name("assets")
_FALLBACK_MEDIA_DIRS = (
    Path("/app/media"),
    Path("/root/gramps/media"),
)


def _resolve_media_file(database, stored_path: str) -> Path | None:
    """Resolve one media path, with GrampsWeb container fallbacks.

    In the GrampsWeb Docker deployment used for validation, the DB may store
    bare hashed filenames while the actual files live under ``/app/media``.
    ``media_path_full()`` then resolves to ``/root/gramps/<file>``, which does
    not exist. Try the standard Gramps resolution first, then a few known
    container roots.
    """
    primary = Path(media_path_full(database, stored_path))
    if primary.is_file():
        return primary
    name_only = Path(stored_path).name
    for base in _FALLBACK_MEDIA_DIRS:
        candidate = base / stored_path
        if candidate.is_file():
            return candidate
        candidate = base / name_only
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True, slots=True)
class SelectedMedia:
    """One local image approved for later decoding and rendering."""

    media_handle: str
    path: Path
    mime_type: str
    rectangle: tuple[int, int, int, int] | None


@dataclass(frozen=True, slots=True)
class PortraitFallback:
    """One privacy-safe fallback ready for the future scene builder."""

    kind: str
    text: str = ""
    svg: str = ""


def _is_private(value) -> bool:
    getter = getattr(value, "get_privacy", None)
    return bool(getter()) if callable(getter) else False


def is_portrait_marked(media_ref, *, include_private: bool) -> bool:
    """Return whether a media reference carries the documented portrait marker."""
    for attribute in media_ref.get_attribute_list():
        if not include_private and _is_private(attribute):
            continue
        attribute_type = str(attribute.get_type()).strip().casefold()
        attribute_value = str(attribute.get_value()).strip().casefold()
        if attribute_type == "portrait" and attribute_value in _TRUE_MARKERS:
            return True
    return False


def _select_reference(database, media_ref, *, include_private: bool):
    """Validate metadata and accessibility without opening the media file."""
    if not include_private and _is_private(media_ref):
        return None

    handle = media_ref.get_reference_handle()
    if not handle:
        return None
    media = database.get_media_from_handle(handle)
    if media is None or (not include_private and _is_private(media)):
        return None

    mime_type = (media.get_mime_type() or "").strip()
    if not mime_type.casefold().startswith("image/"):
        return None

    stored_path = (media.get_path() or "").strip()
    if not stored_path:
        return None
    parsed = urlparse(stored_path)
    if parsed.scheme.casefold() in {"http", "https"}:
        return None

    full_path = _resolve_media_file(database, stored_path)
    if full_path is None:
        return None

    rectangle = media_ref.get_rectangle()
    if rectangle is not None:
        try:
            rectangle = tuple(int(value) for value in rectangle)
        except (TypeError, ValueError):
            rectangle = None
        if rectangle is not None and len(rectangle) != 4:
            rectangle = None

    return SelectedMedia(handle, full_path, mime_type, rectangle)


def select_portrait(
    database,
    person,
    *,
    strategy: str,
    include_private: bool,
) -> SelectedMedia | None:
    """Select one portrait candidate in Gramps order without decoding it."""
    if strategy not in _PORTRAIT_STRATEGIES:
        raise ValueError(f"unsupported portrait strategy: {strategy}")

    references = person.get_media_list()
    if strategy == "primary":
        references = references[:1]
    elif strategy == "tagged_portrait":
        references = tuple(
            media_ref
            for media_ref in references
            if is_portrait_marked(media_ref, include_private=include_private)
        )

    for media_ref in references:
        selected = _select_reference(
            database, media_ref, include_private=include_private
        )
        if selected is not None:
            return selected
    return None


def normalize_rectangle(rectangle) -> tuple[float, float, float, float] | None:
    """Normalize one Gramps percentage rectangle or return full-image semantics."""
    if rectangle is None:
        return None
    try:
        values = tuple(float(value) for value in rectangle)
    except (TypeError, ValueError):
        return None
    if len(values) != 4:
        return None

    x1, y1, x2, y2 = values
    left, right = sorted((max(0.0, min(100.0, x1)), max(0.0, min(100.0, x2))))
    top, bottom = sorted((max(0.0, min(100.0, y1)), max(0.0, min(100.0, y2))))
    if left >= right or top >= bottom:
        return None
    if (left, top, right, bottom) == (0.0, 0.0, 100.0, 100.0):
        return None
    return left, top, right, bottom


def crop_square(
    image: Image.Image,
    rectangle,
    *,
    size_px: int,
    respect_rectangle: bool = True,
) -> Image.Image:
    """Apply an optional Gramps crop, then fit a centered square without stretch."""
    if not isinstance(size_px, int) or size_px <= 0:
        raise ValueError("portrait size must be a positive integer")

    working = image
    normalized = normalize_rectangle(rectangle) if respect_rectangle else None
    if normalized is not None:
        left, top, right, bottom = normalized
        width, height = working.size
        pixel_box = (
            round(width * left / 100.0),
            round(height * top / 100.0),
            round(width * right / 100.0),
            round(height * bottom / 100.0),
        )
        if pixel_box[0] < pixel_box[2] and pixel_box[1] < pixel_box[3]:
            working = working.crop(pixel_box)

    return ImageOps.fit(
        working,
        (size_px, size_px),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )


class PortraitCache:
    """Render-scoped cache for prepared portrait payloads."""

    def __init__(self, renderer: Callable[..., Any]) -> None:
        self._renderer = renderer
        self._payloads: dict[tuple, Any] = {}

    @staticmethod
    def _key(
        selected: SelectedMedia,
        *,
        size_px: int,
        treatment: str,
        respect_rectangle: bool,
    ) -> tuple:
        rectangle = (
            normalize_rectangle(selected.rectangle) if respect_rectangle else None
        )
        return (
            selected.media_handle,
            rectangle,
            size_px,
            treatment,
            bool(respect_rectangle),
        )

    def get_or_prepare(
        self,
        selected: SelectedMedia,
        *,
        size_px: int,
        treatment: str,
        respect_rectangle: bool,
    ):
        """Return a cached payload or render and cache it after success."""
        key = self._key(
            selected,
            size_px=size_px,
            treatment=treatment,
            respect_rectangle=respect_rectangle,
        )
        if key not in self._payloads:
            payload = self._renderer(
                selected,
                size_px=size_px,
                treatment=treatment,
                respect_rectangle=respect_rectangle,
            )
            self._payloads[key] = payload
        return self._payloads[key]

    def clear(self) -> None:
        """Release every payload owned by this render."""
        self._payloads.clear()

    def __len__(self) -> int:
        return len(self._payloads)

    def __enter__(self) -> "PortraitCache":
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> bool:
        self.clear()
        return False


def _letters(value: str) -> str:
    return "".join(character for character in value.strip() if character.isalpha())


def portrait_initials(
    displayed_given: str,
    primary_surname: str,
    *,
    masked: bool,
) -> str:
    """Derive initials only from already-authorized displayed name components."""
    if masked:
        return "•"
    given = _letters(displayed_given)
    surname = _letters(primary_surname)
    if given and surname:
        return (given[0] + surname[0]).upper()
    component = given or surname
    return component[:2].upper() if component else "•"


def _silhouette(kind: str) -> PortraitFallback:
    path = _ASSET_DIR / f"silhouette-{kind}.svg"
    return PortraitFallback(kind=kind, svg=path.read_text(encoding="utf-8").strip())


def portrait_fallback(
    mode: str,
    displayed_given: str,
    primary_surname: str,
    *,
    masked: bool,
    gender,
) -> PortraitFallback:
    """Build a self-contained fallback without consulting protected source data."""
    if mode not in _FALLBACK_MODES:
        raise ValueError(f"unsupported portrait fallback: {mode}")
    if masked:
        return _silhouette("neutral")
    if mode == "empty":
        return PortraitFallback("empty")
    if mode == "initials":
        return PortraitFallback(
            "initials",
            text=portrait_initials(
                displayed_given, primary_surname, masked=False
            ),
        )
    if mode == "neutral":
        return _silhouette("neutral")

    normalized_gender = str(gender).strip().casefold()
    if normalized_gender in {"m", "male", "man", "masculin"}:
        return _silhouette("male")
    if normalized_gender in {"f", "female", "woman", "féminin", "feminin"}:
        return _silhouette("female")
    return _silhouette("neutral")


def prepare_portrait_png(
    selected: SelectedMedia,
    *,
    size_px: int,
    treatment: str,
    respect_rectangle: bool,
) -> bytes:
    """Decode one approved image and return a self-contained square PNG."""
    if treatment not in _TREATMENTS:
        raise ValueError(f"unsupported portrait treatment: {treatment}")
    if not isinstance(size_px, int) or size_px <= 0:
        raise ValueError("portrait size must be a positive integer")

    with Image.open(selected.path) as source:
        oriented = ImageOps.exif_transpose(source)
        oriented.load()
        square = crop_square(
            oriented,
            selected.rectangle,
            size_px=size_px,
            respect_rectangle=respect_rectangle,
        )
        if treatment == "grayscale":
            prepared = ImageOps.grayscale(square).convert("RGB")
        elif treatment == "sepia":
            grayscale = ImageOps.grayscale(square)
            prepared = ImageOps.colorize(
                grayscale, black="#3b2416", white="#f2dfb5"
            )
        elif "A" in square.getbands():
            prepared = square.convert("RGBA")
        else:
            prepared = square.convert("RGB")

        output = BytesIO()
        prepared.save(output, format="PNG")
        return output.getvalue()


def png_data_uri(payload: bytes) -> str:
    """Encode a PNG payload for self-contained SVG embedding."""
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def prepare_portrait_data_uri(
    selected: SelectedMedia | None,
    *,
    allowed: bool,
    size_px: int,
    treatment: str,
    respect_rectangle: bool,
) -> str | None:
    """Prepare an approved portrait, or return None for privacy/fallback paths."""
    if not allowed or selected is None:
        return None
    try:
        payload = prepare_portrait_png(
            selected,
            size_px=size_px,
            treatment=treatment,
            respect_rectangle=respect_rectangle,
        )
    except OSError:
        return None
    return png_data_uri(payload)
