"""
Tools_ExportPDF.py
==================

Utility for exporting the currently displayed LEAP report Preview to PDF.

This diagnostic version preserves the existing export procedure and adds
targeted DEBUG messages so failures can be localized without changing the
workflow.
"""

from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep
from typing import Any, Callable, TypeVar

from pywinauto import Desktop
from pywinauto.keyboard import send_keys
from pywinauto import mouse


# =============================================================================
# SETTINGS
# =============================================================================

CONTROL_SETTLE_SECONDS = 0.35
DIALOG_TIMEOUT = 20.0
POLL_INTERVAL = 0.20

EXPORT_POPUP_CLASS_FRAGMENT = "GalleryDropDownForm"
EXPORT_POPUP_TIMEOUT = 3.0

DEBUG_TRACE = True

T = TypeVar("T")


# =============================================================================
# GENERAL UTILITIES
# =============================================================================

def debug(message: str) -> None:
    if DEBUG_TRACE:
        print(f"DEBUG ExportPDF: {message}")


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
    return "".join(
        character
        for character in str(value).casefold()
        if character.isalnum()
    )


def visible_descendants(window: Any) -> list[Any]:
    return [
        control
        for control in (safe_call(window.descendants, []) or [])
        if safe_call(control.is_visible, False)
    ]


def find_visible_control_by_text(
    window: Any,
    *names: str,
) -> Any | None:
    wanted = {normalize(name) for name in names}

    for control in visible_descendants(window):
        if normalize(safe_text(control)) in wanted:
            return control

    return None


def click_control(control: Any) -> None:
    try:
        control.click_input()
    except Exception:
        control.invoke()

    sleep(CONTROL_SETTLE_SECONDS)


# =============================================================================
# LEAP EXPORT CONTROLS
# =============================================================================

def find_export_to_control(preview: Any) -> Any:
    debug("Searching Preview descendants for 'Export To'.")

    control = find_visible_control_by_text(
        preview,
        "Export To",
        "Export To...",
    )

    if control is None:
        debug("'Export To' control was NOT found.")
        raise RuntimeError(
            'Could not find the LEAP "Export To" control in the Preview window.'
        )

    rect = safe_call(control.rectangle)
    debug(
        "'Export To' control found: "
        f"text={safe_text(control)!r}, rect={rect}"
    )

    return control


def open_export_menu(preview: Any) -> None:
    export_to = find_export_to_control(preview)
    rect = safe_call(export_to.rectangle)

    if rect is None:
        raise RuntimeError(
            'Found the LEAP "Export To" control, but could not determine '
            "its screen rectangle."
        )

    x = max(1, rect.width() - 7)
    y = max(1, rect.height() - 7)

    debug(f"Clicking Export To dropdown at relative coords ({x}, {y}).")

    try:
        export_to.click_input(coords=(x, y))
    except Exception as exc:
        debug(f"Export To dropdown click failed: {exc!r}")
        raise RuntimeError(
            'Found "Export To", but could not click its dropdown arrow.'
        ) from exc

    sleep(0.75)
    debug("Export To dropdown click completed.")


def choose_pdf_export(preview: Any) -> None:
    debug("Entering choose_pdf_export().")

    export_to = find_export_to_control(preview)
    rect = safe_call(export_to.rectangle)

    if rect is None:
        raise RuntimeError(
            'Found the LEAP "Export To" control, but could not determine '
            "its screen rectangle."
        )

    open_export_menu(preview)

    target_x = rect.left + 120
    target_y = rect.bottom + 30

    debug(
        "Clicking presumed PDF File row at screen coords "
        f"({target_x}, {target_y})."
    )

    mouse.move(coords=(target_x, target_y))
    sleep(0.35)
    mouse.click(button="left", coords=(target_x, target_y))

    sleep(0.75)
    debug("PDF File row click completed.")


# =============================================================================
# PDF EXPORT OPTIONS DIALOG
# =============================================================================

