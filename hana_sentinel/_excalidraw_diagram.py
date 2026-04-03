"""Generate HANA Sentinel architecture diagram on Excalidraw canvas."""
import json
import time
import urllib.request

CANVAS = "http://localhost:3100"
USE_NATIVE_LABELS = True


def _api(method, path, data=None):
    """Helper for canvas REST calls."""
    url = f"{CANVAS}{path}"
    body = json.dumps(data).encode() if data else None
    headers = {"Content-Type": "application/json"} if body else {}
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read())
    except Exception as e:
        err_body = ""
        if hasattr(e, "read"):
            err_body = e.read().decode()
        print(f"  {method} {path} → {e}  {err_body}")
        return None

# ── Layout constants ──────────────────────────────────────────────
SUP_W, SUP_H = 300, 80
AGT_W, AGT_H = 200, 55
TOOL_W, TOOL_H = 200, 48

# X positions for 6 columns (250px stride)
COL_X = [60, 310, 560, 810, 1060, 1310]
DIAGRAM_LEFT = COL_X[0]
DIAGRAM_RIGHT = COL_X[-1] + AGT_W
CENTER_X = (DIAGRAM_LEFT + DIAGRAM_RIGHT) / 2

# Y tiers
Y_SUP = 50
Y_AGT1 = 230
Y_AGT2 = 420
Y_TOOL1 = 630
Y_TOOL2 = 780

# Row 2: 5 agents, centered
ROW2_STRIDE = 250
ROW2_TOTAL_W = 4 * ROW2_STRIDE + AGT_W
ROW2_START = CENTER_X - ROW2_TOTAL_W / 2
COL5 = [ROW2_START + i * ROW2_STRIDE for i in range(5)]

# Tool row 1: 3 tools, centered
T1_STRIDE = 280
T1_TOTAL_W = 2 * T1_STRIDE + TOOL_W
T1_START = CENTER_X - T1_TOTAL_W / 2
TOOL1_X = [T1_START + i * T1_STRIDE for i in range(3)]

# Tool row 2: 4 tools, centered
T2_STRIDE = 280
T2_TOTAL_W = 3 * T2_STRIDE + TOOL_W
T2_START = CENTER_X - T2_TOTAL_W / 2
TOOL2_X = [T2_START + i * T2_STRIDE for i in range(4)]

# ── Color palette ─────────────────────────────────────────────────
C_SUP = "#7c3aed"       # Deep violet
C_SUP_STROKE = "#5b21b6"

AGENT_COLORS = {
    "health_agent":           ("#10b981", "#059669"),
    "backup_agent":           ("#3b82f6", "#2563eb"),
    "recovery_agent":         ("#f59e0b", "#d97706"),
    "sql_tuning_agent":       ("#06b6d4", "#0891b2"),
    "capacity_agent":         ("#ec4899", "#db2777"),
    "rag_agent":              ("#14b8a6", "#0d9488"),
    "browser_agent":          ("#8b5cf6", "#7c3aed"),
    "verifier_agent":         ("#f97316", "#ea580c"),
    "instance_monitor_agent": ("#ef4444", "#dc2626"),
    "instance_backup_agent":  ("#22d3ee", "#06b6d4"),
    "instance_healing_agent": ("#a855f7", "#9333ea"),
}

C_TOOL = "#e0e7ff"       # Light indigo
C_TOOL_STROKE = "#6366f1"

# ── Node definitions ──────────────────────────────────────────────
agents_row1 = [
    ("health_agent",      "Health Monitor"),
    ("backup_agent",      "Backup Agent"),
    ("recovery_agent",    "Recovery Agent"),
    ("sql_tuning_agent",  "SQL Tuning"),
    ("capacity_agent",    "Capacity Agent"),
    ("rag_agent",         "RAG Agent"),
]

agents_row2 = [
    ("browser_agent",          "Browser Agent"),
    ("verifier_agent",         "Verifier Agent"),
    ("instance_monitor_agent", "VM Monitor"),
    ("instance_backup_agent",  "Instance Backup"),
    ("instance_healing_agent", "Instance Healing"),
]

tools_row1 = [
    ("hana_tools",    "HANA Tools"),
    ("rag_tools",     "RAG Tools"),
    ("browser_tools", "Browser Tools"),
]

tools_row2 = [
    ("log_preproc",   "Log Preprocessor"),
    ("instance_diag", "VM Diagnostics"),
    ("instance_heal", "VM Healing"),
    ("gcp_snapshots", "GCP Snapshots"),
]

# ── Edges ─────────────────────────────────────────────────────────
sup_edges = [
    "health_agent", "backup_agent", "recovery_agent", "sql_tuning_agent",
    "capacity_agent", "rag_agent", "browser_agent", "verifier_agent",
    "instance_monitor_agent", "instance_backup_agent",
    "instance_healing_agent",
]

