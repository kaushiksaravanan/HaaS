"""
GCP Authentication Helper — Authenticate gcloud CLI for HANA Sentinel.
Uses Google Cloud SDK (gcloud auth login) with credentials from environment.
Supports service key authentication for GCP Compute instances.
"""

import os
import subprocess
import logging
import json
from google.oauth2 import service_account
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

_authenticated = False
_service_account_credentials = None


def ensure_gcloud_auth() -> dict:
    """Ensure gcloud CLI is authenticated and project is set.

    Uses GCP_AUTH_EMAIL from env. For non-interactive login in GCP lab
    environments, uses `gcloud auth login --no-launch-browser`.

    Returns:
        dict: status and account info.
    """
    global _authenticated

    if _authenticated:
        return {"status": "already_authenticated"}

    # Check if gcloud is available
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"status": "error", "error_message": "gcloud CLI not functional"}
    except FileNotFoundError:
        return {
            "status": "error",
            "error_message": "gcloud CLI not found. Install Google Cloud SDK.",
        }
    except Exception as e:
        return {"status": "error", "error_message": f"gcloud check failed: {e}"}

    # Check if already authenticated
    try:
        acct_result = subprocess.run(
            [
                "gcloud",
                "auth",
                "list",
                "--format",
                "value(account)",
                "--filter",
                "status:ACTIVE",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        active_account = acct_result.stdout.strip()
        if active_account:
            logger.info(f"gcloud already authenticated as {active_account}")
            _set_project()
            _authenticated = True
            return {
                "status": "success",
                "account": active_account,
                "note": "Already authenticated",
            }
    except Exception:
        pass  # Continue to login attempt

    # Attempt login
    email = os.getenv("GCP_AUTH_EMAIL", "")
    if not email:
        return {
            "status": "error",
            "error_message": (
                "No active gcloud account and GCP_AUTH_EMAIL not set. "
                "Run 'gcloud auth login' manually or set GCP_AUTH_EMAIL."
            ),
        }

    logger.info(f"Attempting gcloud auth login for {email}")
    try:
        # For GCP lab environments, use activate-service-account if key file exists
        key_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if key_file and os.path.exists(key_file):
            login_result = subprocess.run(
                [
                    "gcloud",
                    "auth",
                    "activate-service-account",
                    email,
                    f"--key-file={key_file}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
        else:
            # Interactive login prompt — user needs to complete in browser
            login_result = subprocess.run(
                ["gcloud", "auth", "login", email, "--no-launch-browser", "--quiet"],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if login_result.returncode == 0:
            _set_project()
            _authenticated = True
            return {
                "status": "success",
                "account": email,
                "message": "gcloud authenticated successfully",
            }
        else:
            return {
                "status": "error",
                "error_message": (
                    f"gcloud auth login failed: {login_result.stderr.strip()}. "
                    "Try running 'gcloud auth login' manually."
                ),
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error_message": "gcloud auth login timed out. Run 'gcloud auth login' manually.",
        }
    except Exception as e:
        return {"status": "error", "error_message": f"Auth failed: {e}"}


def _set_project():
    """Set the active GCP project from environment."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    if project:
        try:
            subprocess.run(
                ["gcloud", "config", "set", "project", project],
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info(f"Set gcloud project to {project}")
        except Exception as e:
            logger.warning(f"Could not set gcloud project: {e}")


def get_gcloud_account() -> str:
    """Return the currently active gcloud account, or empty string."""
    try:
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "list",
                "--format",
                "value(account)",
                "--filter",
                "status:ACTIVE",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def load_service_key_credentials(key_path: str = None):
    """Load service account credentials from JSON key file.

    Args:
        key_path: Path to service key JSON file. If None, uses GCP_SERVICE_KEY_PATH from env.

    Returns:
        google.oauth2.service_account.Credentials object or None
    """
    global _service_account_credentials

    if not key_path:
        key_path = os.getenv("GCP_SERVICE_KEY_PATH", "")

    if not key_path:
        logger.warning("No service key path provided")
        return None

    # Make path absolute if relative
    if not os.path.isabs(key_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        key_path = os.path.join(base_dir, key_path)

    if not os.path.exists(key_path):
        logger.error(f"Service key file not found: {key_path}")
        return None

    try:
        with open(key_path, 'r') as f:
            key_data = json.load(f)

        # Validate key structure
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        for field in required_fields:
            if field not in key_data:
                logger.error(f"Service key missing required field: {field}")
                return None

        if key_data['type'] != 'service_account':
            logger.error(f"Invalid service key type: {key_data['type']}")
            return None

        # Create credentials object
        credentials = service_account.Credentials.from_service_account_file(
            key_path,
            scopes=[
                'https://www.googleapis.com/auth/cloud-platform',
                'https://www.googleapis.com/auth/compute',
            ]
        )

        _service_account_credentials = credentials
        logger.info(f"Loaded service account credentials: {key_data['client_email']}")
        logger.info(f"Project ID: {key_data['project_id']}")

        return credentials

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in service key file: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load service account credentials: {e}")
        return None


def get_service_account_credentials():
    """Get cached service account credentials or load them if not cached.

    Returns:
        google.oauth2.service_account.Credentials object or None
    """
    global _service_account_credentials

    if _service_account_credentials is None:
        _service_account_credentials = load_service_key_credentials()

    # Refresh token if expired
    if _service_account_credentials and not _service_account_credentials.valid:
        try:
            _service_account_credentials.refresh(Request())
            logger.info("Refreshed service account credentials")
        except Exception as e:
            logger.error(f"Failed to refresh service account credentials: {e}")
            return None

    return _service_account_credentials


def authenticate_with_service_key(key_path: str = None) -> dict:
    """Authenticate gcloud CLI using service account key.

    Args:
        key_path: Path to service key JSON file. If None, uses GCP_SERVICE_KEY_PATH from env.

    Returns:
        dict: Authentication status and details
    """
    if not key_path:
        key_path = os.getenv("GCP_SERVICE_KEY_PATH", "")

    if not key_path:
        return {
            "status": "error",
            "error_message": "No service key path provided. Set GCP_SERVICE_KEY_PATH in .env"
        }

    # Make path absolute if relative
    if not os.path.isabs(key_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        key_path = os.path.join(base_dir, key_path)

    if not os.path.exists(key_path):
        return {
            "status": "error",
            "error_message": f"Service key file not found: {key_path}"
        }

    try:
        # Authenticate gcloud with service account
        result = subprocess.run(
            [
                "gcloud",
                "auth",
                "activate-service-account",
                f"--key-file={key_path}"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            # Set project from key file
            with open(key_path, 'r') as f:
                key_data = json.load(f)
                project_id = key_data.get('project_id', '')
                client_email = key_data.get('client_email', '')

            if project_id:
                subprocess.run(
                    ["gcloud", "config", "set", "project", project_id],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

            # Load credentials for programmatic access
            load_service_key_credentials(key_path)

            logger.info(f"Successfully authenticated with service account: {client_email}")
            return {
                "status": "success",
                "account": client_email,
                "project": project_id,
                "message": "Service account authenticated successfully"
            }
        else:
            return {
                "status": "error",
                "error_message": f"Service account activation failed: {result.stderr.strip()}"
            }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Service account authentication failed: {e}"
        }

