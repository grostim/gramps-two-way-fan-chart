# Two-Way Fan Chart for Gramps

A stable graphical-report add-on for **Gramps 6.0.x**. It renders a central couple, ancestors above, descendants below, and privacy-safe portrait medallions in a publication-ready fan chart.

## Screenshot

![Two-Way Fan Chart rendered from synthetic genealogy data](assets/two-way-fan-chart-synthetic-example.png)

*Publication preset with entirely synthetic names and relationships. The vintage portraits are AI-generated fictional identities; no real genealogy or person is shown.*

## Install as a Gramps add-on project

The repository is directly consumable by the Gramps Addon Manager and supports automatic update discovery.

1. Open the **Addon Manager** in Gramps.
2. In **Configuration → Projects**, add a project named `grostim` with this URL:

   ```text
   https://raw.githubusercontent.com/grostim/gramps-two-way-fan-chart/main/gramps60
   ```

3. Return to **Extensions**, refresh the list, select **Two-Way Fan Chart**, and install it.
4. Restart Gramps if requested.

The project exposes the files expected by Gramps:

- `gramps60/listings/addons-en.json`
- `gramps60/listings/addons-fr.json`
- `gramps60/download/TwoWayFanChart.addon.tgz`

### Installation rapide en français

Dans le gestionnaire d’extensions Gramps, ajoutez le projet `grostim` avec l’URL ci-dessus, actualisez la liste, puis installez **Éventail généalogique bidirectionnel** depuis l’onglet **Extensions**.

## Manual installation

