import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PipelineConfig:
    image: Path
    work_dir: Path = Path("data/run")
    api_key: Path = Path("doubao_api.txt")
    model: str = "doubao-1.5-thinking-vision-pro-250428"


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: list[str]


def _stem(path: Path) -> str:
    return path.stem


def build_steps(config: PipelineConfig) -> list[PipelineStep]:
    image = Path(config.image)
    work_dir = Path(config.work_dir)
    api_key = Path(config.api_key)
    stem = _stem(image)

    region_bboxes = work_dir / f"{stem}_bboxes.json"
    region_debug = work_dir / f"{stem}_with_bboxes.png"
    gray_html = work_dir / f"{stem}_layout.html"
    gray_bboxes = work_dir / f"{stem}_gray_bboxes.json"
    uied_json = work_dir / "ip" / f"{stem}.json"
    mapping_json = work_dir / f"mapping_full_{stem}.json"
    mapping_debug = work_dir / f"overlay_{stem}.png"
    final_html = work_dir / f"{stem}_layout_final.html"

    return [
        PipelineStep(
            "detect layout regions",
            [
                sys.executable,
                "block_parsor.py",
                "--image",
                str(image),
                "--api-key",
                str(api_key),
                "--json",
                str(region_bboxes),
                "--debug",
                str(region_debug),
            ],
        ),
        PipelineStep(
            "generate gray html",
            [
                sys.executable,
                "html_generator.py",
                "--model",
                config.model,
                "--image",
                str(image),
                "--bboxes",
                str(region_bboxes),
                "--output",
                str(gray_html),
                "--api-key",
                str(api_key),
            ],
        ),
        PipelineStep(
            "detect gray placeholders",
            [
                sys.executable,
                "image_box_detection.py",
                "--html",
                str(gray_html),
                "--screenshot",
                str(image),
                "--out",
                str(work_dir),
                "--json",
                str(gray_bboxes),
            ],
        ),
        PipelineStep(
            "detect source UI elements",
            [
                sys.executable,
                "UIED/run_single.py",
                "--image",
                str(image),
                "--output-root",
                str(work_dir),
                "--output-json",
                str(uied_json),
            ],
        ),
        PipelineStep(
            "map placeholders to source elements",
            [
                sys.executable,
                "mapping.py",
                "--gray",
                str(gray_bboxes),
                "--uied",
                str(uied_json),
                "--out",
                str(mapping_json),
                "--debug",
                str(mapping_debug),
                "--debug-src",
                str(image),
            ],
        ),
        PipelineStep(
            "replace placeholders",
            [
                sys.executable,
                "image_replacer.py",
                "--mapping",
                str(mapping_json),
                "--uied",
                str(uied_json),
                "--original-image",
                str(image),
                "--gray-html",
                str(gray_html),
                "--output-html",
                str(final_html),
            ],
        ),
    ]


def run_pipeline(config: PipelineConfig, dry_run: bool = False) -> None:
    config.work_dir.mkdir(parents=True, exist_ok=True)
    for step in build_steps(config):
        print(f"\n=== {step.name} ===")
        print(" ".join(step.command))
        if not dry_run:
            subprocess.run(step.command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert a UI screenshot to HTML with the ScreenCoder pipeline.")
    parser.add_argument("--image", required=True, type=Path, help="Source UI screenshot.")
    parser.add_argument("--work-dir", default=Path("data/run"), type=Path, help="Directory for intermediate files and final HTML.")
    parser.add_argument("--api-key", default=Path("doubao_api.txt"), type=Path, help="Doubao API key file.")
    parser.add_argument("--model", default="doubao-1.5-thinking-vision-pro-250428", help="Doubao vision model name.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_pipeline(
        PipelineConfig(
            image=args.image,
            work_dir=args.work_dir,
            api_key=args.api_key,
            model=args.model,
        ),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
