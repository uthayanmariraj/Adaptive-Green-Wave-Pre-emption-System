"""
server.py  —  AGWPS Flask Bridge
=================================
Connects the SUMO simulation to the dashboard by:
  1. Watching hospital_view.json  → merges live ambulance state into sumo_output.json
  2. POST /incident               → accepts dispatches from the dashboard form
                                    and writes pending_dispatch.json for the SUMO runner
  3. Serves sumo_output.json      → polled every 3 s by the dashboard
  4. Serves the dashboard HTML    → open http://localhost:5000 in your browser
  5. Auto-removes completed runs  → after COMPLETED_TTL seconds, removes from active list

Run:
    pip install flask
    python server.py

Directory layout expected (same folder as this file):
    server.py
    agwps_dashboard_merged__1_.html
    hospital_view.json                ← written by your SUMO simulation
    sumo_output.json                  ← auto-created / updated by this server
    pending_dispatch.json             ← written here, consumed by sumo_runner.py
"""

import json, os, time, threading
from flask import Flask, request, jsonify, send_from_directory

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR          = os.path.dirname(os.path.abspath(__file__))
HOSPITAL_VIEW     = os.path.join(BASE_DIR, "hospital_view.json")
SUMO_OUTPUT       = os.path.join(BASE_DIR, "sumo_output.json")
PENDING_DISPATCH  = os.path.join(BASE_DIR, "pending_dispatch.json")
DASHBOARD_HTML    = os.path.join(BASE_DIR, "agwps_dashboard_merged__1_.html")
SYNC_INTERVAL     = 2.0    # seconds between hospital_view.json reads
COMPLETED_TTL     = 10.0   # seconds to keep a completed ambulance before removing it

# ── In-memory state ───────────────────────────────────────────────────────────
ambulances: dict = {}          # keyed by ambulance_id
completed_at: dict = {}        # keyed by ambulance_id → timestamp when it completed
lock = threading.Lock()

