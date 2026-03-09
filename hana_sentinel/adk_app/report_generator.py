"""
PDF Report Generator — Timestamped HANA Sentinel analysis reports.

Generates professional PDF reports summarizing each monitoring cycle:
  - System overview
  - Errors detected & fixed
  - Health metrics
  - Changes applied
  - Verification results
  - Recommendations

Uses reportlab for PDF generation. Output: reports/hana_sentinel_YYYYMMDD_HHMMSS.pdf
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

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Color Palette
# ──────────────────────────────────────────────
BRAND_PRIMARY = HexColor("#1a73e8")  # Google Blue
BRAND_DARK = HexColor("#0d47a1")  # Dark Blue
BRAND_ACCENT = HexColor("#34a853")  # Green
BRAND_WARN = HexColor("#ea4335")  # Red
BRAND_ORANGE = HexColor("#fbbc04")  # Amber
BRAND_BG = HexColor("#f8f9fa")  # Light grey bg
TABLE_HEADER_BG = HexColor("#e8eaf6")  # Soft indigo
TABLE_ALT_BG = HexColor("#f5f5f5")  # Zebra stripe

# ──────────────────────────────────────────────
# Report directory
# ──────────────────────────────────────────────
REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports",
)


def _ensure_reports_dir():
    """Create reports directory if it doesn't exist."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    return REPORTS_DIR


def _get_styles():
    """Build custom paragraph styles."""
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=22,
            textColor=BRAND_DARK,
            spaceAfter=6 * mm,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            fontSize=11,
            textColor=grey,
            alignment=TA_CENTER,
            spaceAfter=10 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeader",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=BRAND_PRIMARY,
            spaceBefore=8 * mm,
            spaceAfter=4 * mm,
            borderWidth=1,
            borderColor=BRAND_PRIMARY,
            borderPadding=(0, 0, 2, 0),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SubHeader",
            parent=styles["Heading3"],
            fontSize=11,
            textColor=BRAND_DARK,
            spaceBefore=4 * mm,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyText2",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="StatusOK",
            parent=styles["Normal"],
            fontSize=10,
            textColor=BRAND_ACCENT,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="StatusError",
            parent=styles["Normal"],
            fontSize=10,
            textColor=BRAND_WARN,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="StatusWarn",
            parent=styles["Normal"],
            fontSize=10,
            textColor=BRAND_ORANGE,
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            parent=styles["Code"],
            fontSize=7,
            leading=9,
            backColor=BRAND_BG,
            borderWidth=0.5,
            borderColor=lightgrey,
            borderPadding=4,
            spaceAfter=3 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Footer",
            parent=styles["Normal"],
            fontSize=7,
            textColor=grey,
            alignment=TA_CENTER,
        )
    )

    return styles


def _make_table(headers: List[str], rows: List[List[str]], col_widths=None) -> Table:
    """Create a styled table with zebra striping."""
    data = [headers] + rows
    tbl = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), BRAND_DARK),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        # Body
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        # Grid
        ("GRID", (0, 0), (-1, -1), 0.5, lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ]

    # Zebra striping
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_BG))

    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _status_text(status: str, styles) -> Paragraph:
    """Return a colored status paragraph."""
    s = status.upper()
    if s in ("SUCCESS", "OK", "PASS", "PASSED", "GREEN", "YES"):
        return Paragraph(f"✓ {status}", styles["StatusOK"])
    elif s in ("ERROR", "FAIL", "FAILED", "CRITICAL", "RED", "NO"):
        return Paragraph(f"✗ {status}", styles["StatusError"])
    else:
        return Paragraph(f"⚠ {status}", styles["StatusWarn"])