def accept_pdf_export_options() -> None:
    print("Waiting for PDF Export Options dialog...")
    debug("Searching for PDF Export Options dialog.")

    deadline = monotonic() + DIALOG_TIMEOUT
    dialog = None

    while monotonic() < deadline:
        try:
            candidate = Desktop(backend="uia").window(
                title_re=r"^PDF Export Options$"
            )
            if candidate.exists(timeout=0.2) and candidate.is_visible():
                dialog = candidate
                debug("Found PDF Export Options using UIA window spec.")
                break
        except Exception:
            pass

        try:
            for candidate in Desktop(backend="uia").windows(visible_only=True):
                if normalize(safe_text(candidate)) == normalize("PDF Export Options"):
                    dialog = candidate
                    debug("Found PDF Export Options by UIA enumeration.")
                    break
        except Exception:
            pass

        if dialog is not None:
            break

        try:
            for candidate in Desktop(backend="win32").windows(visible_only=True):
                if normalize(safe_text(candidate)) == normalize("PDF Export Options"):
                    dialog = candidate
                    debug("Found PDF Export Options by Win32 enumeration.")
                    break
        except Exception:
            pass

        if dialog is not None:
            break

        sleep(POLL_INTERVAL)

    if dialog is None:
        visible_titles: list[str] = []

        for backend in ("uia", "win32"):
            try:
                for window in Desktop(backend=backend).windows(visible_only=True):
                    title = safe_text(window)
                    if title and title not in visible_titles:
                        visible_titles.append(title)
            except Exception:
                pass

        diagnostic = "\n".join(f"  - {title}" for title in visible_titles)

        debug("PDF Export Options dialog timed out.")
        raise RuntimeError(
            'Timed out waiting for window: "PDF Export Options"\n'
            "Visible window titles at timeout:\n"
            f"{diagnostic or '  (none found)'}"
        )

    print("PDF Export Options dialog found.")

    ok_button = find_visible_control_by_text(dialog, "OK")

    if ok_button is None:
        debug("OK button not exposed; trying ENTER.")
        try:
            dialog.set_focus()
            send_keys("{ENTER}")
            sleep(CONTROL_SETTLE_SECONDS)
            print("Accepted PDF Export Options with ENTER.")
            return
        except Exception as exc:
            debug(f"ENTER fallback failed: {exc!r}")
            raise RuntimeError(
                'Found the PDF Export Options dialog, but could not find or '
                'activate its "OK" button.'
            ) from exc

    debug("Clicking PDF Export Options OK button.")
    click_control(ok_button)
    print("PDF Export Options accepted.")


# =============================================================================
# WINDOWS SAVE-AS DIALOG
# =============================================================================

def wait_for_save_as_win32(timeout: float = DIALOG_TIMEOUT) -> Any:
    deadline = monotonic() + timeout
    debug("Waiting for Win32 Save As dialog.")

    while monotonic() < deadline:
        try:
            for window in Desktop(backend="win32").windows(visible_only=True):
                title = safe_text(window)
                class_name = safe_call(window.class_name, "") or ""

                if title in {"Save As", "Save PDF File As"} and class_name == "#32770":
                    debug(
                        "Found Save As dialog: "
                        f"title={title!r}, class={class_name!r}"
                    )
                    return window
        except Exception:
            pass

        sleep(POLL_INTERVAL)

    raise RuntimeError(
        'Timed out waiting for Win32 Save As dialog '
        '(title="Save As", class="#32770").'
    )


def find_filename_edit_win32(save_as: Any) -> Any:
    edits = []

    for control in safe_call(save_as.descendants, []) or []:
        if not safe_call(control.is_visible, False):
            continue

        if (safe_call(control.class_name, "") or "") == "Edit":
            edits.append(control)

    debug(f"Visible Win32 Edit controls found in Save As: {len(edits)}")

    if not edits:
        raise RuntimeError(
            'Could not find the Win32 "File name" Edit control '
            "in the Save As dialog."
        )

    def top(control: Any) -> int:
        rect = safe_call(control.rectangle)
        return rect.top if rect is not None else -1

    edits.sort(key=top, reverse=True)
    return edits[0]


def set_filename_path(save_as: Any, pdf_path: Path) -> None:
    filename_edit = find_filename_edit_win32(save_as)
    full_path = str(pdf_path)

    debug(f"Entering full PDF path: {full_path}")

    try:
        filename_edit.set_edit_text(full_path)
    except Exception:
        filename_edit.set_focus()
        send_keys("^a")
        send_keys(full_path, with_spaces=True)

    sleep(CONTROL_SETTLE_SECONDS)


def overwrite_confirmation_visible() -> bool:
    for backend in ("uia", "win32"):
        try:
            windows = Desktop(backend=backend).windows(visible_only=True)
        except Exception:
            continue

        for window in windows:
            descendants = safe_call(window.descendants, []) or []
            text_blob = " ".join(
                safe_text(control)
                for control in descendants
                if safe_text(control)
            ).casefold()

            if (
                normalize(safe_text(window))
                in {normalize("Confirm Save As"), normalize("Confirm Save")}
                or "already exists" in text_blob
                or "replace" in text_blob
            ):
                return True

    return False


