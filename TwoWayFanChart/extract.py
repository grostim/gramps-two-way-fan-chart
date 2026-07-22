# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only extraction of a normalized genealogy graph from Gramps."""

from __future__ import annotations

from typing import Any

try:
    from .model import (
        AncestorSlot,
        ChartGraph,
        DescendantBranch,
        Diagnostic,
        PersonNode,
        UnionBranch,
    )
except ImportError:  # Gramps top-level add-on loading.
    from model import (  # type: ignore[no-redef]
        AncestorSlot,
        ChartGraph,
        DescendantBranch,
        Diagnostic,
        PersonNode,
        UnionBranch,
    )


class ExtractionError(ValueError):
    """The configured genealogy graph cannot be extracted safely."""


def _person_node(person: Any) -> PersonNode:
    return PersonNode(person.get_handle(), person.get_gramps_id())


def extract_center_family(
    database: Any, family_gramps_id: str
) -> tuple[str, tuple[PersonNode | None, PersonNode | None]]:
    """Resolve the family while preserving both recorded partner roles."""
    family = database.get_family_from_gramps_id(family_gramps_id)
    if family is None:
        raise ExtractionError(f"Center family does not exist: {family_gramps_id}")

    people: list[PersonNode | None] = []
    for handle in (family.get_father_handle(), family.get_mother_handle()):
        person = database.get_person_from_handle(handle)
        people.append(_person_node(person) if person is not None else None)
    if not any(people):
        raise ExtractionError(f"Center family has no recorded partner: {family_gramps_id}")
    return family.get_handle(), (people[0], people[1])


def _child_relations(family: Any, child_handle: str) -> tuple[str, str]:
    for child_ref in family.get_child_ref_list():
        if child_ref.get_reference_handle() == child_handle:
            father = child_ref.get_father_relation()
            mother = child_ref.get_mother_relation()
            return (
                str(father).lower() if father else "unknown",
                str(mother).lower() if mother else "unknown",
            )
    return "unknown", "unknown"


def _child_relation(family: Any, child_handle: str) -> str:
    return _child_relations(family, child_handle)[0]


def _select_parent_family(
    database: Any, person: Any, policy: str
) -> tuple[Any | None, tuple[str, str]]:
    handles = list(person.get_parent_family_handle_list())
    if not handles:
        return None, ("unknown", "unknown")
    if policy not in {"primary", "biological", "first"}:
        raise ValueError(f"Unknown parent family policy: {policy}")

    if policy == "primary":
        selected = person.get_main_parents_family_handle() or handles[0]
        family = database.get_family_from_handle(selected)
        return (
            family,
            _child_relations(family, person.get_handle())
            if family
            else ("unknown", "unknown"),
        )

    if policy == "biological":
        for handle in handles:
            family = database.get_family_from_handle(handle)
            relations = (
                _child_relations(family, person.get_handle())
                if family
                else ("unknown", "unknown")
            )
            if family and "birth" in relations:
                return family, relations

    family = database.get_family_from_handle(handles[0])
    return (
        family,
        _child_relations(family, person.get_handle())
        if family
        else ("unknown", "unknown"),
    )


