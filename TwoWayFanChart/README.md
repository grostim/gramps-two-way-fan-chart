# Two-Way Fan Chart 1.2.60

Graphical report add-on for Gramps 6.0.x: ancestors above a central couple, descendants below, portrait medallions, and publication-safe privacy filtering.

When recorded, the central couple's marriage date and place appear below
their life dates. The label is omitted when privacy rules do not permit the
underlying family or partners to be shown.

## Options reference

Every option of the report menu is documented with its exact effect on
the rendered chart in [`OPTIONS.md`](OPTIONS.md) (English) and
[`OPTIONS.fr.md`](OPTIONS.fr.md) (French). The menu and the
documentation are kept in sync by an automated test
(`tests/test_option_contract.py` covers the menu, `tests/test_options_documentation.py`
covers the documentation), so any change to an option must update the
documentation in the same change.

## Recommended installation

Add this project URL to the Gramps Addon Manager:

```text
https://raw.githubusercontent.com/grostim/gramps-two-way-fan-chart/main/gramps60
```

Then refresh the **Extensions** list and install **Two-Way Fan Chart**.

The **Show ancestor marriages** option is enabled by default: the ancestor fan
gains compact intermediate sectors containing the recorded marriage year and
place for each available parent couple.

The **Show descendant marriages** option is enabled by default: the descendant
fan gains matching intermediate sectors for each recorded union. Narrow distant
sectors retain the marriage year and omit the place when the complete label
would not remain legible.

Descendant branches keep one base color per direct child of the central couple;
each following generation lightens that color progressively so the generation
depth is visible without losing the branch association.

## Manual installation

Install `TwoWayFanChart.addon.tgz` through **Addon Manager → Extensions → Install from file**.

## Releases

The CI publishes a release automatically after a pull request is merged into
`main`. The version is intentionally supplied by the pull request and must be
updated in the builder and registration metadata together. The optional
GrampsWeb rollout downloads the published archive, verifies its SHA-256
checksum, and mounts the same add-on in both the web and Celery runtimes.

## Privacy

Privacy and living-person policies are applied before formatting or media loading. A masked person contributes no real name, portrait, source handle, filename, or private metadata to the generated output.

## License

GPL-3.0-or-later.
