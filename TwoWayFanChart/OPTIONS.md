# Two-Way Fan Chart — Report Options Reference

This document describes every currently exposed configurable option of
the Two-Way Fan Chart report **and its real effect on the rendered chart**.
It is kept in sync with the option menu by an automated test
(`tests/test_option_contract.py`): every menu option must have a
section here, and every section must correspond to an existing menu
option. When you add, remove or rename an option, update this file (and
its French counterpart `OPTIONS.fr.md`) in the same change.

The report menu is organized in categories. Options added by Gramps
itself (privacy and living-people handling) are documented at the end.

---

## Subject and generations

### preset
- Type: enumerated — `publication`, `compact`, `custom`
- Default: `publication`

Applies a profile to the chart-specific options in one click. Page size
and orientation remain controlled by Gramps' standard page setup.

- `publication` — the publication mockup profile: 5 ancestor + 4
  descendant generations, all privacy options fully open, portraits
  enabled.
- `compact` — 2 ancestor + 1 descendant generation, for a quick
  family-sheet look.
- `custom` — the profile is no longer a preset; the chart uses exactly
  the values shown in the menu.

Manually changing any preset-controlled value switches the preset to
`custom` automatically (the chart keeps your new value).

### center_family
- Type: family selector
- Default: stored value, or the first family of the tree

Selects the couple drawn at the center of the chart. The left medallion
is the father, the right medallion is the mother (when both exist).
Ancestors fan out above, descendants below.

### ancestor_generations
- Type: number, 0–8
- Default: `5`

Number of ancestor generations drawn in the upper fan. `0` hides the
ancestor fan entirely. The layout reserves one radial ring per
generation and adapts label detail to the available space.

### descendant_generations
- Type: number, 0–5
- Default: `4`

Number of descendant generations drawn in the lower fan. `0` hides the
descendant fan entirely. Deeper descendants are only drawn when the
paper size leaves enough room for a legible sector.

---

## People and families

### parent_family_policy
- Type: enumerated — `primary`, `biological`, `first`
- Default: `primary`

Which family to follow when a person is the child of several families.

- `primary` — the family whose partner relationship is marked primary
  in Gramps.
- `biological` — the family where the person's birth/interaction is
  marked biological (birth relation), when recorded.
- `first` — the first family listed for the person in the database.

### descendant_family_policy
- Type: enumerated — `all`, `primary`, `first`
- Default: `all`

Which families to expand when a person has several unions.

- `all` — every recorded union produces a descendant branch.
- `primary` — only the union marked primary in Gramps.
- `first` — only the first recorded union.

### show_ancestor_marriages
- Type: boolean
- Default: `true`

When enabled, each ancestor generation ring gains compact intermediate
sectors showing the recorded marriage symbol (⚭), year and place of
each parent couple. The label is omitted when privacy rules do not
allow the couple to be shown.

### show_descendant_marriages
- Type: boolean
- Default: `true`

When enabled, union sectors are inserted after each descendant
generation showing the recorded marriage symbol (⚭), year and place.
From the second generation onward the band carries two lines — the
date on the first, the place on the second — so a distant sector keeps
the place instead of dropping it. The direct-child band keeps a single
line. When a sector is too narrow for the two readable lines, the band
keeps one line and the marriage symbol with the year only.

---

## Portraits and medallions

### show_portraits
- Type: boolean
- Default: `true`

Draws the portrait medallion of every visible person. When disabled,
the medallions show a fallback (initials or silhouette). All portrait
sub-options below are only active while this option is enabled.

### portrait_source
- Type: enumerated — `first_image`, `tagged_portrait`, `primary`
- Default: `first_image`

Which media of the person to use as portrait.

- `first_image` — the first image-type media in Gramps order.
- `tagged_portrait` — the first media reference carrying the documented
  custom attribute `portrait` with a truthy value.
- `primary` — only the media marked primary in Gramps.

The first usable image of the selected set is used, in Gramps order.

### respect_media_crop
- Type: boolean
- Default: `true`

When enabled, a crop rectangle recorded on the media reference is
applied before the square centering. When disabled, the full image is
used.

### portrait_treatment
- Type: enumerated — `color`, `grayscale`, `sepia`
- Default: `color`

Color rendering of the portrait: original colors, grayscale, or sepia
duotone.

---

## Paper and layout

Page size and orientation use Gramps' standard page setup options
(`papers` and `papero`), rather than duplicate Two-Way Fan Chart options.
The selected page dimensions are used for SVG, PDF, and PNG output.

### margin_mm
- Type: number (mm), 0–100
- Default: `12`

Uniform margin around the chart. The drawing area is the paper minus
these margins on all four sides.

---

## Colors and styles

### background_color
- Type: color
- Default: `#FAF9F5`

Background color of the chart (paper color). It is used as the SVG
page background and the PDF/PNG background.

---

## Privacy

### privacy_mode
- Type: enumerated — `include_all`, `full_name_only`,
  `replace_identity`, `exclude`, `publication_safe`
- Default: `include_all`

Policy applied to people **marked private** in the database. It only
has an effect when `Include data marked private` is unchecked (or when
`publication_safe` is selected).

- `include_all` — private people are shown normally.
- `full_name_only` — the full name is kept, dates and portraits are
  dropped.
- `replace_identity` — the identity is replaced by a generic
  "Personne privée" placeholder.
- `exclude` — the person disappears from the chart completely.
- `publication_safe` — the strictest combined profile: private and
  living people are masked regardless of the other options, marriage
  labels of protected families are suppressed.

### incl_private
*(standard Gramps option)*
- Type: boolean
- Default: `true` (checked)

Whether the information in the database marked private is included.
When unchecked, private people are filtered according to
`privacy_mode`.

### living_people
*(standard Gramps option)*
- Type: enumerated — `include_all`, `include_last_name_only`,
  `include_full_name_only`, `replace_complete_name`, `exclude_all`
- Default: `include_all`

How living people are handled.

- `include_all` — living people are shown normally.
- `include_last_name_only` — the surname is kept, all other personal
  data (given names, dates, portrait) is removed.
- `include_full_name_only` — the full name is kept, all other data is
  removed.
- `replace_complete_name` — the identity is replaced by the Gramps
  private placeholder.
- `exclude_all` — living people are removed from the chart completely.

### years_past_death
*(standard Gramps option)*
- Type: number (years), ≥ 0
- Default: `0`

Number of years after a person's death after which the person is no
longer considered living, for the living-people filter above. `0`
means only people with a recorded death date are considered dead.

---

## Output

The report output format (SVG, PDF, PNG) is **always** determined by
the output file extension chosen by the report dialog, the command
line, or Gramps Web. There is no dedicated format option in this add-on
menu.