tool_edges = [
    ("health_agent", "hana_tools"),
    ("backup_agent", "hana_tools"),
    ("recovery_agent", "hana_tools"),
    ("sql_tuning_agent", "hana_tools"),
    ("sql_tuning_agent", "rag_tools"),
    ("capacity_agent", "hana_tools"),
    ("rag_agent", "rag_tools"),
    ("browser_agent", "browser_tools"),
    ("browser_agent", "rag_tools"),
    ("verifier_agent", "hana_tools"),
    ("verifier_agent", "browser_tools"),
    ("verifier_agent", "rag_tools"),
    ("instance_monitor_agent", "instance_diag"),
    ("instance_monitor_agent", "instance_heal"),
    ("instance_monitor_agent", "log_preproc"),
    ("instance_backup_agent", "gcp_snapshots"),
    ("instance_healing_agent", "instance_heal"),
]

# ── Build elements ────────────────────────────────────────────────
elements = []
node_centers = {}   # id -> (cx, cy)

def add_rect(eid, x, y, w, h, bg, stroke, label_text, font_size=18, stroke_width=2, label_color="#ffffff"):
    if USE_NATIVE_LABELS:
        # Native labels: centered by Excalidraw, no separate text element.
        # In REST mode text color is effectively tied to rectangle stroke color,
        # so we use label_color as strokeColor to preserve contrast.
        elements.append({
            "type": "rectangle",
            "id": eid,
            "x": x, "y": y,
            "width": w, "height": h,
            "backgroundColor": bg,
            "strokeColor": label_color,
            "strokeWidth": stroke_width,
            "fillStyle": "solid",
            "opacity": 100,
            "roughness": 0,
            "roundness": {"type": 3},
            "label": {
                "text": label_text,
                "fontSize": font_size,
                "textAlign": "center",
                "verticalAlign": "middle",
            },
        })
    else:
        # Rectangle shape (no label — we create the text element separately)
        elements.append({
            "type": "rectangle",
            "id": eid,
            "x": x, "y": y,
            "width": w, "height": h,
            "backgroundColor": bg,
            "strokeColor": stroke,
            "strokeWidth": stroke_width,
            "fillStyle": "solid",
            "opacity": 100,
            "roughness": 0,
            "roundness": {"type": 3},
            "boundElements": [{"type": "text", "id": f"{eid}_label"}],
        })
        # Bound text element — fill the full container rect so
        # textAlign/verticalAlign center it visually.
        PAD = 5
        text_h = font_size * 1.25
        elements.append({
            "type": "text",
            "id": f"{eid}_label",
            "x": x + PAD,
            "y": y + (h - text_h) / 2,
            "width": w - 2 * PAD,
            "height": text_h,
            "text": label_text,
            "originalText": label_text,
            "fontSize": font_size,
            "fontFamily": 3,
            "textAlign": "center",
            "verticalAlign": "middle",
            "strokeColor": label_color,
            "backgroundColor": "transparent",
            "containerId": eid,
            "autoResize": True,
            "lineHeight": 1.25,
            "opacity": 100,
        })
    node_centers[eid] = (x + w / 2, y + h / 2)

def add_arrow(eid, start_id, end_id, stroke_color="#475569", stroke_width=2,
              stroke_style="solid"):
    sx, sy = node_centers[start_id]
    ex, ey = node_centers[end_id]
    elements.append({
        "type": "arrow",
        "id": eid,
        "x": sx, "y": sy,
        "width": ex - sx,
        "height": ey - sy,
        "strokeColor": stroke_color,
        "strokeWidth": stroke_width,
        "strokeStyle": stroke_style,
        "roughness": 0,
        "opacity": 80,
        "startArrowhead": None,
        "endArrowhead": "arrow",
        "start": {"id": start_id},
        "end": {"id": end_id},
        "points": [[0, 0], [ex - sx, ey - sy]],
    })


def recenter_labels(max_passes: int = 6, settle_seconds: float = 2.0):
    """Re-center *_label texts based on actual rendered text dimensions.

    Canvas frontend sync may adjust text width/height after batch creation,
    so we run a short corrective pass using latest element geometry.
    """
    if settle_seconds > 0:
        print(f"  Waiting {settle_seconds:.1f}s for frontend sync...")
        time.sleep(settle_seconds)

    total_moved = 0
    for pass_idx in range(1, max_passes + 1):
        scene = _api("GET", "/api/elements")
        if not scene or "elements" not in scene:
            print(f"  Recenter pass {pass_idx}: scene unavailable")
            return

        all_elements = scene["elements"]
        rects = {e["id"]: e for e in all_elements if e.get("type") == "rectangle"}
        labels = [e for e in all_elements if e.get("type") == "text" and e.get("id", "").endswith("_label")]

        moved = 0
        for txt in labels:
            txt_id = txt["id"]
            parent_id = txt_id[:-6]  # strip "_label"
            parent = rects.get(parent_id)
            if not parent:
                continue

            nx = parent["x"] + (parent["width"] - txt["width"]) / 2
            ny = parent["y"] + (parent["height"] - txt["height"]) / 2

            if abs(txt["x"] - nx) > 0.2 or abs(txt["y"] - ny) > 0.2:
                _api("PUT", f"/api/elements/{txt_id}", {"x": nx, "y": ny})
                moved += 1
                total_moved += 1

        print(f"  Recenter pass {pass_idx}: moved {moved} label(s)")
        if moved == 0:
            break
        time.sleep(0.6)

    print(f"  Recenter complete: total moved {total_moved}")

