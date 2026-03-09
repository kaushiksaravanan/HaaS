"""
Log Preprocessor — Compress logs before LLM agents.
Prevents context overflow by extracting actionable signals.

Strategies:
1. DEDUP: Remove duplicate/repeated log lines (keep count).
2. FILTER: Keep only ERROR/WARNING/CRITICAL severity lines by default.
3. TAIL: Keep only last N lines.
4. PATTERN: Extract lines matching known error patterns.
5. STATS: Generate statistical summary (counts by severity, top error types).
6. SMART: Combine all strategies for maximum compression.

All output is structured, compact text safe for LLM agents.
"""

import re
import os
import logging
from collections import Counter, OrderedDict
from typing import List, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Configurable Patterns
# ──────────────────────────────────────────────
# Severity patterns to detect log levels
SEVERITY_PATTERNS = {
    "CRITICAL": re.compile(
        r"\b(CRITICAL|FATAL|PANIC|EMERGENCY|EMERG)\b", re.IGNORECASE
    ),
    "ERROR": re.compile(
        r"\b(ERROR|ERR|EXCEPTION|FAIL(?:ED|URE)?|ABORT)\b", re.IGNORECASE
    ),
    "WARNING": re.compile(
        r"\b(WARNING|WARN|DEPRECAT|CAUTION)\b",
        re.IGNORECASE,
    ),
    "INFO": re.compile(r"\b(INFO|NOTICE|STATUS)\b", re.IGNORECASE),
    "DEBUG": re.compile(r"\b(DEBUG|TRACE|VERBOSE)\b", re.IGNORECASE),
}

# HANA-specific error patterns that are always important
HANA_CRITICAL_PATTERNS = [
    re.compile(r"out of memory", re.IGNORECASE),
    re.compile(r"OOM", re.IGNORECASE),
    re.compile(r"allocation failed", re.IGNORECASE),
    re.compile(r"indexserver.*crash", re.IGNORECASE),
    re.compile(r"nameserver.*crash", re.IGNORECASE),
    re.compile(r"dump\s+file", re.IGNORECASE),
    re.compile(r"core\s+dump", re.IGNORECASE),
    re.compile(r"segmentation fault", re.IGNORECASE),
    re.compile(r"signal\s+11", re.IGNORECASE),
    re.compile(r"disk\s+(full|space)", re.IGNORECASE),
    re.compile(r"no space left", re.IGNORECASE),
    re.compile(r"backup.*fail", re.IGNORECASE),
    re.compile(r"replication.*error", re.IGNORECASE),
    re.compile(r"license.*expir", re.IGNORECASE),
    re.compile(r"certificate.*expir", re.IGNORECASE),
    re.compile(r"authentication.*fail", re.IGNORECASE),
    re.compile(r"connection.*refused", re.IGNORECASE),
    re.compile(r"timeout.*exceed", re.IGNORECASE),
    re.compile(r"deadlock", re.IGNORECASE),
    re.compile(r"savepoint.*fail", re.IGNORECASE),
    re.compile(r"log\s+full", re.IGNORECASE),
    re.compile(r"persistence.*error", re.IGNORECASE),
]

# Lines that are noise (always discard)
NOISE_PATTERNS = [
    re.compile(r"^\s*$"),  # empty lines
    re.compile(r"^[-=]{3,}\s*$"),  # separators
    re.compile(r"^\s*\d+\s+rows?\s+selected", re.IGNORECASE),
    re.compile(r"^\s*OK\s*$", re.IGNORECASE),
    re.compile(r"^\s*\.\s*$"),  # dot lines
]

# Maximum output size defaults
MAX_PREPROCESSED_CHARS = int(os.getenv("LOG_MAX_CHARS", "4000"))
MAX_PREPROCESSED_LINES = int(os.getenv("LOG_MAX_LINES", "80"))


def _classify_severity(line: str) -> str:
    """Classify a log line by severity."""
    for sev, pattern in SEVERITY_PATTERNS.items():
        if pattern.search(line):
            return sev
    # Check HANA-specific critical patterns
    for pat in HANA_CRITICAL_PATTERNS:
        if pat.search(line):
            return "CRITICAL"
    return "UNKNOWN"


def _is_noise(line: str) -> bool:
    """Check if a line is noise."""
    return any(p.match(line) for p in NOISE_PATTERNS)


