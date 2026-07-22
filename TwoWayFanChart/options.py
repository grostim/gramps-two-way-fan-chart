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
    StringOption,
)
from gramps.gen.plug.report import MenuReportOptions, stdoptions
from gramps.gen.proxy import LivingProxyDb

try:
    from .config import (
        ChartConfig,
        Orientation,
        OutputFormat,
        PaletteName,
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
        PaletteName,
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
CATEGORY_NAMES = "Names and information"
CATEGORY_PORTRAITS = "Portraits and medallions"
CATEGORY_PAPER = "Paper and layout"
CATEGORY_COLORS = "Colors and styles"
CATEGORY_PRIVACY = "Privacy"
CATEGORY_OUTPUT = "Title, legend and output"
CATEGORY_ADVANCED = "Advanced options"


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


class TwoWayFanChartOptions(MenuReportOptions):
    """Expose stable, headless-safe report options through Gramps."""

    def __init__(self, name, dbase) -> None:
        self._database = dbase
        self._applying_preset = False
        super().__init__(name, dbase)

    def load_previous_values(self) -> None:
        """Load persisted values and select a real family when none is stored."""
        self._applying_preset = True
        try:
            super().load_previous_values()
        finally:
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
        """Build nine specification-aligned categories without GTK widgets."""
        preset = _enum(
            "Preset",
            "publication",
            (
                ("publication", "Publication — mockup"),
                ("family", "Family — mockup"),
                ("monochrome", "Monochrome print"),
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
            NumberOption(_("Ancestor generations"), 3, 0, 8),
        )
        menu.add_option(
            _(CATEGORY_SUBJECT),
            "descendant_generations",
            NumberOption(_("Descendant generations"), 2, 0, 5),
        )
        menu.add_option(
            _(CATEGORY_SUBJECT),
            "show_center_as_couple",
            BooleanOption(_("Double center medallion"), True),
        )
        menu.add_option(
            _(CATEGORY_SUBJECT),
            "include_center_children",
            BooleanOption(_("Show center children"), True),
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
            _(CATEGORY_FAMILIES),
            "show_spouses",
            _enum(
                "Show spouses",
                "all",
                (("none", "None"), ("first", "First"), ("all", "All")),
            ),
        )
        menu.add_option(
            _(CATEGORY_FAMILIES),
            "child_order",
            _enum(
                "Child order",
                "gramps",
                (("gramps", "Gramps order"), ("birth", "Birth"), ("name", "Name")),
            ),
        )

        stdoptions.add_name_format_option(menu, _(CATEGORY_NAMES))
        menu.add_option(
            _(CATEGORY_NAMES),
            "given_name_strategy",
            _enum(
                "Given-name strategy",
                "call_then_first",
                (
                    ("complete", "Complete given names"),
                    ("first", "First given name"),
                    ("call_then_first", "Call name, then first name"),
                    ("nickname", "Nickname"),
                    ("call_and_complete", "Call name and complete given names"),
                    ("nickname_and_call", "Nickname and call name"),
                    ("gramps", "Gramps name format"),
                ),
            ),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "name_case",
            _enum(
                "Name case",
                "stored",
                (("stored", "As stored"), ("small_caps", "Small capitals"), ("upper", "Uppercase")),
            ),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "date_format",
            _enum(
                "Date format",
                "years",
                (("years", "Years only"), ("short", "Localized short date"), ("full", "Localized full date")),
            ),
        )
        menu.add_option(
            _(CATEGORY_NAMES), "show_places", BooleanOption(_("Show places"), False)
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "place_strategy",
            _enum(
                "Place detail",
                "locality",
                (
                    ("gramps", "Full Gramps place"),
                    ("locality", "Locality only"),
                    ("locality_region", "Locality and region"),
                    ("locality_country", "Locality and country"),
                ),
            ),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "show_occupation",
            BooleanOption(_("Show occupation"), False),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "occupation_strategy",
            _enum(
                "Occupation selection",
                "last_dated",
                (
                    ("first_dated", "First dated occupation"),
                    ("last_dated", "Last dated occupation"),
                    ("closest_union", "Closest to main union"),
                    ("distinct", "Distinct occupations"),
                    ("first_nonempty", "First non-empty occupation"),
                ),
            ),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "occupation_maximum",
            NumberOption(_("Maximum occupations"), 1, 1, 5),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "show_sosa",
            BooleanOption(_("Show Sosa numbers"), False),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "show_daboville",
            BooleanOption(_("Show d'Aboville numbers"), False),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "show_residence",
            BooleanOption(_("Show residence"), False),
        )
        menu.add_option(
            _(CATEGORY_NAMES),
            "show_union",
            BooleanOption(_("Show union facts"), False),
        )

        menu.add_option(
            _(CATEGORY_PORTRAITS),
            "show_portraits",
            BooleanOption(_("Show portraits"), True),
        )
        menu.add_option(
            _(CATEGORY_PORTRAITS),
            "portrait_scale",
            NumberOption(_("Relative portrait size"), 1.0, 0.25, 2.0, 0.05),
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
            "portrait_shape",
            _enum("Portrait shape", "circle", (("circle", "Circle"), ("rounded_square", "Rounded square"))),
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
            _(CATEGORY_PORTRAITS),
            "missing_portrait",
            _enum(
                "Missing portrait",
                "initials",
                (
                    ("initials", "Initials"),
                    ("neutral", "Neutral silhouette"),
                    ("gender", "Gender silhouette"),
                    ("empty", "Empty"),
                ),
            ),
        )

        menu.add_option(
            _(CATEGORY_PAPER),
            "paper_size",
            _enum(
                "Paper size",
                "A2",
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
            _(CATEGORY_PAPER), "fit_one_page", BooleanOption(_("Fit on one page"), True)
        )

        menu.add_option(
            _(CATEGORY_COLORS), "background_color", ColorOption(_("Background color"), "#FAF9F5")
        )
        menu.add_option(
            _(CATEGORY_COLORS),
            "palette",
            _enum("Palette", "mockup", (("mockup", "Ivory, earth and olive"), ("monochrome", "Monochrome"))),
        )
        menu.add_option(
            _(CATEGORY_COLORS), "outline_width", NumberOption(_("Outline width"), 1.0, 0.1, 10.0)
        )

        menu.add_option(
            _(CATEGORY_PRIVACY),
            "privacy_mode",
            _enum(
                "Privacy mode",
                "publication_safe",
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
        stdoptions.add_private_data_option(menu, _(CATEGORY_PRIVACY), default=False)
        stdoptions.add_living_people_option(
            menu,
            _(CATEGORY_PRIVACY),
            mode=LivingProxyDb.MODE_REPLACE_COMPLETE_NAME,
            after_death_years=0,
        )

        menu.add_option(
            _(CATEGORY_OUTPUT),
            "title_mode",
            _enum("Title", "automatic", (("automatic", "Automatic"), ("custom", "Custom"), ("none", "None"))),
        )
        menu.add_option(
            _(CATEGORY_OUTPUT), "custom_title", StringOption(_("Custom title"), "")
        )
        menu.add_option(
            _(CATEGORY_OUTPUT), "show_legend", BooleanOption(_("Show legend"), True)
        )
        menu.add_option(
            _(CATEGORY_OUTPUT),
            "output_format",
            _enum("Output format", "svg", (("svg", "SVG"), ("pdf", "PDF"))),
        )
        menu.add_option(
            _(CATEGORY_OUTPUT),
            "open_after_generation",
            BooleanOption(_("Open after generation"), True),
        )
        stdoptions.add_localization_option(menu, _(CATEGORY_OUTPUT))

        menu.add_option(
            _(CATEGORY_ADVANCED),
            "debug_diagnostics",
            BooleanOption(_("Write debug diagnostics"), False),
        )
        for controller in (
            "paper_size",
            "show_portraits",
            "show_places",
            "show_occupation",
        ):
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
            "show_center_as_couple": config.show_center_as_couple,
            "include_center_children": config.include_center_children,
            "parent_family_policy": config.parent_family_policy,
            "descendant_family_policy": config.descendant_family_policy,
            "show_spouses": config.show_spouses,
            "child_order": config.child_order,
            "name_format": config.name_format,
            "given_name_strategy": config.given_name_strategy,
            "name_case": config.name_case,
            "date_format": config.date_format,
            "show_places": config.show_places,
            "place_strategy": config.place_strategy,
            "show_occupation": config.show_occupation,
            "occupation_strategy": config.occupation_strategy,
            "occupation_maximum": config.occupation_maximum,
            "show_sosa": config.show_sosa,
            "show_daboville": config.show_daboville,
            "show_residence": config.show_residence,
            "show_union": config.show_union,
            "show_portraits": config.show_portraits,
            "portrait_scale": config.portrait_scale,
            "portrait_source": config.portrait_source,
            "respect_media_crop": config.respect_media_crop,
            "portrait_shape": config.portrait_shape,
            "portrait_treatment": config.portrait_treatment,
            "missing_portrait": config.missing_portrait,
            "paper_size": config.paper_size.value,
            "orientation": config.orientation.value,
            "margin_mm": config.margin_mm,
            "fit_one_page": config.fit_one_page,
            "background_color": config.background_color,
            "palette": config.palette.value,
            "outline_width": config.outline_width,
            "privacy_mode": config.privacy_mode.value,
            "incl_private": config.include_private,
            "living_people": config.living_people_mode,
            "years_past_death": config.years_past_death,
            "title_mode": config.title_mode,
            "custom_title": config.custom_title,
            "show_legend": config.show_legend,
            "output_format": config.output_format.value,
            "open_after_generation": config.open_after_generation,
            "debug_diagnostics": config.debug_diagnostics,
        }

    def apply_selected_preset(self) -> None:
        """Atomically apply a named preset while preserving the selected family."""
        if self._applying_preset:
            return
        preset = PresetName(self.menu.get_option_by_name("preset").get_value())
        if preset is PresetName.CUSTOM:
            return
        values = self._preset_option_values(build_preset(preset))
        self._applying_preset = True
        try:
            for name, value in values.items():
                self.menu.get_option_by_name(name).set_value(value)
        finally:
            self._applying_preset = False
        self.refresh_dependencies()

    def mark_configuration_custom(self) -> None:
        """Reflect a manual change without recursively reapplying a preset."""
        if self._applying_preset:
            return
        preset = self.menu.get_option_by_name("preset")
        if preset.get_value() == PresetName.CUSTOM.value:
            return
        self._applying_preset = True
        try:
            preset.set_value(PresetName.CUSTOM.value)
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
            "portrait_scale",
            "portrait_source",
            "respect_media_crop",
            "portrait_shape",
            "portrait_treatment",
            "missing_portrait",
        ):
            menu.get_option_by_name(name).set_available(portraits_enabled)

        occupation_enabled = bool(
            menu.get_option_by_name("show_occupation").get_value()
        )
        for name in ("occupation_strategy", "occupation_maximum"):
            menu.get_option_by_name(name).set_available(occupation_enabled)

        menu.get_option_by_name("place_strategy").set_available(
            bool(menu.get_option_by_name("show_places").get_value())
        )

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
                show_center_as_couple=value("show_center_as_couple"),
                include_center_children=value("include_center_children"),
                parent_family_policy=value("parent_family_policy"),
                descendant_family_policy=value("descendant_family_policy"),
                show_spouses=value("show_spouses"),
                child_order=value("child_order"),
                name_format=value("name_format"),
                given_name_strategy=value("given_name_strategy"),
                name_case=value("name_case"),
                date_format=value("date_format"),
                show_places=value("show_places"),
                place_strategy=value("place_strategy"),
                show_occupation=value("show_occupation"),
                occupation_strategy=value("occupation_strategy"),
                occupation_maximum=value("occupation_maximum"),
                show_sosa=value("show_sosa"),
                show_daboville=value("show_daboville"),
                show_residence=value("show_residence"),
                show_union=value("show_union"),
                show_portraits=value("show_portraits"),
                portrait_scale=value("portrait_scale"),
                portrait_source=value("portrait_source"),
                respect_media_crop=value("respect_media_crop"),
                portrait_shape=value("portrait_shape"),
                portrait_treatment=value("portrait_treatment"),
                missing_portrait=value("missing_portrait"),
                paper_size=paper_size,
                orientation=Orientation(value("orientation")),
                margin_mm=value("margin_mm"),
                custom_width_mm=custom_width,
                custom_height_mm=custom_height,
                fit_one_page=value("fit_one_page"),
                background_color=value("background_color"),
                palette=PaletteName(value("palette")),
                outline_width=value("outline_width"),
                privacy_mode=PrivacyMode(value("privacy_mode")),
                include_private=value("incl_private"),
                living_people_mode=value("living_people"),
                years_past_death=value("years_past_death"),
                title_mode=value("title_mode"),
                custom_title=value("custom_title"),
                show_legend=value("show_legend"),
                output_format=OutputFormat(value("output_format")),
                open_after_generation=value("open_after_generation"),
                locale=str(value("trans") or ""),
                debug_diagnostics=value("debug_diagnostics"),
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