def _add_header_footer(canvas, doc):
    """Page header/footer callback."""
    canvas.saveState()
    # Header line
    canvas.setStrokeColor(BRAND_PRIMARY)
    canvas.setLineWidth(1.5)
    canvas.line(15 * mm, A4[1] - 12 * mm, A4[0] - 15 * mm, A4[1] - 12 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(grey)
    canvas.drawString(
        15 * mm, A4[1] - 10 * mm, "HANA Sentinel — Autonomous Monitoring Report"
    )
    canvas.drawRightString(A4[0] - 15 * mm, A4[1] - 10 * mm, f"Page {doc.page}")
    # Footer
    canvas.setLineWidth(0.5)
    canvas.line(15 * mm, 12 * mm, A4[0] - 15 * mm, 12 * mm)
    canvas.drawCentredString(
        A4[0] / 2,
        8 * mm,
        "Generated by HANA Sentinel Agent — Confidential",
    )
    canvas.restoreState()


# ──────────────────────────────────────────────
# Main Report Generator
# ──────────────────────────────────────────────


def generate_report(cycle_data: Dict[str, Any], timestamp: str = "") -> dict:
    """Generate a PDF report from a monitoring cycle's data.

    Args:
        cycle_data: Dict with keys matching the agent loop output:
            - sid: HANA System ID
            - cycle: Cycle number
            - timestamp: ISO timestamp
            - phases: dict of phase results
                - analysis: run_analysis_script output
                - errors: parse_analysis_errors output
                - schema_discovery: discover_hana_schema output
                - fixes: fix_analysis_script output
                - health: dict of health check results
                - verification: verification results
                - learning: learning store results
            - overall_status: success/partial/error
            - recommendations: list of recommendation strings
        timestamp: Override timestamp string (default: now).

    Returns:
        dict: status, report_path, report_size.
    """
    _ensure_reports_dir()
    styles = _get_styles()

    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_display = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sid = cycle_data.get("sid", "HXE")
    cycle_num = cycle_data.get("cycle", 1)
    filename = f"hana_sentinel_{sid}_{ts}.pdf"
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
    story.append(Paragraph("HANA Sentinel", styles["ReportTitle"]))
    story.append(Paragraph("Autonomous Monitoring Report", styles["ReportSubtitle"]))
    story.append(
        Paragraph(
            f"SID: <b>{sid}</b> &nbsp;|&nbsp; Cycle: <b>#{cycle_num}</b> &nbsp;|&nbsp; "
            f"Timestamp: <b>{ts_display}</b>",
            styles["BodyText2"],
        )
    )
    story.append(HRFlowable(width="100%", color=BRAND_PRIMARY, thickness=1.5))
    story.append(Spacer(1, 4 * mm))

    # ── Overall Status ──
    overall = cycle_data.get("overall_status", "unknown")
    story.append(_status_text(f"Overall Status: {overall}", styles))
    story.append(Spacer(1, 4 * mm))

    phases = cycle_data.get("phases", {})

    # ══════════════════════════════════════════
    # 1. SYSTEM OVERVIEW
    # ══════════════════════════════════════════
    story.append(Paragraph("1. System Overview", styles["SectionHeader"]))

    analysis = phases.get("analysis", {})
    overview_rows = [
        ["System ID", sid],
        ["Script Path", analysis.get("script_path", "/home/devstar3254/analysis.sh")],
        ["Cycle Number", str(cycle_num)],
        ["Analysis Output Size", f"{analysis.get('output_length', 0):,} chars"],
        ["Analysis Status", analysis.get("status", "N/A")],
    ]
    story.append(
        _make_table(
            ["Parameter", "Value"], overview_rows, col_widths=[50 * mm, 120 * mm]
        )
    )

    # ══════════════════════════════════════════
    # 2. ERRORS DETECTED
    # ══════════════════════════════════════════
    errors_data = phases.get("errors", {})
    error_count = errors_data.get("error_count", 0)

    story.append(Paragraph("2. Errors Detected", styles["SectionHeader"]))
    story.append(
        Paragraph(
            errors_data.get("summary", f"{error_count} error(s) found"),
            styles["BodyText2"],
        )
    )

    errors_list = errors_data.get("errors", [])
    if errors_list:
        err_rows = []
        for err in errors_list:
            err_type = err.get("type", "")
            if err_type == "invalid_column":
                err_rows.append(
                    [
                        err.get("bad_column", ""),
                        err.get("view_name", "(unknown)"),
                        "Invalid Column",
                        (err.get("original_query", "")[:80] + "...")
                        if len(err.get("original_query", "")) > 80
                        else err.get("original_query", ""),
                    ]
                )
            elif err_type == "dispatch_bug":
                err_rows.append(
                    [
                        "all → run_all",
                        "analysis.sh",
                        "Dispatch Bug",
                        err.get("error_message", ""),
                    ]
                )
        if err_rows:
            story.append(
                _make_table(
                    ["Column/Item", "View/File", "Type", "Details"],
                    err_rows,
                    col_widths=[35 * mm, 40 * mm, 30 * mm, 65 * mm],
                )
            )
    else:
        story.append(
            Paragraph("No errors detected — all queries passed.", styles["StatusOK"])
        )

    # ══════════════════════════════════════════
    # 3. FIXES APPLIED
    # ══════════════════════════════════════════
    fixes_data = phases.get("fixes", {})
    fixes_list = fixes_data.get("fixes_applied", [])

    story.append(Paragraph("3. Fixes Applied", styles["SectionHeader"]))

    if fixes_list:
        fix_rows = []
        for fix in fixes_list:
            fix_rows.append(
                [
                    fix.get("type", ""),
                    fix.get("description", ""),
                    (fix.get("original_query", "")[:60] + "...")
                    if len(fix.get("original_query", "")) > 60
                    else fix.get("original_query", ""),
                    (fix.get("fixed_query", "")[:60] + "...")
                    if len(fix.get("fixed_query", "")) > 60
                    else fix.get("fixed_query", ""),
                ]
            )
        story.append(
            _make_table(
                ["Type", "Description", "Before", "After"],
                fix_rows,
                col_widths=[25 * mm, 50 * mm, 47 * mm, 47 * mm],
            )
        )
        story.append(
            Paragraph(
                f"Total: <b>{fixes_data.get('applied_count', len(fixes_list))}</b> fixes applied. "
                f"Backup: <b>{fixes_data.get('backup_path', 'analysis.sh.bak')}</b>",
                styles["BodyText2"],
            )
        )
    else:
        story.append(
            Paragraph(
                "No fixes were needed or applied this cycle.", styles["BodyText2"]
            )
        )

    # Unfixed errors
    unfixed = fixes_data.get("unfixed_errors", [])
    if unfixed:
        story.append(
            Paragraph("Unfixed Errors (require manual review):", styles["SubHeader"])
        )
        for uf in unfixed:
            story.append(
                Paragraph(
                    f"• {uf.get('bad_column', '')} in {uf.get('view_name', '')}: {uf.get('reason', 'unknown')}",
                    styles["BodyText2"],
                )
            )

    # ══════════════════════════════════════════
    # 4. HEALTH METRICS
    # ══════════════════════════════════════════
    health = phases.get("health", {})

    story.append(Paragraph("4. Health Metrics", styles["SectionHeader"]))

    if health:
        # Services
        services = health.get("services", {})
        if services.get("status") == "success" and services.get("data"):
            story.append(Paragraph("Services", styles["SubHeader"]))
            svc_rows = []
            for row in services["data"][:15]:
                if isinstance(row, dict):
                    svc_rows.append(
                        [
                            row.get("SERVICE_NAME", ""),
                            row.get("ACTIVE_STATUS", row.get("IS_ACTIVE", "")),
                            row.get("HOST", ""),
                            str(row.get("PORT", "")),
                        ]
                    )
                elif isinstance(row, (list, tuple)):
                    svc_rows.append([str(c) for c in row[:4]])
            if svc_rows:
                story.append(
                    _make_table(["Service", "Status", "Host", "Port"], svc_rows)
                )

        # Memory
        memory = health.get("memory", {})
        if memory.get("status") == "success" and memory.get("data"):
            story.append(Paragraph("Memory", styles["SubHeader"]))
            mem_rows = []
            for row in memory["data"][:5]:
                if isinstance(row, dict):
                    mem_rows.append(
                        [
                            row.get("SERVICE_NAME", ""),
                            str(row.get("TOTAL_MEMORY_USED_SIZE", "")),
                            str(row.get("EFFECTIVE_ALLOCATION_LIMIT", "")),
                        ]
                    )
                elif isinstance(row, (list, tuple)):
                    mem_rows.append([str(c) for c in row[:3]])
            if mem_rows:
                story.append(
                    _make_table(["Service", "Used (bytes)", "Limit (bytes)"], mem_rows)
                )

        # Disk / Storage
        storage = health.get("storage", {})
        if storage:
            story.append(Paragraph("Storage", styles["SubHeader"]))
            story.append(
                Paragraph(
                    storage.get("summary", str(storage))[:500],
                    styles["CodeBlock"],
                )
            )
            alerts = storage.get("alerts", [])
            for alert in alerts:
                story.append(Paragraph(f"⚠ {alert}", styles["StatusWarn"]))

        # Alerts
        alerts_data = health.get("alerts", {})
        if alerts_data.get("status") == "success" and alerts_data.get("data"):
            story.append(Paragraph("Active Alerts", styles["SubHeader"]))
            alert_rows = []
            for row in alerts_data["data"][:10]:
                if isinstance(row, dict):
                    alert_rows.append(
                        [
                            str(row.get("ALERT_ID", "")),
                            str(row.get("ALERT_RATING", "")),
                            row.get("ALERT_NAME", row.get("ALERT_DETAILS", ""))[:60],
                        ]
                    )
                elif isinstance(row, (list, tuple)):
                    alert_rows.append([str(c) for c in row[:3]])
            if alert_rows:
                story.append(_make_table(["Alert ID", "Rating", "Details"], alert_rows))

        # Connections
        conns = health.get("connections", {})
        if conns.get("status") == "success":
            story.append(Paragraph("Connections", styles["SubHeader"]))
            story.append(
                Paragraph(
                    f"Total connections: {conns.get('count', 'N/A')}",
                    styles["BodyText2"],
                )
            )
    else:
        story.append(
            Paragraph(
                "Health metrics were not collected this cycle.", styles["BodyText2"]
            )
        )

    # ══════════════════════════════════════════
    # 5. SCHEMA DISCOVERY
    # ══════════════════════════════════════════
    schema = phases.get("schema_discovery", {})
    if schema and schema.get("schema"):
        story.append(Paragraph("5. Schema Discovery", styles["SectionHeader"]))
        for view_name, info in schema.get("schema", {}).items():
            cols = info.get("columns", [])
            story.append(
                Paragraph(
                    f"<b>{info.get('schema', 'SYS')}.{view_name}</b>: "
                    f"{info.get('column_count', len(cols))} columns discovered",
                    styles["BodyText2"],
                )
            )
            if cols:
                cols_text = ", ".join(cols[:30])
                if len(cols) > 30:
                    cols_text += f"... (+{len(cols) - 30} more)"
                story.append(Paragraph(cols_text, styles["CodeBlock"]))

    # ══════════════════════════════════════════
    # 6. VERIFICATION
    # ══════════════════════════════════════════
    verification = phases.get("verification", {})
    story.append(Paragraph("6. Verification", styles["SectionHeader"]))

    if verification:
        v_status = verification.get("status", "unknown")
        story.append(_status_text(f"Verification: {v_status}", styles))

        rerun_errors = verification.get("rerun_errors", {})
        if rerun_errors:
            remaining = rerun_errors.get("error_count", 0)
            story.append(
                Paragraph(
                    f"Remaining errors after fixes: <b>{remaining}</b>",
                    styles["BodyText2"],
                )
            )
    else:
        story.append(
            Paragraph("Verification not performed this cycle.", styles["BodyText2"])
        )

    # ══════════════════════════════════════════
    # 7. LEARNING STORE
    # ══════════════════════════════════════════
    learning = phases.get("learning", {})
    if learning:
        story.append(Paragraph("7. Learning Updates", styles["SectionHeader"]))
        story.append(
            Paragraph(
                f"Status: {learning.get('status', 'N/A')}",
                styles["BodyText2"],
            )
        )
        new_cmds = learning.get("commands_added", [])
        if new_cmds:
            story.append(
                Paragraph(
                    f"New commands learned: {len(new_cmds)}",
                    styles["BodyText2"],
                )
            )

    # ══════════════════════════════════════════
    # 8. RECOMMENDATIONS
    # ══════════════════════════════════════════
    recommendations = cycle_data.get("recommendations", [])
    if recommendations:
        story.append(Paragraph("8. Recommendations", styles["SectionHeader"]))
        for i, rec in enumerate(recommendations, 1):
            story.append(Paragraph(f"{i}. {rec}", styles["BodyText2"]))

    # ── Footer spacer ──
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", color=lightgrey, thickness=0.5))
    story.append(
        Paragraph(
            f"Report generated: {ts_display} &nbsp;|&nbsp; "
            f"HANA Sentinel v1.0 &nbsp;|&nbsp; Cycle #{cycle_num}",
            styles["Footer"],
        )
    )

    # Build PDF
    try:
        doc.build(
            story, onFirstPage=_add_header_footer, onLaterPages=_add_header_footer
        )
        file_size = os.path.getsize(filepath)
        logger.info("Report generated: %s (%d bytes)", filepath, file_size)
        return {
            "status": "success",
            "report_path": filepath,
            "report_filename": filename,
            "report_size": file_size,
            "timestamp": ts,
        }
    except Exception as exc:
        logger.error("Failed to generate report: %s", exc)
        return {
            "status": "error",
            "error_message": str(exc),
        }


# ──────────────────────────────────────────────
# Instance Monitoring Report Generators
# ──────────────────────────────────────────────


def generate_instance_diagnostic_report(diagnostic_data: Dict[str, Any]) -> dict:
    """Generate a PDF report for instance diagnostic results.

    Args:
        diagnostic_data: Dict containing:
            - diagnostic_id: Unique identifier
            - timestamp: ISO timestamp
            - instance_name: GCP instance name (e.g., vlgdbzo3)
            - sid: HANA SID (e.g., ZO3)
            - instance_number: HANA instance number
            - checks: Dict of diagnostic check results
            - issues_detected: List of issue descriptions
            - overall_status: ok/warning/critical
            - issue_count: Number of issues found

    Returns:
        dict: status, report_path, report_size
    """
    _ensure_reports_dir()
    styles = _get_styles()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_display = diagnostic_data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    instance = diagnostic_data.get("instance_name", "unknown")
    sid = diagnostic_data.get("sid", "unknown")
    diagnostic_id = diagnostic_data.get("diagnostic_id", "unknown")

    filename = f"instance_diagnostic_{instance}_{ts}.pdf"
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
    story.append(Paragraph("HANA Instance Diagnostic Report", styles["ReportTitle"]))
    story.append(Paragraph(f"Instance: {instance} (SID: {sid})", styles["ReportSubtitle"]))
    story.append(
        Paragraph(
            f"Diagnostic ID: <b>{diagnostic_id}</b> &nbsp;|&nbsp; "
            f"Timestamp: <b>{ts_display}</b>",
            styles["BodyText2"],
        )
    )
    story.append(HRFlowable(width="100%", color=BRAND_PRIMARY, thickness=1.5))
    story.append(Spacer(1, 4 * mm))

    # ── Overall Status ──
    overall = diagnostic_data.get("overall_status", "unknown")
    issue_count = diagnostic_data.get("issue_count", 0)
    story.append(_status_text(f"Overall Status: {overall}", styles))
    story.append(
        Paragraph(
            f"Issues Detected: <b>{issue_count}</b>",
            styles["BodyText2"],
        )
    )
    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 1. SYSTEM INFORMATION
    # ══════════════════════════════════════════
    story.append(Paragraph("1. System Information", styles["SectionHeader"]))

    sys_rows = [
        ["Instance Name", instance],
        ["SID", sid],
        ["Instance Number", str(diagnostic_data.get("instance_number", "unknown"))],
        ["Diagnostic ID", diagnostic_id],
        ["Timestamp", ts_display],
    ]
    story.append(
        _make_table(
            ["Parameter", "Value"], sys_rows, col_widths=[50 * mm, 120 * mm]
        )
    )

    # ══════════════════════════════════════════
    # 2. ISSUES DETECTED
    # ══════════════════════════════════════════
    issues = diagnostic_data.get("issues_detected", [])

    story.append(Paragraph("2. Issues Detected", styles["SectionHeader"]))

    if issues:
        for i, issue in enumerate(issues, 1):
            story.append(
                Paragraph(
                    f"{i}. {issue}",
                    styles["StatusError"],
                )
            )
    else:
        story.append(
            Paragraph(
                "✓ No issues detected — all diagnostic checks passed.",
                styles["StatusOK"],
            )
        )

    story.append(Spacer(1, 4 * mm))

    # ══════════════════════════════════════════
    # 3. DIAGNOSTIC CHECKS
    # ══════════════════════════════════════════
    checks = diagnostic_data.get("checks", {})

    story.append(Paragraph("3. Diagnostic Checks", styles["SectionHeader"]))

    if checks:
        check_rows = []
        for check_name, check_result in checks.items():
            severity = check_result.get("severity", "unknown")
            message = check_result.get("message", "No details")

            # Severity icon
            if severity == "ok":
                severity_display = "✓ OK"
            elif severity == "warning":
                severity_display = "⚠ Warning"
            elif severity == "critical":
                severity_display = "✗ Critical"
            else:
                severity_display = "? Unknown"

            check_rows.append([
                check_name.replace("_", " ").title(),
                severity_display,
                message[:80] + ("..." if len(message) > 80 else "")
            ])

        if check_rows:
            story.append(
                _make_table(
                    ["Check", "Status", "Details"],
                    check_rows,
                    col_widths=[45 * mm, 30 * mm, 95 * mm],
                )
            )
    else:
        story.append(
            Paragraph(
                "No diagnostic checks were performed.",
                styles["BodyText2"],
            )
        )

    # ══════════════════════════════════════════
    # 4. DETAILED CHECK RESULTS
    # ══════════════════════════════════════════
    story.append(Paragraph("4. Detailed Results", styles["SectionHeader"]))

    for check_name, check_result in checks.items():
        story.append(
            Paragraph(
                f"<b>{check_name.replace('_', ' ').title()}</b>",
                styles["SubHeader"],
            )
        )

        # Process Status
        if check_name == "process_status" and check_result.get("processes"):
            proc_rows = []
            for proc in check_result["processes"]:
                proc_rows.append([
                    proc.get("name", ""),
                    proc.get("status", ""),
                    proc.get("pid", ""),
                ])
            if proc_rows:
                story.append(
                    _make_table(
                        ["Process", "Status", "PID"],
                        proc_rows,
                        col_widths=[60 * mm, 40 * mm, 70 * mm],
                    )
                )

        # Disk Usage
        elif check_name == "disk_usage" and check_result.get("partitions"):
            disk_rows = []
            for part in check_result["partitions"]:
                disk_rows.append([
                    part.get("mount_point", ""),
                    part.get("size", ""),
                    part.get("used", ""),
                    part.get("available", ""),
                    part.get("use_percent", ""),
                ])
            if disk_rows:
                story.append(
                    _make_table(
                        ["Mount Point", "Size", "Used", "Available", "Use %"],
                        disk_rows,
                        col_widths=[50 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm],
                    )
                )

        # Memory Usage
        elif check_name == "memory_usage" and check_result.get("memory_info"):
            mem_info = check_result["memory_info"]
            mem_rows = [
                ["Total", mem_info.get("total", "")],
                ["Used", mem_info.get("used", "")],
                ["Free", mem_info.get("free", "")],
                ["Usage", f"{check_result.get('usage_percent', '')}%"],
            ]
            story.append(
                _make_table(
                    ["Metric", "Value"],
                    mem_rows,
                    col_widths=[50 * mm, 120 * mm],
                )
            )

        # Generic message
        else:
            message = check_result.get("message", "")
            if message:
                story.append(
                    Paragraph(message, styles["BodyText2"])
                )

        story.append(Spacer(1, 2 * mm))

    # ── Footer ──
    story.append(Spacer(1, 10 * mm))
    story.append(HRFlowable(width="100%", color=lightgrey, thickness=0.5))
    story.append(
        Paragraph(
            f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} &nbsp;|&nbsp; "
            f"HANA Sentinel Instance Monitoring &nbsp;|&nbsp; Instance: {instance}",
            styles["Footer"],
        )
    )

    # Build PDF
    try:
        doc.build(
            story, onFirstPage=_add_header_footer, onLaterPages=_add_header_footer
        )
        file_size = os.path.getsize(filepath)
        logger.info("Instance diagnostic report generated: %s (%d bytes)", filepath, file_size)
        return {
            "status": "success",
            "report_path": filepath,
            "report_filename": filename,
            "report_size": file_size,
            "timestamp": ts,
            "report_id": diagnostic_id,
        }
    except Exception as exc:
        logger.error("Failed to generate instance diagnostic report: %s", exc)
        return {
            "status": "error",
            "error_message": str(exc),
        }
