"""
Instance-specific PDF Report Generators for HANA Sentinel.

Generates reports for instance diagnostics and healing operations.
"""

import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import (
    HexColor,
    white,
    black,
    red,
    green,
    orange,
    grey,
    lightgrey,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
)

from .report_generator import (
    _ensure_reports_dir,
    _get_styles,
    _make_table,
    _status_text,
    _add_header_footer,
    BRAND_PRIMARY,
    BRAND_DARK,
    BRAND_ACCENT,
    BRAND_WARN,
    BRAND_ORANGE,
    BRAND_BG,
    TABLE_HEADER_BG,
    TABLE_ALT_BG,
    REPORTS_DIR,
)

logger = logging.getLogger(__name__)


def generate_instance_healing_report(
    diagnostic_data: Dict[str, Any],
    healing_data: Dict[str, Any],
    verification_data: Dict[str, Any] = None,
) -> dict:
    """Generate a comprehensive PDF report for instance healing cycle.

    Args:
        diagnostic_data: Diagnostic results that triggered healing
        healing_data: Healing script execution data containing:
            - certificate_id: Action certificate ID
            - script_name: Name of healing script executed
            - issue_description: Description of issue being fixed
            - execution_time: Timestamp of execution
            - execution_result: Result of healing script
            - changes_made: List of changes applied
        verification_data: Post-healing verification results (optional)

    Returns:
        dict: status, report_path, report_size
    """
    _ensure_reports_dir()
    styles = _get_styles()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    instance = diagnostic_data.get("instance_name", healing_data.get("instance_name", "unknown"))
    sid = diagnostic_data.get("sid", healing_data.get("sid", "unknown"))
    script_name = healing_data.get("script_name", "unknown")
    certificate_id = healing_data.get("certificate_id", "unknown")

    filename = f"instance_healing_{instance}_{script_name}_{ts}.pdf"
    filepath = os.path.join(REPORTS_DIR, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    story = []

    # ── Title ──
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph("HANA Instance Healing Report", styles["ReportTitle"]))
    story.append(Paragraph(f"Instance: {instance} (SID: {sid})", styles["ReportSubtitle"]))
    story.append(
        Paragraph(
            f"Script: <b>{script_name}</b> &nbsp;|&nbsp; "
            f"Certificate: <b>{certificate_id[:8]}</b> &nbsp;|&nbsp; "
            f"Generated: <b>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>",
            styles["BodyText2"],
        )
    )
    story.append(HRFlowable(width="100%", color=BRAND_PRIMARY, thickness=1.5))
    story.append(Spacer(1, 4 * mm))

    # ── Executive Summary ──
    healing_status = healing_data.get("status", "unknown")
    story.append(_status_text(f"Healing Status: {healing_status}", styles))
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 1. ISSUE DETAILS
    # ══════════════════════════════════════════
    story.append(Paragraph("1. Issue Details", styles["SectionHeader"]))

    issue_description = healing_data.get("issue_description", "No description provided")
    story.append(
        Paragraph(
            f"<b>Issue:</b> {issue_description}",
            styles["BodyText2"],
        )
    )

    # Issues from diagnostic
    issues = diagnostic_data.get("issues_detected", [])
    if issues:
        story.append(Paragraph("<b>Detected Issues:</b>", styles["SubHeader"]))
        for issue in issues:
            story.append(
                Paragraph(f"• {issue}", styles["BodyText2"])
            )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 2. DIAGNOSTIC SUMMARY
    # ══════════════════════════════════════════
    story.append(Paragraph("2. Pre-Healing Diagnostic", styles["SectionHeader"]))

    diag_id = diagnostic_data.get("diagnostic_id", "N/A")
    diag_time = diagnostic_data.get("timestamp", "N/A")
    diag_status = diagnostic_data.get("overall_status", "unknown")

    diag_rows = [
        ["Diagnostic ID", diag_id],
        ["Timestamp", diag_time],
        ["Status", diag_status],
        ["Issues Found", str(diagnostic_data.get("issue_count", 0))],
    ]

    story.append(
        _make_table(
            ["Parameter", "Value"],
            diag_rows,
            col_widths=[50 * mm, 120 * mm],
        )
    )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 3. HEALING SCRIPT DETAILS
    # ══════════════════════════════════════════
    story.append(Paragraph("3. Healing Script Details", styles["SectionHeader"]))

    script_info_map = {
        "auto_db_userstoremanagement": {
            "name": "Userstore Management",
            "risk": "MEDIUM (6 points)",
            "purpose": "Reconfigure HANA userstore connectivity"
        },
        "auto_db_metadata": {
            "name": "Database Metadata",
            "risk": "MEDIUM-HIGH (8 points)",
            "purpose": "Fix backup paths, trace permissions, DB parameters"
        },
        "auto_db_dbintegrations": {
            "name": "DB Integrations",
            "risk": "HIGH (12 points)",
            "purpose": "Configure OS-level settings (swappiness, THP, ASLR)"
        },
        "auto_db_eligibility": {
            "name": "DB Eligibility",
            "risk": "MEDIUM (6 points)",
            "purpose": "Validate and fix database eligibility criteria"
        },
    }

    script_info = script_info_map.get(script_name, {
        "name": script_name,
        "risk": "UNKNOWN",
        "purpose": "Unknown healing script"
    })

    script_rows = [
        ["Script Name", script_name],
        ["Display Name", script_info["name"]],
        ["Risk Level", script_info["risk"]],
        ["Purpose", script_info["purpose"]],
        ["Approval Required", "YES"],
    ]

    story.append(
        _make_table(
            ["Parameter", "Value"],
            script_rows,
            col_widths=[50 * mm, 120 * mm],
        )
    )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 4. CHANGES MADE
    # ══════════════════════════════════════════
    story.append(Paragraph("4. Changes Applied", styles["SectionHeader"]))

    changes = healing_data.get("changes_made", [])
    if changes:
        for i, change in enumerate(changes, 1):
            story.append(
                Paragraph(f"{i}. {change}", styles["BodyText2"])
            )
    else:
        story.append(
            Paragraph("No changes documented.", styles["BodyText2"])
        )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 5. EXECUTION LOG
    # ══════════════════════════════════════════
    story.append(Paragraph("5. Execution Log", styles["SectionHeader"]))

    exec_result = healing_data.get("execution_result", {})
    if isinstance(exec_result, dict):
        exec_status = exec_result.get("status", "unknown")
        exec_message = exec_result.get("message", "No message")

        story.append(
            Paragraph(f"<b>Status:</b> {exec_status}", styles["BodyText2"])
        )
        story.append(
            Paragraph(f"<b>Message:</b> {exec_message}", styles["BodyText2"])
        )

        # Execution steps
        steps = exec_result.get("steps", [])
        if steps:
            story.append(Paragraph("<b>Execution Steps:</b>", styles["SubHeader"]))
            for step in steps:
                story.append(
                    Paragraph(f"• {step}", styles["BodyText2"])
                )
    else:
        story.append(
            Paragraph(str(exec_result), styles["CodeBlock"])
        )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 6. VERIFICATION RESULTS
    # ══════════════════════════════════════════
    story.append(Paragraph("6. Verification Results", styles["SectionHeader"]))

    if verification_data:
        verify_status = verification_data.get("overall_status", "unknown")
        story.append(_status_text(f"Verification: {verify_status}", styles))

        checks = verification_data.get("checks_performed", [])
        if checks:
            verify_rows = []
            for check in checks:
                verify_rows.append([
                    check.get("check_name", ""),
                    check.get("result", ""),
                    check.get("message", "")[:60],
                ])
            if verify_rows:
                story.append(
                    _make_table(
                        ["Check", "Result", "Details"],
                        verify_rows,
                        col_widths=[45 * mm, 30 * mm, 95 * mm],
                    )
                )

        issues_remaining = verification_data.get("issues_remaining", [])
        if issues_remaining:
            story.append(Paragraph("<b>Remaining Issues:</b>", styles["SubHeader"]))
            for issue in issues_remaining:
                story.append(
                    Paragraph(f"• {issue}", styles["StatusWarn"])
                )
    else:
        story.append(
            Paragraph(
                "Verification not performed or data not available.",
                styles["BodyText2"],
            )
        )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 7. RECOMMENDATIONS
    # ══════════════════════════════════════════
    recommendations = healing_data.get("recommendations", [])
    if recommendations:
        story.append(Paragraph("7. Recommendations", styles["SectionHeader"]))
        for i, rec in enumerate(recommendations, 1):
            story.append(
                Paragraph(f"{i}. {rec}", styles["BodyText2"])
            )

    # ── Footer ──
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", color=lightgrey, thickness=0.5))
    story.append(
        Paragraph(
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; "
            f"HANA Sentinel Instance Healing &nbsp;|&nbsp; Instance: {instance} &nbsp;|&nbsp; "
            f"Certificate: {certificate_id[:8]}",
            styles["Footer"],
        )
    )

    # Build PDF
    try:
        doc.build(
            story, onFirstPage=_add_header_footer, onLaterPages=_add_header_footer
        )
        file_size = os.path.getsize(filepath)
        logger.info("Instance healing report generated: %s (%d bytes)", filepath, file_size)
        return {
            "status": "success",
            "report_path": filepath,
            "report_filename": filename,
            "report_size": file_size,
            "timestamp": ts,
            "certificate_id": certificate_id,
        }
    except Exception as exc:
        logger.error("Failed to generate instance healing report: %s", exc)
        return {
            "status": "error",
            "error_message": str(exc),
        }
