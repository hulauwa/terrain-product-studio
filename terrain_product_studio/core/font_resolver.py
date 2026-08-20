"""Deterministic font selection shared by the dock and layout composer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class ResolvedFont:
    requested: str
    family: str
    substituted: bool


def resolve_font_family(
    requested: str,
    available_families: Iterable[str],
    fallbacks: Tuple[str, ...] = (
        "Noto Sans",
        "DejaVu Sans",
        "Arial",
        "Liberation Sans",
        "Sans Serif",
    ),
) -> ResolvedFont:
    """Resolve an installed family case-insensitively with visible fallback."""

    requested = (requested or "Sans Serif").strip() or "Sans Serif"
    available = {str(value).casefold(): str(value) for value in available_families}
    exact = available.get(requested.casefold())
    if exact:
        return ResolvedFont(requested, exact, False)
    for fallback in fallbacks:
        resolved = available.get(fallback.casefold())
        if resolved:
            return ResolvedFont(requested, resolved, True)
    # Qt always supplies a platform default even if its family was not listed.
    return ResolvedFont(requested, "Sans Serif", requested.casefold() != "sans serif")
