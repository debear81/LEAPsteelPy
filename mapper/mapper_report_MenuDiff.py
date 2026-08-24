r"""
Milestone 5b: Compare LEAP UI Automation controls before and after opening
Analysis Design.

LEAP Bridge Steel must be running with a .lbsx file open before running this script.

Usage:
    python .\src\mapper_report_MenuDiff.py
    python .\src\mapper_report_MenuDiff.py --pause-after-click
    python .\src\mapper_report_MenuDiff.py --after-action down
    python .\src\mapper_report_MenuDiff.py --after-action right
    python .\src\mapper_report_MenuDiff.py --after-action hover
    python .\src\mapper_report_MenuDiff.py --leave-open

Output:
    mapper\report_maps\analysis_design_diff\
"""

from __future__ import annotations

import argparse
import json
import re
import traceback
from collections import Counter
from pathlib import Path
from time import sleep
from typing import Any

from pywinauto import Desktop
from pywinauto.keyboard import send_keys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
#OUTPUT_DIR = PROJECT_ROOT / "mapper" / "report_maps" / "analysis_design_diff"
OUTPUT_DIR = PROJECT_ROOT / "report_maps" / "analysis_design_diff"
LOG_FILE = OUTPUT_DIR / "mapper_report_MenuDiff.log"

LEAP_TITLE_RE = r".*\.lbsx - LEAP Bridge Steel.*"
SETTLE_AFTER_CLICK = 1.0
SETTLE_AFTER_ACTION = 0.8

ALIASES = {
    "analysis design",
    "analysis / design",
    "analysis/design",
    "analysis & design",
}

LIKELY_MENU_TYPES = {
    "Menu", "MenuItem", "Pane", "Custom", "List", "ListItem",
    "Text", "Button", "SplitButton", "ToolBar", "Tree", "TreeItem",
}


