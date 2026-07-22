# SPDX-License-Identifier: GPL-3.0-or-later
"""Extraction of sanitized, layout-neutral biographical facts."""

from __future__ import annotations

from dataclasses import dataclass

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.place import displayer as place_displayer
from gramps.gen.lib import EventType, PlaceType
from gramps.gen.utils.db import get_birth_or_fallback, get_death_or_fallback
from gramps.gen.utils.location import get_main_location

try:
    from .model import (
        InformationLine,
        InformationProfile,
        PersonView,
        PersonViewSeed,
        VisibilityState,
    )
    from .names import NameFormatter, derive_name_labels
except ImportError:  # Gramps loads add-ons as top-level modules.
    from model import (  # type: ignore[no-redef]
        InformationLine,
        InformationProfile,
        PersonView,
        PersonViewSeed,
        VisibilityState,
    )
    from names import NameFormatter, derive_name_labels  # type: ignore[no-redef]


@dataclass(frozen=True, slots=True)
class VitalFact:
    """One formatted vital date and whether a fallback event supplied it."""

    text: str
    year: int | None
    fallback: bool


@dataclass(frozen=True, slots=True)
class VitalDates:
    """Birth and death facts ready for information profiles."""

    birth: VitalFact
    death: VitalFact


@dataclass(frozen=True, slots=True)
class EventFact:
    """One optional event fact before layout."""

    text: str
    date_text: str
    place: str
    year: int | None


def format_date(date, date_format: str, locale=glocale) -> str:
    """Format one Gramps Date without changing global locale preferences."""
    if date_format not in {"years", "short", "full"}:
        raise ValueError(f"unsupported date format: {date_format}")
    if date is None or not date.is_valid():
        return ""
    if date_format == "years":
        year = date.get_year()
        return str(year) if year else ""
    displayer = locale.date_displayer
    if hasattr(displayer, "set_format"):
        format_number = 1 if date_format == "short" else 2
        displayer = type(displayer)(format=format_number, blocale=locale)
    return displayer.display_formatted(date)


def _event_fact(event, direct_ref, date_format: str, locale) -> VitalFact:
    if event is None:
        return VitalFact("", None, False)
    date = event.get_date_object()
    text = format_date(date, date_format, locale)
    year = date.get_year() if date is not None and date.is_valid() else None
    direct_handle = direct_ref.get_reference_handle() if direct_ref else None
    return VitalFact(text, year or None, event.get_handle() != direct_handle)


def extract_vital_dates(
    database,
    person,
    date_format: str,
    locale=glocale,
) -> VitalDates:
    """Read birth/death events, including Gramps fallback events."""
    if date_format not in {"years", "short", "full"}:
        raise ValueError(f"unsupported date format: {date_format}")
    birth = get_birth_or_fallback(database, person)
    death = get_death_or_fallback(database, person)
    return VitalDates(
        birth=_event_fact(
            birth, person.get_birth_ref(), date_format, locale
        ),
        death=_event_fact(
            death, person.get_death_ref(), date_format, locale
        ),
    )


def format_event_place(
    database,
    event,
    strategy: str,
    *,
    displayer=place_displayer,
) -> str:
    """Format one event place through Gramps, then shorten explicitly."""
    if strategy not in {
        "gramps",
        "locality",
        "locality_region",
        "locality_country",
    }:
        raise ValueError(f"unsupported place strategy: {strategy}")
    if event is None:
        return ""
    displayed = displayer.display_event(database, event).strip()
    if not displayed or strategy == "gramps":
        return displayed

    place_handle = event.get_place_handle()
    get_place = getattr(database, "get_place_from_handle", None)
    place = get_place(place_handle) if place_handle and callable(get_place) else None
    if place is not None:
        location = get_main_location(database, place, event.get_date_object())

        def first_of(*place_types):
            return next(
                (
                    location.get(int(place_type), "").strip()
                    for place_type in place_types
                    if location.get(int(place_type), "").strip()
                ),
                "",
            )

        locality = first_of(
            PlaceType.LOCALITY,
            PlaceType.CITY,
            PlaceType.PARISH,
            PlaceType.NEIGHBORHOOD,
            PlaceType.DISTRICT,
            PlaceType.STREET,
        )
        region = first_of(
            PlaceType.DEPARTMENT,
            PlaceType.REGION,
            PlaceType.STATE,
            PlaceType.PROVINCE,
            PlaceType.COUNTY,
        )
        country = first_of(PlaceType.COUNTRY)
        selected = {
            "locality": (locality,),
            "locality_region": (locality, region),
            "locality_country": (locality, country),
        }[strategy]
        if all(selected):
            return ", ".join(selected)

    # A localized display string is not a semantic hierarchy. If Gramps cannot
    # provide typed levels, preserve its complete label rather than guessing
    # locality/region/country from comma positions.
    return displayed


