"""Optional hosted OCR API clients for ScreenCoder.

The clients normalize different OCR API responses to one lightweight shape so
ScreenCoder can enrich screen schemas without depending on local OCR runtimes.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import requests


@dataclass
class OCRBlock:
    text: str
    bbox: list[float] | None = None
    confidence: float | None = None
    polygon: list[list[float]] | None = None


@dataclass
class OCRResult:
    provider: str
    text: str = ""
    blocks: list[OCRBlock] = field(default_factory=list)
    raw: dict[str, Any] | None = None


@dataclass
class OCRClient:
    provider: str
    is_configured: bool
    manual_gate: str = ""

    def recognize(self, image_path: Path) -> OCRResult:
        raise NotImplementedError


def _compact_text(lines: list[str]) -> str:
    return "\n".join(line.strip() for line in lines if line and line.strip())


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bbox_from_polygon(points: Any) -> list[float] | None:
    if not isinstance(points, list) or not points:
        return None
    xs: list[float] = []
    ys: list[float] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x = _as_float(point[0])
        y = _as_float(point[1])
        if x is None or y is None:
            continue
        xs.append(x)
        ys.append(y)
    if not xs or not ys:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def _normalise_polygon(points: Any) -> list[list[float]] | None:
    if not isinstance(points, list):
        return None
    result: list[list[float]] = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x = _as_float(point[0])
        y = _as_float(point[1])
        if x is not None and y is not None:
            result.append([x, y])
    return result or None


def _bbox_from_xywh(item: Mapping[str, Any]) -> list[float] | None:
    left = _as_float(item.get("Left", item.get("left")))
    top = _as_float(item.get("Top", item.get("top")))
    width = _as_float(item.get("Width", item.get("width")))
    height = _as_float(item.get("Height", item.get("height")))
    if left is None or top is None or width is None or height is None:
        return None
    return [left, top, left + width, top + height]


def _data_uri_for_image(image_path: Path) -> str:
    mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def normalize_replicate_paddleocr_response(payload: Mapping[str, Any]) -> OCRResult:
    """Normalize PaddleOCR-like Replicate prediction output."""

    output = payload.get("output", payload)
    if isinstance(output, str):
        return OCRResult(provider="replicate_paddleocr", text=output.strip(), raw=dict(payload))

    candidates: Any = []
    if isinstance(output, Mapping):
        candidates = output.get("results", output.get("ocr", output.get("blocks", output.get("text", []))))
    elif isinstance(output, list):
        candidates = output

    blocks: list[OCRBlock] = []
    text_lines: list[str] = []
    if isinstance(candidates, str):
        text_lines.append(candidates)
    elif isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, str):
                text_lines.append(item)
                blocks.append(OCRBlock(text=item))
                continue
            if not isinstance(item, Mapping):
                continue
            text = str(item.get("text", item.get("transcription", item.get("label", "")))).strip()
            if not text:
                continue
            polygon = _normalise_polygon(item.get("box", item.get("polygon", item.get("points"))))
            bbox = None
            raw_bbox = item.get("bbox", item.get("bounding_box"))
            if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
                bbox = [float(value) for value in raw_bbox]
            if bbox is None and polygon:
                bbox = _bbox_from_polygon(polygon)
            confidence = _as_float(item.get("score", item.get("confidence", item.get("probability"))))
            text_lines.append(text)
            blocks.append(OCRBlock(text=text, bbox=bbox, confidence=confidence, polygon=polygon))

    if not text_lines and isinstance(output, Mapping):
        generated = output.get("text", output.get("generated_text"))
        if isinstance(generated, str):
            text_lines.append(generated)

    return OCRResult(
        provider="replicate_paddleocr",
        text=_compact_text(text_lines),
        blocks=blocks,
        raw=dict(payload),
    )


def normalize_ocr_space_response(payload: Mapping[str, Any]) -> OCRResult:
    """Normalize OCR.space response as a non-open-source hosted fallback."""

    results = payload.get("ParsedResults") or []
    text_lines: list[str] = []
    blocks: list[OCRBlock] = []
    if isinstance(results, list):
        for parsed in results:
            if not isinstance(parsed, Mapping):
                continue
            parsed_text = parsed.get("ParsedText")
            if isinstance(parsed_text, str) and parsed_text.strip():
                text_lines.append(parsed_text.strip())
            overlay = parsed.get("TextOverlay") or {}
            lines = overlay.get("Lines") if isinstance(overlay, Mapping) else []
            if isinstance(lines, list):
                for line in lines:
                    words = line.get("Words") if isinstance(line, Mapping) else []
                    if not isinstance(words, list):
                        continue
                    for word in words:
                        if not isinstance(word, Mapping):
                            continue
                        text = str(word.get("WordText", "")).strip()
                        if not text:
                            continue
                        blocks.append(OCRBlock(text=text, bbox=_bbox_from_xywh(word)))

    return OCRResult(provider="ocr_space", text=_compact_text(text_lines), blocks=blocks, raw=dict(payload))


class ManualGateOCRClient(OCRClient):
    def __init__(self, provider: str, manual_gate: str) -> None:
        super().__init__(provider=provider, is_configured=False, manual_gate=manual_gate)

    def recognize(self, image_path: Path) -> OCRResult:
        raise RuntimeError(self.manual_gate)


class ReplicatePaddleOCRClient(OCRClient):
    DEFAULT_VERSION = "084b779cb09bc2462335a5768fabaeaaba53bb3f70afd0d2fe48fad71fdc4d5a"

    def __init__(self, token: str, version: str | None = None, timeout: int = 120) -> None:
        super().__init__(provider="replicate_paddleocr", is_configured=True)
        self.token = token
        self.version = version or os.getenv("SCREENCODER_REPLICATE_PADDLEOCR_VERSION", self.DEFAULT_VERSION)
        self.timeout = timeout

    def recognize(self, image_path: Path) -> OCRResult:
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Prefer": "wait",
            },
            json={"version": self.version, "input": {"image": _data_uri_for_image(image_path), "lang": "ch"}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") in {"starting", "processing"} and payload.get("urls", {}).get("get"):
            payload = self._poll(payload["urls"]["get"])
        if payload.get("status") == "failed":
            raise RuntimeError(f"Replicate OCR failed: {payload.get('error')}")
        return normalize_replicate_paddleocr_response(payload)

    def _poll(self, url: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            response = requests.get(url, headers={"Authorization": f"Bearer {self.token}"}, timeout=30)
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") in {"succeeded", "successful"}:
                return payload
            if payload.get("status") == "failed":
                raise RuntimeError(f"Replicate OCR failed: {payload.get('error')}")
            time.sleep(2)
        raise TimeoutError("Timed out waiting for Replicate OCR prediction")


class OCRSpaceClient(OCRClient):
    def __init__(self, api_key: str, timeout: int = 120) -> None:
        super().__init__(provider="ocr_space", is_configured=True)
        self.api_key = api_key
        self.timeout = timeout

    def recognize(self, image_path: Path) -> OCRResult:
        with Path(image_path).open("rb") as handle:
            response = requests.post(
                "https://api.ocr.space/parse/image",
                headers={"apikey": self.api_key},
                data={"language": "chs", "isOverlayRequired": "true", "OCREngine": "2"},
                files={"file": (Path(image_path).name, handle)},
                timeout=self.timeout,
            )
        response.raise_for_status()
        payload = response.json()
        if payload.get("IsErroredOnProcessing"):
            raise RuntimeError(f"OCR.space failed: {payload.get('ErrorMessage')}")
        return normalize_ocr_space_response(payload)


class HuggingFaceOCRClient(OCRClient):
    def __init__(self, token: str, model: str | None = None, timeout: int = 120) -> None:
        super().__init__(provider="hf_ocr", is_configured=True)
        self.token = token
        self.model = model or os.getenv("SCREENCODER_HF_OCR_MODEL", "stepfun-ai/GOT-OCR-2.0-hf")
        self.timeout = timeout

    def recognize(self, image_path: Path) -> OCRResult:
        mime = mimetypes.guess_type(str(image_path))[0] or "image/png"
        response = requests.post(
            f"https://api-inference.huggingface.co/models/{self.model}",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": mime},
            data=Path(image_path).read_bytes(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        text = ""
        if isinstance(payload, list) and payload and isinstance(payload[0], Mapping):
            text = str(payload[0].get("generated_text", payload[0].get("text", ""))).strip()
        elif isinstance(payload, Mapping):
            text = str(payload.get("generated_text", payload.get("text", json.dumps(payload, ensure_ascii=False)))).strip()
        elif isinstance(payload, str):
            text = payload.strip()
        return OCRResult(provider="hf_ocr", text=text, blocks=[], raw={"response": payload})


def build_ocr_client(provider: str | None) -> OCRClient | None:
    provider = (provider or "none").strip().lower().replace("-", "_")
    if provider in {"", "none", "off", "disabled"}:
        return None
    if provider == "replicate_paddleocr":
        token = os.getenv("REPLICATE_API_TOKEN")
        if not token:
            return ManualGateOCRClient(provider, "Set REPLICATE_API_TOKEN to enable hosted PaddleOCR via Replicate.")
        return ReplicatePaddleOCRClient(token)
    if provider == "ocr_space":
        api_key = os.getenv("OCR_SPACE_API_KEY")
        if not api_key:
            return ManualGateOCRClient(provider, "Set OCR_SPACE_API_KEY to enable OCR.space fallback OCR.")
        return OCRSpaceClient(api_key)
    if provider in {"hf", "hf_ocr", "huggingface"}:
        token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        if not token:
            return ManualGateOCRClient("hf_ocr", "Set HF_TOKEN to enable Hugging Face hosted open-model OCR.")
        return HuggingFaceOCRClient(token)
    raise ValueError(f"Unsupported OCR provider: {provider}")
