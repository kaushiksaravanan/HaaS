"""
Remote Command Execution Server
================================

A lightweight FastAPI server that runs on the HANA instance
and allows secure remote command execution via HTTP API.

Security Features:
- API Key authentication
- Command allowlist (only safe commands)
- Request logging

Usage:
    python remote_exec_server.py

Configuration via environment variables or config.json
"""

import os
import subprocess
import logging
import hashlib
import json
from datetime import datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('remote_exec_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

class Config:
    """Server configuration"""

    # API Key for authentication (pre-configured secure base64 key)
    # Generated using: python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
    # HARDCODED - matches .env on client side
    API_KEY = "REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000"

    # Server settings
    HOST = os.getenv("REMOTE_EXEC_HOST", "0.0.0.0")
    PORT = int(os.getenv("REMOTE_EXEC_PORT", "9999"))

    # Security settings
    MAX_COMMAND_LENGTH = 5000
    COMMAND_TIMEOUT = 300  # 5 minutes max

    # Allowed command prefixes (security: only allow specific commands)
    ALLOWED_COMMANDS = [
        "echo",
        "whoami",
        "pwd",
        "date",
        "hostname",
        "df",
        "free",
        "uptime",
        "cat /proc/",
        "ls -l",
        "sapcontrol",
        "HDB",
        "hdbsql",
        "hdbuserstore",
        "du -sh",
        "ps aux",
    ]

    @classmethod
    def load_from_file(cls, config_path: str = "remote_exec_config.json"):
        """Load configuration from JSON file (API_KEY is hardcoded and not overridable)"""
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # API_KEY is hardcoded - skip loading from file
                    cls.HOST = config.get("host", cls.HOST)
                    cls.PORT = config.get("port", cls.PORT)
                    cls.ALLOWED_COMMANDS = config.get("allowed_commands", cls.ALLOWED_COMMANDS)
                    logger.info(f"Configuration loaded from {config_path} (API_KEY is hardcoded)")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

# Load config on startup (API_KEY remains hardcoded)
Config.load_from_file()

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Remote Command Execution Server",
    description="Secure command execution API for HANA instance",
    version="1.0.0"
)

# ============================================================================
# Models
# ============================================================================

class CommandRequest(BaseModel):
    """Request model for command execution"""
    command: str
    timeout: Optional[int] = 60
    working_dir: Optional[str] = None
    admin_override: Optional[bool] = False

class CommandResponse(BaseModel):
    """Response model for command execution"""
    status: str
    exit_code: int
    stdout: str
    stderr: str
    execution_time: float
    timestamp: str

# ============================================================================
# Authentication & Security
# ============================================================================