def extract_vital_places(
    database,
    person,
    place_strategy: str,
    *,
    displayer=place_displayer,
) -> tuple[str, str]:
    """Format birth/death places from the same Gramps fallback events as dates."""
    birth = get_birth_or_fallback(database, person)
    death = get_death_or_fallback(database, person)
    return (
        format_event_place(database, birth, place_strategy, displayer=displayer),
        format_event_place(database, death, place_strategy, displayer=displayer),
    )


def _events_for(database, owner, event_type: int, *, primary_only: bool = False):
    events = []
    references = (
        owner.get_primary_event_ref_list()
        if primary_only and hasattr(owner, "get_primary_event_ref_list")
        else owner.get_event_ref_list()
    )
    for reference in references:
        event = database.get_event_from_handle(reference.get_reference_handle())
        if event is not None and event.get_type() == event_type:
            events.append(event)
    return tuple(events)


def _event_year(event) -> int | None:
    date = event.get_date_object()
    if date is None or not date.is_valid():
        return None
    return date.get_year() or None


def select_occupations(
    database,
    person,
    strategy: str = "last_dated",
    *,
    limit: int = 1,
    reference_year: int | None = None,
) -> tuple[str, ...]:
    """Select occupation descriptions using only V1 specification rules."""
    allowed = {
        "first_dated",
        "last_dated",
        "closest_union",
        "distinct",
        "first_nonempty",
    }
    if strategy not in allowed:
        raise ValueError(f"unsupported occupation strategy: {strategy}")
    if limit < 1:
        raise ValueError("occupation limit must be positive")

    candidates = tuple(
        (event, event.get_description().strip(), _event_year(event))
        for event in _events_for(
            database, person, EventType.OCCUPATION, primary_only=True
        )
        if event.get_description().strip()
    )
    if not candidates:
        return ()
    dated = tuple(candidate for candidate in candidates if candidate[2] is not None)

    if strategy == "distinct":
        distinct = []
        for _, text, _ in candidates:
            if text not in distinct:
                distinct.append(text)
        return tuple(distinct[:limit])
    if strategy == "first_nonempty":
        return (candidates[0][1],)
    if strategy == "closest_union":
        if reference_year is None:
            raise ValueError("closest_union requires reference_year")
        if dated:
            selected = min(dated, key=lambda item: abs(item[2] - reference_year))
            return (selected[1],)
        return (candidates[0][1],)
    if dated:
        key = lambda item: item[2]
        selected = min(dated, key=key) if strategy == "first_dated" else max(dated, key=key)
        return (selected[1],)
    return (candidates[0][1],)


def extract_residence(
    database,
    person,
    place_strategy: str,
    date_format: str,
    *,
    locale=glocale,
    displayer=place_displayer,
) -> EventFact | None:
    """Select the latest dated residence, otherwise the first in Gramps order."""
    events = _events_for(
        database, person, EventType.RESIDENCE, primary_only=True
    )
    if not events:
        return None
    dated = tuple(event for event in events if _event_year(event) is not None)
    selected = max(dated, key=_event_year) if dated else events[0]
    return EventFact(
        text=selected.get_description().strip(),
        date_text=format_date(selected.get_date_object(), date_format, locale),
        place=format_event_place(
            database, selected, place_strategy, displayer=displayer
        ),
        year=_event_year(selected),
    )


def extract_union(
    database,
    family,
    date_format: str,
    place_strategy: str,
    *,
    locale=glocale,
    displayer=place_displayer,
) -> EventFact | None:
    """Extract the first marriage event in the family's Gramps order."""
    events = _events_for(database, family, EventType.MARRIAGE)
    if not events:
        return None
    selected = events[0]
    return EventFact(
        text=selected.get_description().strip(),
        date_text=format_date(selected.get_date_object(), date_format, locale),
        place=format_event_place(
            database, selected, place_strategy, displayer=displayer
        ),
        year=_event_year(selected),
    )


_INFORMATION_ZONES = {
    "central_couple",
    "ancestor_inner",
    "ancestor_outer",
    "children_spouses",
    "descendant_outer",
}


