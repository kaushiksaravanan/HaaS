# GCP Connection Configuration - CORRECTED

## ✅ Configuration Updates Applied

### 1. Zone Correction
**OLD**: `us-central1-a`
**NEW**: `europe-west3-a`

### 2. Project & Location
**Project**: `sap-development`
**Location**: `europe-west3`

### 3. Instance Details
- **Name**: `vlgdbzo3`
- **Zone**: `europe-west3-a`
- **HANA User**: `zo3adm`
- **SID**: `ZO3`
- **Instance Number**: `00`

### 4. Authentication Method
**Service Account**: `uihost@sap-development.iam.gserviceaccount.com`
**Key File**: `hana_db_agent_toolkit/sap-development-23f9847d3c33.json`

### 5. Connection Strategy
✅ **Primary**: gcloud compute ssh (with service account key)
❌ **Disabled**: Direct SSH (blocked by firewall)

### 6. gcloud Command That Will Be Used
```bash
gcloud auth activate-service-account \
  uihost@sap-development.iam.gserviceaccount.com \
  --key-file=hana_db_agent_toolkit/sap-development-23f9847d3c33.json

gcloud compute ssh zo3adm@vlgdbzo3 \
  --zone=europe-west3-a \
  --project=sap-development \
  --command="<command>"
```

## 📝 Environment Variables Set in .env

```bash
# Google Cloud Platform
GOOGLE_CLOUD_PROJECT=sap-development
GOOGLE_CLOUD_LOCATION=europe-west3
GOOGLE_APPLICATION_CREDENTIALS=hana_db_agent_toolkit/sap-development-23f9847d3c33.json
GCP_AUTH_EMAIL=uihost@sap-development.iam.gserviceaccount.com

# GCP Instance for HANA DB Agent Toolkit
GCP_SERVICE_KEY_PATH=hana_db_agent_toolkit/sap-development-23f9847d3c33.json
GCP_TOOLKIT_PROJECT_ID=sap-development
GCP_TOOLKIT_INSTANCE_NAME=vlgdbzo3
GCP_TOOLKIT_ZONE=europe-west3-a
GCP_TOOLKIT_HANA_USER=zo3adm
GCP_TOOLKIT_HANA_SID=ZO3
GCP_TOOLKIT_INSTANCE_NUMBER=00
```

## 🔧 Code Changes Made

### 1. `adk_app/tools/ssh_tools.py`
- Updated `_get_gcp_details()` to prioritize `GCP_TOOLKIT_*` variables
- Added logic to use `zo3adm` user for vlgdbzo3 instance
- Service key authentication is now primary method

### 2. `.env`
- Fixed zone from `us-central1-a` to `europe-west3-a`
- Updated project to `sap-development`
- Set service account email
- Configured `GOOGLE_APPLICATION_CREDENTIALS`

## 📦 Prerequisites

### To Enable Full Connectivity:

**Option 1: Install gcloud CLI (Required)**
```bash
# Windows
# Download from: https://cloud.google.com/sdk/docs/install-sdk#windows

# After installation:
gcloud auth activate-service-account \
  uihost@sap-development.iam.gserviceaccount.com \
  --key-file=hana_db_agent_toolkit/sap-development-23f9847d3c33.json

gcloud config set project sap-development
```

**Option 2: Test Without gcloud (Mock Mode)**
- System will return "connection failed" errors
- UI and API will still work
- Good for development/testing

## 🧪 Testing After gcloud Installation

```bash
# Test 1: Verify gcloud auth
gcloud auth list

# Test 2: Test SSH connection
gcloud compute ssh zo3adm@vlgdbzo3 \
  --zone=europe-west3-a \
  --project=sap-development \
  --command="echo 'Connection successful'"

# Test 3: Run diagnostic via API
curl -X POST http://localhost:8000/api/v1/instance/diagnostics

# Test 4: Check UI
# Open: http://localhost:3001/instance-monitoring
```

## 🎯 Expected Behavior

### Without gcloud CLI:
- ❌ SSH connection fails (expected)
- ✅ API endpoints work
- ✅ Frontend UI loads
- ℹ️ Diagnostics show "connection errors"

### With gcloud CLI installed:
- ✅ Service key authentication
- ✅ SSH to vlgdbzo3 via gcloud
- ✅ All 10 diagnostic checks work
- ✅ Healing scripts can execute
- ✅ VM snapshots can be created

## 🔒 Security Notes

1. **Service Key**: Already configured in project
2. **Direct SSH**: Blocked by firewall (good security practice)
3. **gcloud SSH**: Uses IAM permissions (more secure)
4. **No Password Storage**: Service account uses key file only

## 📊 Connection Flow

```
1. Load service key from: hana_db_agent_toolkit/sap-development-23f9847d3c33.json
2. Authenticate gcloud CLI with service account
3. Execute: gcloud compute ssh zo3adm@vlgdbzo3 --zone=europe-west3-a
4. Switch to HANA user context (already zo3adm)
5. Run commands: sapcontrol, HDB info, df, etc.
6. Return results to API
7. Display in React UI
```

---

**Status**: Configuration is now correct for vlgdbzo3 in europe-west3-a!
**Next Step**: Install gcloud CLI to enable full connectivity.
