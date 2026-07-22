# SPDX-License-Identifier: GPL-3.0-or-later
"""Report rendering warnings — GUI-safe, no GUI imports.

Warnings are collected as structured objects so the caller can decide
how to present them (CLI text, Gramps dialog, etc.) without this module
importing any GUI code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WarningKind(Enum):
    INCLUDE_ALL = "include_all"
    EXCESSIVE_DENSITY = "excessive_density"
    MEDIA_MISSING = "media_missing"


@dataclass(frozen=True, slots=True)
class RenderingWarning:
    """A single rendering warning produced during report generation."""

    kind: WarningKind
    message: str
    blocking: bool = False


def collect_warnings(
    config,
    *,
    db,
    media_missing: bool = False,
) -> list[RenderingWarning]:
    """Collect rendering warnings from config and runtime state.

    Args:
        config: ChartConfig instance.
        db: Gramps database (unused for now, reserved for future checks).
        media_missing: Whether any media objects were missing during rendering.

    Returns:
        List of RenderingWarning instances, possibly empty.
    """
    warnings: list[RenderingWarning] = []

    # Warning: user requested to include everything (privacy risk)
    try:
        from TwoWayFanChart.config import PrivacyMode
    except ModuleNotFoundError:
        from config import PrivacyMode
    privacy_mode = getattr(config, "privacy_mode", PrivacyMode.PUBLICATION_SAFE)
    if privacy_mode == PrivacyMode.INCLUDE_ALL:
        warnings.append(
            RenderingWarning(
                kind=WarningKind.INCLUDE_ALL,
                message=(
                    "Vous avez demandé d'inclure les événements privés "
                    "et les personnes vivantes. Vérifiez que la sortie "
                    "ne sera pas diffusée publiquement."
                ),
                blocking=True,
            )
        )

    # Warning: excessive density (too many generations for the paper size)
    total_gen = getattr(config, "ancestor_generations", 0) + getattr(
        config, "descendant_generations", 0
    )
    if total_gen > 12:
        warnings.append(
            RenderingWarning(
                kind=WarningKind.EXCESSIVE_DENSITY,
                message=(
                    f"Densité excessive ({total_gen} générations au total). "
                    "La lisibilité du graphique peut être compromise."
                ),
                blocking=False,
            )
        )

    # Warning: missing media (non-blocking)
    if media_missing:
        warnings.append(
            RenderingWarning(
                kind=WarningKind.MEDIA_MISSING,
                message=(
                    "Un ou plusieurs portraits sont manquants. "
                    "Des initiales de fallback seront affichées."
                ),
                blocking=False,
            )
        )

    return warnings


def format_warnings_for_cli(warnings: list[RenderingWarning]) -> str:
    """Format warnings as plain text for CLI output."""
    if not warnings:
        return ""
    lines = []
    for w in warnings:
        prefix = "[BLOQUANT]" if w.blocking else "[AVERTISSEMENT]"
        lines.append(f"{prefix} {w.message}")
    return "\n".join(lines)


def format_warnings_for_user(warnings: list[RenderingWarning]) -> str:
    """Format warnings for user-facing display (translatable, GUI or CLI)."""
    if not warnings:
        return ""
    lines = []
    for w in warnings:
        lines.append(w.message)
    return "\n".join(lines)