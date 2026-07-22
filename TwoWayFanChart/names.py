# SPDX-License-Identifier: GPL-3.0-or-later
"""Configurable person-name formatting after privacy sanitization."""

from __future__ import annotations

from dataclasses import dataclass

try:
    from .model import PersonViewSeed, VisibilityState
except ImportError:  # Gramps loads add-ons as top-level modules.
    from model import PersonViewSeed, VisibilityState  # type: ignore[no-redef]

from gramps.gen.const import GRAMPS_LOCALE as glocale
from gramps.gen.display.name import NameDisplay, displayer as global_name_displayer
from gramps.gen.lib import Name, Surname

_ = glocale.translation.gettext

_STRATEGIES = {
    "complete",
    "first",
    "call_then_first",
    "nickname",
    "call_and_complete",
    "nickname_and_call",
    "gramps",
}


@dataclass(frozen=True, slots=True)
class NameLabels:
    """Semantic labels before geometric fitting or truncation."""

    full_label: str
    short_label: str
    name_case: str = "stored"


class NameFormatter:
    """Format sanitized name parts using an isolated Gramps NameDisplay."""

    def __init__(
        self,
        *,
        locale=glocale,
        name_formats=None,
        default_format: int | None = None,
        name_case: str = "stored",
    ) -> None:
        if name_case not in {"stored", "small_caps", "upper"}:
            raise ValueError(f"unsupported name case: {name_case}")
        self.local_display = NameDisplay(locale)
        if name_formats is None:
            name_formats = global_name_displayer.get_name_format()
        if name_formats:
            self.local_display.set_name_format(name_formats)
        if default_format is not None:
            self.local_display.set_default_format(default_format)
        self.name_case = name_case

    @classmethod
    def from_config(cls, config, *, locale=glocale, name_formats=None):
        """Create an isolated formatter from the validated report configuration."""
        return cls(
            locale=locale,
            name_formats=name_formats,
            default_format=config.name_format,
            name_case=config.name_case,
        )

    @staticmethod
    def _first_token(value: str) -> str:
        tokens = value.split()
        return tokens[0] if tokens else ""

    @staticmethod
    def _name(
        seed: PersonViewSeed,
        given_name: str,
        surname_text: str,
        *,
        uppercase_surname: bool = False,
    ) -> Name:
        name = Name()
        name.set_first_name(given_name)
        name.set_call_name(seed.call_name)
        name.set_nick_name(seed.nick_name)
        name.set_family_nick_name(seed.family_nick_name)
        name.set_title(seed.title)
        name.set_suffix(seed.suffix)
        if seed.surname_parts:
            for part in seed.surname_parts:
                surname = Surname()
                transform = str.upper if uppercase_surname else str
                surname.set_surname(transform(part.surname))
                surname.set_prefix(transform(part.prefix))
                surname.set_connector(transform(part.connector))
                surname.set_primary(part.primary)
                surname.set_origintype(part.origin_type)
                name.add_surname(surname)
        elif surname_text:
            surname = Surname()
            surname.set_surname(surname_text)
            surname.set_primary(True)
            name.add_surname(surname)
        return name

    def _fallback_given(self, seed: PersonViewSeed) -> str:
        return (
            seed.call_name.strip()
            or self._first_token(seed.given_name)
            or seed.nick_name.strip()
        )

    def format(self, seed: PersonViewSeed, strategy: str) -> str:
        """Return one name label without mutating global Gramps preferences."""
        if not isinstance(seed, PersonViewSeed):
            raise ValueError("name seed must be a PersonViewSeed")
        if strategy not in _STRATEGIES:
            raise ValueError(f"unsupported name strategy: {strategy}")
        if seed.visibility is VisibilityState.MASKED:
            return seed.masked_label or _("Personne privée")
        if seed.visibility is VisibilityState.EXCLUDED:
            return ""

        surname = seed.surname.strip()
        if self.name_case == "upper":
            surname = surname.upper()

        if strategy == "complete":
            given = seed.given_name.strip()
        elif strategy == "first":
            given = self._first_token(seed.given_name)
        elif strategy in {"call_then_first", "call_and_complete"}:
            given = self._fallback_given(seed)
        elif strategy == "nickname":
            given = seed.nick_name.strip() or self._fallback_given(seed)
        elif strategy == "nickname_and_call":
            nickname = seed.nick_name.strip()
            call = seed.call_name.strip() or self._first_token(seed.given_name)
            if nickname and call and nickname != call:
                given = f"{nickname} “{call}”"
            else:
                given = nickname or call or self._fallback_given(seed)
        else:
            name = self._name(
                seed,
                seed.given_name.strip(),
                surname,
                uppercase_surname=self.name_case == "upper",
            )
            label = self.local_display.display_name(name).strip(" ,")
            return label or _("Sans nom")

        name = self._name(
            seed,
            given,
            surname,
            uppercase_surname=self.name_case == "upper",
        )
        label = self.local_display.display_name(name).strip(" ,")
        return label or _("Sans nom")


def derive_name_labels(
    seed: PersonViewSeed,
    formatter: NameFormatter,
    *,
    short_strategy: str = "call_then_first",
) -> NameLabels:
    """Build stable long and short labels without layout-dependent ellipsis."""
    if not isinstance(formatter, NameFormatter):
        raise ValueError("formatter must be a NameFormatter")
    full_strategy = (
        "nickname_and_call"
        if short_strategy == "nickname_and_call"
        else "complete"
    )
    return NameLabels(
        full_label=formatter.format(seed, full_strategy),
        short_label=formatter.format(seed, short_strategy),
        name_case=formatter.name_case,
    )
