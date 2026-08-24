"""
Report definitions for LEAP Bridge Steel report automation.

This module intentionally contains report metadata only. The driver and
navigation/export tools should import REPORTS and handle the actual LEAP UI
interaction.

Fields
------
name
    User-facing report name.

filename
    Default PDF filename.

menu_keys
    Keyboard sequence used after opening the Analysis Design drop-down.

enabled
    Whether the driver should attempt this report in the current batch.

generation_mode
    How the report is generated after selecting it from the LEAP menu.

    "submit"
        LEAP opens a report-options dialog and waits for the user to click
        Submit before generating the report preview.

    "automatic"
        LEAP generates the report preview automatically as soon as the report
        is selected. No Submit button is expected.

requires
    Zero or more model/analysis capabilities that may be required before the
    report is available. These are metadata flags; the current driver can
    continue relying on LEAP's own "report not available" message until model
    capability detection is added.

navigation_verified
    True only when the menu sequence has actually been tested successfully in
    the current LEAP version.

availability_note
    Human-readable note about known/suspected availability restrictions.
"""

from __future__ import annotations

from typing import Final, TypedDict


class ReportDefinition(TypedDict):
    """Metadata required to identify, open, and save one LEAP report."""

    name: str
    filename: str
    menu_keys: str
    enabled: bool
    generation_mode: str
    requires: tuple[str, ...]
    navigation_verified: bool
    availability_note: str


# ---------------------------------------------------------------------------
# Report definitions
#
# Menu-key logic:
#   Analysis > Dead Load:
#       {HOME}{RIGHT}{HOME}{RIGHT} + report position
#
#   Analysis > Live Load:
#       {HOME}{RIGHT}{HOME}{DOWN}{RIGHT} + report position
#
#   Design:
#       {HOME}{DOWN}{RIGHT} + report position
#
# Only the first three Dead Load sequences have been tested in the current
# workflow. The remaining sequences are built from the observed menu hierarchy
# and should remain navigation_verified=False until confirmed in LEAP.
# ---------------------------------------------------------------------------

