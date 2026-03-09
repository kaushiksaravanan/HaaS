# HANA Database Agent Toolkit - README

## Overview
This toolkit provides AI agents with safe, structured scripts for monitoring and maintaining 24/7 running HANA databases. All operations are designed with safety as the primary concern.

## Directory Structure
```
hana_db_agent_toolkit/
├── docs/
│   └── AGENT_EXECUTION_GUIDE.md    # Main guide for AI agents
├── scripts/
│   ├── quick_diagnostic.sh          # Safe diagnostic checks
│   └── verify_healing.sh            # Verification after healing
└── logs/
    └── (generated log files)
```

## Quick Start for AI Agents

### 1. First Action: Always Run Diagnostics
```bash
cd scripts
chmod +x quick_diagnostic.sh
./quick_diagnostic.sh <SID> <INSTANCE>
```

### 2. Review the Execution Guide
Read `docs/AGENT_EXECUTION_GUIDE.md` for complete instructions on:
- Problem detection and response
- Safe diagnostic commands
- Healing script usage and approval requirements
- Verification procedures

### 3. Before Running Any Healing Script
**⚠️ CRITICAL: Get explicit approval first!**

The guide specifies:
- Which script to use for which problem
- Risk level of each operation
- Required verifications
- Rollback procedures

### 4. After Running Healing Script
```bash
./verify_healing.sh <script_name> <SID> <INSTANCE>
```

## Available Healing Scripts (Located in Parent Directory)

1. **auto_db_userstoremanagement**
   - Purpose: Fix HANA userstore keys
   - Risk: MEDIUM
   - Use for: Userstore connectivity issues

2. **auto_db_metadata**
   - Purpose: Fix backup paths, trace permissions, DB parameters
   - Risk: MEDIUM-HIGH
   - Use for: Backup/configuration issues

3. **auto_db_dbintegrations**
   - Purpose: Fix OS-level settings (swappiness, THP, ASLR)
   - Risk: HIGH
   - Use for: System configuration drift

4. **auto_db_eligibility**
   - Purpose: Validate/fix database backups and archives
   - Risk: MEDIUM
   - Use for: Backup validation failures

## Safety Rules

### ✅ ALWAYS DO:
- Run diagnostics before any action
- Document all operations in logs
- Get approval before running healing scripts
- Verify results after healing
- Escalate if uncertain

### ❌ NEVER DO:
- Run healing scripts without approval
- Make changes during production peak hours without approval
- Modify files outside this toolkit
- Ignore verification failures
- Attempt unapproved operations

## Example Workflow

### Scenario: Database connection issues detected

```bash
# Step 1: Run diagnostics
./quick_diagnostic.sh ABC 00

# Step 2: Review diagnostic output
# Issue found: Userstore key BKPMON not connectable

# Step 3: Request approval
# "I detected that BKPMON userstore key is not connectable.
#  I recommend running auto_db_userstoremanagement to fix this.
#  This script will reconfigure the userstore keys.
#  Risk level: MEDIUM. Approval required to proceed."

# Step 4: After approval, run healing script
cd ..
./auto_db_userstoremanagement <hostname> <parameters>

# Step 5: Verify the fix
cd scripts
./verify_healing.sh auto_db_userstoremanagement ABC 00

# Step 6: Confirm resolution
# "Healing completed successfully. BKPMON key is now connectable.
#  Verification log: logs/verification_auto_db_userstoremanagement_ABC_20260304_103000.log"
```

## Log Files

All operations create logs in the `logs/` directory:
- **Diagnostic logs**: `diagnostic_<SID>_<timestamp>.log`
- **Verification logs**: `verification_<script>_<SID>_<timestamp>.log`
- **Agent action logs**: `agent_actions_<timestamp>.log` (create these!)

## Escalation

Escalate to human operator if:
- Multiple healing attempts fail
- Database is DOWN
- Unfamiliar error encountered
- Verification shows persistent issues
- Any destructive operation is needed

## Important Notes

1. **Healing scripts are in parent directory** (`../auto_db_*`)
2. **This toolkit is READ-ONLY safe** - no modifications to live system without running parent scripts
3. **All healing requires approval** - see AGENT_EXECUTION_GUIDE.md
4. **Verification is mandatory** - always run after healing
5. **Logs are your record** - document everything

## Technical Details

### Supported Systems
- HANA 2.0 SPS 04 and above
- SLES 12 / SLES 15
- Multi-tenant (MDC) and single-tenant HANA systems

### Prerequisites
- Scripts must run as root or authorized user
- Database <sid>adm user must exist
- Userstore keys should be configured (SYSTEM, BKPMON, etc.)

### Common Issues
- **Permission denied**: Ensure running with proper privileges
- **User not found**: Verify SID is correct
- **SQL connection failed**: Database may be down or userstore not configured

## Version History
- v1.0 (2026-03-04): Initial toolkit creation
  - Safe diagnostic script
  - Verification script
  - Comprehensive execution guide

## Contact
For issues with this toolkit or escalations, follow your designated support procedures.

---

**Remember: Safety first. When in doubt, escalate!**
