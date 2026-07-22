# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure privacy decisions applied before formatting or media access."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .config import PrivacyMode
    from .model import PersonViewSeed, SurnamePart, VisibilityState
except ImportError:  # Gramps loads add-ons as top-level modules.
    from config import PrivacyMode  # type: ignore[no-redef]
    from model import PersonViewSeed, SurnamePart, VisibilityState  # type: ignore[no-redef]


@dataclass(frozen=True, slots=True)
class VisibilityDecision:
    """Capabilities granted to every layer after the privacy gate."""

    state: VisibilityState
    expose_real_name: bool
    expose_details: bool
    expose_media: bool
    keep_slot: bool


@dataclass(frozen=True, slots=True)
class PersonPrivacyFacts:
    """Only the privacy facts needed before names or media are touched."""

    is_private: bool
    is_living: bool


@dataclass(frozen=True, slots=True)
class PersonSourceData:
    """Sensitive source values consumed exactly once by the privacy gate."""

    source_handle: str
    given_name: str
    surname: str
    details: tuple[str, ...]
    media_reference: str | None
    call_name: str = ""
    nick_name: str = ""
    title: str = ""
    suffix: str = ""
    family_nick_name: str = ""
    surname_parts: tuple[SurnamePart, ...] = ()


def person_source_data_from_gramps(
    person,
    *,
    details: tuple[str, ...] = (),
    media_reference: str | None = None,
) -> PersonSourceData:
    """Copy sensitive structured name primitives before the privacy decision."""
    name = person.get_primary_name()
    parts = tuple(
        SurnamePart(
            surname=item.get_surname(),
            prefix=item.get_prefix(),
            connector=item.get_connector(),
            primary=bool(item.get_primary()),
            origin_type=int(item.get_origintype()),
        )
        for item in name.get_surname_list()
    )
    surname = " ".join(
        component
        for part in parts
        for component in (part.prefix, part.surname, part.connector)
        if component
    )
    return PersonSourceData(
        source_handle=person.get_handle(),
        given_name=name.get_first_name(),
        surname=surname,
        details=details,
        media_reference=media_reference,
        call_name=name.get_call_name(),
        nick_name=name.get_nick_name(),
        title=name.get_title(),
        suffix=name.get_suffix(),
        family_nick_name=name.get_family_nick_name(),
        surname_parts=parts,
    )


_DECISIONS = {
    VisibilityState.VISIBLE: VisibilityDecision(
        VisibilityState.VISIBLE, True, True, True, True
    ),
    VisibilityState.NAME_ONLY: VisibilityDecision(
        VisibilityState.NAME_ONLY, True, False, False, True
    ),
    VisibilityState.MASKED: VisibilityDecision(
        VisibilityState.MASKED, False, False, False, True
    ),
    VisibilityState.EXCLUDED: VisibilityDecision(
        VisibilityState.EXCLUDED, False, False, False, False
    ),
}

_PROTECTED_POLICY_STATES = {
    PrivacyMode.INCLUDE_ALL: VisibilityState.VISIBLE,
    PrivacyMode.FULL_NAME_ONLY: VisibilityState.NAME_ONLY,
    PrivacyMode.SURNAME_ONLY: VisibilityState.NAME_ONLY,
    PrivacyMode.REPLACE_IDENTITY: VisibilityState.MASKED,
    PrivacyMode.EXCLUDE: VisibilityState.EXCLUDED,
    PrivacyMode.PUBLICATION_SAFE: VisibilityState.MASKED,
}

_GRAMPS_LIVING_STATES = {
    99: VisibilityState.VISIBLE,
    2: VisibilityState.NAME_ONLY,
    1: VisibilityState.NAME_ONLY,
    3: VisibilityState.MASKED,
    0: VisibilityState.EXCLUDED,
}

_RESTRICTION_ORDER = {
    VisibilityState.VISIBLE: 0,
    VisibilityState.NAME_ONLY: 1,
    VisibilityState.MASKED: 2,
    VisibilityState.EXCLUDED: 3,
}


def decision_for_state(state: VisibilityState) -> VisibilityDecision:
    """Return an immutable capability decision for one visibility state."""
    if not isinstance(state, VisibilityState):
        raise ValueError("visibility state must be a VisibilityState")
    return _DECISIONS[state]


def visibility_for_policy(
    mode: PrivacyMode, *, protected: bool
) -> VisibilityState:
    """Map a protected/unprotected person to a visibility state."""
    if not isinstance(mode, PrivacyMode):
        raise ValueError("privacy mode must be a PrivacyMode")
    if not protected:
        return VisibilityState.VISIBLE
    return _PROTECTED_POLICY_STATES[mode]


