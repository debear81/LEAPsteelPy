"""
Tools_Folder.py
===============

Utility for asking the user to select an output folder.

Typical imported use
--------------------
    from Tools_Folder import select_folder

    output_folder = select_folder()

    if output_folder is None:
        print("No output folder selected.")
        return

    print(f"PDF output folder: {output_folder}")


Standalone test
---------------
    py ".\\src\\Tools_Folder.py"
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog


# =============================================================================
# SETTINGS
# =============================================================================

DEFAULT_TITLE = "Select folder for LEAP PDF reports"


# =============================================================================
# FOLDER SELECTION
# =============================================================================

def select_folder(
    *,
    title: str = DEFAULT_TITLE,
    initial_folder: str | Path | None = None,
) -> Path | None:
    """
    Open a Windows folder-selection dialog.

    Parameters
    ----------
    title:
        Text displayed in the folder-selection dialog.

    initial_folder:
        Folder initially shown when the dialog opens.
        If None, tkinter/Windows selects the default location.

    Returns
    -------
    Path
        Selected folder.

    None
        User cancelled the dialog.
    """

    root = tk.Tk()

    try:
        # Hide the empty tkinter main window.
        root.withdraw()

        # Encourage the Windows folder dialog to appear in front.
        #root.attributes("-topmost", True)
        root.update()

        options: dict[str, object] = {
            "title": title,
            "mustexist": True,
        }

        if initial_folder is not None:
            initial_path = Path(initial_folder).expanduser()

            if initial_path.is_dir():
                options["initialdir"] = str(initial_path)

        selected = filedialog.askdirectory(
            parent=root,
            **options,
        )

        if not selected:
            return None

        return Path(selected).resolve()

    finally:
        root.destroy()


# =============================================================================
# STANDALONE TEST
# =============================================================================

def main() -> int:
    print("=" * 80)
    print("OUTPUT FOLDER SELECTION TEST")
    print("=" * 80)
    print()

    folder = select_folder()

    print()

    if folder is None:
        print("Folder selection cancelled.")
        return 0

    print("Selected folder:")
    print(f"  {folder}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())