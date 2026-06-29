


#-----------------WORKINGCODE----------------------------------------
#--------------------------------------------------------------------
# import traci

# # Configuration
# SUMO_CONFIG = "config/simulation.sumocfg"
# AMBULANCE_ID = "AMB-001"
# YELLOW_DISTANCE = 150.0 
# GREEN_DISTANCE = 100.0   

# def run_simulation():
#     traci.start(["sumo-gui", "-c", SUMO_CONFIG])
#     active_preemptions = set()

#     print(f"--- Running Preemption with Conflict Resolution ---")

#     while traci.simulation.getMinExpectedNumber() > 0:
#         traci.simulationStep()

#         if AMBULANCE_ID in traci.vehicle.getIDList():
#             next_tls_data = traci.vehicle.getNextTLS(AMBULANCE_ID)
#             current_target_tls = next_tls_data[0][0] if next_tls_data else None

#             if next_tls_data:
#                 tls_id, tls_index, dist, _ = next_tls_data[0]

#                 # --- 1. CLOSE RANGE: BRUTE FORCE CLEARING ---
#                 if dist < GREEN_DISTANCE:
#                     # Create a state of all RED
#                     num_links = len(traci.trafficlight.getRedYellowGreenState(tls_id))
#                     new_state = ['r'] * num_links
                    
#                     # Set ONLY the ambulance lane to GREEN
#                     new_state[tls_index] = 'G'
                    
#                     traci.trafficlight.setRedYellowGreenState(tls_id, "".join(new_state))
#                     active_preemptions.add(tls_id)

#                 # --- 2. MID RANGE: SAFETY TRANSITION ---
#                 elif dist < YELLOW_DISTANCE:
#                     current_state = list(traci.trafficlight.getRedYellowGreenState(tls_id))
                    
#                     # Find any 'G' or 'g' that isn't the ambulance's lane and turn them 'y'
#                     for i in range(len(current_state)):
#                         if i != tls_index and current_state[i] in ['G', 'g']:
#                             current_state[i] = 'y'
                    
#                     traci.trafficlight.setRedYellowGreenState(tls_id, "".join(current_state))
#                     active_preemptions.add(tls_id)

#             # --- 3. RECOVERY LOGIC ---
#             for locked_tls in list(active_preemptions):
#                 if locked_tls != current_target_tls:
#                     traci.trafficlight.setProgram(locked_tls, "0")
#                     active_preemptions.remove(locked_tls)

#     traci.close()

# if __name__ == "__main__":
#     run_simulation()



#------------------------------------------------------------

# import traci

# # Configuration
# SUMO_CONFIG = "config/simulation.sumocfg"
# AMBULANCE_ID = "AMB-001"
# YELLOW_DISTANCE = 75.0 
# GREEN_DISTANCE = 40.0   

# def run_simulation():
#     traci.start(["sumo-gui", "-c", SUMO_CONFIG])
#     active_preemptions = set()

#     print(f"--- Running Preemption: Full Direction Clearing ---")

#     while traci.simulation.getMinExpectedNumber() > 0:
#         traci.simulationStep()

#         if AMBULANCE_ID in traci.vehicle.getIDList():
#             # Get data for the next traffic light
#             next_tls_data = traci.vehicle.getNextTLS(AMBULANCE_ID)
#             current_target_tls = next_tls_data[0][0] if next_tls_data else None

#             if next_tls_data:
#                 tls_id, tls_index, dist, _ = next_tls_data[0]
                
#                 # NEW: Identify the road (edge) the ambulance is currently on
#                 amb_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
                
#                 # NEW: Get the map of which lanes connect to which TLS indices
#                 # links is a list of tuples: ((fromLane, toLane, viaLane), ...)
#                 links = traci.trafficlight.getControlledLinks(tls_id)

#                 # --- 1. CLOSE RANGE: FORCE ENTIRE DIRECTION GREEN ---
#                 if dist < GREEN_DISTANCE:
#                     new_state = ['r'] * len(links)
                    
#                     for i in range(len(links)):
#                         from_lane = links[i][0][0] # Extract the ID of the incoming lane
#                         # If this lane belongs to the ambulance's road, turn it Green
#                         if amb_edge in from_lane:
#                             new_state[i] = 'G'
                    
