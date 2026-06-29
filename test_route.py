import os, sys
import traci

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))

sumoCmd = ["sumo", "-c", "config/simulation.sumocfg", "--no-step-log", "true", "--no-warnings", "true"]
traci.start(sumoCmd)

tls_id = "B1"
controlled_lanes = traci.trafficlight.getControlledLanes(tls_id)
print(f"Controlled lanes for {tls_id}:", controlled_lanes)

traci.close()
