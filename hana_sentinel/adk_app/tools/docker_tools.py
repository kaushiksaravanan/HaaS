"""
Docker Container Tools — ADK-compatible tool functions.
Provides container-level operations for SAP HANA monitoring.
Supports docker CLI and podman.

NO MOCK — always real container interaction or explicit error.
"""

import os
import subprocess
import logging
import json

logger = logging.getLogger(__name__)


def _detect_runtime() -> str:
    """Detect available container runtime: docker or podman."""
    import shutil

    # 1. Local docker
    if shutil.which("docker"):
        try:
            r = subprocess.run(
                ["docker", "info"], capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                return "docker"
        except Exception:
            pass

    # 2. Local podman
    if shutil.which("podman"):
        try:
            r = subprocess.run(
                ["podman", "info"], capture_output=True, text=True, timeout=10
            )
            if r.returncode == 0:
                return "podman"
        except Exception:
            pass

    return "none"


def _exec_local(runtime: str, args: list, timeout: int = 60) -> dict:
    """Execute a container runtime command locally."""
    cmd = [runtime] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "success" if result.returncode == 0 else "error",
            "source": runtime,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error_message": f"Command timed out after {timeout}s: {' '.join(cmd)}",
        }
    except Exception as e:
        return {"status": "error", "error_message": f"Local {runtime} failed: {e}"}


def _run_container_cmd(args: list, timeout: int = 60) -> dict:
    """Run a container runtime command using detected or configured runtime."""
    runtime = os.getenv("CONTAINER_RUNTIME", "") or _detect_runtime()

    if runtime in ("docker", "podman"):
        return _exec_local(runtime, args, timeout)
    else:
        return {
            "status": "error",
            "error_message": (
                "No container runtime available. Tried: docker, podman. "
                "Set CONTAINER_RUNTIME env var."
            ),
        }


# ──────────────────────────────────────────────
# ADK Tool Functions
# ──────────────────────────────────────────────


def docker_exec(container: str, command: str, user: str = "") -> dict:
    """Execute a command inside a running Docker/Podman container.
    Uses local docker or podman.
    NEVER returns mock data.

    Args:
        container (str): Container name or ID. If empty, reads from HANA_CONTAINER_NAME env var.
        command (str): Shell command to execute inside the container.
        user (str): Optional user to run as (e.g., 'hxeadm'). If empty, reads CONTAINER_USER env var.

    Returns:
        dict: status, stdout, stderr from the command execution inside the container.
    """
    if not container:
        container = os.getenv("HANA_CONTAINER_NAME", "")
    if not container:
        return {
            "status": "error",
            "error_message": "No container specified. Set HANA_CONTAINER_NAME or pass container name.",
        }

    if not user:
        user = os.getenv("CONTAINER_USER", "")

    args = ["exec"]
    if user:
        args.extend(["-u", user])
    args.extend([container, "bash", "-c", command])

    return _run_container_cmd(args)


def docker_logs(container: str = "", lines: int = 100, since: str = "") -> dict:
    """Get logs from a Docker/Podman container.

    Args:
        container (str): Container name or ID. If empty, reads HANA_CONTAINER_NAME.
        lines (int): Number of tail lines to return (default: 100).
        since (str): Show logs since timestamp or relative (e.g., '10m', '1h', '2025-01-01T00:00:00').

    Returns:
        dict: status and container log output.
    """
    if not container:
        container = os.getenv("HANA_CONTAINER_NAME", "")
    if not container:
        return {
            "status": "error",
            "error_message": "No container specified. Set HANA_CONTAINER_NAME.",
        }

    args = ["logs", "--tail", str(lines)]
    if since:
        args.extend(["--since", since])
    args.append(container)

    return _run_container_cmd(args)


def docker_stats(container: str = "") -> dict:
    """Get real-time resource usage stats from a container (CPU, memory, network, disk I/O).

    Args:
        container (str): Container name or ID. If empty, reads HANA_CONTAINER_NAME.

    Returns:
        dict: status and resource usage stats (CPU%, memory, net I/O, block I/O).
    """
    if not container:
        container = os.getenv("HANA_CONTAINER_NAME", "")
    if not container:
        return {
            "status": "error",
            "error_message": "No container specified. Set HANA_CONTAINER_NAME.",
        }

    result = _run_container_cmd(
        [
            "stats",
            "--no-stream",
            "--format",
            "{{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}\t{{.BlockIO}}\t{{.PIDs}}",
            container,
        ]
    )

    if result["status"] == "success" and result.get("stdout"):
        parts = result["stdout"].split("\t")
        if len(parts) >= 7:
            result["parsed"] = {
                "container": parts[0],
                "cpu_pct": parts[1],
                "mem_usage": parts[2],
                "mem_pct": parts[3],
                "net_io": parts[4],
                "block_io": parts[5],
                "pids": parts[6],
            }
    return result