#                     traci.trafficlight.setRedYellowGreenState(tls_id, "".join(new_state))
#                     active_preemptions.add(tls_id)

#                 # --- 2. MID RANGE: TRANSITION CROSS-TRAFFIC TO YELLOW ---
#                 elif dist < YELLOW_DISTANCE:
#                     current_state = list(traci.trafficlight.getRedYellowGreenState(tls_id))
                    
#                     for i in range(len(links)):
#                         from_lane = links[i][0][0]
#                         # If the lane is NOT the ambulance's road and is currently Green, turn it Yellow
#                         if amb_edge not in from_lane and current_state[i] in ['G', 'g']:
#                             current_state[i] = 'y'
                    
#                     traci.trafficlight.setRedYellowGreenState(tls_id, "".join(current_state))
#                     active_preemptions.add(tls_id)

#             # --- 3. RECOVERY LOGIC ---
#             for locked_tls in list(active_preemptions):
#                 if locked_tls != current_target_tls:
#                     traci.trafficlight.setProgram(locked_tls, "0")
#                     active_preemptions.remove(locked_tls)

#     traci.close()

# if __name__ == "__main__":
#     run_simulation()


#---------------------------------------------------------------------

# import traci
# import json
# import os

# # Configuration
# SUMO_CONFIG = "config/simulation.sumocfg"
# AMBULANCE_ID = "AMB-001"
# DATA_FILE = "dashboard_data.json"
# HOSPITAL_FILE = "hospital_view.json"

# def get_dashboard_input():
#     """Reads injury level from dashboard. Defaults to 'Medium'."""
#     if os.path.exists(DATA_FILE):
#         with open(DATA_FILE, "r") as f:
#             try:
#                 data = json.load(f)
#                 return data.get("injury_level", "Medium")
#             except: return "Medium"
#     return "Medium"

# def broadcast_to_hospital(injury):
#     """Calculates TOTAL route distance and ETA for the Hospital View."""
#     # 1. Get current progress
#     driven_dist = traci.vehicle.getDistance(AMBULANCE_ID)
    
#     # 2. Calculate Total Route Length
#     route_id = traci.vehicle.getRouteID(AMBULANCE_ID)
#     edges = traci.route.getEdges(route_id)
#     # SUMO uses edgeID_laneIndex (e.g., A0A1_0) to get lengths
#     total_route_length = sum([traci.lane.getLength(e + "_0") for e in edges])
    
#     # 3. Calculate Remaining stats
#     remaining_dist = max(0, total_route_length - driven_dist)
#     speed = traci.vehicle.getSpeed(AMBULANCE_ID)
#     # Fallback speed (13.89 m/s) if ambulance is stopped to avoid Infinity ETA
#     calc_speed = speed if speed > 1.0 else 13.89
#     total_eta = remaining_dist / calc_speed

#     # 4. Get next TLS for the info box
#     next_tls = traci.vehicle.getNextTLS(AMBULANCE_ID)
#     next_stop = next_tls[0][0] if next_tls else "Arrived"

#     status = {
#         "ambulance_id": AMBULANCE_ID,
#         "eta": round(total_eta, 1),
#         "distance": round(remaining_dist, 1),
#         "total_length": round(total_route_length, 1),
#         "injury_level": injury,
#         "next_stop": next_stop
#     }
#     with open(HOSPITAL_FILE, "w") as f:
#         json.dump(status, f)

# def run_simulation():
#     traci.start(["sumo-gui", "-c", SUMO_CONFIG])
#     active_preemptions = set()

#     ambulance_departed = False
#     departure_time = None
#     completion_time = None

#     while traci.simulation.getMinExpectedNumber() > 0:
#         traci.simulationStep()
#         vehicles = traci.vehicle.getIDList()
#         step = traci.simulation.getTime()

#         if AMBULANCE_ID in vehicles and not ambulance_departed:
#             ambulance_departed = True
#             departure_time = step
#             print(f"Step {step}: Ambulance {AMBULANCE_ID} SPAWNED!")

#         if AMBULANCE_ID in vehicles:
#             injury = get_dashboard_input()
            
#             # Update Dashboard with TOTAL Route Data
#             broadcast_to_hospital(injury)

#             # --- Preemption Logic ---
#             if injury == "Critical":
#                 yellow_dist, green_dist = 250.0, 150.0
#             elif injury == "Serious":
#                 yellow_dist, green_dist = 150.0, 80.0
#             else:
#                 yellow_dist, green_dist = 75.0, 40.0

