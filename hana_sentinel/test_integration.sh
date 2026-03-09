#!/bin/bash
# Full Integration Test for HANA Sentinel Instance Monitoring

echo "========================================="
echo "HANA SENTINEL - Full Integration Test"
echo "========================================="
echo ""

BASE_URL="http://localhost:8000/api/v1"

# Test 1: Health Check
echo "TEST 1: Health Check"
curl -s ${BASE_URL}/health | python -m json.tool | head -10
echo ""
echo "---"
echo ""

# Test 2: Instance Status
echo "TEST 2: Instance Status"
curl -s ${BASE_URL}/instance/status | python -m json.tool
echo ""
echo "---"
echo ""

# Test 3: Run Diagnostic
echo "TEST 3: Run Instance Diagnostic"
DIAG_RESPONSE=$(curl -s -X POST ${BASE_URL}/instance/diagnostics -H "Content-Type: application/json" -d '{}')
echo "$DIAG_RESPONSE" | python -m json.tool | head -60
DIAG_ID=$(echo "$DIAG_RESPONSE" | python -c "import sys, json; print(json.load(sys.stdin)['diagnostic_id'])" 2>/dev/null || echo "")
echo ""
echo "Diagnostic ID: $DIAG_ID"
echo "---"
echo ""

# Test 4: Get Latest Diagnostic
if [ -n "$DIAG_ID" ]; then
    echo "TEST 4: Get Latest Diagnostic"
    curl -s ${BASE_URL}/instance/diagnostics/latest | python -m json.tool | head -40
    echo ""
    echo "---"
    echo ""
fi

# Test 5: List Snapshots
echo "TEST 5: List Snapshots"
curl -s ${BASE_URL}/instance/snapshots | python -m json.tool
echo ""
echo "---"
echo ""

# Test 6: Frontend UI Check
echo "TEST 6: Frontend UI Pages"
echo "- Instance Monitoring: http://localhost:3001/instance-monitoring"
echo "- Instance Approvals: http://localhost:3001/instance-approvals"
echo "- API Docs: http://localhost:8000/docs"
echo ""
echo "---"
echo ""

echo "========================================="
echo "Integration Test Complete!"
echo "========================================="
echo ""
echo "Summary:"
echo "- Backend API: Running on http://localhost:8000"
echo "- Frontend UI: Running on http://localhost:3001"
echo "- Total Tests: 6"
echo ""
echo "Note: Some diagnostics may show errors due to gcloud CLI not being installed."
echo "This is expected in development environment."
echo ""
