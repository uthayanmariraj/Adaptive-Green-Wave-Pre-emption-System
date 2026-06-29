import traci
import json
import os

# Configuration
SUMO_CONFIG = "config/simulation.sumocfg"
AMBULANCE_ID = "AMB-001"
HOSPITAL_FILE = "hospital_view.json"
DATA_FILE = "dashboard_data.json"

# --- QUEUE ALGORITHM PARAMETERS ---
# Minimum distance to trigger green (even if road is empty)
MIN_GREEN_DIST = 60.0  
# Distance added per halting vehicle (accounts for space + startup delay)
DIST_PER_VEHICLE = 12.0 
# Yellow transition starts 40m before green
YELLOW_OFFSET = 40.0   

def get_dashboard_input():
    """Still reads injury for display purposes on the dashboard."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
                return data.get("injury_level", "Standard")
            except: return "Standard"
    return "Standard"

def broadcast_to_hospital(injury):
    """Calculates TOTAL route distance and ETA."""
    try:
        driven_dist = traci.vehicle.getDistance(AMBULANCE_ID)
        route_id = traci.vehicle.getRouteID(AMBULANCE_ID)
        edges = traci.route.getEdges(route_id)
        total_route_length = sum([traci.lane.getLength(e + "_0") for e in edges])
        
        remaining_dist = max(0, total_route_length - driven_dist)
        speed = traci.vehicle.getSpeed(AMBULANCE_ID)
        calc_speed = speed if speed > 1.0 else 13.89
        total_eta = remaining_dist / calc_speed

        next_tls = traci.vehicle.getNextTLS(AMBULANCE_ID)
        next_stop = next_tls[0][0] if next_tls else "Arrived"

        status = {
            "ambulance_id": AMBULANCE_ID,
            "eta": round(total_eta, 1),
            "distance": round(remaining_dist, 1),
            "total_length": round(total_route_length, 1),
            "injury_level": injury,
            "next_stop": next_stop
        }
        with open(HOSPITAL_FILE, "w") as f:
            json.dump(status, f)
    except: pass

def run_simulation():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG])
    active_preemptions = set()

    print("--- Running Pure Queue-Based Autonomous Preemption ---")

    ambulance_departed = False
    departure_time = None
    completion_time = None

    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        vehicles = traci.vehicle.getIDList()
        step = traci.simulation.getTime()

        if AMBULANCE_ID in vehicles and not ambulance_departed:
            ambulance_departed = True
            departure_time = step
            print(f"Step {step}: Ambulance {AMBULANCE_ID} SPAWNED!")

        if AMBULANCE_ID in vehicles:
            injury = get_dashboard_input()
            broadcast_to_hospital(injury)

            next_tls_data = traci.vehicle.getNextTLS(AMBULANCE_ID)
            current_target_tls = next_tls_data[0][0] if next_tls_data else None

            if next_tls_data:
                tls_id, tls_index, dist, _ = next_tls_data[0]
                amb_lane = traci.vehicle.getLaneID(AMBULANCE_ID)
                amb_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
                
                # --- THE ALGORITHM ---
                # 1. Count vehicles stopped in the ambulance's path
                queue_count = traci.lane.getLastStepHaltingNumber(amb_lane)
                
                # 2. Calculate dynamic trigger points
                # Formula: Base + (Number of cars * Buffer distance)
                green_trigger = MIN_GREEN_DIST + (queue_count * DIST_PER_VEHICLE)
                yellow_trigger = green_trigger + YELLOW_OFFSET

                links = traci.trafficlight.getControlledLinks(tls_id)

                # --- 3. EXECUTION ---
                if dist < green_trigger:
                    new_state = ['r'] * len(links)
                    for i in range(len(links)):
                        if amb_edge in links[i][0][0]:
                            new_state[i] = 'G'
                    traci.trafficlight.setRedYellowGreenState(tls_id, "".join(new_state))
                    active_preemptions.add(tls_id)
                    
                elif dist < yellow_trigger:
                    current_state = list(traci.trafficlight.getRedYellowGreenState(tls_id))
                    for i in range(len(links)):
                        if amb_edge not in links[i][0][0] and current_state[i] in ['G', 'g']:
                            current_state[i] = 'y'
                    traci.trafficlight.setRedYellowGreenState(tls_id, "".join(current_state))
                    active_preemptions.add(tls_id)

            # Recovery Logic
            for locked_tls in list(active_preemptions):
                if locked_tls != current_target_tls:
                    traci.trafficlight.setProgram(locked_tls, "0")
                    active_preemptions.remove(locked_tls)

        if ambulance_departed and AMBULANCE_ID not in vehicles:
            completion_time = step
            print(f"\nAmbulance {AMBULANCE_ID} COMPLETED route at step {step}")
            print(f"Time Taken (EVRT): {completion_time - departure_time}s")
            break

    traci.close()

    if not ambulance_departed:
        print(f"ERROR: Ambulance {AMBULANCE_ID} never spawned - check ambulance.rou.xml")

if __name__ == "__main__":
    run_simulation()