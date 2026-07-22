# SPDX-License-Identifier: GPL-3.0-or-later
"""Read the output contract prepared by Gramps without opening the output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


class OutputContextError(ValueError):
    """The Gramps report lifecycle has not supplied a usable output context."""


@dataclass(frozen=True, slots=True)
class ReportOutputContext:
    """Physical page and destination selected by the Gramps GUI or CLI."""

    output_path: Path
    format_name: str
    page_width_cm: float
    page_height_cm: float
    margins_cm: tuple[float, float, float, float]

    @property
    def usable_width_cm(self) -> float:
        """Width inside left and right margins."""
        left, right, _, _ = self.margins_cm
        return self.page_width_cm - left - right

    @property
    def usable_height_cm(self) -> float:
        """Height inside top and bottom margins."""
        _, _, top, bottom = self.margins_cm
        return self.page_height_cm - top - bottom

    @classmethod
    def from_options(cls, options: Any) -> "ReportOutputContext":
        """Project Gramps report options into a backend-neutral context.

        The method is deliberately read-only: it does not create directories,
        open the destination, initialise the document or mutate the handler.
        """
        raw_output = options.get_output()
        if not raw_output:
            raise OutputContextError("A report output destination is required.")

        document = options.get_document()
        paper = getattr(document, "paper", None)
        if paper is None:
            raise OutputContextError("The Gramps document has no paper style.")

        size = paper.get_size()
        margins = (
            float(paper.get_left_margin()),
            float(paper.get_right_margin()),
            float(paper.get_top_margin()),
            float(paper.get_bottom_margin()),
        )
        format_name = str(options.handler.get_format_name()).lower()
        if format_name == "print":
            document_extension = getattr(document, "EXT", None)
            output_extension = Path(raw_output).suffix.lstrip(".")
            concrete_format = document_extension or output_extension
            if concrete_format:
                format_name = str(concrete_format).lower()

        context = cls(
            output_path=Path(raw_output),
            format_name=format_name,
            page_width_cm=float(size.get_width()),
            page_height_cm=float(size.get_height()),
            margins_cm=margins,
        )
        if context.usable_width_cm <= 0 or context.usable_height_cm <= 0:
            raise OutputContextError("The selected paper margins leave no usable area.")
        return context