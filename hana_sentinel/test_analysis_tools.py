"""
Test suite for analysis_tools.py — verifies parse_analysis_errors
against the known output from analysis_output.txt.
"""

import os
import sys

# Add parent to path so we can import the tools directly
sys.path.insert(0, os.path.dirname(__file__))

from adk_app.tools.analysis_tools import (
    parse_analysis_errors,
    _remove_column_from_select,
    _extract_view_from_query,
)


def test_parse_analysis_errors():
    """Test error parsing against the known analysis_output.txt content."""

    # Read the actual analysis output
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "analysis_output.txt"
    )
    if not os.path.exists(output_path):
        # Try alternate location
        output_path = os.path.join(
            os.path.dirname(__file__), "..", "analysis_output.txt"
        )

    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8", errors="replace") as fh:
            output = fh.read()
        print(f"[OK] Read {len(output)} chars from {output_path}")
    else:
        # Use inline sample matching the known errors
        print("[WARN] analysis_output.txt not found, using inline sample")
        output = """
+ run_hdbsql 'SELECT DATABASE_NAME, VERSION, USAGE, START_TIME, ACTIVE_STATUS FROM SYS.M_DATABASE'
* 259: invalid column name: ACTIVE_STATUS  SQLSTATE: HY000
+ run_hdbsql 'SELECT TOP 10 ENTRY_ID, BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, SYS_START_TIME, SYS_END_TIME, ROUND(BACKUP_SIZE / 1024 / 1024, 2) AS SIZE_MB, MESSAGE FROM SYS.M_BACKUP_CATALOG ORDER BY SYS_START_TIME DESC'
* 259: invalid column name: BACKUP_SIZE  SQLSTATE: HY000
+ run_hdbsql 'SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS, ALERT_TIMESTAMP, HOST FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3 ORDER BY ALERT_TIMESTAMP DESC'
* 259: invalid column name: HOST  SQLSTATE: HY000
+ run_hdbsql 'SELECT TOP 10 TRANSACTION_ID, TRANSACTION_STATUS, START_TIME, IDLE_TIME, CONNECTION_ID, TRANSACTION_TYPE FROM SYS.M_TRANSACTIONS WHERE TRANSACTION_STATUS = 0 ORDER BY IDLE_TIME DESC'
* 259: invalid column name: IDLE_TIME  SQLSTATE: HY000
+ run_hdbsql 'SELECT TOP 20 SCHEMA_NAME, TABLE_NAME, TABLE_TYPE, RECORD_COUNT, ROUND(MEMORY_SIZE_IN_TOTAL / 1024 / 1024, 2) AS SIZE_MB FROM SYS.M_CS_TABLES ORDER BY MEMORY_SIZE_IN_TOTAL DESC'
* 259: invalid column name: TABLE_TYPE  SQLSTATE: HY000
+ all
all: command not found
"""

    result = parse_analysis_errors(output)

    print(f"\n--- Parse Results ---")
    print(f"Status:   {result['status']}")
    print(f"Errors:   {result['error_count']}")
    print(f"Summary:  {result['summary']}")
    print(f"Dispatch: {result['has_dispatch_bug']}")

    for err in result["errors"]:
        print(
            f"\n  [{err['type']}] column={err.get('bad_column', '')} "
            f"view={err.get('view_name', '')} line={err.get('line_number', '')}"
        )

    # Assertions
    invalid_cols = [e for e in result["errors"] if e["type"] == "invalid_column"]
    expected_bad_cols = {
        "ACTIVE_STATUS",
        "BACKUP_SIZE",
        "HOST",
        "IDLE_TIME",
        "TABLE_TYPE",
    }
    found_bad_cols = {e["bad_column"] for e in invalid_cols}

    missing = expected_bad_cols - found_bad_cols
    extra = found_bad_cols - expected_bad_cols

    if missing:
        print(f"\n[FAIL] Missing expected bad columns: {missing}")
    if extra:
        print(f"\n[WARN] Unexpected bad columns found: {extra}")
    if not missing and not extra:
        print(f"\n[PASS] All {len(expected_bad_cols)} expected bad columns detected")

    assert not missing, f"Missing columns: {missing}"
    assert result["has_dispatch_bug"], "dispatch bug should be detected"
    print("[PASS] Dispatch bug detected")


def test_extract_view_from_query():
    """Test the helper that extracts view names from SQL queries."""
    cases = [
        ("SELECT * FROM SYS.M_DATABASE", "M_DATABASE"),
        (
            "SELECT * FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS",
            "STATISTICS_CURRENT_ALERTS",
        ),
        ("SELECT TOP 10 A FROM SYS.M_TRANSACTIONS WHERE X = 1", "M_TRANSACTIONS"),
        ("SELECT A FROM SYS.M_CS_TABLES ORDER BY B", "M_CS_TABLES"),
    ]
    all_passed = True
    for query, expected in cases:
        result = _extract_view_from_query(query)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] '{query[:50]}...' → {result} (expected {expected})")

    assert all_passed, "Some view extraction cases failed"
    print("[PASS] All view extraction cases passed")


def test_remove_column_from_select():
    """Test the column removal helper."""
    cases = [
        # (query, bad_col, should_change)
        (
            "SELECT DATABASE_NAME, VERSION, USAGE, START_TIME, ACTIVE_STATUS FROM SYS.M_DATABASE",
            "ACTIVE_STATUS",
            True,
        ),
        (
            "SELECT TOP 10 ENTRY_ID, BACKUP_ID, ENTRY_TYPE_NAME, STATE_NAME, SYS_START_TIME, SYS_END_TIME, ROUND(BACKUP_SIZE / 1024 / 1024, 2) AS SIZE_MB, MESSAGE FROM SYS.M_BACKUP_CATALOG ORDER BY SYS_START_TIME DESC",
            "BACKUP_SIZE",
            True,
        ),
        (
            "SELECT ALERT_ID, ALERT_RATING, ALERT_DETAILS, ALERT_TIMESTAMP, HOST FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS WHERE ALERT_RATING >= 3 ORDER BY ALERT_TIMESTAMP DESC",
            "HOST",
            True,
        ),
        (
            "SELECT TOP 20 SCHEMA_NAME, TABLE_NAME, TABLE_TYPE, RECORD_COUNT, ROUND(MEMORY_SIZE_IN_TOTAL / 1024 / 1024, 2) AS SIZE_MB FROM SYS.M_CS_TABLES ORDER BY MEMORY_SIZE_IN_TOTAL DESC",
            "TABLE_TYPE",
            True,
        ),
    ]
    all_passed = True
    for query, bad_col, should_change in cases:
        result = _remove_column_from_select(query, bad_col)
        changed = result != query
        status = "PASS" if changed == should_change else "FAIL"
        if status == "FAIL":
            all_passed = False
        print(f"  [{status}] Remove '{bad_col}': changed={changed}")
        if changed:
            print(f"    Before: {query[:80]}...")
            print(f"    After:  {result[:80]}...")
        # Verify the bad column is actually gone
        if changed:
            assert bad_col not in result, f"Column '{bad_col}' still in result!"

    assert all_passed, "Some column removal cases failed"
    print("[PASS] All column removal cases passed")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing analysis_tools.py")
    print("=" * 60)

    print("\n--- test_extract_view_from_query ---")
    test_extract_view_from_query()

    print("\n--- test_remove_column_from_select ---")
    test_remove_column_from_select()

    print("\n--- test_parse_analysis_errors ---")
    test_parse_analysis_errors()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
