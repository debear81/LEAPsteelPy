"""
Milestone 5a: Map the nested Analysis / Design report menus in
LEAP Bridge Steel.

PURPOSE
-------
The Analysis Design ribbon command does not directly open a Preview window.
Instead, it opens a popup menu containing first-level choices such as:

    Analysis >
    Design   >

Those items may open additional flyout menus.

This script investigates and documents those popup menus. It is intended to
answer questions such as:

- How is the Analysis Design ribbon command exposed through UI Automation?
- What top-level popup menu appears after the ribbon command is clicked?
- Which MenuItem controls are present?
- Which items have child flyout menus?
- What second-level items appear under Analysis and Design?
- Which titles, automation IDs, class names, and rectangles are stable?
- Does selecting a final menu item open a Preview window?

DEFAULT BEHAVIOR
----------------
The script:

1. Connects to the open LEAP Bridge Steel .lbsx model window.
2. Finds the Reports toolbar.
3. Finds the Analysis Design ribbon command.
4. Clicks the command to open its popup menu.
5. Maps the visible popup menu controls.
6. Expands each first-level item that appears to have a submenu.
7. Maps each resulting flyout menu.
8. Optionally clicks one terminal menu path and observes whether a Preview
   window opens.
9. Writes:
   - a complete desktop/window control-tree snapshot at each stage
   - a compact JSON summary
   - a readable text summary
   - a log file

The mapper does not submit reports, print, save PDFs, or modify the LEAP model.

OUTPUT
------
    <project root>\output\report_maps\analysis_design_menus\

Typical files:

    menu_map_summary.json
    menu_map_summary.txt
    stage_00_before_click.txt
    stage_01_root_menu.txt
    stage_02_analysis_flyout.txt
    stage_03_design_flyout.txt

EXAMPLE USAGE
-------------
Map the menus only:

    python .\src\mapper_report_MenuAnalDes.py

Keep menus open for manual inspection after each stage:

    python .\src\mapper_report_MenuAnalDes.py --pause-each

Try selecting a final menu path after mapping:

    python .\src\mapper_report_MenuAnalDes.py --test-path Analysis "Dead Load"

Try selecting a Design path:

    python .\src\mapper_report_MenuAnalDes.py --test-path Design "Strength I"

Leave the final Preview or menu open:

    python .\src\mapper_report_MenuAnalDes.py --leave-open

NOTES
-----
- LEAP popup menus may be top-level Menu windows, Pane windows, or custom
  WinForms controls.
- Some menu wrappers may disappear and be recreated while navigating.
- Therefore, this script repeatedly re-scans the desktop instead of relying on
  cached wrappers.
- Popup menus are identified primarily by visibility, geometry, process ID,
  and MenuItem descendants rather than by a single fixed class name.
"""

from __future__ import annotations

import argparse
import json
import re
import traceback
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Iterable

from pywinauto import Desktop
from pywinauto.keyboard import send_keys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
#OUTPUT_DIR = PROJECT_ROOT / "mapper" / "report_maps" / "analysis_design_menus"
OUTPUT_DIR = PROJECT_ROOT / "report_maps" / "analysis_design_menus"
LOG_FILE = OUTPUT_DIR / "mapper_report_analysis_design_menus.log"

LEAP_WINDOW_TITLE_PATTERN = r".*\.lbsx - LEAP Bridge Steel.*"

OPEN_MENU_TIMEOUT = 10.0
FLYOUT_TIMEOUT = 8.0
PREVIEW_TIMEOUT = 20.0
POLL_INTERVAL = 0.20
SETTLE_SECONDS = 0.70

REPORT_TITLE_ALIASES = {
    "analysis design",
    "analysis / design",
    "analysis/design",
    "analysis & design",
}

MENU_CONTAINER_CONTROL_TYPES = {
    "Menu",
    "Pane",
    "Window",
    "Custom",
    "ToolBar",
}

INTERESTING_TYPES = {
    "Menu",
    "MenuItem",
    "Pane",
    "Window",
    "Custom",
    "Button",
    "SplitButton",
    "Text",
    "List",
    "ListItem",
}