def _dedup_lines(
    lines: List[str],
) -> List[Tuple[str, int]]:
    """Deduplicate consecutive identical lines.

    Returns (line, count) pairs."""
    if not lines:
        return []
    deduped = []
    current = lines[0]
    count = 1
    for line in lines[1:]:
        ts_re = (
            r"^\d{4}[-/]\d{2}[-/]\d{2}"
            r"[T ]\d{2}:\d{2}:\d{2}[.\d]*\s*"
        )
        norm_current = re.sub(ts_re, "", current)
        norm_line = re.sub(ts_re, "", line)
        if norm_line == norm_current:
            count += 1
        else:
            deduped.append((current, count))
            current = line
            count = 1
    deduped.append((current, count))
    return deduped


def _format_deduped(deduped: List[Tuple[str, int]]) -> List[str]:
    """Format deduplicated lines, showing repeat counts."""
    result = []
    for line, count in deduped:
        if count > 1:
            result.append(f"[x{count}] {line}")
        else:
            result.append(line)
    return result


# ──────────────────────────────────────────────
# Core Preprocessing Functions
# ──────────────────────────────────────────────


def preprocess_log(
    raw_log: str,
    strategy: str = "smart",
    max_lines: int = 0,
    max_chars: int = 0,
    min_severity: str = "WARNING",
    include_stats: bool = True,
) -> str:
    """Preprocess raw log text for LLM consumption.

    Returns compact, structured text.

    Args:
        raw_log: The raw log text to preprocess.
        strategy: Strategy: 'smart', 'filter', 'dedup',
            'tail', 'pattern', 'stats'.
        max_lines: Max output lines (0 = use LOG_MAX_LINES).
        max_chars: Max output chars (0 = use LOG_MAX_CHARS).
        min_severity: Min severity: CRITICAL, ERROR,
            WARNING, INFO, DEBUG.
        include_stats: Whether to prepend a statistical summary.

    Returns:
        Preprocessed, compact log text safe for LLM context.
    """
    if not raw_log or not raw_log.strip():
        return "[LOG EMPTY — no output to analyze]"

    max_l = max_lines or MAX_PREPROCESSED_LINES
    max_c = max_chars or MAX_PREPROCESSED_CHARS

    lines = raw_log.strip().split("\n")
    total_lines = len(lines)

    # Remove noise first
    lines = [ln for ln in lines if not _is_noise(ln)]

    if strategy == "smart":
        return _smart_preprocess(
            lines, total_lines, max_l, max_c, min_severity, include_stats
        )
    elif strategy == "filter":
        return _filter_preprocess(
            lines,
            total_lines,
            max_l,
            max_c,
            min_severity,
        )
    elif strategy == "dedup":
        return _dedup_preprocess(lines, total_lines, max_l, max_c)
    elif strategy == "tail":
        return _tail_preprocess(lines, total_lines, max_l, max_c)
    elif strategy == "pattern":
        return _pattern_preprocess(lines, total_lines, max_l, max_c)
    elif strategy == "stats":
        return _stats_only(lines, total_lines)
    else:
        return _smart_preprocess(
            lines, total_lines, max_l, max_c, min_severity, include_stats
        )


def _severity_rank(sev: str) -> int:
    ranks = {
        "CRITICAL": 0,
        "ERROR": 1,
        "WARNING": 2,
        "INFO": 3,
        "DEBUG": 4,
        "UNKNOWN": 5,
    }
    return ranks.get(sev, 5)