def extract_ancestor_slots(
    database: Any,
    center_people: tuple[PersonNode | None, PersonNode | None],
    generations: int,
    *,
    parent_family_policy: str = "primary",
) -> tuple[tuple[AncestorSlot, ...], tuple[Diagnostic, ...]]:
    """Build complete deterministic slots while retaining unknown positions."""
    if not 0 <= generations <= 8:
        raise ValueError("ancestor generations must be between 0 and 8")
    if parent_family_policy not in {"primary", "biological", "first"}:
        raise ValueError(f"Unknown parent family policy: {parent_family_policy}")

    slots: list[AncestorSlot] = []
    diagnostics: list[Diagnostic] = []
    seen: set[str] = set()
    for lineage_index, root in enumerate(center_people):
        lineage = ("a", "b")[lineage_index]
        current: list[tuple[str | None, tuple[str, ...], str]] = [
            (root.handle if root else None, (root.handle,) if root else (), "birth")
        ]
        for generation in range(1, generations + 1):
            next_generation: list[tuple[str | None, tuple[str, ...], str]] = []
            for child_handle, path, inherited_relation in current:
                parent_handles: tuple[str | None, str | None] = (None, None)
                parent_relations = (inherited_relation, inherited_relation)
                child = None
                if child_handle:
                    try:
                        child = database.get_person_from_handle(child_handle)
                    except Exception:
                        child = None
                if child is not None:
                    family, parent_relations = _select_parent_family(
                        database, child, parent_family_policy
                    )
                    if family is not None:
                        parent_handles = (
                            family.get_father_handle(),
                            family.get_mother_handle(),
                        )

                for parent_handle, relation in zip(parent_handles, parent_relations):
                    index = len(next_generation)
                    position_id = f"ancestor-{lineage}-{generation}-{index}"
                    person = (
                        database.get_person_from_handle(parent_handle)
                        if parent_handle
                        else None
                    )
                    cycle = bool(parent_handle and parent_handle in path)
                    repeated = bool(parent_handle and parent_handle in seen)
                    if parent_handle:
                        seen.add(parent_handle)
                    if cycle:
                        diagnostics.append(
                            Diagnostic(
                                "ANCESTOR_CYCLE",
                                "Ancestor branch stopped because a recorded relationship loops.",
                                position_id,
                            )
                        )
                    elif repeated:
                        diagnostics.append(
                            Diagnostic(
                                "REPEATED_PERSON",
                                "The same recorded person occupies another ancestor slot.",
                                position_id,
                            )
                        )
                    slots.append(
                        AncestorSlot(
                            position_id,
                            generation,
                            index,
                            lineage,
                            _person_node(person) if person else None,
                            relation,
                            repeated,
                            cycle,
                        )
                    )
                    next_generation.append(
                        (
                            None if cycle else parent_handle,
                            path + (parent_handle,) if parent_handle and not cycle else path,
                            relation,
                        )
                    )
            current = next_generation
    return tuple(slots), tuple(diagnostics)


def _select_descendant_families(database: Any, person: Any, policy: str) -> list[Any]:
    handles = list(person.get_family_handle_list())
    if policy not in {"all", "primary", "first"}:
        raise ValueError(f"Unknown descendant family policy: {policy}")
    if not handles:
        return []
    if policy == "all":
        selected = handles
    elif policy == "primary":
        getter = getattr(person, "get_main_family_handle", None)
        selected = [(getter() if getter else None) or handles[0]]
    else:
        selected = [handles[0]]
    return [
        family
        for handle in selected
        if (family := database.get_family_from_handle(handle)) is not None
    ]


def _spouse_handle(family: Any, person_handle: str) -> str | None:
    father = family.get_father_handle()
    mother = family.get_mother_handle()
    if father == person_handle:
        return mother
    if mother == person_handle:
        return father
    return None


def _relation_for_parent(family: Any, child_ref: Any, parent_handle: str) -> str:
    """Return the relation recorded for the role occupied by one parent."""
    if family.get_father_handle() == parent_handle:
        relation = child_ref.get_father_relation()
    elif family.get_mother_handle() == parent_handle:
        relation = child_ref.get_mother_relation()
    else:
        return "unknown"
    return str(relation).lower() if relation else "unknown"