def _lifespan(vitals: VitalDates) -> str:
    birth = vitals.birth.year
    death = vitals.death.year
    if birth and death:
        return f"{birth}–{death}"
    if birth:
        return f"{birth}–"
    if death:
        return f"–{death}"
    return ""


def _event_fact_label(fact: EventFact | None) -> str:
    if fact is None:
        return ""
    parts = tuple(
        value.strip()
        for value in (fact.date_text, fact.place, fact.text)
        if value and value.strip()
    )
    return " · ".join(dict.fromkeys(parts))


def build_information_profile(
    zone: str,
    labels,
    vitals: VitalDates,
    *,
    family_summary: str = "",
    child_count: int | None = None,
    birth_place: str = "",
    death_place: str = "",
    occupations: tuple[str, ...] = (),
    number_label: str = "",
    residence: EventFact | None = None,
    union: EventFact | None = None,
    include_places: bool = False,
    include_occupation: bool = False,
    include_residence: bool = False,
    include_union: bool = False,
) -> InformationProfile:
    """Build prioritized semantic lines for the five V1 chart zones."""
    if zone not in _INFORMATION_ZONES:
        raise ValueError(f"unsupported information zone: {zone}")

    lines = [InformationLine("name", labels.short_label, 1)]
    if zone == "central_couple" and labels.full_label != labels.short_label:
        lines.append(InformationLine("full_name", labels.full_label, 2))

    lifespan = _lifespan(vitals)
    if zone == "descendant_outer":
        if lifespan:
            lines.append(InformationLine("vital_years", lifespan, 4))
    elif lifespan:
        lines.append(InformationLine("lifespan", lifespan, 4))

    if zone == "children_spouses" and child_count is not None:
        lines.append(InformationLine("children", str(child_count), 5))
    if include_places:
        if birth_place:
            lines.append(InformationLine("birth_place", birth_place, 6))
        if death_place:
            lines.append(InformationLine("death_place", death_place, 6))
    if include_occupation and occupations:
        lines.append(InformationLine("occupation", "; ".join(occupations), 7))
    if include_union:
        union_label = _event_fact_label(union)
        if union_label:
            lines.append(InformationLine("union", union_label, 5))
    if include_residence:
        residence_label = _event_fact_label(residence)
        if residence_label:
            lines.append(InformationLine("residence", residence_label, 6))
    if zone == "central_couple" and family_summary:
        lines.append(InformationLine("family_summary", family_summary, 8))
    if number_label:
        lines.append(InformationLine("numbering", number_label, 8))

    return InformationProfile(
        zone, tuple(sorted(lines, key=lambda line: line.priority))
    )


def sosa_number(
    generation: int,
    index: int,
    *,
    enabled: bool = True,
) -> str | None:
    """Return the Sosa number for a zero-based slot in an ancestor generation."""
    if not enabled:
        return None
    if generation < 1 or index < 0 or index >= 2**generation:
        raise ValueError("invalid Sosa slot")
    return str(2**generation + index)


def daboville_number(
    path: tuple[int, ...],
    *,
    enabled: bool = True,
) -> str | None:
    """Return a d'Aboville label for a deterministic one-based child path."""
    if not enabled:
        return None
    if not path or any(index < 1 for index in path):
        raise ValueError("invalid d'Aboville path")
    return ".".join(str(index) for index in path)


_EMPTY_VITALS = VitalDates(
    VitalFact("", None, False),
    VitalFact("", None, False),
)


def simple_name(database, handle: str | None) -> str:
    """Return a short display name for a person handle, or empty string.

    Uses the call name (prénom d'usage) when available, falling back to
    the first given name. This keeps labels short and publication-friendly.
    """
    if not handle:
        return ""
    person = database.get_person_from_handle(handle)
    if person is None:
        return ""
    name = person.get_primary_name()

    # Try to get the call name (prénom d'usage) from the Gramps name object
    call = ""
    try:
        call = name.get_call_name().strip()
    except Exception:
        pass

    given = call or name.get_first_name().strip()
    # If first_name is still multiple words and we have a call name, use call;
    # otherwise take only the first word of given to keep it short
    if not call and " " in given:
        given = given.split()[0]

    surname = ""
    try:
        surnames = [s.get_surname() for s in name.get_surname_list() if s.get_surname()]
        surname = " ".join(surnames).strip()
    except Exception:
        pass

    if surname and given:
        return f"{surname}, {given}"
    if surname:
        return surname
    return given