def _smart_preprocess(
    lines: List[str],
    total: int,
    max_l: int,
    max_c: int,
    min_severity: str,
    include_stats: bool,
) -> str:
    """Smart preprocessing: dedup + filter + stats + truncate."""
    min_rank = _severity_rank(min_severity)

    # Classify all lines
    classified = [(line, _classify_severity(line)) for line in lines]

    # Count by severity
    sev_counts: Counter = Counter()
    for _, sev in classified:
        sev_counts[sev] += 1

    # Always include HANA-critical pattern matches regardless of severity
    critical_matches = []
    for line, _ in classified:
        for pat in HANA_CRITICAL_PATTERNS:
            if pat.search(line):
                critical_matches.append(line)
                break

    # Filter by minimum severity
    filtered = [
        (line, sev) for line, sev in classified if _severity_rank(sev) <= min_rank
    ]

    # Dedup the filtered lines
    deduped = _dedup_lines([line for line, _ in filtered])
    formatted = _format_deduped(deduped)

    # Build output
    parts = []

    if include_stats:
        stats = f"[LOG SUMMARY: {total} total lines"
        sev_parts = []
        for sev in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"]:
            if sev_counts.get(sev, 0) > 0:
                sev_parts.append(f"{sev}={sev_counts[sev]}")
        if sev_parts:
            stats += " | " + ", ".join(sev_parts)
        stats += f" | showing {len(formatted)} after filter+dedup]"
        parts.append(stats)

    # Add critical matches first (always)
    if critical_matches:
        unique_crits = list(OrderedDict.fromkeys(critical_matches))[:10]
        parts.append("[CRITICAL SIGNALS]")
        parts.extend(unique_crits)

    # Add filtered lines
    if formatted:
        if critical_matches:
            parts.append("[FILTERED LOG]")
        parts.extend(formatted[:max_l])

    result = "\n".join(parts)

    # Enforce character limit
    if len(result) > max_c:
        result = (
            result[: max_c - 50]
            + f"\n... [TRUNCATED, {len(result) - max_c + 50} chars omitted]"
        )

    return result


def _filter_preprocess(
    lines: List[str],
    total: int,
    max_l: int,
    max_c: int,
    min_severity: str,
) -> str:
    """Filter by severity only."""
    min_rank = _severity_rank(min_severity)
    filtered = [
        ln for ln in lines if _severity_rank(_classify_severity(ln)) <= min_rank
    ]
    result = f"[FILTERED: {len(filtered)}/{total} lines at {min_severity}+]\n"
    result += "\n".join(filtered[:max_l])
    if len(result) > max_c:
        result = result[: max_c - 30] + "\n... [TRUNCATED]"
    return result


def _dedup_preprocess(
    lines: List[str],
    total: int,
    max_l: int,
    max_c: int,
) -> str:
    """Dedup only."""
    deduped = _dedup_lines(lines)
    formatted = _format_deduped(deduped)
    result = f"[DEDUP: {total} -> {len(formatted)} lines]\n"
    result += "\n".join(formatted[:max_l])
    if len(result) > max_c:
        result = result[: max_c - 30] + "\n... [TRUNCATED]"
    return result


def _tail_preprocess(
    lines: List[str],
    total: int,
    max_l: int,
    max_c: int,
) -> str:
    """Tail last N lines."""
    tail = lines[-max_l:]
    result = f"[TAIL: last {len(tail)} of {total} lines]\n"
    result += "\n".join(tail)
    if len(result) > max_c:
        result = result[: max_c - 30] + "\n... [TRUNCATED]"
    return result


def _pattern_preprocess(
    lines: List[str],
    total: int,
    max_l: int,
    max_c: int,
) -> str:
    """Extract only HANA-specific critical patterns."""
    matches = []
    for line in lines:
        for pat in HANA_CRITICAL_PATTERNS:
            if pat.search(line):
                matches.append(line)
                break
    result = f"[PATTERN MATCH: {len(matches)} critical patterns from {total} lines]\n"
    result += "\n".join(matches[:max_l])
    if len(result) > max_c:
        result = result[: max_c - 30] + "\n... [TRUNCATED]"
    return result


def _stats_only(lines: List[str], total: int) -> str:
    """Statistics summary only — no raw log content."""
    sev_counts: Counter = Counter()
    error_types: Counter = Counter()

    for line in lines:
        sev = _classify_severity(line)
        sev_counts[sev] += 1

        if sev in ("ERROR", "CRITICAL"):
            # Extract error type (first recognizable pattern)
            for pat in HANA_CRITICAL_PATTERNS:
                m = pat.search(line)
                if m:
                    error_types[m.group(0).lower()] += 1
                    break

    parts = [f"[LOG STATISTICS: {total} total lines]"]
    for sev in ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "UNKNOWN"]:
        if sev_counts.get(sev, 0) > 0:
            parts.append(f"  {sev}: {sev_counts[sev]}")

    if error_types:
        parts.append("[TOP ERROR TYPES]")
        for err, count in error_types.most_common(10):
            parts.append(f"  {err}: {count}x")

    return "\n".join(parts)


