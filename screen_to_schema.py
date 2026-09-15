import argparse
from pathlib import Path
import json
import re
import sys

from PIL import Image

from asset_roles import default_roles_for_prefab, default_strategy_for_role
from component_schema import (
    AssetRoleBinding,
    ReferenceHandoff,
    RegionSchema,
    ScreenSchema,
    Viewport,
    save_screen_schema,
)


DEFAULT_REGION_LAYOUTS = {
    "title-stack": (0.10, 0.05, 0.90, 0.22),
    "primary-actions": (0.08, 0.26, 0.92, 0.52),
    "recent-run-panel": (0.10, 0.55, 0.90, 0.72),
    "quick-links": (0.06, 0.76, 0.94, 0.94),
}

LEGACY_REGION_TO_PREFAB = {
    "header": "ritual-title-stack",
    "title-stack": "ritual-title-stack",
    "sidebar": "ornate-action-plaque",
    "primary-actions": "ornate-action-plaque",
    "main content": "journey-status-panel",
    "main-content": "journey-status-panel",
    "recent-run-panel": "journey-status-panel",
    "navigation": "relic-quick-card",
    "quick-links": "relic-quick-card",
    "corner-system-actions": "relic-quick-card",
    "background-ornament": "ritual-background",
}

REGION_CONTENT_PRIORITIES = {
    "title-stack": "L0-branding",
    "primary-actions": "L0-primary-action",
    "recent-run-panel": "L1-status",
    "quick-links": "L2-shortcuts",
    "corner-system-actions": "L2-system",
    "background-ornament": "L3-decoration",
}

REGION_LABELS = {
    "title-stack": "Title area",
    "primary-actions": "Primary actions",
    "recent-run-panel": "Run status panel",
    "quick-links": "Quick links",
    "corner-system-actions": "System actions",
    "background-ornament": "Background ornament",
}


def _slugify(value: str) -> str:
    return value.strip().lower().replace("_", "-").replace(" ", "-")


def _bbox_from_fraction(fraction_bbox: tuple[float, float, float, float], width: int, height: int) -> list[int]:
    x1, y1, x2, y2 = fraction_bbox
    return [
        round(x1 * width),
        round(y1 * height),
        round(x2 * width),
        round(y2 * height),
    ]


def _bbox_to_pixels(
    bbox: list[int] | tuple[int, int, int, int],
    viewport: Viewport,
    bbox_format: str,
) -> list[int]:
    if len(bbox) != 4:
        raise ValueError(f"Expected bbox with 4 coordinates, got {bbox!r}")

    coords = [int(value) for value in bbox]
    if bbox_format == "pixel":
        return coords
    if bbox_format == "normalized":
        return [
            round(coords[0] * viewport.width / 1000),
            round(coords[1] * viewport.height / 1000),
            round(coords[2] * viewport.width / 1000),
            round(coords[3] * viewport.height / 1000),
        ]
    if bbox_format != "auto":
        raise ValueError(f"Unsupported bbox format: {bbox_format}")

    x1, y1, x2, y2 = coords
    if x2 > viewport.width or y2 > viewport.height:
        return _bbox_to_pixels(coords, viewport, "normalized")
    return coords


def _prefab_for_region(region_id: str) -> str:
    return LEGACY_REGION_TO_PREFAB.get(region_id, region_id)


def _asset_bindings_for_prefab(prefab: str) -> list[AssetRoleBinding]:
    return [
        AssetRoleBinding(role=role, strategy=default_strategy_for_role(role))
        for role in default_roles_for_prefab(prefab)
    ]


