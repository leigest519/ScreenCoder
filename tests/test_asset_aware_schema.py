import json
from pathlib import Path

from PIL import Image

from asset_roles import default_roles_for_prefab, default_strategy_for_role, normalize_asset_role
from component_schema import load_screen_schema, screen_schema_from_dict, screen_schema_to_dict
from handoff_writer import build_reference_handoff, render_handoff_markdown
from schema_to_html import render_preview_html
from screen_to_schema import build_screen_schema, extract_crop_source_assets


def test_asset_role_defaults_cover_core_prefabs():
    assert normalize_asset_role("paper_panel") == "paper-panel"
    assert "paper-panel" in default_roles_for_prefab("ornate-action-plaque")
    assert default_strategy_for_role("quick-card-illustration") == "crop-source"


def test_screen_schema_round_trips_asset_roles(tmp_path):
    schema_path = tmp_path / "screen-schema.json"
    data = {
        "page_type": "game-main-menu",
        "viewport": {"width": 820, "height": 1600},
        "theme_hint": "japanese-horror",
        "template_hint": "ornamental-mobile",
        "regions": [
            {
                "id": "primary-actions",
                "label": "Primary actions",
                "prefab": "ornate-action-plaque",
                "bbox": [64, 410, 756, 840],
                "content_priority": "L0-primary-action",
                "content": {"primary_title": "继续旅程"},
                "asset_roles": [
                    {"role": "paper-panel", "strategy": "reference-asset"},
                    {"role": "red-seal", "strategy": "css-procedural"},
                ],
            }
        ],
    }

    schema = screen_schema_from_dict(data)
    schema_path.write_text(json.dumps(screen_schema_to_dict(schema), ensure_ascii=False), encoding="utf-8")
    loaded = load_screen_schema(schema_path)

    assert loaded.regions[0].label == "Primary actions"
    assert loaded.regions[0].content_priority == "L0-primary-action"
    assert screen_schema_to_dict(loaded)["regions"][0]["asset_roles"][0]["role"] == "paper-panel"


def test_build_screen_schema_from_legacy_bboxes_adds_required_regions(tmp_path):
    image_path = tmp_path / "menu.png"
    bbox_path = tmp_path / "bboxes.json"
    Image.new("RGB", (820, 1600), color=(20, 12, 10)).save(image_path)
    bbox_path.write_text(json.dumps({"header": [100, 50, 900, 200]}), encoding="utf-8")

    schema = build_screen_schema(image_path, bbox_path, bbox_format="normalized")
    region_ids = {region.id for region in schema.regions}

    assert schema.viewport.width == 820
    assert schema.regions[0].prefab == "ritual-title-stack"
    assert schema.regions[0].content["source"] == "layout-detection"
    assert {"title-stack", "primary-actions", "recent-run-panel", "quick-links"}.issubset(region_ids)


def test_build_screen_schema_marks_default_regions_as_heuristic(tmp_path):
    image_path = tmp_path / "menu.png"
    Image.new("RGB", (360, 640), color=(20, 12, 10)).save(image_path)

    schema = build_screen_schema(image_path)

    assert {region.content["source"] for region in schema.regions} == {"heuristic"}


def test_preview_and_handoff_render_semantic_assets(tmp_path):
    image_path = tmp_path / "menu.png"
    Image.new("RGB", (360, 640), color=(20, 12, 10)).save(image_path)
    schema = build_screen_schema(image_path)
    crop_paths = extract_crop_source_assets(schema, image_path, tmp_path / "asset-crops")

    html = render_preview_html(schema)
    handoff = render_handoff_markdown(schema, source_image="data/input/menu.png")
    reference = build_reference_handoff(schema)

    assert crop_paths
    assert crop_paths[0].exists()
    assert 'data-prefab="ornate-action-plaque"' in html
    assert "asset-crops/quick-links-quick-card-illustration" in html
    assert "paper-panel" in html
    assert "web-ui-reference" in handoff
    assert "ornate-action-plaque" in reference["prefabs"]
    assert "paper-panel" in reference["missing_assets"]


def test_preview_and_handoff_accept_plain_dict_schema():
    data = {
        "page_type": "game-main-menu",
        "viewport": {"width": 320, "height": 640},
        "regions": [
            {
                "id": "primary-actions",
                "prefab": "ornate-action-plaque",
                "bbox": [10, 20, 300, 180],
                "asset_roles": [{"role": "paper-panel", "strategy": "reference-asset"}],
            }
        ],
    }

    assert 'data-page-type="game-main-menu"' in render_preview_html(data)
    assert build_reference_handoff(data)["prefabs"] == ["ornate-action-plaque"]


def test_crop_source_assets_handle_fully_out_of_bounds_bbox(tmp_path):
    image_path = tmp_path / "menu.png"
    Image.new("RGB", (64, 64), color=(20, 12, 10)).save(image_path)
    schema = build_screen_schema(image_path)
    crop_binding = schema.regions[-1].asset_roles[2]
    crop_binding.source_bbox = [1000, 1000, 1200, 1200]

    crop_paths = extract_crop_source_assets(schema, image_path, tmp_path / "asset-crops")

    assert crop_paths[0].exists()
    assert crop_binding.source_bbox == [0, 0, 1, 1]


def test_screen_to_schema_cli_writes_complete_preview_package(tmp_path):
    import subprocess
    import sys

    image_path = tmp_path / "menu.png"
    output_dir = tmp_path / "run" / "menu"
    Image.new("RGB", (360, 640), color=(20, 12, 10)).save(image_path)

    result = subprocess.run(
        [
            sys.executable,
            "screen_to_schema.py",
            "--image",
            str(image_path),
            "--output",
            str(output_dir / "screen-schema.json"),
            "--preview",
            str(output_dir / "index.html"),
            "--handoff",
            str(output_dir / "handoff.md"),
            "--reference-json",
            str(output_dir / "reference-handoff.json"),
        ],
        check=True,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )

    assert result.stderr == ""
    assert (output_dir / "screen-schema.json").exists()
    assert (output_dir / "index.html").exists()
    assert (output_dir / "handoff.md").exists()
    assert (output_dir / "reference-handoff.json").exists()
    assert list((output_dir / "asset-crops").glob("*.png"))
    assert 'data-page-type="game-main-menu"' in (output_dir / "index.html").read_text(encoding="utf-8")
    assert "web-ui-reference" in (output_dir / "handoff.md").read_text(encoding="utf-8")
