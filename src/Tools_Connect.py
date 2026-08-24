r"""
################################################################################
01_Report_Connect.py
====================

Small, reusable LEAP Bridge Steel connection module.

Purpose
-------
- Connect to the currently open LEAP Bridge Steel model window.
- Locate the Reports toolbar.
- Return both controls in a simple LeapConnection object.
- Perform no report clicking, Preview handling, selection, submission, or printing.

Typical standalone test
-----------------------
Open a .lbsx model in LEAP Bridge Steel, then run:

    py ".\src\Tools_Connect.py"

Typical use from another script
-------------------------------
Because this filename begins with a number, load it by file path with
importlib.util, or rename it later to a conventional module name.

The public entry point is:

    connect_to_leap()

It returns:

    LeapConnection(
        desktop=...,
        main_window=...,
        reports_toolbar=...,
    )
###############################################################################
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pywinauto import Desktop


LEAP_WINDOW_TITLE_PATTERN = r".*\.lbsx - LEAP Bridge Steel.*"

T = TypeVar("T")


@dataclass(frozen=True)
class LeapConnection:
    # Resolved UI Automation controls for the active LEAP model.

    desktop: Desktop
    main_window: Any
    reports_toolbar: Any


def safe_call(
    function: Callable[[], T],
    default: T | None = None,
) -> T | None:
    # Call a no-argument function and return default if it fails.
    try:
        return function()
    except Exception:
        return default


def safe_text(control: Any) -> str:
    # Return a control's displayed text without raising an exception.
    return safe_call(control.window_text, "") or ""


def rectangle_area(control: Any) -> int:
    # Return the control's screen area, or zero if unavailable.
    rect = safe_call(control.rectangle)

    if rect is None:
        return 0

    return max(0, rect.width()) * max(0, rect.height())


def describe_control(control: Any) -> str:
    # Return a compact human-readable control description.
    element_info = getattr(control, "element_info", None)

    control_type = (
        getattr(element_info, "control_type", "")
        if element_info is not None
        else ""
    )

    automation_id = (
        getattr(element_info, "automation_id", "")
        if element_info is not None
        else ""
    )

    class_name = (
        getattr(element_info, "class_name", "")
        if element_info is not None
        else ""
    )

    rectangle = safe_call(control.rectangle, "<unavailable>")

    return (
        f"title={safe_text(control)!r}, "
        f"type={control_type!r}, "
        f"auto_id={automation_id!r}, "
        f"class={class_name!r}, "
        f"rect={rectangle}"
    )


def find_main_leap_window(desktop: Desktop) -> Any:
    # Find the active LEAP Bridge Steel model window.
    # First use the proven .lbsx title pattern. If that fails, inspect visible
    # top-level windows for a Reports toolbar and an Input Data report button.

    matches = desktop.windows(
        title_re=LEAP_WINDOW_TITLE_PATTERN,
        control_type="Window",
        visible_only=True,
    )

    if not matches:
        fallback_matches = []

        for window in desktop.windows(
            control_type="Window",
            visible_only=True,
        ):
            try:
                reports_toolbars = window.descendants(
                    title="Reports",
                    control_type="ToolBar",
                )

                input_buttons = window.descendants(
                    title="Input Data",
                    control_type="Button",
                )

                if reports_toolbars and input_buttons:
                    fallback_matches.append(window)

            except Exception:
                continue

        matches = fallback_matches

    if not matches:
        raise RuntimeError(
            "Could not find an open LEAP Bridge Steel model window.\n"
            "Open LEAP Bridge Steel and load the desired .lbsx model "
            "before running the script."
        )

    # Prefer the largest matching visible window in case LEAP exposes
    # secondary top-level windows with similar titles.
    matches.sort(key=rectangle_area, reverse=True)
    return matches[0]


def find_reports_toolbar(main_window: Any) -> Any:
    # Find the visible Reports toolbar within the LEAP main window.
    toolbars = [
        toolbar
        for toolbar in main_window.descendants(
            title="Reports",
            control_type="ToolBar",
        )
        if safe_call(toolbar.is_visible, False)
        and safe_call(toolbar.is_enabled, False)
    ]

    if not toolbars:
        raise RuntimeError(
            "The LEAP main window was found, but the visible Reports "
            "toolbar was not found."
        )

    toolbars.sort(key=rectangle_area, reverse=True)
    return toolbars[0]


def connect_to_leap(*, focus_main_window: bool = False) -> LeapConnection:
    """ ======================================================================
    Connect to the open LEAP model and resolve its Reports toolbar.

    Parameters
    ----------
    focus_main_window:
        When True, bring the LEAP model window to the foreground after
        connecting. The default is False so this module has minimal UI impact.

    Returns
    -------
    LeapConnection
        A frozen container holding the UIA Desktop, main LEAP window, and
        Reports toolbar.
    ====================================================================== """
    desktop = Desktop(backend="uia")
    main_window = find_main_leap_window(desktop)
    reports_toolbar = find_reports_toolbar(main_window)

    if focus_main_window:
        main_window.set_focus()

    return LeapConnection(
        desktop=desktop,
        main_window=main_window,
        reports_toolbar=reports_toolbar,
    )


def main() -> None:
    # Standalone connection test.
    print("=" * 80)
    print("LEAP REPORT CONNECTION TEST")
    print("=" * 80)

    connection = connect_to_leap(focus_main_window=False)

    print("Connection successful.")
    print()
    print("Main window:")
    print(f"  {describe_control(connection.main_window)}")
    print()
    print("Reports toolbar:")
    print(f"  {describe_control(connection.reports_toolbar)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("CONNECTION FAILED")
        print("-" * 80)
        print(exc)
        raise SystemExit(1) from exc
