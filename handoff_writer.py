"""Write asset-aware handoff documents for web-ui-reference."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping


WEB_UI_REFERENCE_NOTE = (
    "这些资产和组件的长期维护、许可证、Storybook/Playwright 回归与 Godot 合同"
    "应由 web-ui-reference 维护；ScreenCoder 只输出识别和映射初稿。"
)


def _schema_to_dict(schema: Any) -> dict[str, Any]:
    if isinstance(schema, Mapping):
        return dict(schema)

    try:
        from component_schema import screen_schema_to_dict
    except ImportError:
        screen_schema_to_dict = None

    if screen_schema_to_dict is not None:
        return screen_schema_to_dict(schema)
    if is_dataclass(schema):
        return asdict(schema)
    return {
        "page_type": getattr(schema, "page_type", "unknown"),
        "viewport": getattr(schema, "viewport", {}),
        "theme_hint": getattr(schema, "theme_hint", ""),
        "template_hint": getattr(schema, "template_hint", ""),
        "regions": getattr(schema, "regions", []),
        "reference_handoff": getattr(schema, "reference_handoff", None),
    }


def _load_schema(path: str | Path) -> Any:
    try:
        from component_schema import load_screen_schema
    except ImportError:
        with Path(path).open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return load_screen_schema(path)


def _normalise_region(region: Any) -> dict[str, Any]:
    if is_dataclass(region):
        return asdict(region)
    if isinstance(region, Mapping):
        return dict(region)
    return {
        "id": getattr(region, "id", ""),
        "label": getattr(region, "label", ""),
        "bbox": getattr(region, "bbox", [0, 0, 0, 0]),
        "prefab": getattr(region, "prefab", ""),
        "content_priority": getattr(region, "content_priority", ""),
        "content": getattr(region, "content", {}),
        "asset_roles": getattr(region, "asset_roles", []),
    }


def _normalise_role(role: Any) -> dict[str, Any]:
    if is_dataclass(role):
        return asdict(role)
    if isinstance(role, Mapping):
        return dict(role)
    return {
        "role": getattr(role, "role", ""),
        "strategy": getattr(role, "strategy", ""),
        "crop_id": getattr(role, "crop_id", None),
        "source_bbox": getattr(role, "source_bbox", None),
        "notes": getattr(role, "notes", ""),
    }


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _regions(schema_dict: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [_normalise_region(region) for region in schema_dict.get("regions") or []]


def build_reference_handoff(schema: Any) -> dict[str, Any]:
    """Build a compact JSON handoff for web-ui-reference intake."""
    schema_dict = _schema_to_dict(schema)
    regions = _regions(schema_dict)
    region_entries: list[dict[str, Any]] = []
    prefabs: list[str] = []
    missing_assets: list[str] = []
    missing_components: list[str] = []

    for region in regions:
        prefab = region.get("prefab") or ""
        if prefab:
            prefabs.append(str(prefab))
        else:
            missing_components.append(str(region.get("id") or "unmapped-region"))

        role_entries: list[dict[str, Any]] = []
        for raw_role in region.get("asset_roles") or []:
            role = _normalise_role(raw_role)
            role_name = str(role.get("role") or "unknown-role")
            strategy = str(role.get("strategy") or "unknown-strategy")
            role_entries.append(
                {
                    "role": role_name,
                    "strategy": strategy,
                    "crop_id": role.get("crop_id"),
                    "source_bbox": role.get("source_bbox"),
                    "notes": role.get("notes") or "",
                    "maintainer": "web-ui-reference",
                }
            )
            if strategy in {"reference-asset", "manual-art"}:
                missing_assets.append(role_name)
            elif strategy == "crop-source" and not role.get("crop_id"):
                missing_assets.append(role_name)

        region_entries.append(
            {
                "id": region.get("id") or "",
                "label": region.get("label") or "",
                "bbox": region.get("bbox") or [],
                "prefab": prefab,
                "content_priority": region.get("content_priority") or "",
                "asset_roles": role_entries,
            }
        )

    composition = {
        "page_type": schema_dict.get("page_type") or "unknown-page",
        "theme_hint": schema_dict.get("theme_hint") or "",
        "template_hint": schema_dict.get("template_hint") or "",
        "viewport": schema_dict.get("viewport") or {},
        "target_owner": "web-ui-reference",
    }

    return {
        "composition": composition,
        "prefabs": _unique(prefabs),
        "missing_assets": _unique(missing_assets),
        "missing_components": _unique(missing_components),
        "regions": region_entries,
        "maintenance_boundary": WEB_UI_REFERENCE_NOTE,
    }


def _fmt(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_handoff_markdown(schema: Any, source_image: str | None = None) -> str:
    """Render a human-readable handoff document."""
    schema_dict = _schema_to_dict(schema)
    reference = build_reference_handoff(schema)
    regions = reference["regions"]
    lines: list[str] = [
        "# Asset-Aware UI Handoff",
        "",
        "## 页面概览",
        "",
        f"- 页面类型：{_fmt(schema_dict.get('page_type'))}",
        f"- 视口：{_fmt(schema_dict.get('viewport'))}",
        f"- 主题提示：{_fmt(schema_dict.get('theme_hint'))}",
        f"- 模板提示：{_fmt(schema_dict.get('template_hint'))}",
    ]
    if source_image:
        lines.append(f"- 输入截图：{source_image}")
    reference_notes = None
    reference_handoff = schema_dict.get("reference_handoff") or {}
    if isinstance(reference_handoff, Mapping):
        reference_notes = reference_handoff.get("notes")
    if reference_notes:
        lines.append(f"- 备注：{_fmt(reference_notes)}")
    lines.extend(["", f"> {WEB_UI_REFERENCE_NOTE}", ""])

    lines.extend(
        [
            "## 区域与 Prefab 映射",
            "",
            "| Region | Label | BBox | Prefab | Priority |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    if regions:
        for region in regions:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _fmt(region.get("id")),
                        _fmt(region.get("label")),
                        _fmt(region.get("bbox")),
                        _fmt(region.get("prefab")),
                        _fmt(region.get("content_priority")),
                    ]
                )
                + " |"
            )
    else:
        lines.append("| - | - | - | - | - |")

    lines.extend(
        [
            "",
            "## 资产角色策略",
            "",
            "| Region | Role | Strategy | Crop | Source BBox | Notes | Maintainer |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    has_roles = False
    for region in regions:
        for role in region.get("asset_roles") or []:
            has_roles = True
            lines.append(
                "| "
                + " | ".join(
                    [
                        _fmt(region.get("id")),
                        _fmt(role.get("role")),
                        _fmt(role.get("strategy")),
                        _fmt(role.get("crop_id")),
                        _fmt(role.get("source_bbox")),
                        _fmt(role.get("notes")),
                        "web-ui-reference",
                    ]
                )
                + " |"
            )
    if not has_roles:
        lines.append("| - | - | - | - | - | - | web-ui-reference |")

    lines.extend(["", "## 缺失资产", ""])
    missing_assets = reference.get("missing_assets") or []
    if missing_assets:
        for asset in missing_assets:
            lines.append(f"- {asset}：应由 web-ui-reference 补齐或维护。")
    else:
        lines.append("- 未检测到需要补齐的 reference-asset、manual-art 或缺 crop 的 crop-source 资产。")

    lines.extend(["", "## 缺失组件", ""])
    missing_components = reference.get("missing_components") or []
    if missing_components:
        for component in missing_components:
            lines.append(f"- {component}：该区域缺少 prefab 映射，应在 web-ui-reference 中确定组件归属。")
    else:
        lines.append("- 未检测到缺少 prefab 映射的区域。")

    lines.extend(["", "## Reference JSON 摘要", ""])
    lines.append("```json")
    lines.append(
        json.dumps(
            {
                "composition": reference["composition"],
                "prefabs": reference["prefabs"],
                "missing_assets": reference["missing_assets"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def write_handoff(schema: Any, output_path: str | Path, source_image: str | None = None) -> None:
    """Write handoff.md."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_handoff_markdown(schema, source_image=source_image), encoding="utf-8")


def write_reference_json(schema: Any, output_path: str | Path) -> None:
    """Write reference handoff JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_reference_handoff(schema), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Write handoff.md and reference handoff JSON.")
    parser.add_argument("--schema", required=True, help="Path to screen-schema.json.")
    parser.add_argument("--output", required=True, help="Path to write handoff.md.")
    parser.add_argument("--reference-json", required=True, help="Path to write reference handoff JSON.")
    parser.add_argument("--source-image", default=None, help="Optional source screenshot path to mention in handoff.md.")
    args = parser.parse_args()

    schema = _load_schema(args.schema)
    write_handoff(schema, args.output, source_image=args.source_image)
    write_reference_json(schema, args.reference_json)


if __name__ == "__main__":
    main()
