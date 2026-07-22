# SPDX-License-Identifier: GPL-3.0-or-later
"""Report pipeline orchestrator for the two-way fan chart.

This module wires together all previously implemented layers:
config → graph extraction → privacy → person views → scene → SVG/PDF/PNG output.
It contains no business logic of its own — it delegates to the
specialized modules built in gates G2 through G8.
"""

from __future__ import annotations

from pathlib import Path

try:
    from TwoWayFanChart.config import ChartConfig, OutputFormat
    from TwoWayFanChart.extract import extract_chart_graph
    from TwoWayFanChart.facts import simple_name, simple_name_full, simple_dates
    from TwoWayFanChart.media import prepare_portrait_data_uri, select_portrait
    from TwoWayFanChart.privacy import (
        classify_visibility,
        decision_for_state,
        privacy_facts_from_gramps,
    )
    from TwoWayFanChart.geometry import Orientation, PaperRegion, PaperSize
    from TwoWayFanChart.layout import (
        calculate_canvas,
        layout_ancestors,
        layout_center,
        layout_descendants,
        layout_titles,
        layout_legend,
        layout_stats,
    )
    from TwoWayFanChart.model import SceneNode, ScenePage, VisibilityState
    from TwoWayFanChart.render_svg import render_svg
    from TwoWayFanChart.validate import validate_svg_output
except ModuleNotFoundError:
    from config import ChartConfig, OutputFormat  # type: ignore[no-redef]
    from extract import extract_chart_graph  # type: ignore[no-redef]
    from facts import simple_name, simple_name_full, simple_dates  # type: ignore[no-redef]
    from media import prepare_portrait_data_uri, select_portrait  # type: ignore[no-redef]
    from privacy import (  # type: ignore[no-redef]
        classify_visibility,
        decision_for_state,
        privacy_facts_from_gramps,
    )
    from geometry import Orientation, PaperRegion, PaperSize  # type: ignore[no-redef]
    from layout import (  # type: ignore[no-redef]
        calculate_canvas,
        layout_ancestors,
        layout_center,
        layout_descendants,
        layout_titles,
        layout_legend,
        layout_stats,
    )
    from model import SceneNode, ScenePage, VisibilityState  # type: ignore[no-redef]
    from render_svg import render_svg  # type: ignore[no-redef]
    from validate import validate_svg_output  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Label shortening helpers
# ---------------------------------------------------------------------------

# Per-generation max lengths and truncation modes for ancestor labels.
#   gen 1 (parents):         "Surname, FirstName"      max 25 chars
#   gen 2 (grandparents):   "Surname, First"          max 20 chars (first given word)
#   gen 3 (great-grandparents): "Surname, F."          max 15 chars (first letter only)
_ANCESTOR_GEN_LIMITS = {1: 22, 2: 22, 3: 18}

# Descendant label max lengths per generation depth.
_DESC_GEN_LIMITS = {1: 17, 2: 16}


def _shorten_name(label: str, max_len: int, *, mode: str = "first_word") -> str:
    """Shorten a ``"Surname, Given Names"`` label to fit within *max_len*.

    ``mode`` controls how the given names are truncated:
      - ``"full"``: keep full given names, hard-truncate the result.
      - ``"first_word"``: keep only the first given-name word.
      - ``"initial"``: keep only the first letter of the first given word,
        followed by a period.

    The surname is always preserved in full. If the input does not contain
    a comma, it is treated as a plain display name and hard-truncated.
    """
    if not label:
        return ""
    if len(label) <= max_len:
        return label

    if ", " in label:
        surname, given = label.split(", ", 1)
    elif "," in label:
        surname, given = label.split(",", 1)
        given = given.lstrip()
    else:
        # Plain "Given Surname" form — just hard-truncate.
        return label[: max_len - 1].rstrip() + "…"

    if mode == "first_word":
        first_given = given.split()[0] if given.split() else ""
        candidate = f"{surname}, {first_given}".strip(", ").rstrip(",")
    elif mode == "initial":
        first_given = given.strip()[:1]
        candidate = f"{surname}, {first_given}." if first_given else surname
    else:  # "full"
        candidate = label

    if len(candidate) > max_len:
        return candidate[: max_len - 1].rstrip() + "…"
    return candidate


