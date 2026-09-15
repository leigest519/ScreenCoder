from pathlib import Path

from PIL import Image

from handoff_writer import render_handoff_markdown
from ocr_client import (
    OCRBlock,
    OCRResult,
    build_ocr_client,
    normalize_ocr_space_response,
    normalize_replicate_paddleocr_response,
)
from screen_to_schema import apply_ocr_to_schema, build_screen_schema


def test_normalize_replicate_paddleocr_response_returns_text_and_boxes():
    payload = {
        "status": "successful",
        "output": {
            "results": [
                {
                    "text": "继续旅程",
                    "score": 0.98,
                    "box": [[80, 180], [220, 180], [220, 215], [80, 215]],
                },
                {
                    "text": "新的旅程",
                    "confidence": 0.87,
                    "bbox": [90, 260, 210, 295],
                },
            ]
        },
    }

    result = normalize_replicate_paddleocr_response(payload)

    assert result.provider == "replicate_paddleocr"
    assert result.text == "继续旅程\n新的旅程"
    assert result.blocks[0].bbox == [80, 180, 220, 215]
    assert result.blocks[0].confidence == 0.98


def test_normalize_ocr_space_response_keeps_overlay_word_boxes():
    payload = {
        "ParsedResults": [
            {
                "ParsedText": "设置\n成就\n",
                "TextOverlay": {
                    "Lines": [
                        {
                            "Words": [
                                {"WordText": "设置", "Left": 10, "Top": 20, "Width": 30, "Height": 12},
                                {"WordText": "成就", "Left": 300, "Top": 20, "Width": 30, "Height": 12},
                            ]
                        }
                    ]
                },
            }
        ],
        "IsErroredOnProcessing": False,
    }

    result = normalize_ocr_space_response(payload)

    assert result.provider == "ocr_space"
    assert result.text == "设置\n成就"
    assert [block.text for block in result.blocks] == ["设置", "成就"]
    assert result.blocks[1].bbox == [300, 20, 330, 32]


def test_apply_ocr_to_schema_attaches_text_to_intersecting_regions(tmp_path):
    image_path = tmp_path / "menu.png"
    Image.new("RGB", (400, 800), color=(20, 12, 10)).save(image_path)
    schema = build_screen_schema(image_path)
    ocr = OCRResult(
        provider="test",
        text="破宫之十重奏\n继续旅程\n设置",
        blocks=[
            OCRBlock(text="破宫之十重奏", bbox=[50, 40, 350, 90], confidence=0.99),
            OCRBlock(text="继续旅程", bbox=[80, 250, 260, 290], confidence=0.95),
            OCRBlock(text="设置", bbox=[5, 5, 40, 25], confidence=0.7),
        ],
    )

    apply_ocr_to_schema(schema, ocr)
    by_id = {region.id: region for region in schema.regions}

    assert by_id["title-stack"].content["ocr_text"] == ["破宫之十重奏"]
    assert by_id["primary-actions"].content["ocr_text"] == ["继续旅程"]
    assert by_id["title-stack"].content["ocr_provider"] == "test"
    assert "设置" not in by_id["title-stack"].content["ocr_text"]


def test_build_ocr_client_preserves_manual_gate_when_token_missing(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)

    client = build_ocr_client("replicate_paddleocr")

    assert client.is_configured is False
    assert "REPLICATE_API_TOKEN" in client.manual_gate


def test_handoff_renders_ocr_manual_gate_note(tmp_path):
    image_path = tmp_path / "menu.png"
    Image.new("RGB", (360, 640), color=(20, 12, 10)).save(image_path)
    schema = build_screen_schema(image_path)
    schema.reference_handoff.notes = "OCR manual gate: Set REPLICATE_API_TOKEN to enable hosted PaddleOCR."

    handoff = render_handoff_markdown(schema)

    assert "OCR manual gate" in handoff
    assert "REPLICATE_API_TOKEN" in handoff
