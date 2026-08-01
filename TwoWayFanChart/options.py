# SPDX-License-Identifier: GPL-3.0-or-later
"""Gramps-native options for the Two-Way Fan Chart report."""

from __future__ import annotations

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.errors import ReportError
from gramps.gen.plug.docgen import (
    FontStyle,
    GraphicsStyle,
    FONT_SANS_SERIF,
    PARA_ALIGN_CENTER,
    ParagraphStyle,
)
from gramps.gen.plug.menu import (
    BooleanOption,
    ColorOption,
    EnumeratedListOption,
    FamilyOption,
    NumberOption,
)
from gramps.gen.plug.report import MenuReportOptions, stdoptions
from gramps.gen.proxy import LivingProxyDb

try:
    from .config import (
        ChartConfig,
        Orientation,
        OutputFormat,
        PaperSize,
        PresetName,
        PrivacyMode,
        build_preset,
    )
except ImportError:
    # Gramps loads add-ons as top-level modules.
    import os, sys
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    from config import (  # type: ignore[no-redef]
        ChartConfig,
        Orientation,
        OutputFormat,
        PaperSize,
        PresetName,
        PrivacyMode,
        build_preset,
    )

try:
    _trans = glocale.get_addon_translator(__file__)
except ValueError:
    _trans = glocale.translation
_ = _trans.gettext


CATEGORY_SUBJECT = "Subject and generations"
CATEGORY_FAMILIES = "People and families"
CATEGORY_PORTRAITS = "Portraits and medallions"
CATEGORY_PAPER = "Paper and layout"
CATEGORY_COLORS = "Colors and styles"
CATEGORY_PRIVACY = "Privacy"
CATEGORY_OUTPUT = "Output"


def _enum(label: str, value: str, items: tuple[tuple[str, str], ...]):
    option = EnumeratedListOption(_(label), value)
    for item_value, description in items:
        option.add_item(item_value, _(description))
    return option


class CenterFamilyOption(FamilyOption):
    """Reject explicit family IDs before Gramps enters its report try-block."""

    def __init__(self, label: str, database) -> None:
        super().__init__(label)
        self._database = database

    def set_value(self, value) -> None:
        if value and not self._database.get_family_from_gramps_id(value):
            raise ReportError(
                _("Center family required"),
                _("The selected center family does not exist."),
            )
        super().set_value(value)


class _ExplicitOptionsDict(dict[str, object]):
    """Record option keys explicitly assigned by the CLI/WebAPI parser."""

    def __init__(self, values: dict[str, object]) -> None:
        super().__init__(values)
        self.explicit_keys: set[str] = set()
        self.tracking_enabled = True

    def __setitem__(self, key: str, value: object) -> None:
        super().__setitem__(key, value)
        if self.tracking_enabled:
            self.explicit_keys.add(key)