def _ancestor_short_label(label: str, generation: int) -> str:
    """Shorten an ancestor display name according to generation depth."""
    max_len = _ANCESTOR_GEN_LIMITS.get(generation, 10)
    ordered = _mockup_name_order(label)
    if len(ordered) <= max_len:
        return ordered
    return ordered[: max_len - 1].rstrip() + "…"


def _descendant_short_label(label: str, depth: int) -> str:
    """Shorten a descendant display name according to depth.

    The mockup is much more economical in descendant rings than in ancestor
    rings. Children can keep a fuller label, but grandchildren should prefer
    the call name alone to avoid collisions in narrow outer sectors.
    """
    max_len = _DESC_GEN_LIMITS.get(depth, 16)
    if depth >= 2 and label == "Personne privée":
        return ""
    ordered = _mockup_name_order(label)
    if len(ordered) <= max_len:
        return ordered
    return ordered[: max_len - 1].rstrip() + "…"


def _label_initials(label: str) -> str:
    """Build two-letter initials from a display label.

    Accepts both ``"Surname, Given"`` and plain space-separated labels.
    """
    if not label:
        return ""
    cleaned = label.replace(",", " ")
    parts = [p for p in cleaned.split() if p and p[0].isalpha()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _mockup_name_order(label: str) -> str:
    """Convert Gramps ``Surname, Call name`` to the mockup's given-first form."""
    if ", " not in label:
        return label
    surname, given = label.split(", ", 1)
    return f"{given} {surname}".strip()


def _center_name_order(label: str) -> str:
    """Keep the public helper name used by center-layout tests."""
    return _mockup_name_order(label)


def _center_portrait_data_uri(config: ChartConfig, db, handle: str | None) -> str | None:
    """Resolve one center-person portrait from Gramps media, if available."""
    if not config.show_portraits or not handle:
        return None
    try:
        person = db.get_person_from_handle(handle)
    except Exception:
        return None
    if person is None:
        return None
    try:
        selected = select_portrait(
            db,
            person,
            strategy=config.portrait_source,
            include_private=False,
        )
        return prepare_portrait_data_uri(
            selected,
            allowed=True,
            size_px=256,
            treatment=config.portrait_treatment,
            respect_rectangle=config.respect_media_crop,
        )
    except Exception:
        return None


def _build_paper_region(config: ChartConfig) -> PaperRegion:
    """Map config StrEnum values to geometry Enum values."""
    paper_size_map = {
        "A0": PaperSize.A0, "A1": PaperSize.A1, "A2": PaperSize.A2,
        "A3": PaperSize.A3, "A4": PaperSize.A4, "A5": PaperSize.A5,
        "Letter": PaperSize.LETTER, "Legal": PaperSize.LEGAL,
        "Tabloid": PaperSize.TABLOID, "Custom": PaperSize.CUSTOM,
    }
    orientation_map = {
        "portrait": Orientation.PORTRAIT,
        "landscape": Orientation.LANDSCAPE,
    }
    geo_paper = paper_size_map.get(config.paper_size.value, PaperSize.A2)
    geo_orient = orientation_map.get(config.orientation.value, Orientation.LANDSCAPE)
    return PaperRegion(
        paper=geo_paper,
        orientation=geo_orient,
        margin_mm=config.margin_mm,
        custom_width_mm=config.custom_width_mm,
        custom_height_mm=config.custom_height_mm,
    )


def _build_scene(
    config: ChartConfig,
    db,
    center_family_handle: str,
) -> tuple[ScenePage, SceneNode]:
    """Build the full scene tree with real genealogy data.

    Returns (page, root_scene_node) ready for rendering.
    """
    paper = _build_paper_region(config)
    canvas = calculate_canvas(
        paper,
        ancestor_generations=config.ancestor_generations,
        descendant_generations=config.descendant_generations,
    )

    # Extract the real chart graph from the Gramps database
    graph = extract_chart_graph(db, config)

    # Resolve every person's visibility before formatting names, dates or
    # opening media. Results are cached because the same handle can occur in
    # several positions through unions or pedigree collapse.
    visibility_cache: dict[str, tuple[object | None, VisibilityState]] = {}
    portrait_cache: dict[str, str | None] = {}

    def _person_visibility(handle: str | None):
        if not handle:
            return None, VisibilityState.EXCLUDED
        if handle in visibility_cache:
            return visibility_cache[handle]
        try:
            person = db.get_person_from_handle(handle)
            if person is None:
                result = (None, VisibilityState.EXCLUDED)
            else:
                facts = privacy_facts_from_gramps(
                    person,
                    db,
                    years_past_death=config.years_past_death,
                )
                state = classify_visibility(
                    facts,
                    privacy_mode=config.privacy_mode,
                    include_private=config.include_private,
                    living_people_mode=config.living_people_mode,
                )
                result = (person, state)
        except Exception:
            # Privacy inference failure must fail closed.
            result = (None, VisibilityState.MASKED)
        visibility_cache[handle] = result
        return result

    def _safe_name(handle: str | None) -> str:
        _person, state = _person_visibility(handle)
        if state is VisibilityState.MASKED:
            return "Personne privée"
        if state is VisibilityState.EXCLUDED:
            return ""
        return simple_name(db, handle)

    def _safe_dates(handle: str | None) -> str:
        _person, state = _person_visibility(handle)
        if not decision_for_state(state).expose_details:
            return ""
        return simple_dates(db, handle)

    def _safe_portrait(handle: str | None) -> str | None:
        if not handle or not config.show_portraits:
            return None
        if handle in portrait_cache:
            return portrait_cache[handle]
        _person, state = _person_visibility(handle)
        if not decision_for_state(state).expose_media:
            portrait_cache[handle] = None
            return None
        portrait = _center_portrait_data_uri(config, db, handle)
        portrait_cache[handle] = portrait
        return portrait

    def _safe_fallback(handle: str | None, label: str) -> str:
        _person, state = _person_visibility(handle)
        return "•" if state is VisibilityState.MASKED else _label_initials(label)

    # --- Center couple labels ---
    center_left_handle = (
        graph.center_people[0].handle if graph.center_people[0] else None
    )
    center_right_handle = (
        graph.center_people[1].handle if graph.center_people[1] else None
    )
    left_label = _center_name_order(_safe_name(center_left_handle)) or "—"
    right_label = (
        _center_name_order(_safe_name(center_right_handle))
        if center_right_handle
        else None
    )
    left_portrait = _safe_portrait(center_left_handle)
    right_portrait = _safe_portrait(center_right_handle)
    left_dates = _safe_dates(center_left_handle)
    right_dates = _safe_dates(center_right_handle)

    # Statistics line is omitted (not needed for now)
    statistics = None

    center_node = layout_center(
        canvas,
        left_label=left_label,
        right_label=right_label,
        left_dates=left_dates,
        right_dates=right_dates,
        left_portrait=left_portrait,
        right_portrait=right_portrait,
        left_fallback=_safe_fallback(center_left_handle, left_label),
        right_fallback=_safe_fallback(center_right_handle, right_label or ""),
        statistics=statistics,
    )

    # --- Ancestor fan with real person names ---
    # Each slot carries its privacy-safe label, dates and optional portrait.
    ancestor_slots: list[tuple[str, str, str, str | None]] = []
    for slot in graph.ancestor_slots:
        if slot.person is not None:
            full_label = _safe_name(slot.person.handle)
            label = _ancestor_short_label(full_label, slot.generation)
            dates_label = _safe_dates(slot.person.handle)
            portrait = _safe_portrait(slot.person.handle)
        else:
            label = ""
            dates_label = ""
            portrait = None
        ancestor_slots.append((slot.position_id, label, dates_label, portrait))
    ancestors_node = layout_ancestors(
        canvas, ancestor_slots=tuple(ancestor_slots)
    )

    # --- Descendant branches with real person names ---
    def _name_lookup(handle: str | None) -> str:
        return _safe_name(handle)

    def _dates_lookup(handle: str | None) -> str:
        return _safe_dates(handle)

    descendants_node = layout_descendants(
        canvas,
        graph.descendant_branches,
        name_lookup=_name_lookup,
        dates_lookup=_dates_lookup,
        shortener=_descendant_short_label,
        portrait_lookup=_safe_portrait,
    )

    # --- Titles and legend ---
    titles_node = layout_titles(
        canvas,
        ancestor_generations=config.ancestor_generations,
        descendant_generations=config.descendant_generations,
    )
    legend_node = layout_legend(
        canvas,
        show_legend=config.show_legend,
    )

    # --- Stats block ---
    person_count = (
        len(graph.ancestor_slots)
        + len(graph.descendant_branches)
        + sum(1 for _ in _iter_all_descendants(graph.descendant_branches))
        + 2  # center couple
    )
    stats_node = layout_stats(
        canvas,
        person_count=person_count,
        ancestor_generations=config.ancestor_generations,
        descendant_generations=config.descendant_generations,
    )

    # --- Combine all scene nodes ---
    # Legend and stats blocks are omitted (not needed for now)
    children = (
        list(titles_node.children)
        + list(ancestors_node.children)
        + list(descendants_node.children)
        + list(center_node.children)
    )
    scene = SceneNode(children=tuple(children))
    page = ScenePage(width_mm=paper.width_mm, height_mm=paper.height_mm)
    return page, scene


def _iter_all_descendants(branches):
    """Yield all descendant nodes recursively."""
    for branch in branches:
        yield branch
        yield from _iter_all_descendants(branch.children)


def generate_report(
    *,
    config: ChartConfig,
    output_path: Path,
    center_family_handle: str,
    db,
    overwrite: bool = False,
) -> None:
    """Generate a two-way fan chart report from configuration.

    Args:
        config: Validated chart configuration.
        output_path: Destination file path for the output.
        center_family_handle: Gramps family handle for the center couple.
        db: Gramps database handle (read-only).
        overwrite: If False, raise FileExistsError when the output file already exists.

    Raises:
        ValueError: If the family handle is empty or the output format is unsupported.
        FileExistsError: If the output file exists and overwrite is False.
    """
    if not center_family_handle:
        raise ValueError("center_family_handle must not be empty")

    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"output file already exists: {output_path}; use overwrite=True to replace"
        )

    # Build the scene with real data from the Gramps database
    page, scene = _build_scene(config, db, center_family_handle)

    # Determine output format from the file extension
    suffix = output_path.suffix.lower().lstrip(".")
    if suffix == "svg":
        fmt = "svg"
    elif suffix in ("pdf", "png"):
        fmt = suffix
    elif config.output_format.value in ("svg", "pdf", "png") and not suffix:
        fmt = config.output_format.value
    else:
        raise ValueError(f"unsupported output format: {suffix or config.output_format.value}")

    if fmt == "svg":
        _render_svg(config, page, scene, output_path)
    elif fmt in ("pdf", "png"):
        _render_cairo(config, page, scene, output_path, fmt)
    else:
        raise ValueError(f"unsupported output format: {fmt}")