Download `TwoWayFanChart.addon.tgz` from the [latest GitHub release](https://github.com/grostim/gramps-two-way-fan-chart/releases/latest), then use **Addon Manager → Extensions → Install from file**.

## Release and Gramps Web deployment

`main` is the stable channel; `experimental` publishes GitHub pre-releases. Both
branches use the same numeric version sequence and tags (`vX.Y.Z`), with each
release strictly newer than every existing tag. Do not use a `-beta` suffix:
Gramps' version comparator does not interpret it correctly.

Desktop users select a channel by adding the corresponding Addon Manager project
URL and keeping only one project enabled for this add-on:

- Stable: `https://raw.githubusercontent.com/grostim/gramps-two-way-fan-chart/main/gramps60`
- Experimental: `https://raw.githubusercontent.com/grostim/gramps-two-way-fan-chart/experimental/gramps60`

On Gramps Web there is only one shared installation. If deployment is enabled,
a successful release from either branch replaces the active add-on for every
user on that server; an experimental deployment remains active until a later
stable release is deployed. Web plugin discovery requires recreating the web
and Celery services, so this path is opt-in and must be operated deliberately.

A release PR must update the version in `build_addon.py` and
`TwoWayFanChart/TwoWayFanChart.gpr.py`, then regenerate the stable archive and
both listings with `python3 build_addon.py`. Reusing an existing version is
rejected rather than replacing an existing tag or release. Experimental CI
builds transform only the archived registration/listings to experimental
status; the tracked source registration remains stable.

The optional `deploy / GrampsWeb` job is skipped unless the repository variable
`GRAMPSWEB_DEPLOY_ENABLED` is exactly `true`. To enable it, configure the
`PORTAINER_UTIL_TOKEN` secret with Contents read/write on `grostim/portainer-util`
and keep the Portainer stack connected to that repository's `main` branch with
its existing push webhook. No SSH key or GrampsWeb credential is stored here.

The deployment job commits only the validated channel, version, and rollout
markers to `portainer-util`. Portainer retrieves the exact GitHub release asset,
verifies its checksum, stages it outside the plugin scan root, promotes it
atomically, and recreates the web/Celery services.

Rollback is explicit and manual: run the workflow on `main` with `rollback_version`
set to an exact previously published stable tag (for example `v1.2.96`). The
job rejects drafts, prereleases and releases missing either archive or checksum,
then writes a distinct stable rollback marker; the normal release path still
rejects downgrades. The downloader verifies the immutable archive checksum
before promotion. Do not treat a successful release or a Portainer marker update
as proof that Gramps Web has loaded the add-on; verify both services and the
report runtime.

## Usage

1. Open a Gramps family tree.
2. Go to **Reports → Graphical Reports → Two-Way Fan Chart**.
3. Select the center family and the desired privacy/layout preset.
4. If tag markers are useful for a working chart, enable **Show citation
   markers** and enter a Gramps tag in **Highlight tag**. The publication
   profile leaves this option disabled so the fan remains visually uncluttered;
   the signal is cleared automatically for masked or excluded people.
5. Choose the output file format (SVG, PDF, or PNG) through the report
   dialog, the command-line extension, or Gramps Web, and generate the
   report.

The effect of every menu option is documented in
[`TwoWayFanChart/OPTIONS.md`](TwoWayFanChart/OPTIONS.md) (English) and
[`TwoWayFanChart/OPTIONS.fr.md`](TwoWayFanChart/OPTIONS.fr.md) (French).
A CI test keeps this documentation in sync with the option menu: adding,
removing or renaming an option without updating both files fails the
build.

When the selected center family has a recorded marriage event, the chart
displays its marriage date and place below the central couple's life dates.
The information follows the same privacy rules as the rest of the chart.

To include marriage information for each recorded ancestor couple, use
**Show ancestor marriages** (enabled by default). The report then inserts
compact intermediate sectors in the ancestor fan and displays the recorded
marriage year and place, without altering the standard fan layout.

To include the same information for descendant couples, use
**Show descendant marriages** (enabled by default). Intermediate sectors
are inserted after each descendant generation; when a distant sector
cannot carry the place legibly, the label keeps the marriage year only.

Each descendant generation is drawn in a progressively lighter shade of its
direct-child branch color, so a branch remains recognizable across the whole
fan while the generation depth stays readable at a glance.

Headless example:

```bash
gramps -O "MyTree" -a report -p \
  name=two_way_fan_chart,off=svg,of=fan-chart.svg,center_family=F0001
```

## Features

- bidirectional ancestor/descendant fan layout;
- adaptive ancestor depth from 0 to 8 generations, with density-aware detail reduction;
- complete given-name + surname labels for the center and ancestors, with usage-name labels for descendants; records without known life years have no date label;
- central couple marriage date and place when recorded;
- optional intermediate ancestor-marriage sectors with marriage year and place;
- optional intermediate descendant-marriage sectors with year/place fallback;
- privacy filtering before formatting and media loading;
- optional exact-name tag highlighting with a grayscale-distinct marker;
- circular portrait crops with neutral, gendered, or initials fallbacks;
- weighted descendant sectors and narrow-sector radial labels;
- progressive generation shading inside each descendant branch;
- portable vector labels for SVG, librsvg/Cairo, and browser renderers;
- standalone SVG output without network resources or JavaScript;
- optional PDF and PNG output through Cairo;
- GUI and headless CLI support.

## Privacy

By default, the chart includes all individuals, including private and living people, as requested for family use. The **Safe publication** privacy mode remains available when an export must mask living/private people before names, facts, portraits, metadata, and diagnostics reach the renderer. Masked people use neutral visual markers; their source media is not loaded.

No real genealogy database, family portrait, or generated chart based on private data is included in this public repository. The screenshot above was generated exclusively from synthetic fixtures and AI-generated fictional portraits.

## Compatibility

- Gramps: **6.0.x**
- Add-on version: **1.2.97**
- SVG: no optional dependency
- PDF/PNG: Cairo/Pango support required in the Gramps runtime

## Repository contents

- `TwoWayFanChart/` — distributable add-on source
- `gramps60/` — Gramps project listings and installable archive
- `build_addon.py` — distribution builder

## License

GPL-3.0-or-later. See [`LICENSE`](LICENSE).