REPORTS: Final[list[ReportDefinition]] = [

    # =======================================================================
    # ANALYSIS > DEAD LOAD
    # =======================================================================

    {
        "name": "DL Node Displacements",
        "filename": "01_DL_Node_Displacements.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{RIGHT}{HOME}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "DL Girder Forces",
        "filename": "02_DL_Girder_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{RIGHT}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "DL Cross Frame Forces",
        "filename": "03_DL_Cross_Frame_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{RIGHT}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("cross_frame_analysis",),
        "navigation_verified": True,
        "availability_note": 'Unavailable for "Line Girder" analysis.',
        # User note: Not available with Line Girder analysis.
        # Test again with a 3D/system analysis model.
    },
    {
        "name": "DL Cross Frame Detailed Forces",
        "filename": "04_DL_Cross_Frame_Detailed_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{RIGHT}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("cross_frame_analysis",),
        "navigation_verified": True,
        "availability_note": "Expected to require cross-frame/system analysis.",
        # User note: Not available with Line Girder analysis.
        # Test again with a 3D/system analysis model.
    },
    {
        "name": "DL Support Reactions",
        "filename": "05_DL_Support_Reactions.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "automatic",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "Generates automatically; no Submit button.",
    },

    # =======================================================================
    # ANALYSIS > LIVE LOAD
    # =======================================================================

    {
        "name": "LL Distribution Factors",
        "filename": "06_LL_Distribution_Factors.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{HOME}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "LL Girder Forces and Node Displacements",
        "filename": "07_LL_Girder_Forces_and_Node_Displacements.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "LL Centrifugal Forces",
        "filename": "08_LL_Centrifugal_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("centrifugal_force_applicable",),
        "navigation_verified": True,
        "availability_note": "Availability condition has not yet been verified.",
    },
    {
        "name": "LL Cross Frame Forces",
        "filename": "09_LL_Cross_Frame_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("cross_frame_analysis",),
        "navigation_verified": True,
        "availability_note": "Expected to require cross-frame/system analysis.",
    },
    {
        "name": "LL Cross Frame Detailed Forces",
        "filename": "10_LL_Cross_Frame_Detailed_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("cross_frame_analysis",),
        "navigation_verified": True,
        "availability_note": "Expected to require cross-frame/system analysis.",
    },
    {
        "name": "LL Support Reactions",
        "filename": "11_LL_Support_Reactions.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "automatic",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "LL Lane Load Details",
        "filename": "12_LL_Lane_Load_Details.pdf",
        "menu_keys": "{HOME}{RIGHT}{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": False,
        "availability_note": "",
    },

    # =======================================================================
    # DESIGN
    # =======================================================================

    {
        "name": "Design Check",
        "filename": "13_Design_Check.pdf",
        "menu_keys": "{HOME}{DOWN}{RIGHT}{HOME}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "Fatigue",
        "filename": "14_Fatigue.pdf",
        "menu_keys": "{HOME}{DOWN}{RIGHT}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("fatigue_design_applicable",),
        "navigation_verified": True,
        "availability_note": "Availability condition has not yet been verified.",
    },
    {
        "name": "Cross Frame",
        "filename": "15_Cross_Frame.pdf",
        "menu_keys": "{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": ("cross_frame_analysis",),
        "navigation_verified": True,
        "availability_note": "Expected to require cross-frame/system analysis.",
        # User note: Not available with Line Girder analysis.
        # Test again with a 3D/system analysis model.
    },
    {
        "name": "Shear Connector",
        "filename": "16_Shear_Connector.pdf",
        "menu_keys": "{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": True,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": True,
        "availability_note": "",
    },
    {
        "name": "Summary - Under Design",
        "filename": "17_Summary_Under_Design.pdf",
        "menu_keys": "{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": False,
        "availability_note": "",
    },
    {
        "name": "Summary - Over Design",
        "filename": "18_Summary_Over_Design.pdf",
        "menu_keys": "{HOME}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": False,
        "availability_note": "",
    },

    # =======================================================================
    # ANALYSIS > RESPONSE SPECTRUM ANALYSIS
    # =======================================================================

    {
        "name": "RSA Girder Forces",
        "filename": "19_RSA_Girder_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{RIGHT}{HOME}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": ("response_spectrum_analysis",),
        "navigation_verified": False,
        "availability_note": "Response Spectrum Analysis report; navigation/generation behavior not yet verified.",
    },
    {
        "name": "RSA Node Displacements",
        "filename": "20_RSA_Node_Displacements.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{RIGHT}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": ("response_spectrum_analysis",),
        "navigation_verified": False,
        "availability_note": "Response Spectrum Analysis report; navigation/generation behavior not yet verified.",
    },
    {
        "name": "RSA Cross Frame Detailed Forces",
        "filename": "21_RSA_Cross_Frame_Detailed_Forces.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{RIGHT}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": ("response_spectrum_analysis", "cross_frame_analysis"),
        "navigation_verified": False,
        "availability_note": "Response Spectrum Analysis report; expected to require cross-frame/system analysis.",
    },
    {
        "name": "RSA Support Reactions",
        "filename": "22_RSA_Support_Reactions.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": ("response_spectrum_analysis",),
        "navigation_verified": False,
        "availability_note": "Response Spectrum Analysis report; navigation/generation behavior not yet verified.",
    },
    {
        "name": "RSA Mass Participation Factors and Base Shear",
        "filename": "23_RSA_Mass_Participation_Factors_and_Base_Shear.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": ("response_spectrum_analysis",),
        "navigation_verified": False,
        "availability_note": "Response Spectrum Analysis report; navigation/generation behavior not yet verified.",
    },
    {
        "name": "RSA Modal Analysis Results",
        "filename": "24_RSA_Modal_Analysis_Results.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{RIGHT}{DOWN}{DOWN}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": ("response_spectrum_analysis",),
        "navigation_verified": False,
        "availability_note": "Response Spectrum Analysis report; navigation/generation behavior not yet verified.",
    },

    # =======================================================================
    # ANALYSIS > CONSTRUCTION LATERAL MOMENTS
    # =======================================================================

    {
        "name": "Construction Lateral Moments",
        "filename": "25_Construction_Lateral_Moments.pdf",
        "menu_keys": "{HOME}{RIGHT}{DOWN}{DOWN}{DOWN}{ENTER}",
        "enabled": False,
        "generation_mode": "submit",
        "requires": (),
        "navigation_verified": False,
        "availability_note": "Navigation/generation behavior not yet verified.",
    },
]


def get_reports(*, enabled_only: bool = False) -> list[ReportDefinition]:
    """
    Return copies of configured report definitions.

    Args:
        enabled_only:
            If True, return only reports whose ``enabled`` flag is True.
    """
    reports = REPORTS

    if enabled_only:
        reports = [report for report in REPORTS if report["enabled"]]

    return [report.copy() for report in reports]


def get_report_by_name(name: str) -> ReportDefinition:
    """
    Return a copy of the report definition matching ``name``.

    Raises:
        KeyError: If no configured report has the requested name.
    """
    for report in REPORTS:
        if report["name"] == name:
            return report.copy()

    raise KeyError(f"Unknown report: {name}")


if __name__ == "__main__":
    print("=" * 100)
    print("LEAP REPORT LIST")
    print("=" * 100)

    for index, report in enumerate(REPORTS, start=1):
        status = "ON " if report["enabled"] else "OFF"
        verified = "verified" if report["navigation_verified"] else "unverified"
        requires = ", ".join(report["requires"]) or "-"

        print(f"{index:02d}. [{status}] {report['name']}")
        print(f"    PDF:       {report['filename']}")
        print(f"    Menu keys: {report['menu_keys']}")
        print(f"    Nav:       {verified}")
        print(f"    Generate:  {report['generation_mode']}")
        print(f"    Requires:  {requires}")

        if report["availability_note"]:
            print(f"    Note:      {report['availability_note']}")

        print()
