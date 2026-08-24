# LEAPsteelPy

Python automation tools for Bentley LEAP Bridge Steel.

LEAPsteelPy automates repetitive report-generation tasks in LEAP Bridge Steel,
including opening selected reports, generating report previews, and exporting
the results to individual PDF files.

<img width="800" alt="Screenshot 2026-08-24 162548" src="https://github.com/user-attachments/assets/6d98fbb9-a3b1-473f-8e46-7d743bfb9ccd" />

## Current Status

**Experimental / Beta**

The current version can batch-export selected LEAP Bridge Steel Analysis
reports to PDF. It is being released primarily for testing, feedback, and
discussion with other bridge engineers.

## Requirements

- Windows
- Bentley LEAP Bridge Steel 2025
- Python 3
- pywinauto

LEAP Bridge Steel must be running with a model open before starting the
automation.

## Usage

Reports to be exported are selected in:

`src/Reports_List.py`

Run:

`src/LEAPsteelOutput.py`

The script prompts for an output directory and then processes the enabled
reports automatically.

## Limitations

- Currently focused on Analysis report PDF export.
- Not all LEAP reports have been implemented/tested.
- Automation relies on the LEAP Bridge Steel Windows user interface and may
  require adjustment for other LEAP versions.
- This is not affiliated with or supported by Bentley Systems.

## Feedback

This project is under active development. Feedback from LEAP Bridge Steel
users is welcome, particularly regarding:

- Reports that would be useful to automate
- Problems with different LEAP models or configurations
- PDF export workflow
- Potential Excel/XLSX report export


