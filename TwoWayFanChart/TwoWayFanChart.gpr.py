# SPDX-License-Identifier: GPL-3.0-or-later
"""Gramps plugin registration for the Two-Way Fan Chart report."""

register(
    REPORT,
    id="two_way_fan_chart",
    name=_("Two-Way Fan Chart"),
    description=_(
        "Generates a bidirectional fan chart with ancestors, descendants, "
        "and portraits around a center family."
    ),
    version="1.1.2",
    gramps_target_version="6.0",
    status=STABLE,
    fname="TwoWayFanChart.py",
    reportclass="TwoWayFanChartReport",
    optionclass="TwoWayFanChartOptions",
    authors=["Timothée Gros"],
    authors_email=[],
    category=CATEGORY_DRAW,
    report_modes=[REPORT_MODE_GUI, REPORT_MODE_CLI],
    require_active=False,
    help_url="https://github.com/grostim/gramps-two-way-fan-chart",
)