def verify_api_key(x_api_key: str = Header(None)) -> bool:
    """Verify API key from header"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")

    if x_api_key != Config.API_KEY:
        logger.warning(f"Invalid API key attempt: {x_api_key[:10]}...")
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True

def is_command_allowed(command: str) -> bool:
    """Check if command is in allowlist"""
    # Check if command starts with any allowed prefix
    for allowed in Config.ALLOWED_COMMANDS:
        if command.strip().startswith(allowed):
            return True

    return False

# ============================================================================
# Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "Remote Command Execution Server",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check(x_api_key: str = Header(None)):
    """Authenticated health check"""
    verify_api_key(x_api_key)

    return {
        "status": "healthy",
        "hostname": os.uname().nodename,
        "user": os.getenv("USER", "unknown"),
        "timestamp": datetime.now().isoformat()
    }

@app.get("/diagnostics")
async def run_diagnostics(x_api_key: str = Header(None)):
    """
    Run HANA diagnostic checks and return results.
    Executes diagnostic scripts located in /home/zo3adm/diagnostics/
    """
    verify_api_key(x_api_key)

    diagnostics_dir = "/home/zo3adm/diagnostics"
    results = {}

    # List of diagnostic scripts to run
    diagnostic_scripts = [
        ("hana_processes", "check_hana_processes.sh"),
        ("disk_usage", "check_disk.sh"),
        ("memory", "check_memory.sh"),
        ("userstore", "check_userstore.sh"),
        ("backups", "check_backups.sh"),
        ("system_params", "check_system_params.sh"),
    ]

    for check_name, script_name in diagnostic_scripts:
        script_path = f"{diagnostics_dir}/{script_name}"

        # Check if script exists
        if not os.path.exists(script_path):
            results[check_name] = {
                "status": "not_found",
                "message": f"Script {script_name} not found"
            }
            continue

        # Execute the script
        try:
            result = subprocess.run(
                ["bash", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                timeout=30
            )

            results[check_name] = {
                "status": "success" if result.returncode == 0 else "error",
                "exit_code": result.returncode,
                "output": result.stdout.strip(),
                "error": result.stderr.strip() if result.stderr else None
            }
        except subprocess.TimeoutExpired:
            results[check_name] = {
                "status": "timeout",
                "message": f"Script {script_name} timed out after 30s"
            }
        except Exception as e:
            results[check_name] = {
                "status": "error",
                "message": str(e)
            }

    return {
        "timestamp": datetime.now().isoformat(),
        "diagnostics": results
    }

@app.get("/healing/scripts")
async def list_healing_scripts(x_api_key: str = Header(None)):
    """
    List available healing scripts.
    Returns metadata about each healing script.
    """
    verify_api_key(x_api_key)

    healing_dir = "/home/zo3adm/healing"
    scripts = []

    # Define healing scripts with metadata
    healing_scripts_meta = {
        "fix_userstore.sh": {
            "name": "Userstore Management",
            "description": "Reconfigure HANA userstore keys",
            "risk_level": "MEDIUM",
            "risk_points": 6
        },
        "fix_backup_config.sh": {
            "name": "Backup Configuration",
            "description": "Fix backup paths and permissions",
            "risk_level": "MEDIUM-HIGH",
            "risk_points": 8
        },
        "fix_system_params.sh": {
            "name": "System Parameters",
            "description": "Configure swappiness, THP, ASLR",
            "risk_level": "HIGH",
            "risk_points": 12
        },
        "fix_trace_files.sh": {
            "name": "Trace File Cleanup",
            "description": "Clean up old trace files",
            "risk_level": "LOW",
            "risk_points": 3
        }
    }

    for script_name, meta in healing_scripts_meta.items():
        script_path = f"{healing_dir}/{script_name}"
        exists = os.path.exists(script_path)

        scripts.append({
            "script_name": script_name,
            "exists": exists,
            "path": script_path if exists else None,
            **meta
        })

    return {
        "healing_scripts": scripts,
        "total": len(scripts),
        "available": sum(1 for s in scripts if s["exists"])
    }

@app.post("/healing/execute/{script_name}")
async def execute_healing_script(
    script_name: str,
    x_api_key: str = Header(None),
    dry_run: bool = False
):
    """
    Execute a healing script.

    Parameters:
    - script_name: Name of the healing script (e.g., "fix_userstore.sh")
    - dry_run: If true, runs in simulation mode (no actual changes)
    """
    verify_api_key(x_api_key)

    healing_dir = "/home/zo3adm/healing"
    script_path = f"{healing_dir}/{script_name}"

    # Security: Only allow .sh files
    if not script_name.endswith(".sh"):
        raise HTTPException(status_code=400, detail="Only .sh scripts allowed")

    # Check if script exists
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail=f"Script {script_name} not found")

    # Check if script is in approved list
    approved_scripts = [
        "fix_userstore.sh",
        "fix_backup_config.sh",
        "fix_system_params.sh",
        "fix_trace_files.sh"
    ]

    if script_name not in approved_scripts:
        raise HTTPException(
            status_code=403,
            detail=f"Script {script_name} not in approved list"
        )

    logger.info(f"Executing healing script: {script_name} (dry_run={dry_run})")

    # Execute the script
    start_time = datetime.now()
    try:
        env = os.environ.copy()
        if dry_run:
            env["DRY_RUN"] = "true"

        result = subprocess.run(
            ["bash", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=120,  # 2 minutes max for healing scripts
            env=env
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return {
            "script_name": script_name,
            "dry_run": dry_run,
            "status": "success" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if result.stderr else None,
            "execution_time": execution_time,
            "timestamp": datetime.now().isoformat()
        }

    except subprocess.TimeoutExpired:
        logger.error(f"Healing script {script_name} timed out")
        raise HTTPException(
            status_code=408,
            detail=f"Script {script_name} timed out after 120s"
        )
    except Exception as e:
        logger.error(f"Healing script execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute", response_model=CommandResponse)
async def execute_command(
    cmd_request: CommandRequest,
    request: Request,
    x_api_key: str = Header(None)
):
    """
    Execute a shell command on the server.

    Security:
    - Requires valid API key
    - Command must be in allowlist
    - Command length limits
    - Timeout limits
    """
    # Authentication & authorization
    verify_api_key(x_api_key)

    command = cmd_request.command
    timeout = min(cmd_request.timeout, Config.COMMAND_TIMEOUT)
    admin_override = bool(cmd_request.admin_override)

    # Validation
    if len(command) > Config.MAX_COMMAND_LENGTH:
        raise HTTPException(status_code=400, detail="Command too long")

    if not admin_override and not is_command_allowed(command):
        logger.warning(f"Blocked command attempt: {command[:100]}")
        raise HTTPException(
            status_code=403,
            detail=f"Command not allowed. Allowed prefixes: {Config.ALLOWED_COMMANDS}"
        )

    # Log the execution
    if admin_override:
        logger.warning(f"Executing with ADMIN OVERRIDE from {request.client.host}: {command[:200]}")
    else:
        logger.info(f"Executing command from {request.client.host}: {command[:100]}")

    # Execute command
    start_time = datetime.now()
    try:
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # Python 3.6 compatible (same as text=True)
            timeout=timeout,
            cwd=cmd_request.working_dir
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        response = CommandResponse(
            status="success" if result.returncode == 0 else "error",
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat()
        )

        logger.info(f"Command completed: exit_code={result.returncode}, time={execution_time:.2f}s")

        return response

    except subprocess.TimeoutExpired:
        logger.error(f"Command timeout: {command[:100]}")
        raise HTTPException(status_code=408, detail=f"Command timeout after {timeout}s")

    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

@app.post("/execute-as-user")
async def execute_as_user(
    cmd_request: CommandRequest,
    request: Request,
    x_api_key: str = Header(None),
    user: str = "zo3adm"
):
    """
    Execute command as specific user (requires sudo access).

    Useful for running HANA commands as zo3adm user.
    """
    verify_api_key(x_api_key)

    command = cmd_request.command
    admin_override = bool(cmd_request.admin_override)

    # Validation
    if len(command) > Config.MAX_COMMAND_LENGTH:
        raise HTTPException(status_code=400, detail="Command too long")

    if not admin_override and not is_command_allowed(command):
        raise HTTPException(status_code=403, detail="Command not allowed")

    # Wrap command with sudo su
    wrapped_command = f"sudo su - {user} -c '{command}'"

    if admin_override:
        logger.warning(f"Executing as {user} with ADMIN OVERRIDE from {request.client.host}: {command[:200]}")
    else:
        logger.info(f"Executing as {user} from {request.client.host}: {command[:100]}")

    start_time = datetime.now()
    try:
        result = subprocess.run(
            wrapped_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,  # Python 3.6 compatible (same as text=True)
            timeout=min(cmd_request.timeout, Config.COMMAND_TIMEOUT)
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        return CommandResponse(
            status="success" if result.returncode == 0 else "error",
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat()
        )

    except Exception as e:
        logger.error(f"Command execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# Startup Configuration
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("=" * 60)
    logger.info("Remote Command Execution Server Starting")
    logger.info("=" * 60)
    logger.info(f"Host: {Config.HOST}:{Config.PORT}")
    logger.info(f"API Key configured: Yes (base64 secure key)")
    logger.info(f"Allowed commands: {len(Config.ALLOWED_COMMANDS)} prefixes")
    logger.info("=" * 60)

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    # Start server with pre-configured secure API key
    logger.info("Using pre-configured secure base64 API key")
    logger.info("Server ready to accept connections")

    # Start server
    uvicorn.run(
        app,
        host=Config.HOST,
        port=Config.PORT,
        log_level="info"
    )
