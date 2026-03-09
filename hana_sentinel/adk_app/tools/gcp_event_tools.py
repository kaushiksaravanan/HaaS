"""
GCP Event Tools — Pub/Sub and Cloud Run integration for HANA Sentinel.
Pub/Sub: Event-driven monitoring triggers (publish alerts, subscribe to events).
Cloud Run: Dispatch agent tasks to serverless containers.

These tools enable:
1. Publishing HANA alerts/events to Pub/Sub topics for downstream consumers.
2. Subscribing to Pub/Sub topics for event-driven agent activation.
3. Dispatching monitoring/remediation tasks to Cloud Run services.
4. Receiving Cloud Run health pings and task results.

NO MOCK — real GCP calls or explicit error.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pub/Sub Client
# ──────────────────────────────────────────────
_publisher = None
_subscriber = None


def _get_publisher():
    """Lazy-init Pub/Sub publisher client."""
    global _publisher
    if _publisher is None:
        try:
            from google.cloud import pubsub_v1

            _publisher = pubsub_v1.PublisherClient()
        except ImportError:
            raise ImportError(
                "google-cloud-pubsub not installed. "
                "Install via: pip install google-cloud-pubsub"
            )
    return _publisher


def _get_subscriber():
    """Lazy-init Pub/Sub subscriber client."""
    global _subscriber
    if _subscriber is None:
        try:
            from google.cloud import pubsub_v1

            _subscriber = pubsub_v1.SubscriberClient()
        except ImportError:
            raise ImportError(
                "google-cloud-pubsub not installed. "
                "Install via: pip install google-cloud-pubsub"
            )
    return _subscriber


def _get_project() -> str:
    return os.getenv("GOOGLE_CLOUD_PROJECT", "")


def _get_topic(name: str = "") -> str:
    project = _get_project()
    topic = name or os.getenv("PUBSUB_ALERT_TOPIC", "hana-sentinel-alerts")
    return f"projects/{project}/topics/{topic}"


def _get_subscription(name: str = "") -> str:
    project = _get_project()
    sub = name or os.getenv("PUBSUB_EVENT_SUBSCRIPTION", "hana-sentinel-events-sub")
    return f"projects/{project}/subscriptions/{sub}"


# ──────────────────────────────────────────────
# ADK Tool Functions — Pub/Sub
# ──────────────────────────────────────────────


def pubsub_publish_alert(
    alert_type: str,
    severity: str,
    message: str,
    details: str = "",
    topic_name: str = "",
) -> dict:
    """Publish an alert event to Google Cloud Pub/Sub.
    Used to notify downstream systems (dashboards, pagers, ITSM) about HANA events.

    Args:
        alert_type (str): Type of alert (e.g., 'service_down', 'disk_critical', 'backup_failed', 'security_drift').
        severity (str): Severity level (CRITICAL, WARNING, INFO).
        message (str): Human-readable alert message.
        details (str): Additional JSON details or context.
        topic_name (str): Pub/Sub topic name. If empty, uses PUBSUB_ALERT_TOPIC env var.

    Returns:
        dict: status, message_id, and topic path.
    """
    project = _get_project()
    if not project:
        return {
            "status": "error",
            "error_message": "GOOGLE_CLOUD_PROJECT not set. Cannot publish to Pub/Sub.",
        }

    try:
        publisher = _get_publisher()
        topic_path = _get_topic(topic_name)

        payload = {
            "source": "hana_sentinel",
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "hana_sid": os.getenv("HANA_SID", "unknown"),
        }

        data = json.dumps(payload).encode("utf-8")
        future = publisher.publish(
            topic_path,
            data,
            alert_type=alert_type,
            severity=severity,
            source="hana_sentinel",
        )
        message_id = future.result(timeout=30)

        return {
            "status": "success",
            "message_id": message_id,
            "topic": topic_path,
            "alert_type": alert_type,
            "severity": severity,
        }
    except ImportError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Pub/Sub publish failed: {e}",
            "topic": _get_topic(topic_name),
        }


def pubsub_pull_events(
    max_messages: int = 10,
    subscription_name: str = "",
    auto_ack: bool = True,
) -> dict:
    """Pull events from a Google Cloud Pub/Sub subscription.
    Used for event-driven agent activation — e.g., triggered by external alerting.

    Args:
        max_messages (int): Maximum number of messages to pull (default: 10).
        subscription_name (str): Subscription name. If empty, uses PUBSUB_EVENT_SUBSCRIPTION env var.
        auto_ack (bool): Whether to automatically acknowledge messages (default: True).

    Returns:
        dict: status and list of events with their data and attributes.
    """
    project = _get_project()
    if not project:
        return {
            "status": "error",
            "error_message": "GOOGLE_CLOUD_PROJECT not set. Cannot pull from Pub/Sub.",
        }

    try:
        subscriber = _get_subscriber()
        sub_path = _get_subscription(subscription_name)

        response = subscriber.pull(
            request={"subscription": sub_path, "max_messages": max_messages},
            timeout=30,
        )

        events = []
        ack_ids = []
        for msg in response.received_messages:
            try:
                data = json.loads(msg.message.data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                data = msg.message.data.decode("utf-8", errors="replace")

            events.append(
                {
                    "message_id": msg.message.message_id,
                    "data": data,
                    "attributes": dict(msg.message.attributes),
                    "publish_time": msg.message.publish_time.isoformat()
                    if msg.message.publish_time
                    else "",
                }
            )
            ack_ids.append(msg.ack_id)

        if auto_ack and ack_ids:
            subscriber.acknowledge(
                request={"subscription": sub_path, "ack_ids": ack_ids}
            )

        return {
            "status": "success",
            "events": events,
            "count": len(events),
            "subscription": sub_path,
            "acknowledged": auto_ack,
        }
    except ImportError as e:
        return {"status": "error", "error_message": str(e)}
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Pub/Sub pull failed: {e}",
            "subscription": _get_subscription(subscription_name),
        }


def pubsub_create_topic(topic_name: str) -> dict:
    """Create a new Pub/Sub topic for HANA Sentinel events.

    Args:
        topic_name (str): Name for the new topic.

    Returns:
        dict: status and topic path.
    """
    project = _get_project()
    if not project:
        return {"status": "error", "error_message": "GOOGLE_CLOUD_PROJECT not set."}

    try:
        publisher = _get_publisher()
        topic_path = _get_topic(topic_name)
        publisher.create_topic(request={"name": topic_path})
        return {"status": "success", "topic": topic_path}
    except Exception as e:
        if "ALREADY_EXISTS" in str(e):
            return {
                "status": "success",
                "topic": _get_topic(topic_name),
                "note": "Topic already exists",
            }
        return {"status": "error", "error_message": f"Create topic failed: {e}"}


# ──────────────────────────────────────────────
# ADK Tool Functions — Cloud Run
# ──────────────────────────────────────────────


def cloudrun_dispatch_task(
    task_type: str,
    payload: str = "",
    service_name: str = "",
    region: str = "",
) -> dict:
    """Dispatch a monitoring or remediation task to a Cloud Run service.
    Used to run heavyweight agent tasks in serverless containers with auto-scaling.

    Args:
        task_type (str): Type of task (e.g., 'health_check', 'backup_verify', 'log_analysis', 'chaos_test').
        payload (str): JSON payload to send to the Cloud Run service.
        service_name (str): Cloud Run service name. If empty, uses CLOUDRUN_SERVICE env var.
        region (str): GCP region. If empty, uses GOOGLE_CLOUD_LOCATION env var.

    Returns:
        dict: status and Cloud Run response.
    """
    import subprocess

    project = _get_project()
    if not project:
        return {"status": "error", "error_message": "GOOGLE_CLOUD_PROJECT not set."}

    svc = service_name or os.getenv("CLOUDRUN_SERVICE", "hana-sentinel-agent")
    loc = region or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    # Build service URL
    svc_url = os.getenv("CLOUDRUN_SERVICE_URL", "")
    if not svc_url:
        # Try to discover via gcloud
        try:
            result = subprocess.run(
                [
                    "gcloud",
                    "run",
                    "services",
                    "describe",
                    svc,
                    "--project",
                    project,
                    "--region",
                    loc,
                    "--format",
                    "value(status.url)",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                svc_url = result.stdout.strip()
            else:
                return {
                    "status": "error",
                    "error_message": (
                        f"Cannot discover Cloud Run URL for '{svc}' in {loc}. "
                        f"Set CLOUDRUN_SERVICE_URL or deploy the service. "
                        f"stderr: {result.stderr.strip()}"
                    ),
                }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {
                "status": "error",
                "error_message": f"gcloud not available or timed out: {e}. Set CLOUDRUN_SERVICE_URL manually.",
            }

    # Make the HTTP request to Cloud Run
    try:
        import urllib.request
        import urllib.error

        task_payload = {
            "source": "hana_sentinel",
            "task_type": task_type,
            "payload": json.loads(payload) if payload else {},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        req = urllib.request.Request(
            f"{svc_url}/tasks",
            data=json.dumps(task_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        # For authenticated Cloud Run, use identity token
        id_token = os.getenv("CLOUDRUN_ID_TOKEN", "")
        if id_token:
            req.add_header("Authorization", f"Bearer {id_token}")
        else:
            # Try to get token via gcloud
            try:
                token_result = subprocess.run(
                    ["gcloud", "auth", "print-identity-token"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if token_result.returncode == 0:
                    req.add_header(
                        "Authorization", f"Bearer {token_result.stdout.strip()}"
                    )
            except Exception:
                pass  # Proceed without auth (service may allow unauthenticated)

        with urllib.request.urlopen(req, timeout=60) as resp:
            response_data = resp.read().decode("utf-8")
            try:
                response_json = json.loads(response_data)
            except json.JSONDecodeError:
                response_json = response_data

            return {
                "status": "success",
                "service": svc,
                "service_url": svc_url,
                "task_type": task_type,
                "response": response_json,
                "http_status": resp.status,
            }

    except urllib.error.HTTPError as e:
        return {
            "status": "error",
            "error_message": f"Cloud Run HTTP {e.code}: {e.reason}",
            "service_url": svc_url,
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Cloud Run dispatch failed: {e}",
            "service_url": svc_url,
        }


def cloudrun_get_service_status(
    service_name: str = "",
    region: str = "",
) -> dict:
    """Check the status of a Cloud Run service (ready, URL, latest revision).

    Args:
        service_name (str): Cloud Run service name. Uses CLOUDRUN_SERVICE env var if empty.
        region (str): GCP region. Uses GOOGLE_CLOUD_LOCATION if empty.

    Returns:
        dict: Service status including URL, conditions, and latest revision.
    """
    import subprocess

    project = _get_project()
    if not project:
        return {"status": "error", "error_message": "GOOGLE_CLOUD_PROJECT not set."}

    svc = service_name or os.getenv("CLOUDRUN_SERVICE", "hana-sentinel-agent")
    loc = region or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    try:
        result = subprocess.run(
            [
                "gcloud",
                "run",
                "services",
                "describe",
                svc,
                "--project",
                project,
                "--region",
                loc,
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return {
                "status": "error",
                "error_message": f"gcloud describe failed: {result.stderr.strip()}",
                "service": svc,
            }

        info = json.loads(result.stdout)
        conditions = info.get("status", {}).get("conditions", [])
        url = info.get("status", {}).get("url", "")
        latest = info.get("status", {}).get("latestReadyRevisionName", "")

        return {
            "status": "success",
            "service": svc,
            "url": url,
            "latest_revision": latest,
            "conditions": [
                {
                    "type": c.get("type"),
                    "status": c.get("status"),
                    "reason": c.get("reason", ""),
                }
                for c in conditions
            ],
            "ready": any(
                c.get("type") == "Ready" and c.get("status") == "True"
                for c in conditions
            ),
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "error_message": "gcloud CLI not found. Install Google Cloud SDK.",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Cloud Run status check failed: {e}",
        }


def cloudrun_deploy_agent(
    image: str,
    service_name: str = "",
    region: str = "",
    memory: str = "1Gi",
    cpu: str = "1",
    env_vars: str = "",
) -> dict:
    """Deploy or update a HANA Sentinel agent as a Cloud Run service.

    Args:
        image (str): Container image URI (e.g., 'gcr.io/project/hana-sentinel:latest').
        service_name (str): Cloud Run service name. Uses CLOUDRUN_SERVICE env var if empty.
        region (str): GCP region. Uses GOOGLE_CLOUD_LOCATION if empty.
        memory (str): Memory allocation (default: 1Gi).
        cpu (str): CPU allocation (default: 1).
        env_vars (str): Comma-separated KEY=VALUE environment variables.

    Returns:
        dict: Deployment status and service URL.
    """
    import subprocess

    project = _get_project()
    if not project:
        return {"status": "error", "error_message": "GOOGLE_CLOUD_PROJECT not set."}

    svc = service_name or os.getenv("CLOUDRUN_SERVICE", "hana-sentinel-agent")
    loc = region or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    cmd = [
        "gcloud",
        "run",
        "deploy",
        svc,
        "--image",
        image,
        "--project",
        project,
        "--region",
        loc,
        "--memory",
        memory,
        "--cpu",
        cpu,
        "--platform",
        "managed",
        "--no-allow-unauthenticated",
        "--quiet",
    ]

    if env_vars:
        cmd.extend(["--set-env-vars", env_vars])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            # Get URL
            status = cloudrun_get_service_status(svc, loc)
            return {
                "status": "success",
                "service": svc,
                "url": status.get("url", ""),
                "message": f"Deployed {image} to {svc}",
            }
        else:
            return {
                "status": "error",
                "error_message": f"Deployment failed: {result.stderr.strip()}",
            }
    except FileNotFoundError:
        return {"status": "error", "error_message": "gcloud CLI not found."}
    except Exception as e:
        return {"status": "error", "error_message": f"Deploy failed: {e}"}
