r"""
Prepending the comment block with a raw string ("r") will prevent Python from interpreting backslashes in the text
as escape sequences. This is useful for Windows paths and other text that may contain backslashes.

mapper_report_export.py
========================

Diagnostic mapper for LEAP Bridge Steel's Preview > Export To dropdown.

PURPOSE
-------
This script investigates how LEAP exposes the "Export To" dropdown and its
menu items through Windows UI Automation / Win32.

It is intended to answer questions such as:

- Is the Export To dropdown exposed as a top-level popup window?
- Is "PDF File" visible to UIA, Win32, both, or neither?
- What class names, handles, control types, automation IDs, and rectangles
  appear when the dropdown opens?
- Can the first dropdown item be identified by relative geometry even if its
  text is not exposed?
- Which controls/windows appear or disappear after opening the dropdown?

The mapper does NOT submit a report and does NOT export a PDF.

EXPECTED STARTING CONDITION
---------------------------
1. LEAP Bridge Steel is open.
2. A report Preview window is already open.
3. Ideally, the report has already been submitted/generated so the normal
   Preview ribbon is visible.

OUTPUT
------
    <project root>\\mapper\\report_maps\\export_dropdown\\

Typical files:

    export_map_summary.txt
    stage_00_uia_before.txt
    stage_00_win32_before.txt
    stage_01_uia_after_export_click.txt
    stage_01_win32_after_export_click.txt

USAGE
-----
    py .\\src\\mapper_report_export.py

Optional:

    py .\\src\\mapper_report.py --pause

The script leaves the Export To dropdown open for inspection until you press
Enter in the terminal.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from time import sleep
from typing import Any, Callable, TypeVar

sys.coinit_flags = 2

from pywinauto import Desktop


# =============================================================================
# SETTINGS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# OUTPUT_DIR = PROJECT_ROOT / "mapper" / "report_maps" / "export_dropdown"
OUTPUT_DIR = PROJECT_ROOT / "report_maps" / "export_dropdown"
LOG_FILE = OUTPUT_DIR / "mapper_report_export.log"

SETTLE_SECONDS = 1.00

T = TypeVar("T")


# =============================================================================
# BASIC UTILITIES
# =============================================================================

def safe_call(
    function: Callable[[], T],
    default: T | None = None,
) -> T | None:
    try:
        return function()
    except Exception:
        return default


def safe_text(control: Any) -> str:
    return (safe_call(control.window_text, "") or "").strip()


def get_control_type(control: Any) -> str:
    info = getattr(control, "element_info", None)
    return getattr(info, "control_type", "") or ""


def get_class_name(control: Any) -> str:
    info = getattr(control, "element_info", None)

    return (
        getattr(info, "class_name", "")
        or safe_call(control.class_name, "")
        or ""
    )


def get_auto_id(control: Any) -> str:
    info = getattr(control, "element_info", None)
    return getattr(info, "automation_id", "") or ""


def get_process_id(control: Any) -> int | None:
    info = getattr(control, "element_info", None)
    return getattr(info, "process_id", None)


def get_handle(control: Any) -> int | None:
    return safe_call(lambda: int(control.handle), None)


def rectangle_to_dict(control: Any) -> dict[str, int] | None:
    rect = safe_call(control.rectangle)

    if rect is None:
        return None

    return {
        "left": rect.left,
        "top": rect.top,
        "right": rect.right,
        "bottom": rect.bottom,
        "width": rect.width(),
        "height": rect.height(),
    }


def rectangle_area(control: Any) -> int:
    rect = safe_call(control.rectangle)

    if rect is None:
        return 0

    return max(0, rect.width()) * max(0, rect.height())


def describe_control(control: Any) -> dict[str, Any]:
    return {
        "title": safe_text(control),
        "control_type": get_control_type(control),
        "class_name": get_class_name(control),
        "automation_id": get_auto_id(control),
        "rectangle": rectangle_to_dict(control),
        "visible": safe_call(control.is_visible, None),
        "enabled": safe_call(control.is_enabled, None),
        "process_id": get_process_id(control),
        "handle": get_handle(control),
    }


def log(message: str = "") -> None:
    print(message, flush=True)

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


# =============================================================================
# COMMAND LINE
# =============================================================================

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map LEAP Preview's Export To dropdown."
    )

    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause before clicking Export To.",
    )

    return parser.parse_args()


# =============================================================================
# PREVIEW / EXPORT CONTROL
# =============================================================================

def find_preview_uia() -> Any:
    previews = Desktop(backend="uia").windows(
        title="Preview",
        control_type="Window",
        visible_only=True,
    )

    if not previews:
        raise RuntimeError(
            'Could not find an open LEAP "Preview" window.'
        )

    previews.sort(key=rectangle_area, reverse=True)
    return previews[0]


def find_export_to_control(preview: Any) -> Any:
    candidates = []

    for control in safe_call(preview.descendants, []) or []:
        if not safe_call(control.is_visible, False):
            continue

        if safe_text(control).casefold() not in {
            "export to",
            "export to...",
        }:
            continue

        candidates.append(control)

    if not candidates:
        raise RuntimeError(
            'Could not find the visible "Export To" control in Preview.'
        )

    priority = {
        "SplitButton": 0,
        "Button": 1,
        "MenuItem": 2,
        "Custom": 3,
    }

    candidates.sort(
        key=lambda control: (
            priority.get(get_control_type(control), 99),
            -rectangle_area(control),
        )
    )

    return candidates[0]


def click_export_dropdown(export_to: Any) -> None:
    rect = export_to.rectangle()

    log(
        "Clicking Export To dropdown portion at relative coordinates "
        f"({max(1, rect.width() - 7)}, {max(1, rect.height() - 7)})..."
    )

    try:
        export_to.click_input(
            coords=(
                max(1, rect.width() - 7),
                max(1, rect.height() - 7),
            )
        )
    except Exception:
        log("Dropdown-edge click failed; trying normal click.")
        export_to.click_input()

    sleep(SETTLE_SECONDS)


# =============================================================================
# SNAPSHOT / MAPPING
# =============================================================================

def visible_windows(backend: str) -> list[Any]:
    return Desktop(backend=backend).windows(visible_only=True)


def snapshot_keys(backend: str) -> set[tuple[Any, ...]]:
    result: set[tuple[Any, ...]] = set()

    for window in visible_windows(backend):
        data = describe_control(window)
        rect = data["rectangle"]

        if rect is None:
            continue

        result.add(
            (
                data["handle"],
                data["title"],
                data["control_type"],
                data["class_name"],
                rect["left"],
                rect["top"],
                rect["right"],
                rect["bottom"],
            )
        )

    return result


def write_control_tree(
    destination: Path,
    backend: str,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    desktop = Desktop(backend=backend)

    with destination.open("w", encoding="utf-8") as file:
        file.write("=" * 110 + "\n")
        file.write(f"VISIBLE TOP-LEVEL WINDOWS - BACKEND={backend!r}\n")
        file.write("=" * 110 + "\n\n")

        for index, window in enumerate(
            desktop.windows(visible_only=True),
            start=1,
        ):
            file.write("\n" + "#" * 110 + "\n")
            file.write(
                f"WINDOW {index}\n"
                f"{json.dumps(describe_control(window), indent=2)}\n"
            )
            file.write("#" * 110 + "\n")

            try:
                # Most pywinauto versions accept a filename path.
                temp_file = destination.with_name(
                    f"{destination.stem}_window_{index}.txt"
                )
                window.print_control_identifiers(
                    filename=str(temp_file)
                )
                file.write(
                    f"Full control tree written separately to:\n"
                    f"  {temp_file}\n"
                )
            except Exception as exc:
                file.write(
                    f"Could not print control tree: {exc!r}\n"
                )


def collect_controls_near_export(
    backend: str,
    export_rect: dict[str, int],
) -> list[dict[str, Any]]:
    """
    Gather visible controls/windows in the general area below and around the
    Export To button.

    The region is intentionally generous because LEAP may create the popup
    as a separate top-level window or custom WinForms control.
    """

    search_left = export_rect["left"] - 100
    search_right = export_rect["right"] + 450
    search_top = export_rect["top"] - 50
    search_bottom = export_rect["bottom"] + 650

    controls: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    desktop = Desktop(backend=backend)

    roots = list(desktop.windows(visible_only=True))

    # UIA can expose useful popup controls as descendants of Desktop that are
    # not returned as conventional top-level windows.
    if backend == "uia":
        roots.extend(safe_call(desktop.descendants, []) or [])

    for root in roots:
        candidates = [root]

        candidates.extend(
            safe_call(root.descendants, []) or []
        )

        for control in candidates:
            if not safe_call(control.is_visible, False):
                continue

            rect = rectangle_to_dict(control)

            if rect is None:
                continue

            # Basic rectangle intersection test.
            if rect["right"] < search_left:
                continue
            if rect["left"] > search_right:
                continue
            if rect["bottom"] < search_top:
                continue
            if rect["top"] > search_bottom:
                continue

            data = describe_control(control)

            key = (
                data["handle"],
                data["title"],
                data["control_type"],
                data["class_name"],
                rect["left"],
                rect["top"],
                rect["right"],
                rect["bottom"],
            )

            if key in seen:
                continue

            seen.add(key)
            controls.append(data)

    controls.sort(
        key=lambda item: (
            (item["rectangle"] or {}).get("top", 999999),
            (item["rectangle"] or {}).get("left", 999999),
            item["control_type"],
            item["title"],
        )
    )

    return controls


def write_compact_summary(
    destination: Path,
    preview: Any,
    export_to: Any,
    before_uia: set[tuple[Any, ...]],
    before_win32: set[tuple[Any, ...]],
    after_uia: set[tuple[Any, ...]],
    after_win32: set[tuple[Any, ...]],
    nearby_uia: list[dict[str, Any]],
    nearby_win32: list[dict[str, Any]],
) -> None:
    new_uia = sorted(after_uia - before_uia, key=str)
    new_win32 = sorted(after_win32 - before_win32, key=str)

    lines: list[str] = []

    lines.append("=" * 110)
    lines.append("LEAP EXPORT TO DROPDOWN MAP")
    lines.append("=" * 110)
    lines.append("")

    lines.append("PREVIEW")
    lines.append("-" * 110)
    lines.append(json.dumps(describe_control(preview), indent=2))
    lines.append("")

    lines.append("EXPORT TO CONTROL")
    lines.append("-" * 110)
    lines.append(json.dumps(describe_control(export_to), indent=2))
    lines.append("")

    lines.append("NEW UIA TOP-LEVEL WINDOWS AFTER CLICK")
    lines.append("-" * 110)

    if new_uia:
        for item in new_uia:
            lines.append(repr(item))
    else:
        lines.append("(none detected)")

    lines.append("")
    lines.append("NEW WIN32 TOP-LEVEL WINDOWS AFTER CLICK")
    lines.append("-" * 110)

    if new_win32:
        for item in new_win32:
            lines.append(repr(item))
    else:
        lines.append("(none detected)")

    lines.append("")
    lines.append("VISIBLE UIA CONTROLS NEAR EXPORT TO AFTER CLICK")
    lines.append("-" * 110)

    for index, item in enumerate(nearby_uia, start=1):
        lines.append(
            f"{index:03d}. "
            f"title={item['title']!r}, "
            f"type={item['control_type']!r}, "
            f"class={item['class_name']!r}, "
            f"auto_id={item['automation_id']!r}, "
            f"handle={item['handle']!r}, "
            f"rect={item['rectangle']}"
        )

    lines.append("")
    lines.append("VISIBLE WIN32 CONTROLS NEAR EXPORT TO AFTER CLICK")
    lines.append("-" * 110)

    for index, item in enumerate(nearby_win32, start=1):
        lines.append(
            f"{index:03d}. "
            f"title={item['title']!r}, "
            f"type={item['control_type']!r}, "
            f"class={item['class_name']!r}, "
            f"auto_id={item['automation_id']!r}, "
            f"handle={item['handle']!r}, "
            f"rect={item['rectangle']}"
        )

    lines.append("")
    lines.append("LOOK FOR")
    lines.append("-" * 110)
    lines.append(
        '- text such as "PDF File", "HTML File", "MHT File", "RTF File", '
        '"XLS File", "XLSX File", "CSV File", "Text File", or "Image File"'
    )
    lines.append(
        "- a new popup/window whose rectangle closely surrounds the visible "
        "Export To dropdown"
    )
    lines.append(
        "- repeated vertically stacked controls with similar widths/heights; "
        "the first such row is likely PDF File"
    )
    lines.append(
        "- stable class names / handles / relative rectangles that can be "
        "used instead of absolute screen coordinates"
    )
    lines.append("")

    destination.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:
    args = parse_arguments()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")

    log("=" * 110)
    log("LEAP EXPORT TO DROPDOWN MAPPER")
    log("=" * 110)

    preview = find_preview_uia()
    export_to = find_export_to_control(preview)

    log("")
    log(f"Preview handle: {get_handle(preview)}")
    log(f"Preview rect:   {rectangle_to_dict(preview)}")
    log("")
    log("Export To control:")
    log(f"  title:    {safe_text(export_to)!r}")
    log(f"  type:     {get_control_type(export_to)!r}")
    log(f"  class:    {get_class_name(export_to)!r}")
    log(f"  auto_id:  {get_auto_id(export_to)!r}")
    log(f"  handle:   {get_handle(export_to)!r}")
    log(f"  rect:     {rectangle_to_dict(export_to)}")

    export_rect = rectangle_to_dict(export_to)

    if export_rect is None:
        raise RuntimeError(
            "Could not determine the Export To control rectangle."
        )

    # -------------------------------------------------------------------------
    # BEFORE CLICK
    # -------------------------------------------------------------------------

    log("")
    log("Writing BEFORE-click snapshots...")

    before_uia = snapshot_keys("uia")
    before_win32 = snapshot_keys("win32")

    before_uia_file = OUTPUT_DIR / "stage_00_uia_before.txt"
    before_win32_file = OUTPUT_DIR / "stage_00_win32_before.txt"

    write_control_tree(before_uia_file, "uia")
    write_control_tree(before_win32_file, "win32")

    log(f"  {before_uia_file}")
    log(f"  {before_win32_file}")

    if args.pause:
        input(
            "\nPreview is ready. Press Enter to click Export To..."
        )

    # -------------------------------------------------------------------------
    # OPEN EXPORT DROPDOWN
    # -------------------------------------------------------------------------

    log("")
    click_export_dropdown(export_to)

    # -------------------------------------------------------------------------
    # AFTER CLICK
    # -------------------------------------------------------------------------

    log("")
    log("Writing AFTER-click snapshots while dropdown is open...")

    after_uia = snapshot_keys("uia")
    after_win32 = snapshot_keys("win32")

    after_uia_file = (
        OUTPUT_DIR / "stage_01_uia_after_export_click.txt"
    )
    after_win32_file = (
        OUTPUT_DIR / "stage_01_win32_after_export_click.txt"
    )

    write_control_tree(after_uia_file, "uia")
    write_control_tree(after_win32_file, "win32")

    nearby_uia = collect_controls_near_export(
        "uia",
        export_rect,
    )
    nearby_win32 = collect_controls_near_export(
        "win32",
        export_rect,
    )

    summary_file = OUTPUT_DIR / "export_map_summary.txt"

    write_compact_summary(
        destination=summary_file,
        preview=preview,
        export_to=export_to,
        before_uia=before_uia,
        before_win32=before_win32,
        after_uia=after_uia,
        after_win32=after_win32,
        nearby_uia=nearby_uia,
        nearby_win32=nearby_win32,
    )

    log(f"  {after_uia_file}")
    log(f"  {after_win32_file}")
    log("")
    log(f"Compact summary:")
    log(f"  {summary_file}")

    log("")
    log("=" * 110)
    log("EXPORT DROPDOWN IS BEING LEFT OPEN FOR VISUAL INSPECTION")
    log("=" * 110)
    log("")
    log(
        "Compare the visible dropdown to export_map_summary.txt, then "
        "press Enter here."
    )

    input()

    log("")
    log("Mapper complete.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())

    except KeyboardInterrupt:
        print()
        print("Mapper cancelled.")
        raise SystemExit(130)

    except Exception:
        print()
        print("=" * 110)
        print("MAPPER FAILED")
        print("=" * 110)
        print(traceback.format_exc())
        input("Press Enter to close...")
        raise SystemExit(1)