# ──────────────────────────────────────────────
# HDB Storage Path Analyzer
# ──────────────────────────────────────────────


def preprocess_df_output(df_output: str) -> str:
    """Parse and summarize `df -h` output, flagging paths that are critical.

    Args:
        df_output: Raw output from `df -h` command.

    Returns:
        Compact summary with only HDB-relevant paths and warnings.
    """
    if not df_output or not df_output.strip():
        return "[DF OUTPUT EMPTY]"

    hdb_keywords = [
        "hana",
        "hdb",
        "/data",
        "/log",
        "/backup",
        "/shared",
        "/usr/sap",
    ]
    lines = df_output.strip().split("\n")
    header = lines[0] if lines else ""
    data_lines = lines[1:] if len(lines) > 1 else []

    relevant = []
    warnings = []

    for line in data_lines:
        parts = line.split()
        if len(parts) < 5:
            continue

        # Check if path is HDB-relevant
        mount = parts[-1] if len(parts) >= 6 else parts[-1]
        is_hdb = any(kw in mount.lower() or kw in line.lower() for kw in hdb_keywords)

        # Extract usage percentage
        pct_str = ""
        for p in parts:
            if p.endswith("%"):
                pct_str = p
                break

        if pct_str:
            try:
                pct = int(pct_str.rstrip("%"))
                if pct >= 90:
                    warnings.append(
                        f"CRITICAL: {mount} at {pct}% ({parts[2]} used of {parts[1]})"
                    )
                    relevant.append(f"! {line}")
                elif pct >= 80:
                    warnings.append(f"WARNING: {mount} at {pct}%")
                    relevant.append(f"* {line}")
                elif is_hdb:
                    relevant.append(f"  {line}")
            except ValueError:
                if is_hdb:
                    relevant.append(f"  {line}")
        elif is_hdb:
            relevant.append(f"  {line}")

    parts_out = []
    if warnings:
        parts_out.append("[STORAGE ALERTS]")
        parts_out.extend(warnings)
    parts_out.append(
        f"[HDB STORAGE: {len(relevant)} relevant paths from {len(data_lines)} total]"
    )
    if relevant:
        parts_out.append(header)
        parts_out.extend(relevant)

    return "\n".join(parts_out)


def preprocess_ps_output(ps_output: str) -> str:
    """Parse and summarize `ps aux` output, keeping only SAP/HANA processes.

    Args:
        ps_output: Raw output from `ps aux` or `ps aux | grep hdb`.

    Returns:
        Compact process summary with only HANA-relevant processes and resource usage.
    """
    if not ps_output or not ps_output.strip():
        return "[NO PROCESSES FOUND]"

    hana_keywords = [
        "hdb",
        "sap",
        "indexserver",
        "nameserver",
        "compileserver",
        "preprocessor",
        "diserver",
        "dpserver",
        "webdispatcher",
        "sapstartsrv",
        "sapcontrol",
        "hdbnameserver",
    ]

    lines = ps_output.strip().split("\n")
    header = lines[0] if lines and "PID" in lines[0].upper() else ""
    data_lines = lines[1:] if header else lines

    relevant = []
    for line in data_lines:
        if any(kw in line.lower() for kw in hana_keywords):
            relevant.append(line)

    if not relevant:
        return "[NO HANA PROCESSES FOUND in output]"

    result = f"[HANA PROCESSES: {len(relevant)} found]\n"
    if header:
        result += header + "\n"
    result += "\n".join(relevant)
    return result


# ──────────────────────────────────────────────
# ADK Tool Functions
# ──────────────────────────────────────────────


