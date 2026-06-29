"""
sumo_runner.py  —  AGWPS SUMO Simulation Runner
================================================
Runs the SUMO simulation in a continuous loop.

Key behaviours
--------------
1. DISPATCH INJECTION
   Polls pending_dispatch.json (written by server.py whenever the dashboard
   submits a new ambulance).  For each pending entry it inserts a new vehicle
   into the running simulation on the default ambulance route:
       A0B0 → B0B1 → B1C1 → C1D1   (INT-11 → City Hospital, Scenario D)

2. TRAFFIC PRE-EMPTION
   For every tracked ambulance, when the next traffic light is within 100 m
   the relevant signal phase is forced green.  Once the ambulance has passed,
   the signal reverts to its normal programme.

3. LIVE STATUS UPDATES  →  hospital_view.json
   Every step, each tracked ambulance's remaining distance, ETA, and progress
   are written so server.py / the dashboard stay in sync.

4. ARRIVAL DETECTION  →  hospital_view.json  +  completed_runs.json
   When an ambulance reaches within 5 m of its destination its status is
   flipped to "Arrived", its record is persisted to completed_runs.json, and
   it is removed from the active tracking set.

Run:
    python sumo_runner.py
"""

import os, sys, json, time, traci

# ── Config ────────────────────────────────────────────────────────────────────
SUMO_CONFIG       = "config/simulation.sumocfg"
PENDING_DISPATCH  = "pending_dispatch.json"
HOSPITAL_VIEW     = "hospital_view.json"
COMPLETED_RUNS    = "completed_runs.json"
PREEMPT_LOG       = "preempt_log.txt"

# Default route: INT-11 (A0) → City Hospital (D1 area)
DEFAULT_ROUTE_EDGES = "A0B0 B0B1 B1C1 C1C2 C2D2 D2D3"
DEFAULT_ROUTE_ID    = "amb_route_default"
TOTAL_LENGTH        = 1174.8   # metres — updated length for the new 6-edge route

# ── Helpers ───────────────────────────────────────────────────────────────────

def read_pending_dispatches() -> list:
    """Read and clear pending_dispatch.json.  Returns list of dispatch dicts."""
    if not os.path.exists(PENDING_DISPATCH):
        return []
    try:
        with open(PENDING_DISPATCH, "r") as f:
            pending = json.load(f)
        # Clear the file immediately so we don't re-process
        with open(PENDING_DISPATCH, "w") as f:
            json.dump([], f)
        return pending if isinstance(pending, list) else []
    except Exception as e:
        print(f"[runner] Error reading pending_dispatch.json: {e}")
        return []


