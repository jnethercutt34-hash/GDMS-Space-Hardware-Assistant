"""Router for Phase 7 — Schematic DRC (Design Rule Check)."""
import logging

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from models.schematic_drc import (
    DRCReport,
    DRCViolation,
    NetlistSummary,
    Severity,
)
from services.netlist_parser import parse_netlist
from services.drc_rules_engine import run_deterministic_rules
from services.drc_ai_checker import run_ai_checks

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_report(violations, netlist) -> DRCReport:
    """Compute counts and build DRCReport from violations + netlist."""
    error_count = sum(1 for v in violations if v.severity == Severity.Error)
    warning_count = sum(1 for v in violations if v.severity == Severity.Warning)
    info_count = sum(1 for v in violations if v.severity == Severity.Info)
    total_rules_checked = 13  # 8 general + 5 space-compliance deterministic rules
    pass_count = max(total_rules_checked - len(set(v.rule_id for v in violations)), 0)

    if error_count > 0:
        overall = "FAIL"
    elif warning_count > 0:
        overall = "WARNING"
    else:
        overall = "PASS"

    summary = NetlistSummary(
        component_count=len(netlist.components),
        net_count=len(netlist.nets),
        power_net_count=len(netlist.power_nets),
        ground_net_count=len(netlist.ground_nets),
    )

    return DRCReport(
        netlist_summary=summary,
        violations=violations,
        pass_count=pass_count,
        warning_count=warning_count,
        error_count=error_count,
        info_count=info_count,
        overall_status=overall,
    )


# ---------------------------------------------------------------------------
# POST /api/drc/upload-netlist — parse only (no DRC)
# ---------------------------------------------------------------------------

@router.post("/drc/upload-netlist")
async def upload_netlist(file: UploadFile = File(...)):
    """Parse a netlist file and return the parsed structure.

    Accepts .asc (Xpedition), .csv, or OrCAD format.
    """
    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    try:
        netlist = parse_netlist(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Netlist parsing failed")
        raise HTTPException(status_code=500, detail=f"Parsing failed: {exc}")

    return netlist.model_dump()


# ---------------------------------------------------------------------------
# POST /api/drc/analyze — full DRC (deterministic + AI)
# ---------------------------------------------------------------------------

@router.post("/drc/analyze")
async def analyze(file: UploadFile = File(...)):
    """Parse netlist and run full DRC analysis (deterministic + AI).

    Returns a DRCReport with all violations, counts, and overall status.
    """
    contents = await file.read()
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError:
        text = contents.decode("latin-1")

    try:
        netlist = parse_netlist(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Netlist parsing failed")
        raise HTTPException(status_code=500, detail=f"Parsing failed: {exc}")

    # Deterministic rules
    violations = run_deterministic_rules(netlist)

    # AI checks (best-effort)
    try:
        ai_violations = run_ai_checks(netlist)
        violations.extend(ai_violations)
    except Exception:
        logger.warning("AI DRC checks failed — continuing with deterministic results only")

    report = _build_report(violations, netlist)
    return report.model_dump()


# ---------------------------------------------------------------------------
# POST /api/drc/export — export DRC report
# ---------------------------------------------------------------------------

class DRCExportRequest(BaseModel):
    report: DRCReport
    format: str = "markdown"  # "csv" or "markdown"


@router.post("/drc/export")
async def export(payload: DRCExportRequest):
    """Export a DRC report as CSV or Markdown."""
    fmt = payload.format.lower()
    report = payload.report

    if fmt == "csv":
        lines = ["Rule ID,Severity,Category,Message,Affected Nets,Affected Components,Recommendation,AI Generated"]
        for v in report.violations:
            nets = "; ".join(v.affected_nets)
            comps = "; ".join(v.affected_components)
            msg = v.message.replace('"', '""')
            rec = v.recommendation.replace('"', '""')
            lines.append(
                f'{v.rule_id},{v.severity.value},{v.category.value},"{msg}","{nets}","{comps}","{rec}",{v.ai_generated}'
            )
        content = "\n".join(lines)
        return PlainTextResponse(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="drc_report.csv"'},
        )

    elif fmt == "markdown":
        lines = [
            "# Schematic DRC Report",
            "",
            f"**Overall Status:** {report.overall_status}",
            "",
            f"| Metric | Count |",
            f"|--------|-------|",
            f"| Components | {report.netlist_summary.component_count} |",
            f"| Nets | {report.netlist_summary.net_count} |",
            f"| Power Nets | {report.netlist_summary.power_net_count} |",
            f"| Ground Nets | {report.netlist_summary.ground_net_count} |",
            f"| Errors | {report.error_count} |",
            f"| Warnings | {report.warning_count} |",
            f"| Info | {report.info_count} |",
            f"| Rules Passed | {report.pass_count} |",
            "",
            "## Violations",
            "",
        ]

        if not report.violations:
            lines.append("✅ No violations found.")
        else:
            for v in report.violations:
                icon = "🔴" if v.severity == Severity.Error else "🟡" if v.severity == Severity.Warning else "🔵"
                ai_tag = " *(AI)*" if v.ai_generated else ""
                lines.append(f"### {icon} {v.rule_id} — {v.category.value}{ai_tag}")
                lines.append(f"**Severity:** {v.severity.value}")
                lines.append(f"**Message:** {v.message}")
                if v.affected_nets:
                    lines.append(f"**Nets:** {', '.join(v.affected_nets)}")
                if v.affected_components:
                    lines.append(f"**Components:** {', '.join(v.affected_components)}")
                lines.append(f"**Recommendation:** {v.recommendation}")
                lines.append("")

        content = "\n".join(lines)
        return PlainTextResponse(
            content=content,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="drc_report.md"'},
        )

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown export format: '{fmt}'. Use 'csv' or 'markdown'.",
        )