class TwoWayFanChartOptions(MenuReportOptions):
    """Expose stable, headless-safe report options through Gramps."""

    def __init__(self, name, dbase) -> None:
        self._database = dbase
        self._applying_preset = False
        super().__init__(name, dbase)
        self.options_dict = _ExplicitOptionsDict(self.options_dict)

    def load_previous_values(self) -> None:
        """Load persisted values and select a real family when none is stored."""
        self._applying_preset = True
        self.options_dict.tracking_enabled = False
        try:
            super().load_previous_values()
        finally:
            self.options_dict.explicit_keys.clear()
            self.options_dict.tracking_enabled = True
            self._applying_preset = False
        center_option = self.menu.get_option_by_name("center_family")
        family_id = center_option.get_value()
        family = (
            self._database.get_family_from_gramps_id(family_id)
            if family_id
            else None
        )
        if family:
            self.refresh_dependencies()
            return
        try:
            family_handle = next(self._database.iter_family_handles())
        except StopIteration as error:
            raise ReportError(
                _("Center family required"),
                _("The selected family tree contains no family."),
            ) from error
        family = self._database.get_family_from_handle(family_handle)
        if family is None:
            raise ReportError(
                _("Center family required"),
                _("The selected family tree contains no usable family."),
            )
        center_option.set_value(family.get_gramps_id())
        self.refresh_dependencies()

    def add_menu_options(self, menu) -> None:
        """Build the supported option categories without GTK widgets."""
        preset = _enum(
            "Preset",
            "publication",
            (
                ("publication", "Publication — mockup"),
                ("family", "Family — mockup"),
                ("compact", "Compact view"),
                ("custom", "Custom"),
            ),
        )
        menu.add_option(_(CATEGORY_SUBJECT), "preset", preset)
        center = CenterFamilyOption(_("Center family"), self._database)
        menu.add_option(_(CATEGORY_SUBJECT), "center_family", center)
        menu.add_option(
            _(CATEGORY_SUBJECT),
            "ancestor_generations",
            NumberOption(_("Ancestor generations"), 5, 0, 8),
        )
        menu.add_option(
            _(CATEGORY_SUBJECT),
            "descendant_generations",
            NumberOption(_("Descendant generations"), 3, 0, 5),
        )
        menu.add_option(
            _(CATEGORY_FAMILIES),
            "parent_family_policy",
            _enum(
                "Parent family to follow",
                "primary",
                (
                    ("primary", "Primary family"),
                    ("biological", "Prefer biological parents"),
                    ("first", "First available family"),
                ),
            ),
        )
        menu.add_option(
            _(CATEGORY_FAMILIES),
            "descendant_family_policy",
            _enum(
                "Descendant families",
                "all",
                (
                    ("all", "All families"),
                    ("primary", "Primary family only"),
                    ("first", "First family"),
                ),
            ),
        )
        menu.add_option(
            _(CATEGORY_PORTRAITS),
            "show_portraits",
            BooleanOption(_("Show portraits"), True),
        )
        menu.add_option(
            _(CATEGORY_PORTRAITS),
            "portrait_source",
            _enum(
                "Portrait source",
                "first_image",
                (
                    ("first_image", "First image media"),
                    ("tagged_portrait", "First media marked portrait"),
                    ("primary", "Primary Gramps media"),
                ),
            ),
        )
        menu.add_option(
            _(CATEGORY_PORTRAITS),
            "respect_media_crop",
            BooleanOption(_("Respect MediaRef crop"), True),
        )
        menu.add_option(
            _(CATEGORY_PORTRAITS),
            "portrait_treatment",
            _enum(
                "Portrait treatment",
                "color",
                (("color", "Color"), ("grayscale", "Grayscale"), ("sepia", "Sepia")),
            ),
        )
        menu.add_option(
            _(CATEGORY_PAPER),
            "paper_size",
            _enum(
                "Paper size",
                "A0",
                tuple((value, value) for value in ("A5", "A4", "A3", "A2", "A1", "A0", "Letter", "Legal", "Tabloid", "Custom")),
            ),
        )
        menu.add_option(
            _(CATEGORY_PAPER),
            "orientation",
            _enum(
                "Orientation",
                "landscape",
                (("portrait", "Portrait"), ("landscape", "Landscape"), ("automatic", "Automatic")),
            ),
        )
        menu.add_option(
            _(CATEGORY_PAPER), "margin_mm", NumberOption(_("Uniform margin (mm)"), 12, 0, 100)
        )
        menu.add_option(
            _(CATEGORY_PAPER), "custom_width_mm", NumberOption(_("Custom width (mm)"), 594, 1, 2000)
        )
        menu.add_option(
            _(CATEGORY_PAPER), "custom_height_mm", NumberOption(_("Custom height (mm)"), 420, 1, 2000)
        )
        menu.add_option(
            _(CATEGORY_COLORS), "background_color", ColorOption(_("Background color"), "#FAF9F5")
        )
        menu.add_option(
            _(CATEGORY_PRIVACY),
            "privacy_mode",
            _enum(
                "Privacy mode",
                "include_all",
                (
                    ("include_all", "Include all"),
                    ("full_name_only", "Full name only"),
                    ("surname_only", "Surname only"),
                    ("replace_identity", "Replace complete identity"),
                    ("exclude", "Exclude completely"),
                    ("publication_safe", "Safe publication"),
                ),
            ),
        )
        stdoptions.add_private_data_option(menu, _(CATEGORY_PRIVACY), default=True)
        stdoptions.add_living_people_option(
            menu,
            _(CATEGORY_PRIVACY),
            mode=LivingProxyDb.MODE_INCLUDE_ALL,
            after_death_years=0,
        )

        menu.add_option(
            _(CATEGORY_OUTPUT),
            "output_format",
            _enum("Output format", "svg", (("svg", "SVG"), ("pdf", "PDF"))),
        )
        for controller in ("paper_size", "show_portraits"):
            menu.get_option_by_name(controller).connect(
                "value-changed", self.refresh_dependencies
            )
        menu.get_option_by_name("preset").connect(
            "value-changed", self.apply_selected_preset
        )
        for name in self._preset_option_values(ChartConfig()):
            menu.get_option_by_name(name).connect(
                "value-changed", self.mark_configuration_custom
            )
        self.refresh_dependencies()

    @staticmethod
    def _preset_option_values(config: ChartConfig) -> dict[str, object]:
        """Map preset-controlled configuration fields to stable menu keys."""
        return {
            "ancestor_generations": config.ancestor_generations,
            "descendant_generations": config.descendant_generations,
            "parent_family_policy": config.parent_family_policy,
            "descendant_family_policy": config.descendant_family_policy,
            "show_portraits": config.show_portraits,
            "portrait_source": config.portrait_source,
            "respect_media_crop": config.respect_media_crop,
            "portrait_treatment": config.portrait_treatment,
            "paper_size": config.paper_size.value,
            "orientation": config.orientation.value,
            "margin_mm": config.margin_mm,
            "background_color": config.background_color,
            "privacy_mode": config.privacy_mode.value,
            "incl_private": config.include_private,
            "living_people": config.living_people_mode,
            "years_past_death": config.years_past_death,
            "output_format": config.output_format.value,
        }

    def apply_selected_preset(self) -> None:
        """Atomically apply a named preset while preserving the selected family."""
        if self._applying_preset:
            return
        preset = PresetName(self.menu.get_option_by_name("preset").get_value())
        if preset is PresetName.CUSTOM:
            return
        values = self._preset_option_values(build_preset(preset))
        # Gramps CLI/GrampsWeb applies request options in JSON insertion order.
        # If explicit fields were parsed before ``preset``, the preset callback
        # must not silently erase them. The tracked handler dictionary records
        # exact request keys, including values equal to the persisted baseline.
        handler = getattr(self, "handler", None)
        handler_values = getattr(handler, "options_dict", {}) if handler else {}
        explicit_names = getattr(handler_values, "explicit_keys", set())
        explicit_overrides = {
            name: handler_values[name]
            for name, preset_value in values.items()
            if name in explicit_names
            and handler_values[name] != preset_value
        }
        self._applying_preset = True
        try:
            for name, value in values.items():
                self.menu.get_option_by_name(name).set_value(value)
            for name, value in explicit_overrides.items():
                self.menu.get_option_by_name(name).set_value(value)
            if explicit_overrides:
                preset_option = self.menu.get_option_by_name("preset")
                preset_option.disable_signals()
                try:
                    preset_option.set_value(PresetName.CUSTOM.value)
                finally:
                    preset_option.enable_signals()
                handler_values["preset"] = PresetName.CUSTOM.value
        finally:
            self._applying_preset = False
        self.refresh_dependencies()

    def mark_configuration_custom(self) -> None:
        """Reflect a manual change only when it differs from the active preset."""
        if self._applying_preset:
            return
        preset_option = self.menu.get_option_by_name("preset")
        preset = PresetName(preset_option.get_value())
        if preset is PresetName.CUSTOM:
            return
        expected_values = self._preset_option_values(build_preset(preset))
        if all(
            self.menu.get_option_by_name(name).get_value() == expected
            for name, expected in expected_values.items()
        ):
            return
        self._applying_preset = True
        try:
            preset_option.set_value(PresetName.CUSTOM.value)
            handler = getattr(self, "handler", None)
            handler_values = getattr(handler, "options_dict", None) if handler else None
            if handler_values is not None:
                handler_values["preset"] = PresetName.CUSTOM.value
        finally:
            self._applying_preset = False

    def refresh_dependencies(self) -> None:
        """Coordinate pure option availability without depending on GTK widgets."""
        menu = self.menu
        custom_paper = menu.get_option_by_name("paper_size").get_value() == "Custom"
        for name in ("custom_width_mm", "custom_height_mm"):
            menu.get_option_by_name(name).set_available(custom_paper)

        portraits_enabled = bool(
            menu.get_option_by_name("show_portraits").get_value()
        )
        for name in (
            "portrait_source",
            "respect_media_crop",
            "portrait_treatment",
        ):
            menu.get_option_by_name(name).set_available(portraits_enabled)

    def build_chart_config(self) -> ChartConfig:
        """Project the complete Gramps menu into one validated value object."""
        menu = self.menu

        def value(name: str):
            return menu.get_option_by_name(name).get_value()

        center_family = value("center_family")
        if not center_family or not self._database.get_family_from_gramps_id(
            center_family
        ):
            raise ReportError(
                _("Center family required"),
                _("Select an existing family before generating the chart."),
            )

        paper_size = PaperSize(value("paper_size"))
        custom_width = value("custom_width_mm") if paper_size is PaperSize.CUSTOM else None
        custom_height = (
            value("custom_height_mm") if paper_size is PaperSize.CUSTOM else None
        )
        try:
            return ChartConfig(
                center_family=center_family,
                preset=PresetName(value("preset")),
                ancestor_generations=value("ancestor_generations"),
                descendant_generations=value("descendant_generations"),
                parent_family_policy=value("parent_family_policy"),
                descendant_family_policy=value("descendant_family_policy"),
                show_portraits=value("show_portraits"),
                portrait_source=value("portrait_source"),
                respect_media_crop=value("respect_media_crop"),
                portrait_treatment=value("portrait_treatment"),
                paper_size=paper_size,
                orientation=Orientation(value("orientation")),
                margin_mm=value("margin_mm"),
                custom_width_mm=custom_width,
                custom_height_mm=custom_height,
                background_color=value("background_color"),
                privacy_mode=PrivacyMode(value("privacy_mode")),
                include_private=value("incl_private"),
                living_people_mode=value("living_people"),
                years_past_death=value("years_past_death"),
                output_format=OutputFormat(value("output_format")),
            )
        except (TypeError, ValueError) as error:
            raise ReportError(
                _("Invalid chart options"),
                str(error),
            ) from error

    def get_subject(self) -> str:
        return _("Two-Way Fan Chart")

    def make_default_style(self, default_style):
        """Make the default output style for the Two-Way Fan Chart report."""
        # Paragraph Styles
        f_style = FontStyle()
        f_style.set_size(18)
        f_style.set_bold(1)
        f_style.set_type_face(FONT_SANS_SERIF)
        p_style = ParagraphStyle()
        p_style.set_font(f_style)
        p_style.set_alignment(PARA_ALIGN_CENTER)
        p_style.set_description(_("The style used for the title."))
        default_style.add_paragraph_style("TWFC-Title", p_style)

        f_style = FontStyle()
        f_style.set_size(9)
        f_style.set_type_face(FONT_SANS_SERIF)
        p_style = ParagraphStyle()
        p_style.set_font(f_style)
        p_style.set_alignment(PARA_ALIGN_CENTER)
        p_style.set_description(_("The basic style used for the text display."))
        default_style.add_paragraph_style("TWFC-Text", p_style)

        f_style = FontStyle()
        f_style.set_size(7)
        f_style.set_type_face(FONT_SANS_SERIF)
        p_style = ParagraphStyle()
        p_style.set_font(f_style)
        p_style.set_alignment(PARA_ALIGN_CENTER)
        p_style.set_description(_("The style used for generation labels."))
        default_style.add_paragraph_style("TWFC-GenLabel", p_style)

        # Graphics Styles
        g_style = GraphicsStyle()
        g_style.set_paragraph_style("TWFC-Title")
        default_style.add_draw_style("TWFC-Graphic-title", g_style)

        g_style = GraphicsStyle()
        g_style.set_paragraph_style("TWFC-Text")
        default_style.add_draw_style("TWFC-Graphic-text", g_style)

        g_style = GraphicsStyle()
        g_style.set_paragraph_style("TWFC-GenLabel")
        default_style.add_draw_style("TWFC-Graphic-genlabel", g_style)
