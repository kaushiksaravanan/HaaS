"""Upload remote_exec_server_v2.py to the GCP server via /execute endpoint."""
import base64
import json
import urllib.request
import sys

SERVER = "http://10.238.36.146:9999"
API_KEY = "REMOTE_EXEC_KEY_REVOKED_PLACEHOLDER_0000000000000000"
LOCAL_FILE = "remote_exec_server_v2.py"
REMOTE_TMP = "/tmp/server_b64.txt"
REMOTE_DEST = "/tmp/remote_exec_server_v2_new.py"
CHUNK_SIZE = 3500  # Stay well under 5000 char limit

def execute(cmd, timeout=30):
    data = json.dumps({"command": cmd, "timeout": timeout, "admin_override": True}).encode()
    req = urllib.request.Request(
        f"{SERVER}/execute",
        data=data,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=timeout + 5)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}

# Read and encode file
with open(LOCAL_FILE, "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

print(f"File size: {len(b64)} base64 chars")

# Clear temp file
r = execute(f"rm -f {REMOTE_TMP}")
print(f"Clear: {r.get('status')}")

# Upload chunks
chunks = [b64[i:i+CHUNK_SIZE] for i in range(0, len(b64), CHUNK_SIZE)]
print(f"Uploading {len(chunks)} chunks...")

for idx, chunk in enumerate(chunks, 1):
    cmd = f"printf '%s' '{chunk}' >> {REMOTE_TMP}"
    r = execute(cmd)
    if r.get("status") != "success":
        print(f"FAIL chunk {idx}: {r}")
        sys.exit(1)
    print(f"  Chunk {idx}/{len(chunks)} OK")

# Decode
r = execute(f"base64 -d {REMOTE_TMP} > {REMOTE_DEST}")
print(f"Decode: {r.get('status')} - {r.get('stdout', '')} {r.get('stderr', '')}")

# Verify
r = execute(f"wc -l {REMOTE_DEST}")
print(f"Line count: {r.get('stdout', '').strip()}")

r = execute(f"head -1 {REMOTE_DEST}")
print(f"First line: {r.get('stdout', '').strip()}")

r = execute(f"grep -c 'def run_hdbsql' {REMOTE_DEST}")
print(f"run_hdbsql functions: {r.get('stdout', '').strip()}")

print("\nDone! File at", REMOTE_DEST)