def extract_descendant_branches(
    database: Any,
    center_family_handle: str,
    generations: int,
    *,
    descendant_family_policy: str = "all",
    allowed_relations: frozenset[str] | None = None,
) -> tuple[tuple[DescendantBranch, ...], tuple[Diagnostic, ...]]:
    """Extract recorded descendant unions without charging spouses a generation."""
    if not 0 <= generations <= 5:
        raise ValueError("descendant generations must be between 0 and 5")
    if descendant_family_policy not in {"all", "primary", "first"}:
        raise ValueError(
            f"Unknown descendant family policy: {descendant_family_policy}"
        )
    if generations == 0:
        return (), ()
    allowed = (
        frozenset(relation.lower() for relation in allowed_relations)
        if allowed_relations is not None
        else None
    )
    center_family = database.get_family_from_handle(center_family_handle)
    if center_family is None:
        raise ExtractionError(f"Center family handle does not exist: {center_family_handle}")

    diagnostics: list[Diagnostic] = []

    def build_branch(
        person_handle: str,
        generation: int,
        relation: str,
        position_id: str,
        path: tuple[str, ...],
    ) -> DescendantBranch | None:
        person = database.get_person_from_handle(person_handle)
        if person is None:
            diagnostics.append(
                Diagnostic(
                    "MISSING_DESCENDANT",
                    "A recorded descendant handle cannot be resolved.",
                    position_id,
                )
            )
            return None

        if person_handle in path:
            diagnostics.append(
                Diagnostic(
                    "DESCENDANT_CYCLE",
                    "Descendant branch stopped because a recorded relationship loops.",
                    position_id,
                )
            )
            return DescendantBranch(
                position_id,
                _person_node(person),
                generation,
                (),
                (),
                relation,
                True,
            )

        unions: list[UnionBranch] = []
        children: list[DescendantBranch] = []
        for union_index, family in enumerate(
            _select_descendant_families(
                database, person, descendant_family_policy
            )
        ):
            child_refs_with_relations = [
                (ref, _relation_for_parent(family, ref, person_handle))
                for ref in family.get_child_ref_list()
            ]
            child_refs_with_relations = [
                (ref, child_relation)
                for ref, child_relation in child_refs_with_relations
                if allowed is None or child_relation in allowed
            ]
            union = UnionBranch(
                family.get_handle(),
                _spouse_handle(family, person_handle),
                tuple(ref.get_reference_handle() for ref, _ in child_refs_with_relations),
                tuple(relation for _, relation in child_refs_with_relations),
            )
            unions.append(union)
            if generation < generations:
                for child_index, (child_ref, child_relation) in enumerate(
                    child_refs_with_relations
                ):
                    child = build_branch(
                        child_ref.get_reference_handle(),
                        generation + 1,
                        child_relation,
                        f"{position_id}-{union_index}-{child_index}",
                        path + (person_handle,),
                    )
                    if child is not None:
                        children.append(child)
        return DescendantBranch(
            position_id,
            _person_node(person),
            generation,
            tuple(unions),
            tuple(children),
            relation,
        )

    branches: list[DescendantBranch] = []
    center_path = tuple(
        handle
        for handle in (
            center_family.get_father_handle(),
            center_family.get_mother_handle(),
        )
        if handle
    )
    center_parent_handle = (
        center_family.get_father_handle() or center_family.get_mother_handle()
    )
    for index, child_ref in enumerate(center_family.get_child_ref_list()):
        relation = _relation_for_parent(
            center_family, child_ref, center_parent_handle
        )
        if allowed is not None and relation not in allowed:
            continue
        branch = build_branch(
            child_ref.get_reference_handle(),
            1,
            relation,
            f"desc-{index}",
            center_path,
        )
        if branch is not None:
            branches.append(branch)
    return tuple(branches), tuple(diagnostics)


def extract_chart_graph(database: Any, config: Any) -> ChartGraph:
    """Build the complete normalized graph exclusively through database reads."""
    center_handle, center_people = extract_center_family(
        database, config.center_family
    )
    ancestor_slots, ancestor_diagnostics = extract_ancestor_slots(
        database,
        center_people,
        config.ancestor_generations,
        parent_family_policy=config.parent_family_policy,
    )
    descendants, descendant_diagnostics = extract_descendant_branches(
        database,
        center_handle,
        config.descendant_generations,
        descendant_family_policy=config.descendant_family_policy,
    )
    return ChartGraph(
        center_handle,
        center_people,
        ancestor_slots,
        descendants,
        ancestor_diagnostics + descendant_diagnostics,
    )
