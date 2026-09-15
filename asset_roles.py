"""Asset role constants and prefab defaults for asset-aware HTML generation."""

from __future__ import annotations


ALLOWED_ASSET_ROLES = frozenset(
    {
        "ritual-background",
        "ornate-border",
        "paper-panel",
        "brass-plate",
        "red-seal",
        "corner-rivet",
        "symbolic-icon",
        "portrait-frame",
        "quick-card-illustration",
        "title-logotype",
        "ink-divider",
        "blood-smear",
        "rope-knot",
        "hanging-tag",
        "progress-petal",
        "damage-scratch",
    }
)


ALLOWED_ASSET_STRATEGIES = frozenset(
    {
        "css-procedural",
        "crop-source",
        "reference-asset",
        "manual-art",
    }
)


_DEFAULT_STRATEGY_BY_ROLE = {
    "ritual-background": "css-procedural",
    "ornate-border": "reference-asset",
    "paper-panel": "reference-asset",
    "brass-plate": "reference-asset",
    "red-seal": "css-procedural",
    "corner-rivet": "reference-asset",
    "symbolic-icon": "reference-asset",
    "portrait-frame": "reference-asset",
    "quick-card-illustration": "crop-source",
    "title-logotype": "manual-art",
    "ink-divider": "css-procedural",
    "blood-smear": "css-procedural",
    "rope-knot": "reference-asset",
    "hanging-tag": "reference-asset",
    "progress-petal": "css-procedural",
    "damage-scratch": "css-procedural",
}


PREFAB_ASSET_ROLE_HINTS = {
    "ritual-title-stack": [
        "title-logotype",
        "ink-divider",
        "red-seal",
        "blood-smear",
    ],
    "ornate-action-plaque": [
        "paper-panel",
        "brass-plate",
        "ornate-border",
        "red-seal",
        "corner-rivet",
    ],
    "journey-status-panel": [
        "paper-panel",
        "ornate-border",
        "hanging-tag",
        "progress-petal",
        "damage-scratch",
    ],
    "relic-quick-card": [
        "paper-panel",
        "portrait-frame",
        "quick-card-illustration",
        "symbolic-icon",
        "corner-rivet",
    ],
    "title-stack": [
        "title-logotype",
        "ink-divider",
        "red-seal",
    ],
    "primary-actions": [
        "paper-panel",
        "brass-plate",
        "ornate-border",
        "red-seal",
        "corner-rivet",
    ],
    "recent-run-panel": [
        "paper-panel",
        "ornate-border",
        "hanging-tag",
        "progress-petal",
        "damage-scratch",
    ],
    "quick-links": [
        "paper-panel",
        "symbolic-icon",
        "rope-knot",
        "hanging-tag",
    ],
    "corner-system-actions": [
        "brass-plate",
        "corner-rivet",
        "symbolic-icon",
    ],
    "background-ornament": [
        "ritual-background",
        "ornate-border",
        "blood-smear",
        "damage-scratch",
    ],
}


DEFAULT_PREFABS = frozenset(PREFAB_ASSET_ROLE_HINTS)


def normalize_asset_role(role: str) -> str:
    """Normalize and validate an asset role name."""

    if not isinstance(role, str):
        raise TypeError("asset role must be a string")

    normalized = role.strip().lower().replace("_", "-")
    if normalized not in ALLOWED_ASSET_ROLES:
        raise ValueError(f"unknown asset role: {role!r}")

    return normalized


def default_roles_for_prefab(prefab: str) -> list[str]:
    """Return default asset roles for a prefab, or an empty list when unknown."""

    if not isinstance(prefab, str):
        raise TypeError("prefab must be a string")

    return list(PREFAB_ASSET_ROLE_HINTS.get(prefab.strip(), ()))


def default_strategy_for_role(role: str) -> str:
    """Return the default generation strategy for an asset role."""

    normalized = normalize_asset_role(role)
    return _DEFAULT_STRATEGY_BY_ROLE[normalized]