def click_save_win32(save_as: Any) -> None:
    save_button = None

    try:
        candidate = save_as.child_window(
            title="&Save",
            class_name="Button",
        )

        if candidate.exists(timeout=0.5):
            save_button = candidate
    except Exception:
        pass

    if save_button is None:
        for control in safe_call(save_as.descendants, []) or []:
            if not safe_call(control.is_visible, False):
                continue

            if (
                (safe_call(control.class_name, "") or "") == "Button"
                and safe_text(control) in {"&Save", "Save"}
            ):
                save_button = control
                break

    if save_button is None:
        raise RuntimeError(
            'Could not find the Win32 "Save" button in the Save As dialog.'
        )

    # A programmatic .click() occasionally returned successfully without the
    # Windows common dialog actually accepting the Save command.  Prefer a
    # physical input click, then verify that the dialog changed state.
    debug("Physically clicking Save button.")

    try:
        save_as.set_focus()
    except Exception:
        pass

    sleep(0.15)

    try:
        save_button.click_input()
    except Exception as exc:
        debug(f"Save click_input failed: {exc!r}; trying ENTER instead.")
        try:
            save_as.set_focus()
        except Exception:
            pass
        send_keys("{ENTER}")

    # Do not blindly advance to the next export stage.  The Save As window
    # should either disappear or produce an overwrite-confirmation dialog.
    deadline = monotonic() + 2.0

    while monotonic() < deadline:
        if not safe_call(save_as.is_visible, False):
            debug("Save As dialog closed after Save command.")
            return

        if overwrite_confirmation_visible():
            debug("Save command accepted; overwrite confirmation appeared.")
            return

        sleep(POLL_INTERVAL)

    # If the physical click was swallowed, a focused Enter is a reliable
    # second attempt because Save is the default button in this dialog.
    debug("Save As still visible; retrying Save with ENTER.")
    try:
        save_as.set_focus()
    except Exception:
        pass
    send_keys("{ENTER}")

    deadline = monotonic() + 2.0
    while monotonic() < deadline:
        if not safe_call(save_as.is_visible, False):
            debug("Save As dialog closed after ENTER retry.")
            return

        if overwrite_confirmation_visible():
            debug("ENTER retry accepted; overwrite confirmation appeared.")
            return

        sleep(POLL_INTERVAL)

    raise RuntimeError(
        'The Save As dialog did not respond to either the Save button or ENTER.'
    )


def handle_overwrite_confirmation() -> None:
    deadline = monotonic() + 2.0

    while monotonic() < deadline:
        for backend in ("uia", "win32"):
            try:
                windows = Desktop(backend=backend).windows(visible_only=True)
            except Exception:
                continue

            for window in windows:
                descendants = safe_call(window.descendants, []) or []

                text_blob = " ".join(
                    safe_text(control)
                    for control in descendants
                    if safe_text(control)
                ).casefold()

                if (
                    normalize(safe_text(window))
                    not in {
                        normalize("Confirm Save As"),
                        normalize("Confirm Save"),
                    }
                    and "already exists" not in text_blob
                    and "replace" not in text_blob
                ):
                    continue

                debug("Overwrite confirmation detected.")

                for control in descendants:
                    if normalize(safe_text(control)) in {
                        normalize("Yes"),
                        normalize("&Yes"),
                        normalize("Replace"),
                    }:
                        click_control(control)
                        debug("Overwrite confirmation accepted.")
                        return

        sleep(POLL_INTERVAL)

    debug("No overwrite confirmation appeared.")


def save_pdf_as(pdf_path: Path) -> None:
    print("Waiting for Save As dialog...")

    save_as = wait_for_save_as_win32()

    print("Save As dialog found.")
    print(f"Setting PDF path:\n  {pdf_path}")

    set_filename_path(save_as, pdf_path)
    click_save_win32(save_as)
    handle_overwrite_confirmation()

    # After any overwrite confirmation is handled, make sure Save As really
    # went away before looking for LEAP's post-export "open this file" prompt.
    deadline = monotonic() + 3.0
    while monotonic() < deadline:
        if not safe_call(save_as.is_visible, False):
            debug("Verified Save As dialog is closed.")
            debug("Save As stage completed.")
            return
        sleep(POLL_INTERVAL)

    raise RuntimeError(
        'Save As is still visible after the Save/overwrite workflow completed.'
    )


