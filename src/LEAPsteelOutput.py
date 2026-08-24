r"""
20_Driver_Output.py
===================

Multi-report LEAP automation driver.

Initial test configuration
--------------------------
The report definitions are stored in Reports_List.py.

For the current development stage, Reports_List.py contains three Dead Load
reports:

    1. DL Node Displacements
    2. DL Girder Forces
    3. DL Cross Frame Forces

Workflow
--------
1. Ask the user to select the PDF output folder.
2. Connect to the currently open LEAP Bridge Steel instance.
3. Loop through the configured reports in Reports_List.py.
4. Process only reports whose enabled flag is True.
5. For each enabled report:
       - open the report,
       - if generation_mode == "submit", wait for the user to click Submit
         or close/cancel the report,
       - if generation_mode == "automatic", allow LEAP's automatically
         generated report to finish,
       - export the completed Preview to PDF,
       - close the Preview,
       - continue to the next report.
6. Exit after all enabled reports have been processed.

Typical use
-----------
    py ".\\src\\20_Driver_Output.py"
"""

from __future__ import annotations

import ctypes
import importlib.util
import re
import sys

# pywinauto / COM initialization mode used by the LEAP automation scripts.
sys.coinit_flags = 2

import traceback
from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable, NamedTuple, TypeVar

from pywinauto import Desktop
from pywinauto.keyboard import send_keys

from Reports_List import REPORTS, ReportDefinition
from Tools_Folder import select_folder
from Tools_ExportPDF import export_preview_to_pdf


# =============================================================================
# FILES / SETTINGS
# =============================================================================

SCRIPT_FILE = Path(__file__).resolve()
SCRIPT_DIR = SCRIPT_FILE.parent

# CONNECT_FILE = SCRIPT_DIR / "01_Report_Connect.py"
CONNECT_FILE = SCRIPT_DIR / "Tools_Connect.py"

MENU_SETTLE_SECONDS = 0.65
CONTROL_SETTLE_SECONDS = 0.35
PREVIEW_TIMEOUT = 25.0
POLL_INTERVAL = 0.20
AUTOMATIC_REPORT_SETTLE_SECONDS = 2.5
READY_STABLE_POLLS = 3

# For the multi-report driver, the Preview should normally close after each
# successful PDF export so the next report can be opened cleanly.
CLOSE_PREVIEW_AFTER_EXPORT = True

ANALYSIS_DESIGN_ALIASES = {
    "analysis design",
    "analysis / design",
    "analysis/design",
    "analysis & design",
}

T = TypeVar("T")


# =============================================================================
# GENERAL UTILITIES
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


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def control_type(control: Any) -> str:
    info = getattr(control, "element_info", None)
    return getattr(info, "control_type", "") if info is not None else ""


def rectangle_area(control: Any) -> int:
    rect = safe_call(control.rectangle)

    if rect is None:
        return 0

    return max(0, rect.width()) * max(0, rect.height())