def log(message: str = "") -> None:
    print(message, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def safe_call(function, default=None):
    try:
        return function()
    except Exception:
        return default


def text(control) -> str:
    return safe_call(control.window_text, "") or ""


def control_type(control) -> str:
    return getattr(control.element_info, "control_type", None) or ""


def class_name(control) -> str:
    return (
        getattr(control.element_info, "class_name", None)
        or safe_call(control.class_name, "")
        or ""
    )


def auto_id(control) -> str:
    return getattr(control.element_info, "automation_id", None) or ""


def process_id(control) -> int | None:
    return getattr(control.element_info, "process_id", None)


def runtime_id(control):
    value = getattr(control.element_info, "runtime_id", None)
    if value is None:
        return None
    try:
        return list(value)
    except Exception:
        return str(value)


def handle(control) -> int | None:
    return safe_call(lambda: control.handle, None)


def rect_dict(control) -> dict[str, int] | None:
    rect = safe_call(control.rectangle, None)
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


def area(control) -> int:
    rect = safe_call(control.rectangle, None)
    if rect is None:
        return 0
    return max(0, rect.width()) * max(0, rect.height())


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def is_analysis_design(value: str) -> bool:
    return normalize(value) in {normalize(alias) for alias in ALIASES}


def parent_description(control) -> dict[str, Any] | None:
    parent = safe_call(control.parent, None)
    if parent is None:
        return None
    return {
        "title": text(parent),
        "control_type": control_type(parent),
        "class_name": class_name(parent),
        "automation_id": auto_id(parent),
        "rectangle": rect_dict(parent),
        "process_id": process_id(parent),
        "handle": handle(parent),
    }


def describe(control, sequence: int, source: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "source": source,
        "title": text(control),
        "control_type": control_type(control),
        "class_name": class_name(control),
        "automation_id": auto_id(control),
        "rectangle": rect_dict(control),
        "visible": safe_call(control.is_visible, None),
        "enabled": safe_call(control.is_enabled, None),
        "process_id": process_id(control),
        "handle": handle(control),
        "runtime_id": runtime_id(control),
        "parent": parent_description(control),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diff LEAP UIA controls before and after opening Analysis Design."
    )
    parser.add_argument("--all-processes", action="store_true")
    parser.add_argument("--include-invisible", action="store_true")
    parser.add_argument("--pause-after-click", action="store_true")
    parser.add_argument(
        "--after-action",
        choices=("none", "down", "right", "hover"),
        default="none",
    )
    parser.add_argument("--leave-open", action="store_true")
    return parser.parse_args()


def find_main_window(desktop):
    matches = desktop.windows(
        title_re=LEAP_TITLE_RE,
        control_type="Window",
        visible_only=True,
    )
    if matches:
        matches.sort(key=area, reverse=True)
        return matches[0]
    raise RuntimeError("Could not find an open LEAP Bridge Steel .lbsx window.")


def find_reports_toolbar(main_window):
    matches = [
        item
        for item in main_window.descendants(title="Reports", control_type="ToolBar")
        if safe_call(item.is_visible, False)
    ]
    if not matches:
        raise RuntimeError("Could not find the Reports toolbar.")
    matches.sort(key=area, reverse=True)
    return matches[0]


def find_analysis_design(main_window, reports_toolbar):
    candidates = []
    for root in (reports_toolbar, main_window):
        for item in safe_call(root.descendants, []):
            if not safe_call(item.is_visible, False):
                continue
            if not safe_call(item.is_enabled, False):
                continue
            if is_analysis_design(text(item)):
                candidates.append(item)

    if not candidates:
        raise RuntimeError("Could not find the Analysis Design ribbon command.")

    priority = {"SplitButton": 0, "Button": 1, "MenuItem": 2, "Custom": 3, "Pane": 4}
    candidates.sort(key=lambda item: (priority.get(control_type(item), 99), -area(item)))
    return candidates[0]


def wrapper_identity(control) -> tuple[Any, ...]:
    rid = runtime_id(control)
    if isinstance(rid, list):
        rid = tuple(rid)
    return (
        process_id(control), rid, handle(control), control_type(control),
        text(control), class_name(control), str(rect_dict(control)),
    )


def collect_wrappers(desktop, main_window, leap_pid: int, all_processes: bool):
    collected = []
    seen = set()

    def add(item, source: str):
        key = wrapper_identity(item)
        if key not in seen:
            seen.add(key)
            collected.append((item, source))

    add(main_window, "leap_window")
    for item in safe_call(main_window.descendants, []):
        add(item, "leap_descendant")

    for window in safe_call(lambda: desktop.windows(visible_only=False), []):
        if not all_processes and process_id(window) != leap_pid:
            continue
        add(window, "desktop_window")
        for item in safe_call(window.descendants, []):
            if all_processes or process_id(item) in {None, leap_pid}:
                add(item, "desktop_descendant")

    return collected


def take_snapshot(
    desktop,
    main_window,
    leap_pid: int,
    all_processes: bool,
    include_invisible: bool,
    label: str,
) -> dict[str, Any]:
    controls = []
    for sequence, (item, source) in enumerate(
        collect_wrappers(desktop, main_window, leap_pid, all_processes),
        start=1,
    ):
        record = describe(item, sequence, source)
        if include_invisible or record["visible"] is True:
            controls.append(record)

    return {
        "label": label,
        "captured_control_count": len(controls),
        "controls": controls,
    }


def exact_key(item: dict[str, Any]) -> tuple[Any, ...]:
    rect = item.get("rectangle") or {}
    parent = item.get("parent") or {}
    rid = item.get("runtime_id")
    if isinstance(rid, list):
        rid = tuple(rid)
    return (
        item.get("process_id"), rid, item.get("control_type"), item.get("title"),
        item.get("automation_id"), item.get("class_name"),
        rect.get("left"), rect.get("top"), rect.get("right"), rect.get("bottom"),
        parent.get("control_type"), parent.get("title"),
    )


def relaxed_key(item: dict[str, Any]) -> tuple[Any, ...]:
    rect = item.get("rectangle") or {}
    parent = item.get("parent") or {}
    return (
        item.get("process_id"), item.get("control_type"), item.get("title"),
        item.get("automation_id"), item.get("class_name"),
        rect.get("left"), rect.get("top"), rect.get("right"), rect.get("bottom"),
        parent.get("control_type"),
    )


def unmatched(source, comparison_counter, key_function):
    remaining = comparison_counter.copy()
    output = []
    for item in source:
        key = key_function(item)
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            output.append(item)
    return output


def calculate_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_items = before["controls"]
    after_items = after["controls"]

    before_exact = Counter(exact_key(item) for item in before_items)
    after_exact = Counter(exact_key(item) for item in after_items)
    before_relaxed = Counter(relaxed_key(item) for item in before_items)
    after_relaxed = Counter(relaxed_key(item) for item in after_items)

    exact_added = unmatched(after_items, before_exact, exact_key)
    exact_removed = unmatched(before_items, after_exact, exact_key)
    relaxed_added = unmatched(after_items, before_relaxed, relaxed_key)
    relaxed_removed = unmatched(before_items, after_relaxed, relaxed_key)

    likely = [
        item for item in relaxed_added
        if item.get("control_type") in LIKELY_MENU_TYPES
        or item.get("title", "").strip()
    ]
    likely.sort(key=lambda item: (
        (item.get("rectangle") or {}).get("left", 999999),
        (item.get("rectangle") or {}).get("top", 999999),
        item.get("control_type", ""),
        item.get("title", ""),
    ))

    return {
        "before_label": before["label"],
        "after_label": after["label"],
        "before_count": len(before_items),
        "after_count": len(after_items),
        "exact_added_count": len(exact_added),
        "exact_removed_count": len(exact_removed),
        "relaxed_added_count": len(relaxed_added),
        "relaxed_removed_count": len(relaxed_removed),
        "exact_added": exact_added,
        "exact_removed": exact_removed,
        "relaxed_added": relaxed_added,
        "relaxed_removed": relaxed_removed,
        "likely_menu_additions": likely,
    }


def compact_line(item: dict[str, Any]) -> str:
    parent = item.get("parent") or {}
    return (
        f"seq={item.get('sequence'):04d} | title={item.get('title')!r} | "
        f"type={item.get('control_type')!r} | class={item.get('class_name')!r} | "
        f"auto_id={item.get('automation_id')!r} | rect={item.get('rectangle')} | "
        f"visible={item.get('visible')} | enabled={item.get('enabled')} | "
        f"source={item.get('source')!r} | parent_type={parent.get('control_type')!r} | "
        f"parent_title={parent.get('title')!r}"
    )


def write_json(data: Any, path: Path) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_diff_text(diff: dict[str, Any], path: Path) -> None:
    lines = [
        "=" * 120,
        f"UIA DIFFERENCE: {diff['before_label']} -> {diff['after_label']}",
        "=" * 120,
        "",
        f"Before controls: {diff['before_count']}",
        f"After controls:  {diff['after_count']}",
        f"Exact additions/removals: {diff['exact_added_count']} / {diff['exact_removed_count']}",
        f"Relaxed additions/removals: {diff['relaxed_added_count']} / {diff['relaxed_removed_count']}",
        "",
        "LIKELY MENU ADDITIONS",
        "-" * 120,
    ]
    lines.extend(compact_line(item) for item in diff["likely_menu_additions"])
    if not diff["likely_menu_additions"]:
        lines.append("No likely menu additions detected.")

    lines.extend(["", "ALL RELAXED ADDITIONS", "-" * 120])
    lines.extend(compact_line(item) for item in diff["relaxed_added"])
    if not diff["relaxed_added"]:
        lines.append("No relaxed additions detected.")

    lines.extend(["", "ALL RELAXED REMOVALS", "-" * 120])
    lines.extend(compact_line(item) for item in diff["relaxed_removed"])
    if not diff["relaxed_removed"]:
        lines.append("No relaxed removals detected.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_visible_controls(snapshot: dict[str, Any], path: Path) -> None:
    controls = sorted(snapshot["controls"], key=lambda item: (
        (item.get("rectangle") or {}).get("top", 999999),
        (item.get("rectangle") or {}).get("left", 999999),
        item.get("control_type", ""),
        item.get("title", ""),
    ))
    lines = ["=" * 120, f"VISIBLE CONTROLS: {snapshot['label']}", "=" * 120, ""]
    lines.extend(compact_line(item) for item in controls)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def choose_hover_record(diff: dict[str, Any]) -> dict[str, Any] | None:
    candidates = []
    priority = {"MenuItem": 0, "ListItem": 1, "Button": 2, "Custom": 3, "Text": 4, "Pane": 5}

    for item in diff["likely_menu_additions"]:
        rect = item.get("rectangle") or {}
        if rect.get("width", 0) >= 20 and rect.get("height", 0) >= 12:
            candidates.append(item)

    if not candidates:
        return None

    candidates.sort(key=lambda item: (
        priority.get(item.get("control_type"), 99),
        0 if item.get("title", "").strip() else 1,
        (item.get("rectangle") or {}).get("top", 999999),
        (item.get("rectangle") or {}).get("left", 999999),
    ))
    return candidates[0]


def find_live_match(desktop, main_window, leap_pid, all_processes, record):
    target = relaxed_key(record)
    for item, source in collect_wrappers(desktop, main_window, leap_pid, all_processes):
        if relaxed_key(describe(item, 0, source)) == target:
            return item
    return None


def perform_after_action(action, desktop, main_window, leap_pid, all_processes, diff):
    result = {"action": action, "performed": False, "target": None, "error": None}
    try:
        if action == "down":
            send_keys("{DOWN}")
            result["performed"] = True
        elif action == "right":
            send_keys("{RIGHT}")
            result["performed"] = True
        elif action == "hover":
            record = choose_hover_record(diff)
            if record is None:
                raise RuntimeError("No suitable newly appeared control was available for hovering.")
            live = find_live_match(desktop, main_window, leap_pid, all_processes, record)
            if live is None:
                raise RuntimeError("The selected hover target could not be re-resolved.")
            rect = live.rectangle()
            live.move_mouse_input(coords=(max(1, rect.width() // 2), max(1, rect.height() // 2)))
            result["performed"] = True
            result["target"] = record
        sleep(SETTLE_AFTER_ACTION)
    except Exception as exc:
        result["error"] = repr(exc)
    return result


def close_menus() -> None:
    for _ in range(4):
        send_keys("{ESC}")
        sleep(0.15)


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text("", encoding="utf-8")

    log("=" * 120)
    log("Starting Milestone 5b Analysis Design UIA difference mapper...")
    log("=" * 120)

    desktop = Desktop(backend="uia")
    main_window = find_main_window(desktop)
    leap_pid = process_id(main_window)
    reports_toolbar = find_reports_toolbar(main_window)
    command = find_analysis_design(main_window, reports_toolbar)

    log(f"Connected to LEAP window: {text(main_window)!r}")
    log(f"LEAP process ID: {leap_pid}")
    log(
        f"Analysis Design command: title={text(command)!r}, "
        f"type={control_type(command)!r}, rect={command.rectangle()}"
    )

    before = take_snapshot(
        desktop, main_window, leap_pid, args.all_processes,
        args.include_invisible, "before_click"
    )
    before_file = OUTPUT_DIR / "snapshot_00_before.json"
    write_json(before, before_file)
    log(f"Before-click snapshot: {before['captured_control_count']} controls")

    main_window.set_focus()
    sleep(0.4)
    main_window = find_main_window(desktop)
    reports_toolbar = find_reports_toolbar(main_window)
    command = find_analysis_design(main_window, reports_toolbar)

    log("Clicking Analysis Design SplitButton...")
    command.click_input()
    sleep(SETTLE_AFTER_CLICK)

    after_click = take_snapshot(
        desktop, main_window, leap_pid, args.all_processes,
        args.include_invisible, "after_click"
    )
    after_file = OUTPUT_DIR / "snapshot_01_after_click.json"
    write_json(after_click, after_file)

    diff1 = calculate_diff(before, after_click)
    diff1_json = OUTPUT_DIR / "diff_00_to_01.json"
    diff1_txt = OUTPUT_DIR / "diff_00_to_01.txt"
    visible_file = OUTPUT_DIR / "visible_controls_after_click.txt"
    write_json(diff1, diff1_json)
    write_diff_text(diff1, diff1_txt)
    write_visible_controls(after_click, visible_file)

    log(f"After-click snapshot: {after_click['captured_control_count']} controls")
    log(f"Relaxed additions: {diff1['relaxed_added_count']}")
    log(f"Likely menu additions: {len(diff1['likely_menu_additions'])}")
    for item in diff1["likely_menu_additions"]:
        log(
            f"  NEW: title={item['title']!r}, type={item['control_type']!r}, "
            f"class={item['class_name']!r}, rect={item['rectangle']}"
        )

    if args.pause_after_click:
        input("\nInspect the open menu. Press Enter to continue...")

    action_result = None
    after_action = None
    diff2 = None

    if args.after_action != "none":
        log("")
        log(f"Performing after-action: {args.after_action!r}")
        action_result = perform_after_action(
            args.after_action, desktop, main_window, leap_pid,
            args.all_processes, diff1
        )
        log(f"After-action performed: {action_result['performed']}")
        if action_result["error"]:
            log(f"After-action error: {action_result['error']}")

        after_action = take_snapshot(
            desktop, main_window, leap_pid, args.all_processes,
            args.include_invisible, f"after_action_{args.after_action}"
        )
        write_json(after_action, OUTPUT_DIR / "snapshot_02_after_action.json")
        diff2 = calculate_diff(after_click, after_action)
        write_json(diff2, OUTPUT_DIR / "diff_01_to_02.json")
        write_diff_text(diff2, OUTPUT_DIR / "diff_01_to_02.txt")
        log(f"Second-stage likely additions: {len(diff2['likely_menu_additions'])}")

    if not args.leave_open:
        close_menus()

    summary = {
        "leap_window": describe(main_window, 0, "summary"),
        "reports_toolbar": describe(reports_toolbar, 0, "summary"),
        "analysis_design_command": describe(command, 0, "summary"),
        "settings": vars(args),
        "diff_00_to_01": diff1,
        "after_action": action_result,
        "diff_01_to_02": diff2,
        "output_files": {
            "snapshot_before": str(before_file),
            "snapshot_after_click": str(after_file),
            "diff_before_to_after_json": str(diff1_json),
            "diff_before_to_after_text": str(diff1_txt),
            "visible_controls_after_click": str(visible_file),
            "summary_json": str(OUTPUT_DIR / "mapper_summary.json"),
            "summary_text": str(OUTPUT_DIR / "mapper_summary.txt"),
        },
    }

    write_json(summary, OUTPUT_DIR / "mapper_summary.json")

    summary_lines = [
        "=" * 120,
        "LEAP ANALYSIS DESIGN UIA DIFFERENCE MAPPER",
        "=" * 120,
        "",
        f"LEAP window: {summary['leap_window']['title']!r}",
        f"Analysis Design type: {summary['analysis_design_command']['control_type']!r}",
        f"Controls before/after: {diff1['before_count']} / {diff1['after_count']}",
        f"Relaxed additions: {diff1['relaxed_added_count']}",
        f"Likely menu additions: {len(diff1['likely_menu_additions'])}",
        "",
        "LIKELY MENU ADDITIONS",
        "-" * 120,
    ]
    summary_lines.extend(compact_line(item) for item in diff1["likely_menu_additions"])
    if not diff1["likely_menu_additions"]:
        summary_lines.append("No likely menu additions detected.")
    if action_result is not None:
        summary_lines.extend([
            "", "AFTER ACTION", "-" * 120,
            json.dumps(action_result, indent=2, ensure_ascii=False),
        ])
    if diff2 is not None:
        summary_lines.extend([
            "", "SECOND DIFF", "-" * 120,
            f"Relaxed additions: {diff2['relaxed_added_count']}",
            f"Likely menu additions: {len(diff2['likely_menu_additions'])}",
        ])
        summary_lines.extend(compact_line(item) for item in diff2["likely_menu_additions"])

    (OUTPUT_DIR / "mapper_summary.txt").write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )

    log("")
    log(f"Summary JSON: {OUTPUT_DIR / 'mapper_summary.json'}")
    log(f"Summary text: {OUTPUT_DIR / 'mapper_summary.txt'}")
    log("=" * 120)
    log("Milestone 5b mapping completed.")
    log("=" * 120)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("")
        log("SCRIPT FAILED:")
        log(traceback.format_exc())
    input("Press Enter to close this script...")