def privacy_facts_from_gramps(
    person,
    database,
    *,
    current_year: int | None = None,
    years_past_death: int = 0,
) -> PersonPrivacyFacts:
    """Delegate probable-life inference to Gramps and retain only two booleans."""
    if years_past_death < 0:
        raise ValueError("years past death must not be negative")
    from gramps.gen.lib import Date
    from gramps.gen.utils.alive import probably_alive

    current_date = None
    if current_year is not None:
        current_date = Date()
        current_date.set_year(current_year)

    unfiltered_person = person
    get_handle = getattr(person, "get_handle", None)
    person_handle = get_handle() if callable(get_handle) else None
    get_unfiltered_person = getattr(database, "get_unfiltered_person", None)
    if person_handle and callable(get_unfiltered_person):
        unfiltered_person = get_unfiltered_person(person_handle) or person
    underlying_database = getattr(database, "db", database)
    return PersonPrivacyFacts(
        is_private=bool(unfiltered_person.get_privacy()),
        is_living=bool(
            probably_alive(
                unfiltered_person,
                underlying_database,
                current_date,
                years_past_death,
            )
        ),
    )


def classify_visibility(
    facts: PersonPrivacyFacts,
    *,
    privacy_mode: PrivacyMode,
    include_private: bool,
    living_people_mode: int,
) -> VisibilityState:
    """Combine private and living restrictions before any data projection."""
    if not isinstance(facts, PersonPrivacyFacts):
        raise ValueError("privacy facts must be PersonPrivacyFacts")
    if not isinstance(privacy_mode, PrivacyMode):
        raise ValueError("privacy mode must be a PrivacyMode")
    if living_people_mode not in _GRAMPS_LIVING_STATES:
        raise ValueError("living people mode is not supported by Gramps")

    states = [VisibilityState.VISIBLE]
    if facts.is_private and (
        not include_private or privacy_mode is PrivacyMode.PUBLICATION_SAFE
    ):
        states.append(visibility_for_policy(privacy_mode, protected=True))
    if facts.is_living:
        if privacy_mode is PrivacyMode.PUBLICATION_SAFE:
            states.append(VisibilityState.MASKED)
        else:
            states.append(_GRAMPS_LIVING_STATES[living_people_mode])
    return max(states, key=_RESTRICTION_ORDER.__getitem__)


def project_person_seed(
    position_id: str,
    source: PersonSourceData,
    state: VisibilityState,
    *,
    living_people_mode: int,
    surname_only: bool = False,
) -> PersonViewSeed | None:
    """Consume sensitive values and return only data authorized for rendering."""
    if not position_id:
        raise ValueError("position id must not be empty")
    if not isinstance(source, PersonSourceData):
        raise ValueError("source must be PersonSourceData")
    if not isinstance(state, VisibilityState):
        raise ValueError("visibility state must be a VisibilityState")
    if living_people_mode not in _GRAMPS_LIVING_STATES:
        raise ValueError("living people mode is not supported by Gramps")
    if source.source_handle and source.source_handle in position_id:
        raise ValueError("safe position id must be independent from source identity")

    if state is VisibilityState.EXCLUDED:
        return None
    if state is VisibilityState.MASKED:
        return PersonViewSeed(
            position_id=position_id,
            visibility=state,
            given_name="",
            surname="",
            details=(),
            media_reference=None,
            masked_label="Personne privée",
        )
    if state is VisibilityState.NAME_ONLY:
        given_name = "" if surname_only else source.given_name
        return PersonViewSeed(
            position_id=position_id,
            visibility=state,
            given_name=given_name,
            surname=source.surname,
            details=(),
            media_reference=None,
            call_name="" if surname_only else source.call_name,
            nick_name="" if surname_only else source.nick_name,
            title="" if surname_only else source.title,
            suffix="" if surname_only else source.suffix,
            family_nick_name="" if surname_only else source.family_nick_name,
            surname_parts=source.surname_parts,
        )
    return PersonViewSeed(
        position_id=position_id,
        visibility=state,
        given_name=source.given_name,
        surname=source.surname,
        details=source.details,
        media_reference=source.media_reference,
        call_name=source.call_name,
        nick_name=source.nick_name,
        title=source.title,
        suffix=source.suffix,
        family_nick_name=source.family_nick_name,
        surname_parts=source.surname_parts,
    )


def sanitize_person_for_rendering(
    position_id: str,
    source: PersonSourceData,
    facts: PersonPrivacyFacts,
    *,
    privacy_mode: PrivacyMode,
    include_private: bool,
    living_people_mode: int,
) -> PersonViewSeed | None:
    """Authoritative boundary: classify first, then emit one sanitized seed."""
    state = classify_visibility(
        facts,
        privacy_mode=privacy_mode,
        include_private=include_private,
        living_people_mode=living_people_mode,
    )
    private_surname_only = (
        facts.is_private
        and (not include_private or privacy_mode is PrivacyMode.PUBLICATION_SAFE)
        and privacy_mode is PrivacyMode.SURNAME_ONLY
    )
    living_surname_only = facts.is_living and living_people_mode == 1
    return project_person_seed(
        position_id,
        source,
        state,
        living_people_mode=living_people_mode,
        surname_only=private_surname_only or living_surname_only,
    )