# --- Title ---
elements.append({
    "type": "text",
    "id": "title",
    "x": CENTER_X - 250,
    "y": -40,
    "width": 500,
    "height": 40,
    "text": "HANA Ops Agent — Architecture",
    "fontSize": 28,
    "fontFamily": "3",
    "textAlign": "center",
    "strokeColor": "#1e293b",
    "opacity": 100,
})

# --- Tier labels ---
for lid, lx, ly, txt in [
    ("lbl_supervisor", -120, Y_SUP + SUP_H // 2 - 10, "Orchestrator"),
    ("lbl_agents", -120, (Y_AGT1 + Y_AGT2) / 2 + 5, "Agents"),
    ("lbl_tools", -120, (Y_TOOL1 + Y_TOOL2) / 2, "Tools"),
]:
    elements.append({
        "type": "text",
        "id": lid,
        "x": lx, "y": ly,
        "width": 120, "height": 30,
        "text": txt,
        "fontSize": 16,
        "fontFamily": 3,
        "textAlign": "right",
        "strokeColor": "#94a3b8",
        "opacity": 70,
    })

# --- Supervisor node ---
add_rect("supervisor", CENTER_X - SUP_W / 2, Y_SUP,
         SUP_W, SUP_H, C_SUP, C_SUP_STROKE,
         "\U0001f6e1\ufe0f  HANA Ops\nOrchestration Agent\n(Google ADK)",
         font_size=18, stroke_width=3)

# --- Agent nodes ---
for i, (aid, alabel) in enumerate(agents_row1):
    bg, stroke = AGENT_COLORS[aid]
    add_rect(aid, COL_X[i], Y_AGT1, AGT_W, AGT_H, bg, stroke, alabel)

for i, (aid, alabel) in enumerate(agents_row2):
    bg, stroke = AGENT_COLORS[aid]
    add_rect(aid, COL5[i], Y_AGT2, AGT_W, AGT_H, bg, stroke, alabel)

# --- Tool nodes ---
for i, (tid, tlabel) in enumerate(tools_row1):
    add_rect(tid, TOOL1_X[i], Y_TOOL1, TOOL_W, TOOL_H, C_TOOL, C_TOOL_STROKE, tlabel, font_size=14, stroke_width=1, label_color="#1e293b")

for i, (tid, tlabel) in enumerate(tools_row2):
    add_rect(tid, TOOL2_X[i], Y_TOOL2, TOOL_W, TOOL_H, C_TOOL, C_TOOL_STROKE, tlabel, font_size=14, stroke_width=1, label_color="#1e293b")

# --- Supervisor → Agent arrows (solid, darker) ---
for tgt in sup_edges:
    add_arrow(f"e-sup-{tgt}", "supervisor", tgt, stroke_color="#7c3aed", stroke_width=2)

# --- Agent → Tool arrows (dashed, lighter) ---
for src, tgt in tool_edges:
    add_arrow(f"e-{src}-{tgt}", src, tgt, stroke_color="#94a3b8", stroke_width=1,
              stroke_style="dashed")

# ── Send to canvas ────────────────────────────────────────────────
# Step 1: Clear canvas properly
print("Clearing canvas...")
_api("DELETE", "/api/elements/clear")
time.sleep(1)

# Step 2: Send all elements in batch (rectangles + text labels + arrows + decorations)
print(f"Sending {len(elements)} elements...")
result = _api("POST", "/api/elements/batch", {"elements": elements})
if result and result.get("success"):
    print(f"  Batch OK: {result.get('count', '?')} elements created")
else:
    print(f"  Batch FAILED: {result}")

# Step 3: Re-center labels after frontend sync settles text widths
if USE_NATIVE_LABELS:
    print("Using native labels (no separate text recenter pass needed).")
else:
    print("Re-centering labels...")
    recenter_labels(max_passes=6, settle_seconds=2.0)

# Step 4: Set viewport to fit diagram
_api("POST", "/api/viewport", {"scrollToContent": True})

print("Done!")
