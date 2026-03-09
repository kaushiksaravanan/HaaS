# GCP Connection Configuration

## Instance Details
- **Name**: `vlgdbzo3`
- **Zone**: `europe-west3-a`
- **Project**: `sap-development`
- **HANA User**: `zo3adm`
- **SID**: `ZO3`
- **Instance Number**: `02`

## Connection Method

All access to the HANA server is via the **Remote Exec HTTP Server** running on port 9999.

```
Local Machine → HTTP POST → Remote Exec Server (10.238.36.146:9999) → Shell → HANA
```

### Remote Exec Server Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/execute` | POST | Execute shell command |
| `/hana/sql` | POST | Execute HANA SQL query |
| `/hana/metrics/current` | GET | Current HANA metrics |
| `/hana/metrics/history` | GET | Historical metrics |
| `/health` | GET | Server health check |

### Authentication
All requests require the `X-API-Key` header.

## Environment Variables

```bash
# Remote Exec Server
REMOTE_EXEC_URL=http://10.238.36.146:9999
REMOTE_EXEC_API_KEY=<your-api-key>

# HANA Connection (used by remote exec server)
HANA_SID=ZO3
HANA_INSTANCE_NR=02
HANA_USER=SYSTEM
HANA_HOST=localhost
HANA_PORT=30213
```

## Connection Flow

```
1. Frontend/API makes request to local FastAPI backend (port 8000)
2. Backend sends HTTP request to Remote Exec Server (port 9999)
3. Remote Exec Server executes command on vlgdbzo3
4. Results returned via HTTP response
5. Backend processes and returns to frontend
```