def simple_name_full(database, handle: str | None) -> str:
    """Return a full display name (all given names) for the center couple."""
    if not handle:
        return ""
    person = database.get_person_from_handle(handle)
    if person is None:
        return ""
    name = person.get_primary_name()
    try:
        from gramps.gen.display.name import displayer as name_displayer
        label = name_displayer.display_name(name).strip(" ,")
        return label or ""
    except Exception:
        given = name.get_first_name().strip()
        surname = " ".join(
            s.get_surname()
            for s in name.get_surname_list()
            if s.get_surname()
        ).strip()
        return f"{given} {surname}".strip()


def simple_dates(database, handle: str | None) -> str:
    """Return a compact life-years label for a person handle.

    Returns one of:
      - "YYYY–YYYY" when both birth and death years are known
      - "YYYY–"     when only birth year is known
      - "–YYYY"     when only death year is known
      - ""          when neither is known

    Uses Gramps' fallback birth/death event search so that christening
    or burial events are considered when birth/death are missing.
    """
    if not handle:
        return ""
    person = database.get_person_from_handle(handle)
    if person is None:
        return ""
    try:
        birth = get_birth_or_fallback(database, person)
        death = get_death_or_fallback(database, person)
    except Exception:
        return ""
    birth_year = _event_year(birth) if birth is not None else None
    death_year = _event_year(death) if death is not None else None
    if birth_year and death_year:
        return f"{birth_year}–{death_year}"
    if birth_year:
        return f"{birth_year}–"
    if death_year:
        return f"–{death_year}"
    return ""


def build_person_view(
    seed: PersonViewSeed,
    database,
    person,
    config,
    zone: str,
    *,
    family=None,
    family_summary: str = "",
    child_count: int | None = None,
    ancestor_slot: tuple[int, int] | None = None,
    descendant_path: tuple[int, ...] | None = None,
    union_year: int | None = None,
    locale=glocale,
    name_formats=None,
) -> PersonView:
    """Format a sanitized seed and read details only for fully visible people."""
    if not isinstance(seed, PersonViewSeed):
        raise ValueError("person view requires a sanitized PersonViewSeed")
    if seed.visibility is VisibilityState.EXCLUDED:
        raise ValueError("excluded person cannot produce a PersonView")

    formatter = NameFormatter.from_config(
        config,
        locale=locale,
        name_formats=name_formats,
    )
    labels = derive_name_labels(
        seed,
        formatter,
        short_strategy=config.given_name_strategy,
    )

    vitals = _EMPTY_VITALS
    birth_place = death_place = ""
    occupations: tuple[str, ...] = ()
    residence = None
    union = None
    number_label = ""
    if seed.visibility is VisibilityState.VISIBLE:
        vitals = extract_vital_dates(database, person, config.date_format, locale)
        if config.show_places:
            birth_place, death_place = extract_vital_places(
                database, person, config.place_strategy
            )
        if config.show_occupation:
            occupations = select_occupations(
                database,
                person,
                config.occupation_strategy,
                limit=config.occupation_maximum,
                reference_year=union_year,
            )
        if config.show_residence:
            residence = extract_residence(
                database,
                person,
                config.place_strategy,
                config.date_format,
                locale=locale,
            )
        if config.show_union and family is not None:
            union = extract_union(
                database,
                family,
                config.date_format,
                config.place_strategy,
                locale=locale,
            )
        if config.show_sosa and ancestor_slot is not None:
            number_label = f"Sosa {sosa_number(*ancestor_slot)}"
        elif config.show_daboville and descendant_path is not None:
            number_label = f"d’Aboville {daboville_number(descendant_path)}"
    else:
        family_summary = ""
        child_count = None
        number_label = ""

    information = build_information_profile(
        zone,
        labels,
        vitals,
        family_summary=family_summary,
        child_count=child_count,
        birth_place=birth_place,
        death_place=death_place,
        occupations=occupations,
        number_label=number_label,
        residence=residence,
        union=union,
        include_places=config.show_places and seed.visibility is VisibilityState.VISIBLE,
        include_occupation=(
            config.show_occupation and seed.visibility is VisibilityState.VISIBLE
        ),
        include_residence=(
            config.show_residence and seed.visibility is VisibilityState.VISIBLE
        ),
        include_union=config.show_union and seed.visibility is VisibilityState.VISIBLE,
    )
    return PersonView(
        seed=seed,
        full_label=labels.full_label,
        short_label=labels.short_label,
        name_case=labels.name_case,
        vital_dates=vitals,
        information=information,
        residence=residence,
        union=union,
    )