def load_module(module_name: str, file_path: Path) -> Any:
    """Load a Python file by path without requiring it to be a package."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Required module was not found:\n{file_path}")

    existing = sys.modules.get(module_name)

    if existing is not None:
        return existing

    spec = importlib.util.spec_from_file_location(module_name, file_path)

    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module:\n{file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def window_exists(window: Any) -> bool:
    handle = safe_call(lambda: int(window.handle))

    if handle is None:
        return False

    return bool(ctypes.windll.user32.IsWindow(handle))


# =============================================================================
# REPORT OPENING / NAVIGATION
# =============================================================================


def existing_preview_handles() -> set[int]:
    handles: set[int] = set()

    for preview in Desktop(backend="uia").windows(
        title="Preview",
        control_type="Window",
        visible_only=True,
    ):
        handle = safe_call(lambda: int(preview.handle))

        if handle is not None:
            handles.add(handle)

    return handles


class ReportOpenResult(NamedTuple):
    status: str
    preview: Any | None = None
    message: str = ""


def existing_dialog_handles() -> set[int]:
    """Return handles for visible standard Windows dialog boxes."""
    handles: set[int] = set()

    for dialog in Desktop(backend="win32").windows(
        class_name="#32770",
        visible_only=True,
    ):
        handle = safe_call(lambda: int(dialog.handle))

        if handle is not None:
            handles.add(handle)

    return handles


def dialog_message(dialog: Any) -> str:
    """Collect the useful text displayed by a LEAP message dialog."""
    title = safe_text(dialog)
    parts: list[str] = []

    for control in safe_call(dialog.descendants, []) or []:
        text = safe_text(control)

        if not text:
            continue

        if text == title or normalize(text) in {"ok", "cancel", "yes", "no"}:
            continue

        if text not in parts:
            parts.append(text)

    return " ".join(parts).strip() or title


def dismiss_ok_dialog(dialog: Any) -> None:
    """Dismiss a standard informational dialog using its OK button."""
    try:
        ok_button = dialog.child_window(title="OK", class_name="Button")

        if ok_button.exists(timeout=0.2):
            ok_button.click_input()
            sleep(CONTROL_SETTLE_SECONDS)
            return
    except Exception:
        pass

    safe_call(dialog.set_focus)
    send_keys("{ENTER}")
    sleep(CONTROL_SETTLE_SECONDS)


def wait_for_report_open_result(
    before_preview_handles: set[int],
    before_dialog_handles: set[int],
) -> ReportOpenResult:
    """
    Wait for either the report Preview or a new LEAP informational dialog.

    Some report commands are not valid for the current analysis type. LEAP
    reports that condition with a modal message box instead of opening Preview.
    Those dialogs are dismissed here and returned as a normal skip condition.
    """
    deadline = monotonic() + PREVIEW_TIMEOUT

    while monotonic() < deadline:
        previews = Desktop(backend="uia").windows(
            title="Preview",
            control_type="Window",
            visible_only=True,
        )

        new_previews = [
            preview
            for preview in previews
            if safe_call(lambda: int(preview.handle)) not in before_preview_handles
        ]

        if new_previews:
            new_previews.sort(key=rectangle_area, reverse=True)
            return ReportOpenResult("preview", new_previews[0])

        dialogs = Desktop(backend="win32").windows(
            class_name="#32770",
            visible_only=True,
        )

        new_dialogs = [
            dialog
            for dialog in dialogs
            if safe_call(lambda: int(dialog.handle)) not in before_dialog_handles
        ]

        for dialog in new_dialogs:
            title = safe_text(dialog)
            message = dialog_message(dialog)
            combined = f"{title} {message}".casefold()

            # Restrict automatic dismissal to dialogs that look like LEAP
            # messages. This avoids accidentally accepting an unrelated dialog.
            if "leap bridge steel" not in combined:
                continue

            if not any(
                normalize(safe_text(control)) == "ok"
                for control in safe_call(dialog.descendants, []) or []
            ):
                continue

            print()
            print("LEAP message:")
            print(f"  {message}")

            dismiss_ok_dialog(dialog)
            print("Dialog dismissed.")

            return ReportOpenResult("message", None, message)

        sleep(POLL_INTERVAL)

    raise RuntimeError(
        "Timed out waiting for either the LEAP Preview window "
        "or a LEAP message dialog."
    )


def find_analysis_design_command(connection: Any) -> Any:
    alias_keys = {normalize(alias) for alias in ANALYSIS_DESIGN_ALIASES}
    candidates = []

    for root in (connection.reports_toolbar, connection.main_window):
        for control in safe_call(root.descendants, []) or []:
            if normalize(safe_text(control)) not in alias_keys:
                continue

            if not safe_call(control.is_visible, False):
                continue

            if not safe_call(control.is_enabled, False):
                continue

            candidates.append(control)

    if not candidates:
        raise RuntimeError("Could not find the Analysis Design report command.")

    priority = {
        "SplitButton": 0,
        "Button": 1,
        "MenuItem": 2,
        "Custom": 3,
    }

    candidates.sort(
        key=lambda item: (
            priority.get(control_type(item), 99),
            -rectangle_area(item),
        )
    )

    return candidates[0]


def open_report(
    connection: Any,
    report: ReportDefinition,
) -> ReportOpenResult:
    """
    Open one report using the keyboard sequence stored in Reports_List.py.
    """
    before_preview_handles = existing_preview_handles()
    before_dialog_handles = existing_dialog_handles()
    command = find_analysis_design_command(connection)

    connection.main_window.set_focus()
    sleep(CONTROL_SETTLE_SECONDS)

    rect = command.rectangle()

    try:
        # Click the drop-down portion of the Analysis Design split button.
        command.click_input(
            coords=(
                max(1, rect.width() - 8),
                max(1, rect.height() - 8),
            )
        )
    except Exception:
        command.click_input()

    sleep(MENU_SETTLE_SECONDS)

    sequence = report["menu_keys"]

    print(f"Menu keys: {sequence}")
    send_keys(sequence, pause=0.15)

    return wait_for_report_open_result(
        before_preview_handles,
        before_dialog_handles,
    )


# =============================================================================
# USER INTERACTION / REPORT GENERATION
# =============================================================================


def visible_buttons(window: Any) -> list[Any]:
    return [
        button
        for button in safe_call(
            lambda: window.descendants(control_type="Button"),
            [],
        )
        or []
        if safe_call(button.is_visible, False)
    ]


def button_snapshot(window: Any) -> list[str]:
    return [
        safe_text(button)
        for button in visible_buttons(window)
        if safe_text(button)
    ]


def has_visible_button(window: Any, button_name: str) -> bool:
    target = normalize(button_name)

    return any(
        normalize(safe_text(button)) == target
        for button in visible_buttons(window)
    )


def find_submit_button(preview: Any) -> Any | None:
    for button in visible_buttons(preview):
        if normalize(safe_text(button)) == "submit":
            return button

    return None


def refreshed_preview(preview_handle: int) -> Any | None:
    """Return a fresh UIA wrapper for an existing Preview window.

    LEAP can refresh/rebuild the UI Automation tree after Submit. Reacquiring
    the wrapper avoids polling controls through a stale pywinauto object.
    """
    if not ctypes.windll.user32.IsWindow(preview_handle):
        return None

    try:
        candidate = Desktop(backend="uia").window(
            handle=preview_handle,
        ).wrapper_object()

        if not safe_call(candidate.is_visible, False):
            return None

        return candidate

    except Exception:
        return None


def visible_enabled_button(window: Any, button_name: str) -> bool:
    """Return True when a named button is both visible and enabled."""
    target = normalize(button_name)

    for button in safe_call(
        lambda: window.descendants(control_type="Button"),
        [],
    ) or []:
        if normalize(safe_text(button)) != target:
            continue

        if (
            safe_call(button.is_visible, False)
            and safe_call(button.is_enabled, False)
        ):
            return True

    return False


def preview_is_export_ready(preview: Any) -> bool:
    """Return True when generated-report toolbar controls are enabled.

    Before Submit, LEAP shows Print / Export To in the ribbon but disables
    them. Once report content is populated, those controls become enabled.
    This is a stable post-generation condition and does not depend on catching
    the short-lived Stop button.
    """
    return (
        visible_enabled_button(preview, "Print")
        or visible_enabled_button(preview, "Export To")
    )


def wait_for_user_action(
    preview: Any,
    report_name: str,
) -> str:
    """Wait for the report Preview to become export-ready or be closed.

    The Preview wrapper is reacquired on every poll because LEAP may rebuild
    its UI Automation tree after Submit. Report completion is identified from
    stable enabled toolbar controls (Print / Export To), rather than requiring
    the transient Stop button to be observed.
    """
    preview_handle = safe_call(lambda: int(preview.handle))

    if preview_handle is None:
        raise RuntimeError("Could not determine the Preview window handle.")

    initial_preview = refreshed_preview(preview_handle) or preview
    submit_button = find_submit_button(initial_preview)
    initial_ready = preview_is_export_ready(initial_preview)

    print()
    print(f"{report_name} dialog is open.")
    print(f"Preview handle: {preview_handle}")
    print(f"Visible buttons: {button_snapshot(initial_preview)}")
    print(f"Submit found:   {submit_button is not None}")
    print(f"Export ready:   {initial_ready}")
    print()
    print("Waiting for user:")
    print("  Close/Cancel -> skip report")
    print("  Submit       -> generate and export PDF")
    print()

    stop_seen = False
    ready_polls = 0

    while True:
        if not ctypes.windll.user32.IsWindow(preview_handle):
            return "closed"

        current = refreshed_preview(preview_handle)
        if current is None:
            sleep(POLL_INTERVAL)
            continue

        stop_visible = has_visible_button(current, "Stop")
        if stop_visible and not stop_seen:
            stop_seen = True
            print("Report generation activity detected (Stop visible).")

        # Do not call a report ready while Stop is still visible.
        ready_now = (not stop_visible) and preview_is_export_ready(current)

        if ready_now:
            ready_polls += 1

            # Require several consecutive polls to avoid acting on a transient
            # UI state while LEAP is rebuilding the Preview.
            if ready_polls >= READY_STABLE_POLLS:
                if stop_seen:
                    print("Report generation complete; export controls enabled.")
                else:
                    print("Report populated; export controls enabled.")
                return "submitted"
        else:
            ready_polls = 0

        sleep(POLL_INTERVAL)


def wait_for_automatic_generation(
    preview: Any,
    report_name: str,
) -> str:
    """
    Wait for an automatically generated LEAP report to be ready for export.

    Reports such as Support Reactions and Construction Lateral Moments do not
    present a Submit button. Selecting the menu command immediately opens the
    Preview and generates the report.

    A short initial settle period prevents PDF export from starting before LEAP
    has had time to begin/populate the report. If a visible Stop button remains
    after that period, wait until it disappears.
    """
    preview_handle = safe_call(lambda: int(preview.handle))

    if preview_handle is None:
        raise RuntimeError("Could not determine the Preview window handle.")

    print()
    print(f"{report_name} generates automatically.")
    print(f"Preview handle: {preview_handle}")
    print("No Submit action required.")
    print("Waiting for automatic report generation...")

    deadline = monotonic() + AUTOMATIC_REPORT_SETTLE_SECONDS

    while monotonic() < deadline:
        if not ctypes.windll.user32.IsWindow(preview_handle):
            return "closed"

        sleep(POLL_INTERVAL)

    # If LEAP is still actively generating, its Stop button remains visible.
    while has_visible_button(preview, "Stop"):
        if not ctypes.windll.user32.IsWindow(preview_handle):
            return "closed"

        sleep(POLL_INTERVAL)

    print("Automatic report generation complete.")
    return "generated"


# =============================================================================
# PDF EXPORT / CLEANUP
# =============================================================================


def export_report_pdf(
    preview: Any,
    output_folder: Path,
    report: ReportDefinition,
) -> Path:
    """Export one completed LEAP Preview to the selected output folder."""
    filename = report["filename"]

    print()
    print("Exporting PDF...")
    print(f"  File: {filename}")

    pdf_path = export_preview_to_pdf(
        preview,
        output_folder,
        filename,
        overwrite=True,
    )

    print()
    print("PDF export complete:")
    print(f"  {pdf_path}")

    return pdf_path


def close_preview(preview: Any) -> None:
    """Close the LEAP Preview after a successful export."""
    if not window_exists(preview):
        return

    try:
        preview.close()
        sleep(CONTROL_SETTLE_SECONDS)
        return
    except Exception:
        pass

    # Fallback for windows where .close() is not exposed reliably.
    safe_call(preview.set_focus)
    send_keys("%{F4}")
    sleep(CONTROL_SETTLE_SECONDS)


# =============================================================================
# MAIN
# =============================================================================


def main() -> int:
    connection = None
    preview = None

    try:
        enabled_reports = [
            report
            for report in REPORTS
            if report["enabled"]
        ]

        print("=" * 80)
        print("LEAP MULTI-REPORT OUTPUT DRIVER")
        print("=" * 80)
        print(f"Configured reports: {len(REPORTS)}")
        print(f"Enabled reports:    {len(enabled_reports)}")
        print()

        for number, report in enumerate(enabled_reports, start=1):
            print(
                f"  {number:02d}. "
                f"{report['name']} -> {report['filename']} "
                f"[{report['generation_mode']}]"
            )

        if not enabled_reports:
            print("No reports are enabled in Reports_List.py.")
            return 0

        print()

        # -----------------------------------------------------------------
        # 1. SELECT PDF OUTPUT FOLDER
        # -----------------------------------------------------------------

        print("Opening folder picker...")

        output_folder = select_folder()

        if output_folder is None:
            print("Folder selection cancelled.")
            return 0

        output_folder = Path(output_folder)

        print()
        print("Selected PDF output folder:")
        print(f"  {output_folder}")
        print()

        # -----------------------------------------------------------------
        # 2. CONNECT TO LEAP
        # -----------------------------------------------------------------

        connector = load_module(
            #"leap_report_connect",
            "leap_connect",
            CONNECT_FILE,
        )

        connection = connector.connect_to_leap(
            focus_main_window=True,
        )

        # -----------------------------------------------------------------
        # 3. PROCESS CONFIGURED REPORTS
        # -----------------------------------------------------------------

        exported_count = 0
        skipped_count = 0

        for index, report in enumerate(enabled_reports, start=1):
            report_name = report["name"]

            print()
            print("=" * 80)
            print(f"REPORT {index} OF {len(enabled_reports)}")
            print(f"  {report_name}")
            print("=" * 80)

            open_result = open_report(connection, report)

            if open_result.status == "message":
                skipped_count += 1
                preview = None

                print("Report unavailable for the current analysis/model state.")
                print()
                print(f"Skipped: {report_name}")
                print("Moving to next report...")
                continue

            preview = open_result.preview

            if preview is None:
                raise RuntimeError(
                    f"Report opening returned no Preview for: {report_name}"
                )

            generation_mode = report["generation_mode"]

            if generation_mode == "submit":
                result = wait_for_user_action(
                    preview,
                    report_name,
                )

            elif generation_mode == "automatic":
                result = wait_for_automatic_generation(
                    preview,
                    report_name,
                )

            else:
                raise ValueError(
                    f"Unknown generation_mode for {report_name}: "
                    f"{generation_mode!r}"
                )

            if result == "closed":
                skipped_count += 1
                preview = None

                print()
                print(f"Skipped: {report_name}")
                print("Moving to next report...")
                continue

            # LEAP may have rebuilt the Preview UIA tree while generating the
            # report. Hand the exporter a fresh wrapper, not the pre-Submit one.
            preview_handle = safe_call(lambda: int(preview.handle))
            if preview_handle is not None:
                fresh_preview = refreshed_preview(preview_handle)
                if fresh_preview is not None:
                    preview = fresh_preview

            export_report_pdf(
                preview,
                output_folder,
                report,
            )

            exported_count += 1

            if CLOSE_PREVIEW_AFTER_EXPORT:
                close_preview(preview)
                preview = None
                print("Preview closed.")

            print()
            print(f"Completed: {report_name}")

        # -----------------------------------------------------------------
        # 4. FINISHED
        # -----------------------------------------------------------------

        print()
        print("=" * 80)
        print("REPORT WORKFLOW COMPLETE")
        print("=" * 80)
        print(f"Configured: {len(REPORTS)}")
        print(f"Enabled:    {len(enabled_reports)}")
        print(f"Exported:   {exported_count}")
        print(f"Skipped:    {skipped_count}")

        return 0

    except KeyboardInterrupt:
        print()
        print("Driver cancelled from terminal.")
        return 130

    except Exception:
        print()
        print("=" * 80)
        print("DRIVER FAILED")
        print("=" * 80)
        print(traceback.format_exc())
        return 1

    finally:
        if preview is not None and not CLOSE_PREVIEW_AFTER_EXPORT:
            pass

        if connection is not None:
            safe_call(connection.main_window.set_focus)


if __name__ == "__main__":
    raise SystemExit(main())
