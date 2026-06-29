import os, sys, traci, json  # ← add json here

SUMO_CONFIG = "config/simulation.sumocfg"
AMBULANCE_ID = "AMB-001"
TOTAL_LENGTH = 783.2  # ← add this constant

traci.start(["sumo", "-c", SUMO_CONFIG, "--no-step-log", "true", "--no-warnings", "true"])

with open("preempt_log.txt", "w") as f:
    active_preemptions = set()
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        if AMBULANCE_ID in traci.vehicle.getIDList():
            next_tls_data = traci.vehicle.getNextTLS(AMBULANCE_ID)
            current_target_tls = next_tls_data[0][0] if next_tls_data else None

            if next_tls_data:
                tls_id, tls_index, dist, current_state = next_tls_data[0]
                if dist < 100:
                    state_list = list(traci.trafficlight.getRedYellowGreenState(tls_id))
                    if state_list[tls_index] != 'G':
                        state_list[tls_index] = 'G'
                        traci.trafficlight.setRedYellowGreenState(tls_id, "".join(state_list))
                        active_preemptions.add(tls_id)
                        f.write(f"Step {traci.simulation.getTime()}: Forced GREEN at {tls_id} index {tls_index}. New state: {''.join(state_list)}\n")
                    else:
                        f.write(f"Step {traci.simulation.getTime()}: {tls_id} index {tls_index} is already G. State: {''.join(state_list)}\n")
            
            for locked_tls in list(active_preemptions):
                if locked_tls != current_target_tls:
                    traci.trafficlight.setProgram(locked_tls, "0")
                    active_preemptions.remove(locked_tls)
                    f.write(f"Step {traci.simulation.getTime()}: Released {locked_tls}\n")

            # ↓ ADD THIS BLOCK HERE — after all TLS logic, still inside the if AMBULANCE_ID block
            remaining_distance = traci.vehicle.getDrivingDistance(AMBULANCE_ID, 
                                     traci.vehicle.getRoadID(AMBULANCE_ID), 0)
            speed = traci.vehicle.getSpeed(AMBULANCE_ID)
            current_eta = (remaining_distance / speed) if speed > 0.5 else 99
            arrived = remaining_distance < 5.0

            with open("hospital_view.json", "w") as hv:
                json.dump({
                    "ambulance_id": "AMB-001",
                    "eta": round(current_eta),
                    "distance": round(remaining_distance, 1),
                    "total_length": TOTAL_LENGTH,
                    "injury_level": "Medium",
                    "next_stop": "Arrived" if arrived else "City Hospital"
                }, hv)

traci.close()