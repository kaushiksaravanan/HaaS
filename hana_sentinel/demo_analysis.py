"""
Demo: Self-Learning Analysis Tools — Full Local Pipeline

This script demonstrates the self-learning analysis flow:
  Phase 1: Parse the known analysis_output.txt for SQL errors
  Phase 2: Show what the agent would discover from the HANA catalog
  Phase 3: Generate fix commands for the broken queries
  Phase 4: Show the corrected queries
"""

import os
import sys
import json

# Setup path
sys.path.insert(0, os.path.dirname(__file__))

from adk_app.tools.analysis_tools import (
    parse_analysis_errors,
    _remove_column_from_select,
    _extract_view_from_query,
)


def print_header(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_phase(num, title):
    print(f"\n{'─' * 70}")
    print(f"  Phase {num}: {title}")
    print(f"{'─' * 70}\n")


def main():
    print_header("HANA Sentinel — Self-Learning Analysis Demo")

    # ── Load the analysis output ──
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "analysis_output.txt"
    )
    if not os.path.exists(output_path):
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "analysis_output.txt"
        )

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8", errors="replace") as fh:
            raw_output = fh.read()
        print(
            f"  Loaded analysis output: {len(raw_output):,} chars from {os.path.basename(output_path)}"
        )
    else:
        print("  [ERROR] analysis_output.txt not found!")
        return

    # ════════════════════════════════════════════
    # PHASE 1: ERROR DETECTION
    # ════════════════════════════════════════════
    print_phase(1, "ERROR DETECTION — Parsing analysis.sh output")

    result = parse_analysis_errors(raw_output)

    print(f"  Status:        {result['status']}")
    print(f"  Errors found:  {result['error_count']}")
    print(f"  Dispatch bug:  {'Yes' if result['has_dispatch_bug'] else 'No'}")
    print(f"  Summary:       {result['summary']}")
    print()

    invalid_cols = [e for e in result["errors"] if e["type"] == "invalid_column"]
    for i, err in enumerate(invalid_cols, 1):
        print(f"  Error {i}:")
        print(f"    Bad column:  {err['bad_column']}")
        print(f"    View:        {err['view_name'] or '(could not determine)'}")
        if err["original_query"]:
            q = err["original_query"]
            print(f"    Query:       {q[:90]}{'...' if len(q) > 90 else ''}")
        print()

    dispatch_bugs = [e for e in result["errors"] if e["type"] == "dispatch_bug"]
    if dispatch_bugs:
        print(f"  Dispatch Bug:")
        print(f"    {dispatch_bugs[0]['error_message']}")
        print(f"    Fix: {dispatch_bugs[0].get('fix', 'N/A')}")
        print()

    # ════════════════════════════════════════════
    # PHASE 2: SCHEMA DISCOVERY (simulated)
    # ════════════════════════════════════════════
    print_phase(2, "SCHEMA DISCOVERY — What the agent would query")

    failing_views = list(set(e["view_name"] for e in invalid_cols if e["view_name"]))
    print(f"  Views to discover: {', '.join(failing_views)}\n")

    for view in failing_views:
        from adk_app.tools.analysis_tools import _VIEW_SCHEMA_MAP

        schema_info = _VIEW_SCHEMA_MAP.get(view, ("?", "?"))
        print(f"  → {schema_info[0]}.{schema_info[1]}")
        print(f"    Agent would run:")
        print(f"    docker exec -u hxeadm hxehana hdbsql -i 90 \\")
        print(f'      "SELECT COLUMN_NAME FROM SYS.TABLE_COLUMNS')
        print(
            f"       WHERE SCHEMA_NAME='{schema_info[0]}' AND TABLE_NAME='{schema_info[1]}'\""
        )
        print()

    # ════════════════════════════════════════════
    # PHASE 3: AUTO-FIX — Generate corrected queries
    # ════════════════════════════════════════════
    print_phase(3, "AUTO-FIX — Generating corrected SQL queries")

    fixes = []
    for err in invalid_cols:
        if not err["original_query"]:
            continue
        original = err["original_query"]
        bad_col = err["bad_column"]
        fixed = _remove_column_from_select(original, bad_col)

        if fixed != original:
            fixes.append(
                {
                    "view": err["view_name"],
                    "bad_column": bad_col,
                    "original": original,
                    "fixed": fixed,
                }
            )
            print(f"  ✓ Fixed: Removed '{bad_col}' from {err['view_name'] or 'query'}")
            print(f"    BEFORE: {original[:80]}...")
            print(f"    AFTER:  {fixed[:80]}...")
            print()
        else:
            print(
                f"  ✗ Could not auto-fix: '{bad_col}' in {err['view_name'] or 'query'}"
            )
            print()

    # ════════════════════════════════════════════
    # PHASE 4: SUMMARY
    # ════════════════════════════════════════════
    print_phase(4, "SUMMARY — What would happen on the VM")

    print(f"  Total errors detected:     {result['error_count']}")
    print(f"  Invalid columns found:     {len(invalid_cols)}")
    print(f"  Auto-fixable queries:      {len(fixes)}")
    print(
        f"  Dispatch bug detected:     {'Yes' if result['has_dispatch_bug'] else 'No'}"
    )
    print()
    print(f"  On the VM, the agent would:")
    print(f"  1. Backup analysis.sh → analysis.sh.bak")
    print(f"  2. Apply {len(fixes)} sed commands to remove invalid columns")
    if result["has_dispatch_bug"]:
        print(f"  3. Fix the 'all' dispatch case to call run_all")
    print(f"  4. Re-run analysis.sh and verify no more errors")
    print(f"  5. Record the fixes in LearningCommandStore for future reference")

    print_header("Demo Complete")
    print(f"  To run the full self-healing loop on the VM, the agent calls:")
    print(f"  → run_and_learn_analysis('HXE', 'all')")
    print()


if __name__ == "__main__":
    main()