#             next_tls_data = traci.vehicle.getNextTLS(AMBULANCE_ID)
#             current_target_tls = next_tls_data[0][0] if next_tls_data else None

#             if next_tls_data:
#                 tls_id, tls_index, dist, _ = next_tls_data[0]
#                 amb_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
#                 links = traci.trafficlight.getControlledLinks(tls_id)

#                 if dist < green_dist:
#                     new_state = ['r'] * len(links)
#                     for i in range(len(links)):
#                         if amb_edge in links[i][0][0]: new_state[i] = 'G'
#                     traci.trafficlight.setRedYellowGreenState(tls_id, "".join(new_state))
#                     active_preemptions.add(tls_id)
#                 elif dist < yellow_dist:
#                     current_state = list(traci.trafficlight.getRedYellowGreenState(tls_id))
#                     for i in range(len(links)):
#                         if amb_edge not in links[i][0][0] and current_state[i] in ['G', 'g']:
#                             current_state[i] = 'y'
#                     traci.trafficlight.setRedYellowGreenState(tls_id, "".join(current_state))
#                     active_preemptions.add(tls_id)

#             # Recovery
#             for locked_tls in list(active_preemptions):
#                 if locked_tls != current_target_tls:
#                     traci.trafficlight.setProgram(locked_tls, "0")
#                     active_preemptions.remove(locked_tls)

#         if ambulance_departed and AMBULANCE_ID not in vehicles:
#             completion_time = step
#             print(f"\nAmbulance {AMBULANCE_ID} COMPLETED route at step {step}")
#             print(f"Time Taken (EVRT): {completion_time - departure_time}s")
#             break

#     traci.close()

#     if not ambulance_departed:
#         print(f"ERROR: Ambulance {AMBULANCE_ID} never spawned - check ambulance.rou.xml")

# if __name__ == "__main__":
#     run_simulation()

#--------------------------------------------------
import traci
import json
import os

# Configuration
SUMO_CONFIG = "config/simulation.sumocfg"
AMBULANCE_ID = "AMB-001"
DATA_FILE = "dashboard_data.json"
HOSPITAL_FILE = "hospital_view.json"

# Static Preemption Thresholds
YELLOW_DIST_TRIGGER = 60.0
GREEN_DIST_TRIGGER = 50.0

def get_dashboard_input():
    """Still reads injury level for display on the dashboard."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                data = json.load(f)
                return data.get("injury_level", "Standard")
            except: return "Standard"
    return "Standard"

def broadcast_to_hospital(injury):
    """Calculates TOTAL route distance and ETA for the Hospital View."""
    try:
        driven_dist = traci.vehicle.getDistance(AMBULANCE_ID)
        route_id = traci.vehicle.getRouteID(AMBULANCE_ID)
        edges = traci.route.getEdges(route_id)
        
        # Calculate Total Route Length
        total_route_length = sum([traci.lane.getLength(e + "_0") for e in edges])
        
        # Calculate remaining stats
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
    except:
        pass

def run_simulation():
    traci.start(["sumo-gui", "-c", SUMO_CONFIG])
    active_preemptions = set()

    ambulance_departed = False
    departure_time = None
    completion_time = None

    print(f"--- Running Preemption: Fixed 50m Strategy ---")

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
                amb_edge = traci.vehicle.getRoadID(AMBULANCE_ID)
                links = traci.trafficlight.getControlledLinks(tls_id)

                # --- 1. GREEN PREEMPTION (50m) ---
                if dist < GREEN_DIST_TRIGGER:
                    new_state = ['r'] * len(links)
                    for i in range(len(links)):
                        if amb_edge in links[i][0][0]:
                            new_state[i] = 'G'
                    traci.trafficlight.setRedYellowGreenState(tls_id, "".join(new_state))
                    active_preemptions.add(tls_id)

                # --- 2. YELLOW TRANSITION (80m) ---
                elif dist < YELLOW_DIST_TRIGGER:
                    current_state = list(traci.trafficlight.getRedYellowGreenState(tls_id))
                    for i in range(len(links)):
                        from_lane = links[i][0][0]
                        if amb_edge not in from_lane and current_state[i] in ['G', 'g']:
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