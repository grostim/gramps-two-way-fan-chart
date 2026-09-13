# Two-Way Fan Chart 1.2.40

Graphical report add-on for Gramps 6.0.x: ancestors above a central couple, descendants below, portrait medallions, and publication-safe privacy filtering.

## Recommended installation

Add this project URL to the Gramps Addon Manager:

```text
https://raw.githubusercontent.com/grostim/gramps-two-way-fan-chart/main/gramps60
```

Then refresh the **Extensions** list and install **Two-Way Fan Chart**.

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
