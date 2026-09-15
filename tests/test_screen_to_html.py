import sys
from pathlib import Path

from screen_to_html import PipelineConfig, build_steps


def test_build_steps_uses_consistent_paths_for_input_image():
    config = PipelineConfig(
        image=Path("examples/menu.png"),
        work_dir=Path("out/menu"),
        api_key=Path("keys/doubao.txt"),
        model="demo-model",
    )

    steps = build_steps(config)

    assert [step.name for step in steps] == [
        "detect layout regions",
        "generate gray html",
        "detect gray placeholders",
        "detect source UI elements",
        "map placeholders to source elements",
        "replace placeholders",
    ]
    assert steps[0].command == [
        sys.executable,
        "block_parsor.py",
        "--image",
        "examples/menu.png",
        "--api-key",
        "keys/doubao.txt",
        "--json",
        "out/menu/menu_bboxes.json",
        "--debug",
        "out/menu/menu_with_bboxes.png",
    ]
    assert steps[1].command[-8:] == [
        "--image",
        "examples/menu.png",
        "--bboxes",
        "out/menu/menu_bboxes.json",
        "--output",
        "out/menu/menu_layout.html",
        "--api-key",
        "keys/doubao.txt",
    ]
    assert steps[1].command[-2:] == ["--api-key", "keys/doubao.txt"]
    assert steps[2].command[-2:] == ["--json", "out/menu/menu_gray_bboxes.json"]
    assert "out/menu/ip/menu.json" in steps[3].command
    assert steps[-1].command[-2:] == ["--output-html", "out/menu/menu_layout_final.html"]