def log(message: str = "") -> None:
    """Write a line to both the console and the log file."""
    print(message, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def safe_call(function, default=None):
    try:
        return function()
    except Exception:
        return default


def safe_text(control) -> str:
    return safe_call(control.window_text, "") or ""


def get_control_type(control) -> str:
    return getattr(control.element_info, "control_type", None) or ""


def get_class_name(control) -> str:
    return (
        getattr(control.element_info, "class_name", None)
        or safe_call(control.class_name, "")
        or ""
    )


def get_auto_id(control) -> str:
    return getattr(control.element_info, "automation_id", None) or ""


def get_process_id(control) -> int | None:
    return getattr(control.element_info, "process_id", None)


def get_handle(control) -> int | None:
    return safe_call(lambda: control.handle, None)


def rectangle_to_dict(control) -> dict[str, int] | None:
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


def rectangle_area(control) -> int:
    rect = safe_call(control.rectangle, None)

    if rect is None:
        return 0

    return max(0, rect.width()) * max(0, rect.height())


def describe_control(control, index: int | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
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

    if index is not None:
        data["index"] = index

    return data


def normalize_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def title_matches_analysis_design(value: str) -> bool:
    normalized = normalize_title(value)

    return any(
        normalize_title(alias) == normalized
        for alias in REPORT_TITLE_ALIASES
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Map the nested Analysis / Design report menus in "
            "LEAP Bridge Steel."
        )
    )

    parser.add_argument(
        "--pause-each",
        action="store_true",
        help=(
            "Pause after each mapped menu stage for manual inspection."
        ),
    )

    parser.add_argument(
        "--test-path",
        nargs="+",
        metavar="MENU_ITEM",
        help=(
            "After mapping, attempt to select the supplied menu path. "
            'Example: --test-path Analysis "Dead Load"'
        ),
    )

    parser.add_argument(
        "--leave-open",
        action="store_true",
        help=(
            "Leave the final menu or Preview window open."
        ),
    )

    parser.add_argument(
        "--no-hover",
        action="store_true",
        help=(
            "Do not use mouse hover while expanding first-level menu items."
        ),
    )

    return parser.parse_args()


def find_main_leap_window(desktop):
    matches = desktop.windows(
        title_re=LEAP_WINDOW_TITLE_PATTERN,
        control_type="Window",
        visible_only=True,
    )

    if matches:
        matches.sort(key=rectangle_area, reverse=True)
        return matches[0]

    candidates = []

    for window in desktop.windows(
        control_type="Window",
        visible_only=True,
    ):
        try:
            reports = window.descendants(
                title="Reports",
                control_type="ToolBar",
            )

            analysis_commands = [
                control
                for control in window.descendants()
                if title_matches_analysis_design(safe_text(control))
            ]

            if reports and analysis_commands:
                candidates.append(window)

        except Exception:
            continue

    if not candidates:
        raise RuntimeError(
            "Could not find an open LEAP Bridge Steel model window. "
            "Open a .lbsx model before running this script."
        )

    candidates.sort(key=rectangle_area, reverse=True)
    return candidates[0]


def find_reports_toolbar(main_window):
    toolbars = [
        toolbar
        for toolbar in main_window.descendants(
            title="Reports",
            control_type="ToolBar",
        )
        if safe_call(toolbar.is_visible, False)
    ]

    if not toolbars:
        raise RuntimeError(
            "The LEAP window was found, but the Reports toolbar was not found."
        )

    toolbars.sort(key=rectangle_area, reverse=True)
    return toolbars[0]


def find_analysis_design_command(main_window, reports_toolbar):
    candidates = []

    for root in (reports_toolbar, main_window):
        for control in safe_call(root.descendants, []):
            try:
                if not safe_call(control.is_visible, False):
                    continue

                if not safe_call(control.is_enabled, False):
                    continue

                title = safe_text(control).strip()

                if title_matches_analysis_design(title):
                    candidates.append(control)

            except Exception:
                continue

    if not candidates:
        raise RuntimeError(
            "Could not find the Analysis Design ribbon command."
        )

    priority = {
        "SplitButton": 0,
        "Button": 1,
        "MenuItem": 2,
        "Custom": 3,
        "Pane": 4,
    }

    candidates.sort(
        key=lambda control: (
            priority.get(get_control_type(control), 99),
            -rectangle_area(control),
        )
    )

    return candidates[0]


def visible_top_level_windows(desktop) -> list[Any]:
    return desktop.windows(visible_only=True)


def snapshot_window_keys(desktop) -> set[tuple[Any, ...]]:
    keys = set()

    for window in visible_top_level_windows(desktop):
        rect = safe_call(window.rectangle, None)

        if rect is None:
            continue

        keys.add(
            (
                get_handle(window),
                safe_text(window),
                get_control_type(window),
                get_class_name(window),
                rect.left,
                rect.top,
                rect.right,
                rect.bottom,
            )
        )

    return keys


def control_key(control) -> tuple[Any, ...]:
    rect = safe_call(control.rectangle, None)

    if rect is None:
        return (
            get_handle(control),
            safe_text(control),
            get_control_type(control),
            get_class_name(control),
        )

    return (
        get_handle(control),
        safe_text(control),
        get_control_type(control),
        get_class_name(control),
        rect.left,
        rect.top,
        rect.right,
        rect.bottom,
    )


def is_plausible_popup_container(control, leap_pid: int) -> bool:
    if not safe_call(control.is_visible, False):
        return False

    if get_process_id(control) not in {None, leap_pid}:
        return False

    rect = safe_call(control.rectangle, None)

    if rect is None or rect.width() <= 0 or rect.height() <= 0:
        return False

    control_type = get_control_type(control)

    if control_type not in MENU_CONTAINER_CONTROL_TYPES:
        return False

    menu_items = safe_call(
        lambda: control.descendants(control_type="MenuItem"),
        [],
    )

    if menu_items:
        return True

    # Some WinForms popup menus expose selectable entries as Text or Custom.
    interesting_children = [
        child
        for child in safe_call(control.descendants, [])
        if get_control_type(child) in {"Text", "Custom", "ListItem"}
        and safe_text(child).strip()
        and safe_call(child.is_visible, False)
    ]

    return len(interesting_children) >= 2


def find_popup_containers(desktop, leap_pid: int) -> list[Any]:
    candidates = []

    for window in visible_top_level_windows(desktop):
        try:
            if is_plausible_popup_container(window, leap_pid):
                candidates.append(window)
        except Exception:
            continue

    # Include desktop descendants because some popup menus are not returned as
    # conventional top-level windows.
    for control in safe_call(desktop.descendants, []):
        try:
            if is_plausible_popup_container(control, leap_pid):
                candidates.append(control)
        except Exception:
            continue

    unique = {}

    for candidate in candidates:
        key = control_key(candidate)
        existing = unique.get(key)

        if existing is None or rectangle_area(candidate) > rectangle_area(existing):
            unique[key] = candidate

    result = list(unique.values())
    result.sort(
        key=lambda control: (
            safe_call(control.rectangle, None).left,
            safe_call(control.rectangle, None).top,
        )
    )

    return result


def wait_for_popup_growth(
    desktop,
    leap_pid: int,
    previous_keys: set[tuple[Any, ...]],
    timeout: float,
) -> list[Any]:
    deadline = monotonic() + timeout
    last = []

    while monotonic() < deadline:
        current = find_popup_containers(desktop, leap_pid)
        last = current
        current_keys = {control_key(item) for item in current}

        if current and current_keys != previous_keys:
            return current

        sleep(POLL_INTERVAL)

    return last


def visible_preview_windows(desktop) -> list[Any]:
    previews = desktop.windows(
        title="Preview",
        control_type="Window",
        visible_only=True,
    )
    previews.sort(key=rectangle_area, reverse=True)
    return previews


def wait_for_preview_or_menu_change(
    desktop,
    leap_pid: int,
    old_preview_handles: set[int],
    old_popup_keys: set[tuple[Any, ...]],
    timeout: float,
) -> tuple[str, Any]:
    deadline = monotonic() + timeout

    while monotonic() < deadline:
        previews = visible_preview_windows(desktop)

        for preview in previews:
            handle = get_handle(preview)

            if handle not in old_preview_handles:
                return "preview", preview

        popups = find_popup_containers(desktop, leap_pid)
        popup_keys = {control_key(item) for item in popups}

        if popup_keys != old_popup_keys:
            return "menu_change", popups

        sleep(POLL_INTERVAL)

    return "timeout", None


def gather_menu_entries(container) -> list[Any]:
    entries = []

    for control_type in ("MenuItem", "ListItem"):
        for control in safe_call(
            lambda: container.descendants(control_type=control_type),
            [],
        ):
            try:
                if (
                    safe_call(control.is_visible, False)
                    and safe_text(control).strip()
                ):
                    entries.append(control)
            except Exception:
                continue

    if not entries:
        for control in safe_call(container.descendants, []):
            try:
                if (
                    get_control_type(control) in {"Text", "Custom"}
                    and safe_call(control.is_visible, False)
                    and safe_call(control.is_enabled, True)
                    and safe_text(control).strip()
                ):
                    entries.append(control)
            except Exception:
                continue

    unique = {}

    for entry in entries:
        key = control_key(entry)

        if key not in unique:
            unique[key] = entry

    result = list(unique.values())
    result.sort(
        key=lambda control: (
            control.rectangle().top,
            control.rectangle().left,
        )
    )
    return result


def describe_menu_container(container) -> dict[str, Any]:
    entries = gather_menu_entries(container)

    return {
        "container": describe_control(container),
        "entries": [
            describe_control(entry, index=index)
            for index, entry in enumerate(entries, start=1)
        ],
    }


def write_desktop_tree(destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as file:
        file.write("=" * 100 + "\n")
        file.write("VISIBLE TOP-LEVEL WINDOWS\n")
        file.write("=" * 100 + "\n\n")

        desktop = Desktop(backend="uia")

        for index, window in enumerate(
            desktop.windows(visible_only=True),
            start=1,
        ):
            file.write(f"\n{'#' * 100}\n")
            file.write(f"WINDOW {index}: {describe_control(window)!r}\n")
            file.write(f"{'#' * 100}\n")

            try:
                window.print_control_identifiers(filename=file)
            except TypeError:
                # pywinauto versions differ: some require a path rather than
                # a writable file object.
                temp = destination.with_name(
                    destination.stem + f"_window_{index}.txt"
                )
                window.print_control_identifiers(filename=str(temp))
                file.write(
                    f"Control tree written separately to: {temp}\n"
                )
            except Exception as exc:
                file.write(f"Could not print control tree: {exc!r}\n")


def pause_if_requested(enabled: bool, message: str) -> None:
    if enabled:
        input(message)


def close_all_popups() -> None:
    # Escape several times because nested flyouts may need more than one key.
    for _ in range(4):
        send_keys("{ESC}")
        sleep(0.20)


def choose_entry_by_title(
    containers: Iterable[Any],
    requested_title: str,
):
    normalized = normalize_title(requested_title)
    matches = []

    for container in containers:
        for entry in gather_menu_entries(container):
            title = safe_text(entry).strip()

            if normalize_title(title) == normalized:
                matches.append(entry)

    if not matches:
        available = sorted(
            {
                safe_text(entry).strip()
                for container in containers
                for entry in gather_menu_entries(container)
                if safe_text(entry).strip()
            }
        )

        raise RuntimeError(
            f"Menu item {requested_title!r} was not found. "
            f"Available visible items: {available!r}"
        )

    # Prefer the rightmost entry when duplicate titles occur in nested menus.
    matches.sort(
        key=lambda control: (
            control.rectangle().left,
            control.rectangle().top,
        ),
        reverse=True,
    )

    return matches[0]


def expand_entry(
    entry,
    desktop,
    leap_pid: int,
    use_hover: bool,
) -> tuple[list[Any], str]:
    previous = find_popup_containers(desktop, leap_pid)
    previous_keys = {control_key(item) for item in previous}

    methods = []

    if use_hover:
        methods.append("hover")

    methods.extend(["expand", "click"])

    last_error = None

    for method in methods:
        try:
            if method == "hover":
                rect = entry.rectangle()
                entry.move_mouse_input(
                    coords=(max(1, rect.width() // 2), max(1, rect.height() // 2))
                )

            elif method == "expand":
                entry.expand()

            elif method == "click":
                entry.click_input()

            sleep(SETTLE_SECONDS)

            current = find_popup_containers(desktop, leap_pid)
            current_keys = {control_key(item) for item in current}

            if current_keys != previous_keys or len(current) > len(previous):
                return current, method

        except Exception as exc:
            last_error = repr(exc)

    raise RuntimeError(
        f"Could not expand menu item {safe_text(entry)!r}. "
        f"Last error: {last_error}"
    )


def map_first_level_item(
    desktop,
    leap_pid: int,
    item_title: str,
    stage_number: int,
    pause_each: bool,
    use_hover: bool,
) -> dict[str, Any]:
    root_containers = find_popup_containers(desktop, leap_pid)
    entry = choose_entry_by_title(root_containers, item_title)

    log("")
    log(f"Expanding first-level menu item: {item_title!r}")

    result: dict[str, Any] = {
        "item_title": item_title,
        "entry_before_expansion": describe_control(entry),
        "expansion_method": None,
        "error": None,
        "visible_popup_containers_after": [],
    }

    try:
        containers_after, method = expand_entry(
            entry=entry,
            desktop=desktop,
            leap_pid=leap_pid,
            use_hover=use_hover,
        )

        result["expansion_method"] = method
        result["visible_popup_containers_after"] = [
            describe_menu_container(container)
            for container in containers_after
        ]

        stage_file = OUTPUT_DIR / (
            f"stage_{stage_number:02d}_{normalize_title(item_title)}_flyout.txt"
        )
        write_desktop_tree(stage_file)
        result["stage_file"] = str(stage_file)

        log(f"Expanded with method: {method}")
        log(f"Stage tree written to: {stage_file}")

        pause_if_requested(
            pause_each,
            f"\nInspect the {item_title!r} flyout. Press Enter to continue...",
        )

    except Exception as exc:
        result["error"] = repr(exc)
        log(f"Expansion failed: {exc!r}")

    return result


def reopen_root_menu(
    desktop,
    main_window,
    reports_toolbar,
    command,
    leap_pid: int,
) -> list[Any]:
    close_all_popups()
    main_window.set_focus()
    sleep(0.40)

    # Re-resolve because prior popup interaction may invalidate the wrapper.
    main_window = find_main_leap_window(desktop)
    reports_toolbar = find_reports_toolbar(main_window)
    command = find_analysis_design_command(main_window, reports_toolbar)

    before = {control_key(item) for item in find_popup_containers(desktop, leap_pid)}
    command.click_input()
    sleep(SETTLE_SECONDS)

    containers = wait_for_popup_growth(
        desktop=desktop,
        leap_pid=leap_pid,
        previous_keys=before,
        timeout=OPEN_MENU_TIMEOUT,
    )

    if not containers:
        raise RuntimeError(
            "Analysis Design was clicked, but no popup menu was detected."
        )

    return containers


def test_menu_path(
    desktop,
    main_window,
    reports_toolbar,
    command,
    leap_pid: int,
    path: list[str],
    leave_open: bool,
) -> dict[str, Any]:
    log("")
    log("=" * 100)
    log(f"Testing menu path: {' > '.join(path)}")
    log("=" * 100)

    result: dict[str, Any] = {
        "path": path,
        "steps": [],
        "result": None,
        "preview": None,
        "error": None,
    }

    try:
        containers = reopen_root_menu(
            desktop,
            main_window,
            reports_toolbar,
            command,
            leap_pid,
        )

        for index, title in enumerate(path, start=1):
            entry = choose_entry_by_title(containers, title)
            is_last = index == len(path)

            step = {
                "index": index,
                "title": title,
                "entry": describe_control(entry),
                "action": None,
            }

            if not is_last:
                containers, method = expand_entry(
                    entry=entry,
                    desktop=desktop,
                    leap_pid=leap_pid,
                    use_hover=True,
                )
                step["action"] = f"expanded via {method}"
                result["steps"].append(step)
                continue

            old_preview_handles = {
                get_handle(preview)
                for preview in visible_preview_windows(desktop)
                if get_handle(preview) is not None
            }
            old_popup_keys = {
                control_key(item)
                for item in find_popup_containers(desktop, leap_pid)
            }

            entry.click_input()
            step["action"] = "clicked"
            result["steps"].append(step)

            outcome, payload = wait_for_preview_or_menu_change(
                desktop=desktop,
                leap_pid=leap_pid,
                old_preview_handles=old_preview_handles,
                old_popup_keys=old_popup_keys,
                timeout=PREVIEW_TIMEOUT,
            )

            result["result"] = outcome

            if outcome == "preview":
                result["preview"] = describe_control(payload)
                log(
                    "Preview opened: "
                    f"title={safe_text(payload)!r}, "
                    f"handle={get_handle(payload)}"
                )

                preview_file = OUTPUT_DIR / "stage_test_path_preview.txt"
                try:
                    payload.print_control_identifiers(
                        filename=str(preview_file)
                    )
                    result["preview_tree_file"] = str(preview_file)
                except Exception as exc:
                    result["preview_tree_error"] = repr(exc)

                if not leave_open:
                    try:
                        payload.close()
                    except Exception:
                        payload.set_focus()
                        send_keys("%{F4}")

            elif outcome == "menu_change":
                result["visible_popup_containers_after"] = [
                    describe_menu_container(container)
                    for container in payload
                ]
                log("Final click changed the visible popup-menu set.")

            else:
                log(
                    "No Preview or detectable popup-menu change occurred "
                    "before the timeout."
                )

        if not leave_open:
            close_all_popups()

    except Exception as exc:
        result["error"] = repr(exc)
        log(f"Test path failed: {exc!r}")

        if not leave_open:
            close_all_popups()

    return result


def write_text_summary(
    destination: Path,
    summary: dict[str, Any],
) -> None:
    lines = []

    lines.append("=" * 100)
    lines.append("LEAP ANALYSIS / DESIGN MENU MAP")
    lines.append("=" * 100)
    lines.append("")

    lines.append("LEAP WINDOW")
    lines.append("-" * 100)
    lines.append(json.dumps(summary["leap_window"], indent=2))
    lines.append("")

    lines.append("ANALYSIS DESIGN COMMAND")
    lines.append("-" * 100)
    lines.append(json.dumps(summary["analysis_design_command"], indent=2))
    lines.append("")

    lines.append("ROOT POPUP CONTAINERS")
    lines.append("-" * 100)

    for index, container in enumerate(
        summary["root_popup_containers"],
        start=1,
    ):
        lines.append(f"Container {index}")
        lines.append(json.dumps(container["container"], indent=2))
        lines.append("Entries:")

        for entry in container["entries"]:
            lines.append(
                f"  {entry['index']:02d}. "
                f"title={entry['title']!r}, "
                f"type={entry['control_type']!r}, "
                f"auto_id={entry['automation_id']!r}, "
                f"class={entry['class_name']!r}, "
                f"rect={entry['rectangle']}"
            )

        lines.append("")

    lines.append("FIRST-LEVEL FLYOUT RESULTS")
    lines.append("-" * 100)

    for result in summary["first_level_results"]:
        lines.append(f"Item: {result['item_title']!r}")
        lines.append(
            f"Expansion method: {result['expansion_method']!r}"
        )
        lines.append(f"Error: {result['error']!r}")

        for container_index, container in enumerate(
            result["visible_popup_containers_after"],
            start=1,
        ):
            lines.append(f"  Popup container {container_index}:")

            for entry in container["entries"]:
                lines.append(
                    f"    - {entry['title']!r} "
                    f"[{entry['control_type']}] "
                    f"rect={entry['rectangle']}"
                )

        lines.append("")

    if summary.get("test_path_result") is not None:
        lines.append("TEST PATH RESULT")
        lines.append("-" * 100)
        lines.append(
            json.dumps(
                summary["test_path_result"],
                indent=2,
                ensure_ascii=False,
            )
        )
        lines.append("")

    destination.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    args = parse_arguments()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Start a fresh log for each run.
    LOG_FILE.write_text("", encoding="utf-8")

    log("=" * 100)
    log("Starting Milestone 5a Analysis / Design menu mapper...")
    log("=" * 100)

    desktop = Desktop(backend="uia")
    main_window = find_main_leap_window(desktop)
    leap_pid = get_process_id(main_window)

    log(f"Connected to LEAP window: {safe_text(main_window)!r}")
    log(f"LEAP process ID: {leap_pid}")

    reports_toolbar = find_reports_toolbar(main_window)
    command = find_analysis_design_command(
        main_window,
        reports_toolbar,
    )

    log(
        "Analysis Design command found: "
        f"title={safe_text(command)!r}, "
        f"type={get_control_type(command)!r}, "
        f"class={get_class_name(command)!r}, "
        f"rect={command.rectangle()}"
    )

    before_file = OUTPUT_DIR / "stage_00_before_click.txt"
    write_desktop_tree(before_file)
    log(f"Before-click control tree written to: {before_file}")

    main_window.set_focus()
    sleep(0.50)

    popup_keys_before = {
        control_key(item)
        for item in find_popup_containers(desktop, leap_pid)
    }

    log("Clicking Analysis Design...")
    command.click_input()
    sleep(SETTLE_SECONDS)

    root_containers = wait_for_popup_growth(
        desktop=desktop,
        leap_pid=leap_pid,
        previous_keys=popup_keys_before,
        timeout=OPEN_MENU_TIMEOUT,
    )

    if not root_containers:
        stage_file = OUTPUT_DIR / "stage_01_no_menu_detected.txt"
        write_desktop_tree(stage_file)

        raise RuntimeError(
            "Analysis Design was clicked, but no popup menu container was "
            f"detected. Diagnostic tree: {stage_file}"
        )

    root_file = OUTPUT_DIR / "stage_01_root_menu.txt"
    write_desktop_tree(root_file)

    log(
        f"Detected {len(root_containers)} visible popup container(s)."
    )
    log(f"Root-menu control tree written to: {root_file}")

    root_descriptions = [
        describe_menu_container(container)
        for container in root_containers
    ]

    all_root_titles = [
        entry["title"]
        for container in root_descriptions
        for entry in container["entries"]
    ]

    log(f"Visible root menu entries: {all_root_titles!r}")

    pause_if_requested(
        args.pause_each,
        "\nInspect the root Analysis Design menu. Press Enter to continue...",
    )

    first_level_targets = []

    for preferred_title in ("Analysis", "Design"):
        if any(
            normalize_title(title) == normalize_title(preferred_title)
            for title in all_root_titles
        ):
            first_level_targets.append(preferred_title)

    # If the expected labels were not exposed, still try each root entry so the
    # diagnostics remain useful.
    if not first_level_targets:
        first_level_targets = [
            title
            for title in all_root_titles
            if title.strip()
        ]

    first_level_results = []
    stage_number = 2

    for target in first_level_targets:
        # Reopen the root menu before each independent expansion.
        root_containers = reopen_root_menu(
            desktop,
            main_window,
            reports_toolbar,
            command,
            leap_pid,
        )

        result = map_first_level_item(
            desktop=desktop,
            leap_pid=leap_pid,
            item_title=target,
            stage_number=stage_number,
            pause_each=args.pause_each,
            use_hover=not args.no_hover,
        )

        first_level_results.append(result)
        stage_number += 1

    summary: dict[str, Any] = {
        "leap_window": describe_control(main_window),
        "reports_toolbar": describe_control(reports_toolbar),
        "analysis_design_command": describe_control(command),
        "root_popup_containers": root_descriptions,
        "first_level_results": first_level_results,
        "test_path_result": None,
        "output_files": {
            "before_click_tree": str(before_file),
            "root_menu_tree": str(root_file),
        },
    }

    if args.test_path:
        summary["test_path_result"] = test_menu_path(
            desktop=desktop,
            main_window=main_window,
            reports_toolbar=reports_toolbar,
            command=command,
            leap_pid=leap_pid,
            path=args.test_path,
            leave_open=args.leave_open,
        )

    elif not args.leave_open:
        close_all_popups()

    json_file = OUTPUT_DIR / "menu_map_summary.json"
    text_file = OUTPUT_DIR / "menu_map_summary.txt"

    json_file.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    write_text_summary(
        destination=text_file,
        summary=summary,
    )

    log("")
    log(f"JSON summary written to: {json_file}")
    log(f"Text summary written to: {text_file}")
    log("")
    log("=" * 100)
    log("Milestone 5a menu mapping completed.")
    log("=" * 100)


if __name__ == "__main__":
    try:
        main()

    except Exception:
        log("")
        log("SCRIPT FAILED:")
        log(traceback.format_exc())

    input("Press Enter to close this script...")