def preprocess_command_output(
    raw_output: str,
    context: str = "general",
    strategy: str = "smart",
    max_lines: int = 0,
    max_chars: int = 0,
) -> dict:
    """Preprocess raw command output for LLM agents.

    Reduces context by filtering noise, deduplicating,
    and summarizing.

    Args:
        raw_output (str): Raw command output.
        context (str): Context hint: 'general', 'log',
            'disk', 'process', 'trace', 'hdbsql'.
        strategy (str): Strategy: 'smart' (default),
            'filter', 'dedup', 'tail', 'pattern', 'stats'.
        max_lines (int): Max output lines (0 = default 80).
        max_chars (int): Max output chars (0 = default 4000).

    Returns:
        dict: status, preprocessed output,
            original/compressed size, ratio.
    """
    if not raw_output:
        return {
            "status": "success",
            "preprocessed": "[EMPTY OUTPUT]",
            "original_chars": 0,
            "compressed_chars": 13,
            "compression_ratio": 1.0,
        }

    original_chars = len(raw_output)

    # Route to specialized preprocessor based on context
    if context == "disk":
        preprocessed = preprocess_df_output(raw_output)
    elif context == "process":
        preprocessed = preprocess_ps_output(raw_output)
    elif context in ("log", "trace"):
        preprocessed = preprocess_log(
            raw_output,
            strategy=strategy,
            max_lines=max_lines,
            max_chars=max_chars,
        )
    elif context == "hdbsql":
        # For SQL output, just truncate long result sets
        lines = raw_output.strip().split("\n")
        max_l = max_lines or MAX_PREPROCESSED_LINES
        if len(lines) > max_l:
            preprocessed = "\n".join(lines[:max_l])
            preprocessed += (
                f"\n... [{len(lines) - max_l} more rows, {len(lines)} total]"
            )
        else:
            preprocessed = raw_output.strip()
    else:
        preprocessed = preprocess_log(
            raw_output,
            strategy=strategy,
            max_lines=max_lines,
            max_chars=max_chars,
        )

    compressed_chars = len(preprocessed)
    ratio = original_chars / max(compressed_chars, 1)

    return {
        "status": "success",
        "preprocessed": preprocessed,
        "original_chars": original_chars,
        "compressed_chars": compressed_chars,
        "compression_ratio": round(ratio, 1),
    }


def check_hdb_storage(
    data_path: str = "",
    log_path: str = "",
    backup_path: str = "",
    shared_path: str = "",
) -> dict:
    """Check HDB storage paths and available space.
    Runs df on all HDB-relevant paths and returns a preprocessed summary.
    This is a convenience wrapper that uses docker_exec or ssh_execute.

    Args:
        data_path (str): HDB data volume path.
            Defaults to HANA_DATA_PATH env or
            /hana/data.
        log_path (str): HDB log volume path. Defaults to /hana/log.
        backup_path (str): Backup path. Defaults to /hana/backup.
        shared_path (str): Shared path. Defaults to /hana/shared.

    Returns:
        dict: Preprocessed storage status per path,
            with alerts for critical/warning.
    """
    data = data_path or os.getenv("HANA_DATA_PATH", "/hana/data")
    log = log_path or os.getenv("HANA_LOG_PATH", "/hana/log")
    backup = backup_path or os.getenv("HANA_BACKUP_PATH", "/hana/backup")
    shared = shared_path or os.getenv("HANA_SHARED_PATH", "/hana/shared")

    paths = [data, log, backup, shared]
    df_cmd = (
        "df -h "
        + " ".join(paths)
        + " 2>/dev/null; df -ih "
        + " ".join(paths)
        + " 2>/dev/null"
    )

    # Try docker first, then SSH
    result = None
    container = os.getenv("HANA_CONTAINER_NAME", "")
    if container:
        try:
            from .docker_tools import docker_exec

            result = docker_exec(container, df_cmd)
        except Exception:
            pass

    if result is None or result.get("status") != "success":
        try:
            from .ssh_tools import ssh_execute

            result = ssh_execute(df_cmd)
        except Exception as e:
            return {
                "status": "error",
                "error_message": (
                    f"Cannot check HDB storage — no container or SSH: {e}"
                ),
                "paths_checked": paths,
            }

    if result.get("status") != "success":
        return {
            "status": "error",
            "error_message": result.get("error_message", "Command failed"),
            "paths_checked": paths,
        }

    # Preprocess the df output
    raw = result.get("stdout", result.get("output", ""))
    preprocessed = preprocess_df_output(raw)

    # Parse alerts from preprocessed text
    alerts = []
    for line in preprocessed.split("\n"):
        if line.startswith("CRITICAL:") or line.startswith("WARNING:"):
            alerts.append(line)

    return {
        "status": "success",
        "summary": preprocessed,
        "paths_checked": paths,
        "alerts": alerts,
        "has_critical": any("CRITICAL" in a for a in alerts),
        "has_warning": any("WARNING" in a for a in alerts),
    }