def _render_svg(
    config: ChartConfig,
    page: ScenePage,
    scene: SceneNode,
    output_path: Path,
) -> None:
    """Render the scene to an SVG file."""
    svg = render_svg(
        page, scene,
        background_color=config.background_color,
        title="Two-Way Fan Chart",
        description="Bidirectional genealogy fan chart",
        metadata={
            "preset": config.preset.value,
            "paper": f"{config.paper_size.value} {config.orientation.value}",
            "generations": f"{config.ancestor_generations}+{config.descendant_generations}",
        },
    )

    errors = validate_svg_output(svg)
    if errors:
        # Log errors but don't block — diagnostics will be embedded in metadata
        pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".svg.tmp")
    tmp_path.write_text(svg, encoding="utf-8")
    tmp_path.rename(output_path)


def _render_cairo(
    config: ChartConfig,
    page: ScenePage,
    scene: SceneNode,
    output_path: Path,
    fmt: str,
) -> None:
    """Render the scene to a PDF or PNG file via Cairo."""
    import sys
    addon_dir = None
    # Ensure addon dir is on sys.path for sibling import
    try:
        from TwoWayFanChart.render_cairo import render_cairo_pdf, render_cairo_png
    except Exception:
        try:
            # Add the addon directory to sys.path if not already there
            import os as _os
            _here = _os.path.dirname(_os.path.abspath(__file__))
            if _here not in sys.path:
                sys.path.insert(0, _here)
            from render_cairo import render_cairo_pdf, render_cairo_png  # type: ignore[no-redef]
        except Exception as exc:
            raise RuntimeError(
                f"Cairo rendering is not available; pycairo is required for PDF/PNG output ({exc})"
            ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "pdf":
        render_cairo_pdf(
            output_path, page, scene,
            background_color=config.background_color,
        )
    else:
        render_cairo_png(
            output_path, page, scene,
            background_color=config.background_color,
            dpi=150,
        )