def docker_inspect(container: str = "") -> dict:
    """Inspect a container's configuration and state.

    Args:
        container (str): Container name or ID. If empty, reads HANA_CONTAINER_NAME.

    Returns:
        dict: status and full container configuration (image, ports, mounts, env, state).
    """
    if not container:
        container = os.getenv("HANA_CONTAINER_NAME", "")
    if not container:
        return {
            "status": "error",
            "error_message": "No container specified. Set HANA_CONTAINER_NAME.",
        }

    result = _run_container_cmd(["inspect", container])

    if result["status"] == "success" and result.get("stdout"):
        try:
            parsed = json.loads(result["stdout"])
            if isinstance(parsed, list) and len(parsed) > 0:
                info = parsed[0]
                result["parsed"] = {
                    "id": info.get("Id", "")[:12],
                    "name": info.get("Name", "").lstrip("/"),
                    "image": info.get("Config", {}).get("Image", ""),
                    "state": info.get("State", {}).get("Status", ""),
                    "started_at": info.get("State", {}).get("StartedAt", ""),
                    "restart_count": info.get("RestartCount", 0),
                    "ports": info.get("NetworkSettings", {}).get("Ports", {}),
                    "mounts": [
                        {
                            "source": m.get("Source", ""),
                            "destination": m.get("Destination", ""),
                            "rw": m.get("RW", True),
                        }
                        for m in info.get("Mounts", [])
                    ],
                }
        except json.JSONDecodeError:
            pass  # Raw output already in result["stdout"]
    return result


def docker_list_containers(all_containers: bool = False) -> dict:
    """List running (or all) containers on the host.

    Args:
        all_containers (bool): If True, include stopped containers.

    Returns:
        dict: status and list of containers with name, image, status, ports.
    """
    args = ["ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"]
    if all_containers:
        args.insert(1, "-a")

    result = _run_container_cmd(args)

    if result["status"] == "success" and result.get("stdout"):
        containers = []
        for line in result["stdout"].strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 3:
                containers.append(
                    {
                        "name": parts[0],
                        "image": parts[1] if len(parts) > 1 else "",
                        "status": parts[2] if len(parts) > 2 else "",
                        "ports": parts[3] if len(parts) > 3 else "",
                    }
                )
        result["containers"] = containers
    return result


def docker_health_check(container: str = "") -> dict:
    """Run health check on a container: check if running, inspect health status,
    verify key HANA processes inside the container.

    Args:
        container (str): Container name or ID. If empty, reads HANA_CONTAINER_NAME.

    Returns:
        dict: comprehensive health status including container state and HANA process status.
    """
    if not container:
        container = os.getenv("HANA_CONTAINER_NAME", "")
    if not container:
        return {
            "status": "error",
            "error_message": "No container specified. Set HANA_CONTAINER_NAME.",
        }

    health = {"container": container, "checks": {}}

    # 1. Container state
    inspect_result = docker_inspect(container)
    if inspect_result["status"] == "success" and inspect_result.get("parsed"):
        health["checks"]["container_state"] = inspect_result["parsed"]["state"]
        health["checks"]["started_at"] = inspect_result["parsed"]["started_at"]
        health["checks"]["restart_count"] = inspect_result["parsed"]["restart_count"]
    else:
        health["checks"]["container_state"] = "unknown"
        health["status"] = "error"
        health["error_message"] = inspect_result.get(
            "error_message", "Cannot inspect container"
        )
        return health

    # 2. Resource usage
    stats_result = docker_stats(container)
    if stats_result["status"] == "success" and stats_result.get("parsed"):
        health["checks"]["resources"] = stats_result["parsed"]

    # 3. HANA processes inside container
    proc_result = docker_exec(container, "ps aux | grep -E 'hdb|sap' | grep -v grep")
    if proc_result["status"] == "success":
        health["checks"]["hana_processes"] = proc_result["stdout"]

    # 4. Disk inside container
    disk_result = docker_exec(
        container, "df -h /hana/data /hana/log /hana/shared 2>/dev/null || df -h"
    )
    if disk_result["status"] == "success":
        health["checks"]["disk_usage"] = disk_result["stdout"]

    health["status"] = "success"
    health["overall"] = (
        "healthy"
        if health["checks"].get("container_state") == "running"
        else "unhealthy"
    )
    return health
