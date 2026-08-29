# SPDX-License-Identifier: GPL-3.0-or-later
"""Privacy-safe tag projection for cited-person markers."""

from __future__ import annotations

from typing import Any, Iterable, cast


def resolve_highlight_tag_handle(db: Any, tag_name: str) -> str | None:
    """Resolve an optional Gramps tag by its exact display name.

    The lookup is intentionally kept separate from the render model. Callers
    should project only the resulting boolean after applying privacy rules;
    handles and tag names must not enter the scene tree or output artefacts.
    """
    if not tag_name:
        return None
    getter = getattr(db, "get_tag_from_name", None)
    if not callable(getter):
        return None
    try:
        tag = getter(tag_name)
    except Exception:
        return None
    if tag is None:
        return None
    handle_getter = getattr(tag, "get_handle", None)
    if not callable(handle_getter):
        return None
    return cast(str | None, handle_getter())


def tagged_person_is_highlighted(
    person: Any | None,
    tag_handle: str | None,
    *,
    identity_exposed: bool,
) -> bool:
    """Return tag membership only when the person's identity is exposed."""
    if not identity_exposed or person is None or not tag_handle:
        return False
    getter = getattr(person, "get_tag_list", None)
    if not callable(getter):
        return False
    try:
        return tag_handle in cast(Iterable[str], getter())
    except Exception:
        return False
