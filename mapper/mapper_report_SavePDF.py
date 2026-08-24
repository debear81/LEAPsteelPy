r"""
mapper_report_SavePDF_v2.py
===========================

Focused mapper for LEAP's PDF Save As dialog.

Important:
LEAP appears to expose the Save As dialog as a CHILD/DESCENDANT of the Preview
window rather than as a normal top-level desktop window. This mapper therefore
searches both top-level windows and their descendants.

Starting condition:
    The PDF Save As dialog is already visible.

Output:
    <project root>\mapper\report_maps\save_pdf_dialog\
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any

sys.coinit_flags = 2

from pywinauto import Desktop


PROJECT_ROOT = Path(__file__).resolve().parent.parent
#OUTPUT_DIR = PROJECT_ROOT / "mapper" / "report_maps" / "save_pdf_dialog"
OUTPUT_DIR = PROJECT_ROOT / "report_maps" / "save_pdf_dialog"
LOG_FILE = OUTPUT_DIR / "mapper_report_SavePDF.log"


def safe_call(func, default=None):
    try:
        return func()
    except Exception:
        return default


def text(control: Any) -> str:
    return (safe_call(control.window_text, "") or "").strip()


def control_type(control: Any) -> str:
    return getattr(getattr(control, "element_info", None), "control_type", "") or ""


def class_name(control: Any) -> str:
    info = getattr(control, "element_info", None)
    return (
        getattr(info, "class_name", "")
        or safe_call(control.class_name, "")
        or ""
    )


def auto_id(control: Any) -> str:
    return getattr(getattr(control, "element_info", None), "automation_id", "") or ""


def handle(control: Any):
    return safe_call(lambda: int(control.handle), None)


def rect_dict(control: Any):
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


def area(control: Any) -> int:
    rect = safe_call(control.rectangle)
    if rect is None:
        return 0
    return max(0, rect.width()) * max(0, rect.height())


def describe(control: Any) -> dict:
    return {
        "title": text(control),
        "control_type": control_type(control),
        "class_name": class_name(control),
        "automation_id": auto_id(control),
        "handle": handle(control),
        "rectangle": rect_dict(control),
        "visible": safe_call(control.is_visible, None),
        "enabled": safe_call(control.is_enabled, None),
    }


def log(message=""):
    print(message, flush=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def looks_like_save_dialog(control: Any) -> bool:
    if not safe_call(control.is_visible, False):
        return False

    title = text(control).casefold()

    if title in {"save as", "save pdf file as"}:
        return True

    if "save" in title and (" as" in title or "pdf" in title):
        return True

    # Some child dialogs may expose weak/blank titles. In that case,
    # identify a container that owns a File name edit and Save button.
    descendants = safe_call(control.descendants, []) or []

    has_save = any(
        text(item).casefold() == "save"
        and control_type(item) == "Button"
        for item in descendants
    )

    has_filename_edit = any(
        control_type(item) == "Edit"
        and auto_id(item) == "1001"
        for item in descendants
    )

    return has_save and has_filename_edit


def find_save_dialog(backend: str) -> Any:
    desktop = Desktop(backend=backend)
    candidates = []

    # Search top-level windows first.
    windows = desktop.windows(visible_only=True)

    for window in windows:
        if looks_like_save_dialog(window):
            candidates.append(window)

    # Then search descendants of every top-level window.
    for window in windows:
        for item in safe_call(window.descendants, []) or []:
            if looks_like_save_dialog(item):
                candidates.append(item)

    # UIA may expose additional useful descendants directly from Desktop.
    for item in safe_call(desktop.descendants, []) or []:
        if looks_like_save_dialog(item):
            candidates.append(item)

    # Deduplicate.
    unique = {}

    for item in candidates:
        rect = rect_dict(item) or {}
        key = (
            handle(item),
            text(item),
            control_type(item),
            class_name(item),
            rect.get("left"),
            rect.get("top"),
            rect.get("right"),
            rect.get("bottom"),
        )
        unique[key] = item

    candidates = list(unique.values())

    if not candidates:
        diagnostic = []

        for window in windows:
            diagnostic.append(
                f"TOP: title={text(window)!r}, "
                f"type={control_type(window)!r}, "
                f"class={class_name(window)!r}"
            )

            for item in safe_call(window.descendants, []) or []:
                if text(item) or control_type(item) in {"Window", "Pane", "Edit", "Button"}:
                    diagnostic.append(
                        f"  CHILD: title={text(item)!r}, "
                        f"type={control_type(item)!r}, "
                        f"class={class_name(item)!r}, "
                        f"auto_id={auto_id(item)!r}, "
                        f"rect={rect_dict(item)}"
                    )

        diagnostic_file = OUTPUT_DIR / f"diagnostic_{backend}_all_titled_controls.txt"
        diagnostic_file.write_text("\n".join(diagnostic), encoding="utf-8")

        raise RuntimeError(
            f"Could not find Save As dialog with backend={backend!r}.\n"
            f"Diagnostic written to:\n  {diagnostic_file}"
        )

    candidates.sort(key=area, reverse=True)
    return candidates[0]


def collect_controls(dialog: Any) -> list[dict]:
    items = [dialog] + (safe_call(dialog.descendants, []) or [])
    result = []

    for item in items:
        if safe_call(item.is_visible, False):
            result.append(describe(item))

    result.sort(
        key=lambda x: (
            (x["rectangle"] or {}).get("top", 999999),
            (x["rectangle"] or {}).get("left", 999999),
            x["control_type"],
            x["title"],
        )
    )

    return result


def write_map(path: Path, backend: str, dialog: Any) -> None:
    controls = collect_controls(dialog)

    lines = [
        "=" * 120,
        f"LEAP PDF SAVE AS MAP - {backend.upper()}",
        "=" * 120,
        "",
        "DIALOG",
        "-" * 120,
        json.dumps(describe(dialog), indent=2),
        "",
        "VISIBLE CONTROLS",
        "-" * 120,
    ]

    for i, item in enumerate(controls, start=1):
        lines.append(
            f"{i:03d}. title={item['title']!r} | "
            f"type={item['control_type']!r} | "
            f"class={item['class_name']!r} | "
            f"auto_id={item['automation_id']!r} | "
            f"handle={item['handle']!r} | "
            f"rect={item['rectangle']}"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tree_path = path.with_name(path.stem + "_tree.txt")
    try:
        dialog.print_control_identifiers(filename=str(tree_path))
    except Exception as exc:
        with path.open("a", encoding="utf-8") as f:
            f.write(f"\nCould not write control tree: {exc!r}\n")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")

    log("=" * 120)
    log("LEAP PDF SAVE AS DIALOG MAPPER - V2")
    log("=" * 120)
    log("")
    log("Searching top-level windows AND descendants...")

    uia_dialog = find_save_dialog("uia")
    log("")
    log("UIA candidate found:")
    log(json.dumps(describe(uia_dialog), indent=2))

    uia_file = OUTPUT_DIR / "stage_00_uia_save_dialog.txt"
    write_map(uia_file, "uia", uia_dialog)

    try:
        win32_dialog = find_save_dialog("win32")
        log("")
        log("Win32 candidate found:")
        log(json.dumps(describe(win32_dialog), indent=2))

        win32_file = OUTPUT_DIR / "stage_00_win32_save_dialog.txt"
        write_map(win32_file, "win32", win32_dialog)

    except Exception as exc:
        log("")
        log(f"Win32 mapping did not find the dialog: {exc}")
        log("UIA mapping was still completed.")

    log("")
    log(f"Output folder:\n  {OUTPUT_DIR}")
    input("\nPress Enter when finished reviewing the open Save As dialog...")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print()
        print("=" * 120)
        print("MAPPER FAILED")
        print("=" * 120)
        print(traceback.format_exc())
        input("Press Enter to close...")
        raise SystemExit(1)
