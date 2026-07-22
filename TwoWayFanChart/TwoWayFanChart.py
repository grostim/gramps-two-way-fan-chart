# SPDX-License-Identifier: GPL-3.0-or-later
"""Two-Way Fan Chart graphical report for Gramps 6.0."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import ReportError
from gramps.gen.plug.report import Report

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext

# Ensure this addon's directory is on sys.path so sibling modules can
# be imported whether Gramps loads us as a package or top-level module.
_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))
if _ADDON_DIR not in sys.path:
    sys.path.insert(0, _ADDON_DIR)

from options import TwoWayFanChartOptions  # noqa: E402
import pipeline  # noqa: E402


class TwoWayFanChartReport(Report):
    """Generate a bidirectional genealogy fan chart."""

    def write_report(self) -> None:
        """Generate the fan chart through the production pipeline."""
        config = self.options_class.build_chart_config()

        # Determine output path and format from Gramps options
        # In CLI mode, the output path is in options.handler; in GUI mode,
        # it's accessible via get_output(). Handle both.
        output_path = None
        format_name = None

        # Try GUI-style access first
        try:
            raw_output = self.options_class.get_output()
            if raw_output:
                output_path = Path(raw_output)
        except Exception:
            pass

        # Fallback: CLI-style access via handler
        if output_path is None:
            handler = getattr(self.options_class, "handler", None)
            if handler:
                raw = getattr(handler, "output", None) or getattr(handler, "of", None)
                if raw:
                    output_path = Path(raw)

        if output_path is None:
            output_path = Path("two_way_fan_chart.svg")

        # Determine format from output extension or handler
        format_name = output_path.suffix.lower().lstrip(".")
        if not format_name or format_name == "print":
            handler = getattr(self.options_class, "handler", None)
            if handler:
                fmt = getattr(handler, "format_name", None)
                if fmt:
                    format_name = str(fmt).lower()
        if not format_name:
            format_name = "svg"

        # Dispatch to the pipeline — it handles SVG, PDF, and PNG
        try:
            pipeline.generate_report(
                config=config,
                output_path=output_path,
                center_family_handle=config.center_family,
                db=self.database,
                overwrite=True,
            )
        except Exception as exc:
            raise ReportError(
                _("Report generation failed"),
                str(exc),
            ) from exc
        self._custom_output_written = True

    def end_report(self) -> None:
        """Keep Gramps' document backend from overwriting our custom output."""
        if not getattr(self, "_custom_output_written", False):
            super().end_report()