app = Flask(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def injury_to_issue(level: str) -> str:
    return {
        "Critical": "Critical Injury — Priority Response",
        "High":     "Serious Trauma — High Priority",
        "Medium":   "Moderate Injury — En Route",
        "Low":      "Minor Injury — Routine Transfer",
    }.get(level, "Emergency")


def compute_progress(distance: float, total_length: float) -> float:
    # Guard against SUMO's INVALID_DOUBLE (-1073741824) leaking through
    if total_length <= 0 or distance < 0:
        return 0.0
    travelled = max(0.0, total_length - distance)
    return min(100.0, round(travelled / total_length * 100, 1))


def hospital_view_to_record(hv: dict) -> dict:
    amb_id       = hv.get("ambulance_id", "AMB-001")
    distance     = float(hv.get("distance", 0))
    total_length = float(hv.get("total_length", 1))
    next_stop    = hv.get("next_stop", "")
    injury_level = hv.get("injury_level", "Medium")
    eta          = float(hv.get("eta", 0))

    arrived  = (next_stop == "Arrived") or (distance == 0 and total_length > 0)
    status   = "Completed" if arrived else "En Route"
    progress = 100.0 if arrived else compute_progress(distance, total_length)

    # evrt is the *expected* total route time for the scenario — not the
    # live remaining eta.  Use the scenario lookup so the dashboard always
    # shows the correct comparison value.
    scenario = hv.get("scenario", "D")
    SCENARIO_EVRT = {"A": 118, "B": 89, "C": 78, "D": 55}
    evrt = SCENARIO_EVRT.get(scenario, 55)

    return {
        "id":          amb_id,
        "issue":       injury_to_issue(injury_level),
        "origin":      hv.get("origin", "INT-11"),
        "destination": hv.get("destination", "City Hospital"),
        "dest":        hv.get("destination", "City Hospital"),
        "scenario":    scenario,
        "evrt":        evrt,
        "status":      status,
        "progress":    progress,
        "injury_level": injury_level,
        "eta":         max(0, int(eta)) if eta and eta > 0 else 0,
    }


def write_sumo_output():
    """Serialise current ambulances dict → sumo_output.json, omitting stale completed runs."""
    now = time.time()
    with lock:
        # Remove ambulances that have been completed for longer than COMPLETED_TTL
        to_remove = [
            amb_id for amb_id, t in completed_at.items()
            if now - t > COMPLETED_TTL
        ]
        for amb_id in to_remove:
            ambulances.pop(amb_id, None)
            completed_at.pop(amb_id, None)
            print(f"[cleanup] Removed completed ambulance {amb_id} from active list")

        data = {
            "ambulances": list(ambulances.values()),
            "queue_cleared_rate": _queue_cleared_rate(),
            "last_updated": time.time(),
        }
    with open(SUMO_OUTPUT, "w") as f:
        json.dump(data, f, indent=2)


def _queue_cleared_rate() -> int:
    total     = len(ambulances)
    completed = sum(1 for a in ambulances.values() if a["status"] == "Completed")
    if total == 0:
        return 92
    return round(completed / total * 100)


def write_pending_dispatch(dispatch_record: dict):
    """
    Append a new dispatch request to pending_dispatch.json.
    The SUMO runner polls this file and injects the vehicle into the simulation.
    """
    try:
        existing = []
        if os.path.exists(PENDING_DISPATCH):
            with open(PENDING_DISPATCH, "r") as f:
                existing = json.load(f)
        existing.append(dispatch_record)
        with open(PENDING_DISPATCH, "w") as f:
            json.dump(existing, f, indent=2)
        print(f"[dispatch] Wrote pending dispatch for {dispatch_record.get('id')} → {PENDING_DISPATCH}")
    except Exception as e:
        print(f"[dispatch] Failed to write pending_dispatch.json: {e}")


# ── Background sync thread ────────────────────────────────────────────────────

def sync_hospital_view():
    """
    Reads hospital_view.json every SYNC_INTERVAL seconds.
    Merges changes into ambulances dict, records completion timestamps,
    and rewrites sumo_output.json.
    """
    last_mtime = 0.0
    while True:
        try:
            if os.path.exists(HOSPITAL_VIEW):
                mtime = os.path.getmtime(HOSPITAL_VIEW)
                if mtime != last_mtime:
                    last_mtime = mtime
                    with open(HOSPITAL_VIEW) as f:
                        raw = json.load(f)

                    entries = raw if isinstance(raw, list) else [raw]

                    with lock:
                        for hv in entries:
                            rec    = hospital_view_to_record(hv)
                            amb_id = rec["id"]

                            if amb_id in ambulances:
                                prev_status = ambulances[amb_id].get("status")
                                ambulances[amb_id].update(rec)
                                # Record the moment it completed for TTL removal
                                if rec["status"] == "Completed" and prev_status != "Completed":
                                    completed_at[amb_id] = time.time()
                                    print(f"[sync] {amb_id} marked Completed — will remove in {COMPLETED_TTL}s")
                            else:
                                ambulances[amb_id] = rec
                                if rec["status"] == "Completed":
                                    completed_at[amb_id] = time.time()

                    write_sumo_output()
                    print(f"[sync] Updated {len(entries)} ambulance(s) from hospital_view.json")

        except Exception as e:
            print(f"[sync] Error reading hospital_view.json: {e}")

        time.sleep(SYNC_INTERVAL)


# ── Flask routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "agwps_dashboard_merged__1_.html")


@app.route("/sumo_output.json")
def sumo_output():
    if not os.path.exists(SUMO_OUTPUT):
        write_sumo_output()
    return send_from_directory(BASE_DIR, "sumo_output.json")


@app.route("/incident", methods=["POST"])
def incident():
    """
    Accept a dispatch from the dashboard form or the hospital 'Raise Incident' button.

    Dispatch form payload:
        { id, issue, origin, destination, scenario, evrt, status }
    Raise incident payload:
        { type, pickup, urgency, hospital }
    """
    data = request.get_json(silent=True) or {}

    # ── Case 1: ambulance dispatch from Page 1 ──────────────────────────────
    if "id" in data:
        amb_id = data["id"]

        # Build the ambulance record
        record = {
            "id":          amb_id,
            "issue":       data.get("issue", "Emergency"),
            "origin":      data.get("origin", "INT-11"),
            "destination": data.get("destination", "City Hospital"),
            "dest":        data.get("destination", "City Hospital"),
            "scenario":    data.get("scenario", "D"),
            "evrt":        data.get("evrt", 55),
            "status":      "En Route",
            "progress":    0,
        }

        with lock:
            if amb_id not in ambulances:
                ambulances[amb_id] = record
            else:
                ambulances[amb_id].update(record)

        write_sumo_output()

        # Tell the SUMO runner to inject this ambulance into the simulation
        write_pending_dispatch({
            "id":          amb_id,
            "origin":      data.get("origin", "INT-11"),
            "destination": data.get("destination", "City Hospital"),
            "scenario":    data.get("scenario", "D"),
            "injury_level": data.get("injury_level", "Medium"),
            "issue":       data.get("issue", "Emergency"),
            "dispatched_at": time.time(),
        })

        print(f"[dispatch] Registered {amb_id} → {data.get('destination')}")
        return jsonify({"ok": True, "id": amb_id})

    # ── Case 2: incident raised from Page 2 (hospital) ──────────────────────
    if "type" in data:
        print(f"[incident] {data.get('type')} at {data.get('pickup')} — {data.get('urgency')}")
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "Unrecognised payload"}), 400


@app.route("/hospital_view.json")
def hospital_view_endpoint():
    if os.path.exists(HOSPITAL_VIEW):
        return send_from_directory(BASE_DIR, "hospital_view.json")
    return jsonify({}), 404


@app.route("/ambulance/<amb_id>", methods=["DELETE"])
def delete_ambulance(amb_id: str):
    """Manually remove an ambulance from the active list (e.g. after dashboard confirms removal)."""
    with lock:
        removed = ambulances.pop(amb_id, None)
        completed_at.pop(amb_id, None)
    if removed:
        write_sumo_output()
        print(f"[delete] Removed {amb_id} via DELETE request")
        return jsonify({"ok": True, "removed": amb_id})
    return jsonify({"ok": False, "error": "Not found"}), 404


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Clear stale state files from previous runs
    for f in [HOSPITAL_VIEW, SUMO_OUTPUT, PENDING_DISPATCH]:
        if os.path.exists(f):
            try: os.remove(f)
            except OSError: pass

    t = threading.Thread(target=sync_hospital_view, daemon=True)
    t.start()
    print("=" * 60)
    print("  AGWPS Bridge Server")
    print("  Dashboard   → http://localhost:5000")
    print(f"  Watching    → {HOSPITAL_VIEW}")
    print(f"  Writing     → {SUMO_OUTPUT}")
    print(f"  Dispatches  → {PENDING_DISPATCH}  (read by sumo_runner.py)")
    print(f"  Cleanup TTL → {COMPLETED_TTL}s after arrival")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)
