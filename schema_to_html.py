"""Render asset-aware screen schemas as standalone HTML previews."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, is_dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence


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


def _slug(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9_-]+", "-", text)
    return text.strip("-") or "unknown"


def _attr(value: Any) -> str:
    return escape(str(value), quote=True)


def _region_bbox(region: Mapping[str, Any]) -> tuple[float, float, float, float]:
    bbox = region.get("bbox") or [0, 0, 0, 0]
    if len(bbox) != 4:
        return 0.0, 0.0, 0.0, 0.0
    x1, y1, x2, y2 = (float(item or 0) for item in bbox)
    return x1, y1, max(0.0, x2 - x1), max(0.0, y2 - y1)


def _viewport(schema_dict: Mapping[str, Any]) -> tuple[int, int]:
    viewport = schema_dict.get("viewport") or {}
    if is_dataclass(viewport):
        viewport = asdict(viewport)
    width = int(viewport.get("width") or 820)
    height = int(viewport.get("height") or 1600)
    return max(1, width), max(1, height)


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


def _render_content(content: Any) -> str:
    if not content:
        return ""
    if not isinstance(content, Mapping):
        return f'<p class="content-value">{escape(str(content))}</p>'

    parts: list[str] = []
    for key, value in content.items():
        if value is None or value == "":
            continue
        class_name = f"content-{_slug(key)}"
        label = str(key).replace("_", " ")
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            items = "".join(f"<li>{escape(str(item))}</li>" for item in value)
            parts.append(
                f'<div class="content-item {class_name}">'
                f'<span class="content-key">{escape(label)}</span><ul>{items}</ul></div>'
            )
        elif isinstance(value, Mapping):
            nested = ", ".join(f"{k}: {v}" for k, v in value.items())
            parts.append(
                f'<div class="content-item {class_name}">'
                f'<span class="content-key">{escape(label)}</span>'
                f'<span class="content-value">{escape(nested)}</span></div>'
            )
        else:
            parts.append(
                f'<div class="content-item {class_name}">'
                f'<span class="content-key">{escape(label)}</span>'
                f'<span class="content-value">{escape(str(value))}</span></div>'
            )
    return "\n".join(parts)


def _render_role_layers(roles: list[dict[str, Any]]) -> str:
    layers: list[str] = []
    for role in roles:
        role_name = role.get("role") or "unknown-role"
        strategy = role.get("strategy") or "unknown-strategy"
        style = ""
        if strategy == "crop-source" and role.get("crop_id"):
            style = f' style="background-image:url({_attr(role.get("crop_id"))})"'
        layers.append(
            f'<span class="asset-layer asset-{_slug(role_name)} strategy-{_slug(strategy)}" '
            f'data-role="{_attr(role_name)}" data-strategy="{_attr(strategy)}"'
            f'{_optional_attr("data-crop-id", role.get("crop_id"))}{style}></span>'
        )
    return "\n".join(layers)


def _optional_attr(name: str, value: Any) -> str:
    if value is None or value == "":
        return ""
    return f' {name}="{_attr(value)}"'


def _render_region(region: Mapping[str, Any], index: int) -> str:
    x, y, width, height = _region_bbox(region)
    region_id = region.get("id") or f"region-{index + 1}"
    label = region.get("label") or region_id
    prefab = region.get("prefab") or "unmapped-prefab"
    priority = region.get("content_priority") or "unprioritized"
    roles = [_normalise_role(role) for role in region.get("asset_roles") or []]
    role_names = [role.get("role") or "unknown-role" for role in roles]
    strategy_names = [role.get("strategy") or "unknown-strategy" for role in roles]
    classes = [
        "region",
        f"region-{_slug(region_id)}",
        f"prefab-{_slug(prefab)}",
        f"priority-{_slug(priority)}",
        *(f"has-{_slug(role)}" for role in role_names),
    ]
    style = f"left:{x:.2f}px;top:{y:.2f}px;width:{width:.2f}px;height:{height:.2f}px;"
    role_chips = "".join(
        f'<span class="role-chip strategy-{_slug(strategy_names[i])}">'
        f"{escape(role_names[i])}</span>"
        for i in range(len(role_names))
    )

    return f"""
      <section class="{' '.join(classes)}"
        style="{style}"
        data-region-id="{_attr(region_id)}"
        data-prefab="{_attr(prefab)}"
        data-label="{_attr(label)}"
        data-content-priority="{_attr(priority)}"
        data-asset-roles="{_attr(','.join(role_names))}"
        data-asset-strategies="{_attr(','.join(strategy_names))}">
        {_render_role_layers(roles)}
        <div class="region-body">
          <div class="region-meta">
            <span class="prefab-label">{escape(str(prefab))}</span>
            <span class="region-label">{escape(str(label))}</span>
          </div>
          <div class="region-content">
            {_render_content(region.get("content") or {})}
          </div>
          <div class="asset-roles">{role_chips}</div>
        </div>
      </section>"""


def _base_css(width: int, height: int) -> str:
    return f"""
    :root {{
      --paper: #d7b980;
      --paper-light: #f0d59b;
      --ink: #2c1a14;
      --brass: #a97825;
      --brass-light: #e2b557;
      --seal: #9f1f18;
      --shadow: rgba(28, 14, 8, 0.36);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: start center;
      padding: 24px;
      color: var(--ink);
      background:
        radial-gradient(circle at 20% 10%, rgba(178, 40, 32, 0.20), transparent 22rem),
        radial-gradient(circle at 80% 80%, rgba(166, 120, 38, 0.24), transparent 26rem),
        linear-gradient(135deg, #18110f, #352017 58%, #140d0b);
      font-family: Georgia, "Times New Roman", serif;
    }}
    .screen-preview {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
      background:
        radial-gradient(circle at 50% -10%, rgba(226, 181, 87, 0.22), transparent 30%),
        linear-gradient(180deg, #332018 0%, #201411 100%);
      border: 1px solid rgba(226, 181, 87, 0.34);
      box-shadow: 0 24px 80px rgba(0, 0, 0, 0.45);
      transform-origin: top center;
    }}
    .screen-preview::after {{
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
      background-size: 18px 18px;
      mix-blend-mode: overlay;
    }}
    .region {{
      position: absolute;
      display: flex;
      padding: 12px;
      border: 1px solid rgba(239, 205, 135, 0.36);
      background: rgba(86, 53, 32, 0.58);
      box-shadow: 0 10px 28px var(--shadow), inset 0 0 0 1px rgba(255,255,255,0.08);
      overflow: hidden;
    }}
    .region-body {{
      position: relative;
      z-index: 2;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: 8px;
      justify-content: center;
    }}
    .region-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
      opacity: 0.88;
    }}
    .prefab-label, .region-label, .role-chip {{
      padding: 3px 7px;
      border-radius: 999px;
      background: rgba(35, 20, 15, 0.62);
      color: #f2dca9;
    }}
    .region-label {{ background: rgba(159, 31, 24, 0.42); }}
    .region-content {{
      display: grid;
      gap: 5px;
      font-size: clamp(12px, 2.2vw, 20px);
      line-height: 1.18;
      text-shadow: 0 1px 0 rgba(255,255,255,0.14);
    }}
    .content-key {{
      display: block;
      font-size: 0.58em;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      opacity: 0.62;
    }}
    .content-value {{ font-weight: 700; }}
    .content-primary-title .content-value,
    .content-title .content-value {{
      font-size: 1.5em;
      color: #2d160f;
    }}
    .asset-roles {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      margin-top: auto;
      font-size: 10px;
    }}
    .strategy-reference-asset {{ border: 1px solid rgba(226, 181, 87, 0.55); }}
    .strategy-crop-source {{ border: 1px solid rgba(132, 174, 116, 0.65); }}
    .strategy-manual-art {{ border: 1px dashed rgba(203, 72, 56, 0.75); }}
    .has-paper-panel, .prefab-paper-panel {{
      background:
        linear-gradient(90deg, rgba(96, 53, 28, 0.15), transparent 10%, transparent 90%, rgba(96, 53, 28, 0.16)),
        radial-gradient(circle at 24% 20%, rgba(255,255,255,0.20), transparent 22%),
        linear-gradient(135deg, var(--paper-light), var(--paper));
      border-color: rgba(91, 47, 25, 0.48);
    }}
    .has-brass-plate, .prefab-brass-plate {{
      background:
        linear-gradient(160deg, rgba(255,255,255,0.30), transparent 20%),
        linear-gradient(180deg, var(--brass-light), var(--brass) 52%, #6a4318);
      border: 2px solid rgba(66, 39, 14, 0.68);
      color: #24130b;
    }}
    .has-ornate-border, .prefab-ornate-action-plaque {{
      border: 4px double rgba(226, 181, 87, 0.82);
      border-radius: 18px;
    }}
    .has-ornate-border::before, .prefab-ornate-action-plaque::before {{
      content: "";
      position: absolute;
      inset: 7px;
      border: 1px solid rgba(255, 231, 172, 0.38);
      border-radius: 12px;
      pointer-events: none;
    }}
    .has-red-seal::after, .prefab-red-seal::after {{
      content: "";
      position: absolute;
      right: 12px;
      bottom: 12px;
      width: min(54px, 22%);
      aspect-ratio: 1;
      border-radius: 50%;
      background:
        radial-gradient(circle, transparent 42%, rgba(255,255,255,0.16) 43% 49%, transparent 50%),
        radial-gradient(circle at 45% 42%, #b72b22, var(--seal));
      box-shadow: 0 2px 8px rgba(77, 10, 8, 0.38);
      opacity: 0.82;
    }}
    .has-corner-rivet::before {{
      box-shadow:
        10px 10px 0 0 rgba(99, 57, 18, 0.75),
        calc(100% - 10px) 10px 0 0 rgba(99, 57, 18, 0.75),
        10px calc(100% - 10px) 0 0 rgba(99, 57, 18, 0.75),
        calc(100% - 10px) calc(100% - 10px) 0 0 rgba(99, 57, 18, 0.75);
    }}
    .has-portrait-frame, .prefab-portrait-frame {{
      border-radius: 22px;
      background: radial-gradient(ellipse at 50% 35%, rgba(240, 213, 155, 0.35), rgba(39, 22, 17, 0.7));
    }}
    .has-ink-divider .region-content {{
      border-top: 1px solid rgba(44, 26, 20, 0.42);
      border-bottom: 1px solid rgba(44, 26, 20, 0.24);
      padding-block: 8px;
    }}
    .asset-layer {{
      position: absolute;
      inset: 0;
      pointer-events: none;
      z-index: 1;
    }}
    .strategy-crop-source {{
      background-size: cover;
      background-position: center;
      opacity: 0.34;
      mix-blend-mode: multiply;
    }}
    .asset-crop-source {{
      background: repeating-linear-gradient(135deg, rgba(118, 157, 103, 0.15) 0 8px, transparent 8px 16px);
    }}
    .asset-manual-art {{
      background: repeating-linear-gradient(45deg, rgba(159, 31, 24, 0.12) 0 7px, transparent 7px 15px);
    }}
    @media (max-width: {width + 48}px) {{
      body {{ padding: 0; place-items: start; }}
      .screen-preview {{
        transform: scale(calc(100vw / {width}));
      }}
    }}
    """


def render_preview_html(schema: Any) -> str:
    """Return a standalone preview HTML document for a ScreenSchema-like object."""
    schema_dict = _schema_to_dict(schema)
    width, height = _viewport(schema_dict)
    regions = [_normalise_region(region) for region in schema_dict.get("regions") or []]
    page_type = schema_dict.get("page_type") or "unknown-page"
    theme_hint = schema_dict.get("theme_hint") or ""
    template_hint = schema_dict.get("template_hint") or ""
    rendered_regions = "\n".join(_render_region(region, i) for i, region in enumerate(regions))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(str(page_type))} preview</title>
  <style>{_base_css(width, height)}</style>
</head>
<body>
  <main class="screen-preview theme-{_slug(theme_hint)} template-{_slug(template_hint)}"
    data-page-type="{_attr(page_type)}"
    data-theme-hint="{_attr(theme_hint)}"
    data-template-hint="{_attr(template_hint)}"
    data-viewport-width="{width}"
    data-viewport-height="{height}">
    {rendered_regions}
  </main>
</body>
</html>
"""


def write_preview_html(schema: Any, output_path: str | Path) -> None:
    """Write a standalone preview HTML document."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_preview_html(schema), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render screen-schema.json to standalone preview.html.")
    parser.add_argument("--schema", required=True, help="Path to screen-schema.json.")
    parser.add_argument("--output", required=True, help="Path to write preview.html.")
    args = parser.parse_args()

    schema = _load_schema(args.schema)
    write_preview_html(schema, args.output)


if __name__ == "__main__":
    main()