# =============================================================================
# POST-EXPORT "OPEN THIS FILE?" DIALOG
# =============================================================================

def dismiss_open_pdf_prompt(timeout: float = 8.0) -> None:
    deadline = monotonic() + timeout
    debug('Waiting for "Do you want to open this file?" prompt.')

    while monotonic() < deadline:
        for backend in ("uia", "win32"):
            try:
                desktop = Desktop(backend=backend)
                roots = desktop.windows(visible_only=True)
            except Exception:
                continue

            candidates = list(roots)

            for root in roots:
                candidates.extend(safe_call(root.descendants, []) or [])

            if backend == "uia":
                candidates.extend(safe_call(desktop.descendants, []) or [])

            for candidate in candidates:
                if not safe_call(candidate.is_visible, False):
                    continue

                descendants = safe_call(candidate.descendants, []) or []

                candidate_text = safe_text(candidate)
                text_blob = " ".join(
                    [candidate_text]
                    + [
                        safe_text(control)
                        for control in descendants
                        if safe_text(control)
                    ]
                ).casefold()

                if "do you want to open this file" not in text_blob:
                    continue

                debug(f'Found open-file prompt using backend={backend}.')

                for control in descendants:
                    if normalize(safe_text(control)) in {
                        normalize("No"),
                        normalize("&No"),
                    }:
                        try:
                            control.click_input()
                        except Exception:
                            try:
                                control.click()
                            except Exception:
                                control.invoke()

                        sleep(CONTROL_SETTLE_SECONDS)
                        print('Dismissed "open PDF" prompt with No.')
                        return

                try:
                    no_button = candidate.child_window(
                        title_re=r"^&?No$",
                        class_name="Button",
                    )

                    if no_button.exists(timeout=0.2):
                        try:
                            no_button.click()
                        except Exception:
                            no_button.click_input()

                        sleep(CONTROL_SETTLE_SECONDS)
                        print('Dismissed "open PDF" prompt with No.')
                        return
                except Exception:
                    pass

        sleep(POLL_INTERVAL)

    raise RuntimeError(
        'Timed out trying to dismiss the LEAP "Do you want to open this file?" '
        'prompt.'
    )


# =============================================================================
# PUBLIC EXPORT FUNCTION
# =============================================================================

def export_preview_to_pdf(
    preview: Any,
    output_folder: str | Path,
    filename: str,
    *,
    overwrite: bool = True,
) -> Path:
    debug(
        "ENTER export_preview_to_pdf("
        f"output_folder={output_folder!r}, "
        f"filename={filename!r}, overwrite={overwrite})"
    )

    folder = Path(output_folder).expanduser().resolve()

    if not folder.is_dir():
        raise NotADirectoryError(f"Output folder does not exist:\n{folder}")

    clean_filename = Path(filename).name

    if not clean_filename.casefold().endswith(".pdf"):
        clean_filename += ".pdf"

    pdf_path = folder / clean_filename
    debug(f"Resolved PDF path: {pdf_path}")

    if pdf_path.exists() and not overwrite:
        raise FileExistsError(f"PDF already exists:\n{pdf_path}")

    debug("Stage 1/4: choose_pdf_export()")
    choose_pdf_export(preview)

    debug("Stage 2/4: accept_pdf_export_options()")
    accept_pdf_export_options()

    debug("Stage 3/4: save_pdf_as()")
    save_pdf_as(pdf_path)

    debug("Stage 4/4: dismiss_open_pdf_prompt()")
    dismiss_open_pdf_prompt()

    debug("Export dialogs completed; waiting for PDF file to appear.")

    deadline = monotonic() + DIALOG_TIMEOUT

    while monotonic() < deadline:
        if pdf_path.is_file():
            debug(f"PDF file found on disk: {pdf_path}")
            return pdf_path
        sleep(POLL_INTERVAL)

    raise RuntimeError(
        "LEAP completed the export dialogs, but the PDF file was not found:\n"
        f"{pdf_path}"
    )


# =============================================================================
# STANDALONE NOTE
# =============================================================================

def main() -> int:
    print("=" * 80)
    print("LEAP PDF EXPORT TOOL")
    print("=" * 80)
    print()
    print("This module is intended to be called by a report driver.")
    print("It requires an already-open submitted LEAP Preview window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
