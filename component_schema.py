"""Dataclass schema helpers for asset-aware screen descriptions."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from asset_roles import (
    ALLOWED_ASSET_STRATEGIES,
    default_strategy_for_role,
    normalize_asset_role,
)


BBox = list[float]


@dataclass
class Viewport:
    width: int
    height: int


@dataclass
class AssetRoleBinding:
    role: str
    strategy: str
    crop_id: str | None = None
    source_bbox: BBox | None = None
    notes: str | None = None


@dataclass
class RegionSchema:
    id: str
    prefab: str
    bbox: BBox
    label: str | None = None
    content_priority: str | None = None
    content: dict[str, Any] = field(default_factory=dict)
    asset_roles: list[AssetRoleBinding] = field(default_factory=list)


@dataclass
class ReferenceHandoff:
    composition: str | None = None
    prefabs: list[str] = field(default_factory=list)
    missing_assets: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class ScreenSchema:
    page_type: str
    viewport: Viewport
    theme_hint: str | None = None
    template_hint: str | None = None
    regions: list[RegionSchema] = field(default_factory=list)
    reference_handoff: ReferenceHandoff | None = None


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    return value


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _require_string(value, name)


def _parse_bbox(value: Any, name: str) -> BBox:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{name} must contain exactly four numbers")

    bbox: BBox = []
    for item in value:
        if not isinstance(item, (int, float)) or isinstance(item, bool):
            raise TypeError(f"{name} values must be numbers")
        bbox.append(float(item))
    return bbox


def _parse_viewport(value: Any) -> Viewport:
    data = _require_mapping(value, "viewport")
    width = data.get("width")
    height = data.get("height")
    if not isinstance(width, int) or isinstance(width, bool):
        raise TypeError("viewport.width must be an integer")
    if not isinstance(height, int) or isinstance(height, bool):
        raise TypeError("viewport.height must be an integer")
    if width <= 0 or height <= 0:
        raise ValueError("viewport width and height must be positive")
    return Viewport(width=width, height=height)


def _parse_asset_role_binding(value: Any) -> AssetRoleBinding:
    if isinstance(value, str):
        role = normalize_asset_role(value)
        return AssetRoleBinding(role=role, strategy=default_strategy_for_role(role))

    data = _require_mapping(value, "asset_roles[]")
    role = normalize_asset_role(data.get("role"))
    strategy = _require_string(data.get("strategy"), "asset_roles[].strategy")
    strategy = strategy.strip()
    if strategy not in ALLOWED_ASSET_STRATEGIES:
        raise ValueError(f"unknown asset strategy: {strategy!r}")

    source_bbox = None
    if data.get("source_bbox") is not None:
        source_bbox = _parse_bbox(data.get("source_bbox"), "asset_roles[].source_bbox")

    return AssetRoleBinding(
        role=role,
        strategy=strategy,
        crop_id=_optional_string(data.get("crop_id"), "asset_roles[].crop_id"),
        source_bbox=source_bbox,
        notes=_optional_string(data.get("notes"), "asset_roles[].notes"),
    )


def _parse_region(value: Any) -> RegionSchema:
    data = _require_mapping(value, "regions[]")
    prefab = data.get("prefab", data.get("component_prefab", ""))
    asset_roles = data.get("asset_roles", [])
    if not isinstance(asset_roles, list):
        raise TypeError("regions[].asset_roles must be a list")

    content = data.get("content", {})
    if content is None:
        content = {}
    if not isinstance(content, dict):
        raise TypeError("regions[].content must be a dict")

    return RegionSchema(
        id=_require_string(data.get("id"), "regions[].id"),
        prefab=_require_string(prefab, "regions[].prefab"),
        bbox=_parse_bbox(data.get("bbox"), "regions[].bbox"),
        label=_optional_string(data.get("label"), "regions[].label"),
        content_priority=_optional_string(data.get("content_priority"), "regions[].content_priority"),
        content=dict(content),
        asset_roles=[_parse_asset_role_binding(item) for item in asset_roles],
    )


def _parse_reference_handoff(value: Any) -> ReferenceHandoff:
    data = _require_mapping(value, "reference_handoff")

    prefabs = data.get("prefabs", [])
    if not isinstance(prefabs, list) or not all(isinstance(item, str) for item in prefabs):
        raise TypeError("reference_handoff.prefabs must be a list of strings")

    missing_assets = data.get("missing_assets", [])
    if not isinstance(missing_assets, list):
        raise TypeError("reference_handoff.missing_assets must be a list")

    return ReferenceHandoff(
        composition=_optional_string(data.get("composition"), "reference_handoff.composition"),
        prefabs=list(prefabs),
        missing_assets=[normalize_asset_role(item) for item in missing_assets],
        notes=_optional_string(data.get("notes"), "reference_handoff.notes"),
    )


def screen_schema_from_dict(data: dict) -> ScreenSchema:
    """Build a validated ScreenSchema from a plain dictionary."""

    source = _require_mapping(data, "screen schema")
    regions = source.get("regions", [])
    if not isinstance(regions, list):
        raise TypeError("regions must be a list")

    reference_handoff = None
    if source.get("reference_handoff") is not None:
        reference_handoff = _parse_reference_handoff(source.get("reference_handoff"))

    return ScreenSchema(
        page_type=_require_string(source.get("page_type"), "page_type"),
        viewport=_parse_viewport(source.get("viewport")),
        theme_hint=_optional_string(source.get("theme_hint"), "theme_hint"),
        template_hint=_optional_string(source.get("template_hint"), "template_hint"),
        regions=[_parse_region(item) for item in regions],
        reference_handoff=reference_handoff,
    )


def _asset_role_to_dict(binding: AssetRoleBinding) -> dict[str, Any]:
    result: dict[str, Any] = {
        "role": normalize_asset_role(binding.role),
        "strategy": binding.strategy,
    }
    if result["strategy"] not in ALLOWED_ASSET_STRATEGIES:
        raise ValueError(f"unknown asset strategy: {result['strategy']!r}")
    if binding.crop_id is not None:
        result["crop_id"] = binding.crop_id
    if binding.source_bbox is not None:
        result["source_bbox"] = _parse_bbox(binding.source_bbox, "asset_roles[].source_bbox")
    if binding.notes is not None:
        result["notes"] = binding.notes
    return result


def screen_schema_to_dict(schema: ScreenSchema) -> dict:
    """Convert a ScreenSchema into a JSON-serializable dictionary."""

    if not isinstance(schema, ScreenSchema):
        raise TypeError("schema must be a ScreenSchema")

    result: dict[str, Any] = {
        "page_type": schema.page_type,
        "viewport": {
            "width": schema.viewport.width,
            "height": schema.viewport.height,
        },
        "theme_hint": schema.theme_hint,
        "template_hint": schema.template_hint,
        "regions": [
            {
                "id": region.id,
                "label": region.label,
                "prefab": region.prefab,
                "bbox": _parse_bbox(region.bbox, "regions[].bbox"),
                "content_priority": region.content_priority,
                "content": dict(region.content),
                "asset_roles": [_asset_role_to_dict(binding) for binding in region.asset_roles],
            }
            for region in schema.regions
        ],
    }

    if schema.reference_handoff is not None:
        handoff = schema.reference_handoff
        result["reference_handoff"] = {
            "composition": handoff.composition,
            "prefabs": list(handoff.prefabs),
            "missing_assets": [normalize_asset_role(role) for role in handoff.missing_assets],
            "notes": handoff.notes,
        }

    return result


def load_screen_schema(path) -> ScreenSchema:
    """Load a screen schema JSON file."""

    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return screen_schema_from_dict(data)


def save_screen_schema(schema, path) -> None:
    """Save a screen schema JSON file with stable formatting."""

    data = screen_schema_to_dict(schema)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
