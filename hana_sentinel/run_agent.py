#!/usr/bin/env python3
"""
HANA Sentinel — Agent Runner (CLI)

Usage:
    python run_agent.py                        # Run one monitoring cycle
    python run_agent.py --loop                 # Run continuous loop (5 min default)
    python run_agent.py --loop --interval 600  # Every 10 minutes
    python run_agent.py --loop --max-cycles 3  # Run 3 cycles then stop
    python run_agent.py --report-only          # Generate report from last saved data
    python run_agent.py --sid HXE              # Specify HANA SID
"""

import os
import sys
import io
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid cp1252 encoding errors
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Project root
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# Load .env
try:
    from dotenv import load_dotenv

    env_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"  Loaded .env from {env_path}")
except ImportError:
    pass


def setup_logging(verbose: bool = False, log_file: str = ""):
    """Configure logging to console + optional file."""
    level = logging.DEBUG if verbose else logging.INFO

    fmt = "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s"
    datefmt = "%H:%M:%S"

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_dir = os.path.join(PROJECT_ROOT, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, log_file)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))
        print(f"  Logging to: {log_path}")

    logging.basicConfig(level=level, format=fmt, datefmt=datefmt, handlers=handlers)


def run_single_cycle(sid: str, verbose: bool):
    """Execute one monitoring cycle."""
    from adk_app.agent_loop import run_cycle

    result = run_cycle(sid=sid, cycle_num=1)

    # Print summary
    print("\n" + "=" * 60)
    print(f"  Cycle Result: {result.get('overall_status', 'unknown')}")
    print("=" * 60)

    phases = result.get("phases", {})

    # Errors
    errors = phases.get("errors", {})
    print(f"\n  Errors detected: {errors.get('error_count', 0)}")

    # Fixes
    fixes = phases.get("fixes", {})
    print(f"  Fixes applied:   {fixes.get('applied_count', 0)}")

    # Health
    health = phases.get("health", {})
    health_ok = sum(1 for v in health.values() if v.get("status") == "success")
    print(f"  Health checks:   {health_ok}/{len(health)} passed")

    # Verification
    verification = phases.get("verification", {})
    v_checks = verification.get("checks", [])
    v_passed = sum(1 for c in v_checks if c.get("passed"))
    print(f"  Verifications:   {v_passed}/{len(v_checks)} passed")

    # Report
    report = phases.get("report", {})
    if report.get("status") == "success":
        print(f"\n  [PDF] Report: {report.get('report_path')}")
    else:
        print(f"\n  [!] Report: {report.get('error_message', 'not generated')}")

    # Recommendations
    recs = result.get("recommendations", [])
    if recs:
        print(f"\n  Recommendations:")
        for r in recs:
            print(f"    - {r}")

    return result


def run_continuous_loop(sid: str, interval: int, max_cycles: int, verbose: bool):
    """Run the monitoring loop continuously."""
    from adk_app.agent_loop import run_loop

    print(f"\n  Starting continuous agent loop")
    print(f"  SID: {sid}  |  Interval: {interval}s  |  Max: {max_cycles or 'infinite'}")
    print(f"  Press Ctrl+C to stop\n")

    run_loop(sid=sid, interval=interval, max_cycles=max_cycles)


def generate_report_only(sid: str):
    """Generate a report from the last saved cycle data (if available)."""
    from adk_app.report_generator import generate_report

    # Build minimal cycle data for a standalone report
    cycle_data = {
        "sid": sid,
        "cycle": 0,
        "timestamp": datetime.now().isoformat(),
        "overall_status": "report_only",
        "phases": {
            "analysis": {"status": "skipped", "output_length": 0},
            "errors": {"error_count": 0, "errors": [], "summary": "Report-only mode"},
            "fixes": {"fixes_applied": [], "applied_count": 0},
            "health": {},
            "verification": {},
        },
        "recommendations": [
            "This is a standalone report — run a full cycle for live data"
        ],
    }

    # Try to load last cycle data
    data_dir = os.path.join(PROJECT_ROOT, "adk_app", "data")
    last_cycle_path = os.path.join(data_dir, "last_cycle.json")
    if os.path.exists(last_cycle_path):
        try:
            with open(last_cycle_path, "r") as fh:
                cycle_data = json.load(fh)
            print(f"  Loaded last cycle data from {last_cycle_path}")
        except Exception as exc:
            print(f"  Could not load last cycle data: {exc}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = generate_report(cycle_data, timestamp=ts)

    if result.get("status") == "success":
        print(f"\n  [PDF] Report generated: {result['report_path']}")
        print(f"  Size: {result['report_size']:,} bytes")
    else:
        print(f"\n  [X] Report failed: {result.get('error_message')}")


def main():
    parser = argparse.ArgumentParser(
        description="HANA Sentinel — Autonomous Monitoring Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sid",
        default=os.getenv("HANA_SID", "HXE"),
        help="HANA System ID (default: from HANA_SID env or HXE)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously in a loop",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("AGENT_LOOP_INTERVAL", "300")),
        help="Seconds between cycles (default: 300)",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Max cycles to run in loop mode (0 = infinite)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate a report from last saved data without running analysis",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_file = f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    setup_logging(verbose=args.verbose, log_file=log_file)

    print("+===========================================+")
    print("|       HANA Sentinel -- Agent Runner       |")
    print("+===========================================+")
    print(f"  SID: {args.sid}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.report_only:
        generate_report_only(args.sid)
    elif args.loop:
        run_continuous_loop(args.sid, args.interval, args.max_cycles, args.verbose)
    else:
        run_single_cycle(args.sid, args.verbose)

    print("\nDone.")


if __name__ == "__main__":
    main()