def _safe_filename(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-") or "asset"


def _make_region(region_id: str, bbox: list[int], prefab: str | None = None, source: str = "heuristic") -> RegionSchema:
    semantic_id = _slugify(region_id)
    component_prefab = prefab or _prefab_for_region(semantic_id)
    content = {
        "label": REGION_LABELS.get(semantic_id, region_id),
        "source": source,
    }
    return RegionSchema(
        id=semantic_id,
        label=REGION_LABELS.get(semantic_id, region_id),
        bbox=bbox,
        prefab=component_prefab,
        content_priority=REGION_CONTENT_PRIORITIES.get(semantic_id, "L2-supporting"),
        content=content,
        asset_roles=_asset_bindings_for_prefab(component_prefab),
    )


def _clamp_bbox(bbox: list[float], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = [round(float(value)) for value in bbox]
    if x2 <= 0 or y2 <= 0 or x1 >= width or y1 >= height:
        return 0, 0, max(1, min(width, 1)), max(1, min(height, 1))

    x1 = max(0, min(width, x1))
    x2 = max(0, min(width, x2))
    y1 = max(0, min(height, y1))
    y2 = max(0, min(height, y2))
    if x2 <= x1:
        x2 = min(width, x1 + 1)
    if y2 <= y1:
        y2 = min(height, y1 + 1)
    return x1, y1, x2, y2


def _bbox_intersection_area(a: list[float], b: list[float]) -> float:
    ax1, ay1, ax2, ay2 = [float(value) for value in a]
    bx1, by1, bx2, by2 = [float(value) for value in b]
    width = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    height = max(0.0, min(ay2, by2) - max(ay1, by1))
    return width * height


def apply_ocr_to_schema(schema: ScreenSchema, ocr_result) -> ScreenSchema:
    """Attach normalized OCR text blocks to intersecting schema regions."""

    for region in schema.regions:
        matched_blocks = []
        matched_text: list[str] = []
        for block in getattr(ocr_result, "blocks", []) or []:
            bbox = getattr(block, "bbox", None)
            text = str(getattr(block, "text", "")).strip()
            if not bbox or not text:
                continue
            if _bbox_intersection_area(region.bbox, bbox) <= 0:
                continue
            matched_text.append(text)
            matched_blocks.append(
                {
                    "text": text,
                    "bbox": [float(value) for value in bbox],
                    "confidence": getattr(block, "confidence", None),
                }
            )
        if matched_text:
            region.content["ocr_text"] = matched_text
            region.content["ocr_blocks"] = matched_blocks
            region.content["ocr_provider"] = getattr(ocr_result, "provider", "unknown")
    return schema


def extract_crop_source_assets(
    schema: ScreenSchema,
    image_path: Path,
    output_dir: Path,
    crop_id_prefix: str = "asset-crops",
) -> list[Path]:
    """Crop source-image regions for bindings that request the crop-source strategy."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with Image.open(image_path) as image:
        width, height = image.size
        for region in schema.regions:
            for index, binding in enumerate(region.asset_roles):
                if binding.strategy != "crop-source":
                    continue
                x1, y1, x2, y2 = _clamp_bbox(binding.source_bbox or region.bbox, width, height)
                filename = f"{_safe_filename(region.id)}-{_safe_filename(binding.role)}-{index}.png"
                crop_path = output_dir / filename
                image.crop((x1, y1, x2, y2)).save(crop_path)
                binding.crop_id = str(Path(crop_id_prefix) / filename)
                binding.source_bbox = [x1, y1, x2, y2]
                written.append(crop_path)
    return written


def _load_bbox_regions(bboxes_path: Path, viewport: Viewport, bbox_format: str) -> list[RegionSchema]:
    with bboxes_path.open("r", encoding="utf-8") as file:
        raw_bboxes = json.load(file)

    if not isinstance(raw_bboxes, dict):
        raise ValueError(f"Expected a bbox mapping in {bboxes_path}, got {type(raw_bboxes).__name__}")

    regions = []
    for name, bbox in raw_bboxes.items():
        semantic_id = _slugify(name)
        regions.append(_make_region(semantic_id, _bbox_to_pixels(bbox, viewport, bbox_format), source="layout-detection"))
    return regions


def _heuristic_regions(viewport: Viewport) -> list[RegionSchema]:
    return [
        _make_region(region_id, _bbox_from_fraction(fraction_bbox, viewport.width, viewport.height))
        for region_id, fraction_bbox in DEFAULT_REGION_LAYOUTS.items()
    ]


def _ensure_required_regions(regions: list[RegionSchema], viewport: Viewport) -> list[RegionSchema]:
    present = {region.id for region in regions}
    required = ["title-stack", "primary-actions", "recent-run-panel", "quick-links"]
    completed = list(regions)
    for region_id in required:
        if region_id not in present:
            completed.append(
                _make_region(
                    region_id,
                    _bbox_from_fraction(DEFAULT_REGION_LAYOUTS[region_id], viewport.width, viewport.height),
                )
            )
    return completed


def _reference_handoff_for(regions: list[RegionSchema]) -> ReferenceHandoff:
    prefabs = sorted({region.prefab for region in regions})
    missing_assets = sorted(
        {
            binding.role
            for region in regions
            for binding in region.asset_roles
            if binding.strategy in {"reference-asset", "manual-art"}
        }
    )
    return ReferenceHandoff(
        composition="horror-ornamental",
        prefabs=prefabs,
        missing_assets=missing_assets,
    )


def build_screen_schema(
    image_path: Path,
    bboxes_path: Path | None = None,
    bbox_format: str = "auto",
    page_type: str = "game-main-menu",
    theme_hint: str = "japanese-horror",
    template_hint: str = "ornamental-mobile",
) -> ScreenSchema:
    with Image.open(image_path) as image:
        width, height = image.size

    viewport = Viewport(width=width, height=height)
    if bboxes_path:
        regions = _load_bbox_regions(bboxes_path, viewport, bbox_format)
        regions = _ensure_required_regions(regions, viewport)
    else:
        regions = _heuristic_regions(viewport)

    return ScreenSchema(
        page_type=page_type,
        viewport=viewport,
        theme_hint=theme_hint,
        template_hint=template_hint,
        regions=regions,
        reference_handoff=_reference_handoff_for(regions),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an asset-aware ScreenCoder schema for a UI screenshot.")
    parser.add_argument("--image", required=True, type=Path, help="Source screenshot path.")
    parser.add_argument("--bboxes", type=Path, default=None, help="Optional region bbox JSON from block_parsor.py.")
    parser.add_argument(
        "--bbox-format",
        choices=["auto", "normalized", "pixel"],
        default="auto",
        help="Coordinate format for --bboxes. Auto treats boxes outside the viewport as normalized 0-1000 boxes.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Output screen-schema.json path.")
    parser.add_argument("--preview", type=Path, default=None, help="Optional standalone preview.html output path.")
    parser.add_argument("--handoff", type=Path, default=None, help="Optional handoff.md output path.")
    parser.add_argument("--reference-json", type=Path, default=None, help="Optional web-ui-reference handoff JSON path.")
    parser.add_argument("--asset-crops", type=Path, default=None, help="Directory for crop-source asset snippets.")
    parser.add_argument("--no-crops", action="store_true", help="Do not extract crop-source assets.")
    parser.add_argument(
        "--ocr-provider",
        default="none",
        choices=["none", "replicate_paddleocr", "hf_ocr", "ocr_space"],
        help="Optional hosted OCR provider. replicate_paddleocr uses an open-source PaddleOCR model on Replicate and requires REPLICATE_API_TOKEN.",
    )
    parser.add_argument("--ocr-output", type=Path, default=None, help="Optional normalized OCR JSON output path.")
    parser.add_argument("--page-type", default="game-main-menu", help="Schema page_type.")
    parser.add_argument("--theme-hint", default="japanese-horror", help="Schema theme_hint.")
    parser.add_argument("--template-hint", default="ornamental-mobile", help="Schema template_hint.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output or Path("data/run") / args.image.stem / "screen-schema.json"

    schema = build_screen_schema(
        image_path=args.image,
        bboxes_path=args.bboxes,
        bbox_format=args.bbox_format,
        page_type=args.page_type,
        theme_hint=args.theme_hint,
        template_hint=args.template_hint,
    )

    if args.ocr_provider != "none":
        from ocr_client import build_ocr_client

        ocr_client = build_ocr_client(args.ocr_provider)
        if ocr_client is not None and ocr_client.is_configured:
            ocr_result = ocr_client.recognize(args.image)
            apply_ocr_to_schema(schema, ocr_result)
            if args.ocr_output:
                args.ocr_output.parent.mkdir(parents=True, exist_ok=True)
                args.ocr_output.write_text(
                    json.dumps(
                        {
                            "provider": ocr_result.provider,
                            "text": ocr_result.text,
                            "blocks": [block.__dict__ for block in ocr_result.blocks],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
        elif ocr_client is not None:
            note = f"OCR manual gate: {ocr_client.manual_gate}"
            if schema.reference_handoff is not None:
                schema.reference_handoff.notes = note
            print(note, file=sys.stderr)

    if not args.no_crops:
        crop_dir = args.asset_crops or output_path.parent / "asset-crops"
        extract_crop_source_assets(schema, args.image, crop_dir)

    save_screen_schema(schema, output_path)

    if args.preview:
        from schema_to_html import write_preview_html

        write_preview_html(schema, args.preview)
    if args.handoff:
        from handoff_writer import write_handoff

        write_handoff(schema, args.handoff, source_image=args.image)
    if args.reference_json:
        from handoff_writer import write_reference_json

        write_reference_json(schema, args.reference_json)


if __name__ == "__main__":
    main()