def load_completed_runs() -> list:
    if not os.path.exists(COMPLETED_RUNS):
        return []
    try:
        with open(COMPLETED_RUNS, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_completed_run(record: dict):
    runs = load_completed_runs()
    # Update existing record or append
    existing = next((r for r in runs if r["ambulance_id"] == record["ambulance_id"]), None)
    if existing:
        existing.update(record)
    else:
        runs.append(record)
    with open(COMPLETED_RUNS, "w") as f:
        json.dump(runs, f, indent=2)


def write_hospital_view(active_ambulances: dict):
    """
    Write hospital_view.json.
    active_ambulances: { veh_id: { meta fields } }
    """
    entries = list(active_ambulances.values())
    if len(entries) == 1:
        # Backward-compatible single-object format
        with open(HOSPITAL_VIEW, "w") as f:
            json.dump(entries[0], f)
    else:
        with open(HOSPITAL_VIEW, "w") as f:
            json.dump(entries, f, indent=2)


def generate_dynamic_route(origin_label, hospital_name):
    # Map origin, e.g. "INT-11" -> Node A0
    try:
        r = int(origin_label[4]) - 1
        c = int(origin_label[5]) - 1
        cols = ['A', 'B', 'C', 'D']
        start_node = f"{cols[c]}{r}"
    except Exception:
        start_node = "A0"
        
    # Map destination hospital to node
    hosp = hospital_name.lower()
    if 'city' in hosp: end_node = 'D3'
    elif 'metro' in hosp: end_node = 'D1'
    elif 'general' in hosp: end_node = 'B2'
    else: end_node = 'D3'

    print(f"[router] Attempting to route from {start_node} to {end_node}")

    all_edges = traci.edge.getIDList()
    
    # Use 'in' instead of startswith/endswith to capture reverse edges like '-B2C2'
    start_edges = [e for e in all_edges if (start_node in e) and not e.startswith(":")]
    end_edges   = [e for e in all_edges if (end_node in e) and not e.startswith(":")]
    
    print(f"[router] found start_edges: {start_edges}, end_edges: {end_edges}")

    if not start_edges or not end_edges:
        print("[router] Missing start or end edges.")
        return []

    best_route = []
    best_time = float('inf')
    
    for s in start_edges:
        for e in end_edges:
            try:
                route = traci.simulation.findRoute(s, e)
                if route and len(route.edges) > 0:
                    if route.travelTime < best_time:
                        best_time = route.travelTime
                        best_route = list(route.edges)
            except Exception as ex:
                pass
                
    if best_route:
        print(f"[router] Success! Dynamic edges: {best_route}")
    return best_route

def inject_ambulance(dispatch: dict) -> tuple:
    """
    Dynamically generates a route and inserts a vehicle.
    Returns (True, total_length) if successful, otherwise (False, 0.0)
    """
    veh_id  = dispatch["id"]
    step    = traci.simulation.getTime()
    origin  = dispatch.get("origin", "INT-11")
    dest    = dispatch.get("destination", "City Hospital")

    # Generate custom path
    route_edges = generate_dynamic_route(origin, dest)
    if not route_edges:
        route_edges = DEFAULT_ROUTE_EDGES.split()
        print(f"[runner] Dynamic route failed. Falling back to default for {veh_id}")

    route_id = f"route_{veh_id}_{int(time.time() * 1000)}"

    try:
        traci.route.add(route_id, route_edges)

        traci.vehicle.add(
            vehID    = veh_id,
            routeID  = route_id,
            typeID   = "passenger",
            depart   = "now",
            departLane  = "best",
            departSpeed = "max",
        )
        traci.vehicle.setColor(veh_id, (255, 0, 0, 255))
        
        # Calculate standard length for progress tracking
        tot_len = 0.0
        for edge_id in route_edges:
            try: tot_len += traci.lane.getLength(edge_id + "_0")
            except Exception: tot_len += 200.0
            
        print(f"[runner] Step {step}: Injected '{veh_id}' directly from {origin} to {dest} (Length: {tot_len:.1f}m)")
        return True, tot_len

    except traci.exceptions.TraCIException as e:
        print(f"[runner] Failed to inject '{veh_id}': {e}")
        return False, 0.0


# ── Main simulation loop ──────────────────────────────────────────────────────

def run():
    traci.start([
        "sumo-gui", "-c", SUMO_CONFIG,
        "--no-step-log", "true",
        "--no-warnings", "true",
        "--start", "true", # optionally start automatically
        "--scale", "0.3",  # reduce background traffic to 30%
    ])

    # active_ambulances:  veh_id → hospital_view-shaped dict
    active_ambulances: dict = {}
    # active_preemptions: set of TLS IDs currently forced green
    active_preemptions: dict = {}   # veh_id → set of locked TLS IDs

    route_added   = False   # have we called traci.route.add yet?
    processed_ids = set()   # dispatch IDs we have already injected

    with open(PREEMPT_LOG, "w") as log:

        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            time.sleep(0.05)  # Enforce a 50ms delay per step so we can see the simulation
            step = traci.simulation.getTime()

            # ── 1. Check for new dispatches every step ──────────────────────
            pending = read_pending_dispatches()
            for dispatch in pending:
                veh_id = dispatch.get("id")
                if not veh_id or veh_id in processed_ids:
                    continue
                processed_ids.add(veh_id)

                ok, route_length = inject_ambulance(dispatch)
                if ok:
                    # Initialise tracking record
                    active_ambulances[veh_id] = {
                        "ambulance_id": veh_id,
                        "eta":          999,
                        "distance":     route_length,
                        "total_length": route_length,
                        "injury_level": dispatch.get("injury_level", "Medium"),
                        "origin":       dispatch.get("origin", "INT-11"),
                        "destination":  dispatch.get("destination", "City Hospital"),
                        "scenario":     dispatch.get("scenario", "D"),
                        "issue":        dispatch.get("issue", "Emergency"),
                        "next_stop":    dispatch.get("destination", "City Hospital"),
                        "has_departed": False,
                    }
                    active_preemptions[veh_id] = set()

            # ── 2. Track each active ambulance ──────────────────────────────
            sim_vehicles = set(traci.vehicle.getIDList())
            arrived_ids  = []

            for veh_id, rec in active_ambulances.items():

                # ── 2a. Pre-emption ─────────────────────────────────────────
                if veh_id in sim_vehicles:
                    rec["has_departed"] = True
                    next_tls_data = traci.vehicle.getNextTLS(veh_id)
                    current_target_tls = next_tls_data[0][0] if next_tls_data else None

                    # Initialize release queue if not present
                    if "release_queue" not in rec:
                        rec["release_queue"] = {}

                    if next_tls_data:
                        tls_id, tls_index, dist, current_state = next_tls_data[0]
                        if dist < 150:
                            # Read the LIVE state and only flip the ambulance's index to G.
                            # Never blank out other lanes — that would red-light the ambulance's
                            # own approach if its link index differs from what we assumed.
                            live_state = list(traci.trafficlight.getRedYellowGreenState(tls_id))

                            # Also check ALL links at this TLS that serve the ambulance's
                            # incoming edge so we don't miss a split-phase junction.
                            try:
                                controlled_links = traci.trafficlight.getControlledLinks(tls_id)
                                amb_road = traci.vehicle.getRoadID(veh_id)
                                for link_idx, links in enumerate(controlled_links):
                                    for link in links:
                                        # link = (incoming_lane, outgoing_lane, via_lane)
                                        if link and link[0].startswith(amb_road):
                                            live_state[link_idx] = 'G'
                            except Exception:
                                pass  # fall back to just forcing the reported index

                            # Always force the reported link index green
                            live_state[tls_index] = 'G'
                            desired_state_str = "".join(live_state)

                            # Cancel any pending release if we re-acquire this TLS
                            if tls_id in rec["release_queue"]:
                                del rec["release_queue"][tls_id]

                            current_live = traci.trafficlight.getRedYellowGreenState(tls_id)
                            active_preemptions[veh_id].add(tls_id)

                            if current_live != desired_state_str:
                                traci.trafficlight.setRedYellowGreenState(tls_id, desired_state_str)
                                # Do NOT call setPhaseDuration here — locking the timer
                                # prevents SUMO from stepping through to the phase that
                                # actually serves the ambulance's lane.
                                log.write(f"Step {step}: [{veh_id}] Forced GREEN at {tls_id} index {tls_index} (road={traci.vehicle.getRoadID(veh_id)}). State: {desired_state_str}\n")
                            else:
                                log.write(f"Step {step}: [{veh_id}] {tls_id} index {tls_index} already G. State: {current_live}\n")

                    # FIX 2: Delayed Release mechanism
                    # Move passed signals from active tracking to the delayed release queue
                    for locked_tls in list(active_preemptions.get(veh_id, set())):
                        if locked_tls != current_target_tls:
                            rec["release_queue"][locked_tls] = step + 4.0 # 4 second buffer to cross
                            active_preemptions[veh_id].discard(locked_tls)
                            log.write(f"Step {step}: [{veh_id}] Queued release for {locked_tls}\n")

                    # Process the delayed release queue
                    for q_tls, release_step in list(rec["release_queue"].items()):
                        if step >= release_step:
                            traci.trafficlight.setProgram(q_tls, "0")
                            del rec["release_queue"][q_tls]
                            log.write(f"Step {step}: [{veh_id}] Executed delayed release for {q_tls}\n")

                    # ── 2b. Distance / ETA / progress ───────────────────────
                    try:
                        road_id            = traci.vehicle.getRoadID(veh_id)
                        remaining_distance = traci.vehicle.getDrivingDistance(veh_id, road_id, 0)

                        # SUMO returns -1073741824.0 (INVALID_DOUBLE) when the
                        # vehicle hasn't fully entered the network yet.  Skip
                        # the update for this step so we don't corrupt the record.
                        SUMO_INVALID = -1073741824.0
                        if remaining_distance <= SUMO_INVALID or remaining_distance < 0:
                            continue

                        speed   = traci.vehicle.getSpeed(veh_id)
                        eta     = int(remaining_distance / speed) if speed > 0.5 else 999
                        arrived = remaining_distance < 5.0

                        tot_len = rec.get("total_length", 1174.8)
                        travelled = max(0.0, tot_len - remaining_distance)
                        progress  = min(100.0, round(travelled / tot_len * 100, 1)) if tot_len > 0 else 0

                        rec.update({
                            "eta":       eta,
                            "distance":  round(remaining_distance, 1),
                            "progress":  progress,
                            "next_stop": "Arrived" if arrived else rec.get("destination", "City Hospital"),
                        })

                        if arrived:
                            arrived_ids.append(veh_id)

                    except traci.exceptions.TraCIException:
                        # Vehicle may have just been removed by SUMO
                        arrived_ids.append(veh_id)

                else:
                    if rec["has_departed"]:
                        # Vehicle is no longer in the simulation → treat as arrived
                        rec.update({"eta": 0, "distance": 0.0, "next_stop": "Arrived"})
                        arrived_ids.append(veh_id)

            # ── 3. Handle arrivals ──────────────────────────────────────────
            for veh_id in set(arrived_ids):
                rec = active_ambulances[veh_id]
                rec.update({"eta": 0, "distance": 0.0, "next_stop": "Arrived"})

                # We MUST hold it here for 5 seconds. If we immediately pop it,
                # the server.py won't see "Arrived" and the dashboard will never update!
                if "arrival_time" not in rec:
                    rec["arrival_time"] = time.time()
                    # Persist to completed_runs.json
                    completed_record = {
                        **rec,
                        "status":       "Completed",
                        "completed_at": time.time(),
                    }
                    save_completed_run(completed_record)
                    log.write(f"Step {step}: [{veh_id}] ARRIVED at {rec.get('destination','City Hospital')}\n")
                    print(f"[runner] Step {step}: {veh_id} arrived — marked Completed")

                # Remove from active tracking only after 5 seconds
                if time.time() - rec["arrival_time"] > 5.0:
                    active_ambulances.pop(veh_id, None)
                    active_preemptions.pop(veh_id, None)
                    # Allow this ID to be re-dispatched in a future run
                    processed_ids.discard(veh_id)

            # ── 4. Write hospital_view.json ─────────────────────────────────
            if active_ambulances:
                write_hospital_view(active_ambulances)
            # If nothing is active we leave the last state in hospital_view.json
            # so the server still has something to serve

            log.flush()

    traci.close()
    print("[runner] Simulation complete.")



if __name__ == "__main__":
    if 'SUMO_HOME' in os.environ:
        sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
    run()