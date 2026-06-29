import traci
import subprocess
import time

def verify():
    sumo_cmd = [
        "sumo",
        "-c", "config/simulation.sumocfg",
        "--quit-on-end",
        "--no-warnings"
    ]

    traci.start(sumo_cmd)

    print("=== NETWORK VERIFICATION ===")
    print(f"Simulation loaded successfully")

    # Get all traffic light IDs
    tls_ids = traci.trafficlight.getIDList()
    print(f"Traffic lights found: {len(tls_ids)}")
    print(f"TLS IDs: {list(tls_ids)}")

    # Get all edges
    edge_ids = traci.edge.getIDList()
    real_edges = [e for e in edge_ids if not e.startswith(':')]
    print(f"Road edges found: {len(real_edges)}")

    # Run 200 steps and monitor signals and vehicles
    print("\n=== RUNNING 200 STEPS ===")
    for step in range(200):
        traci.simulationStep()

        if step % 50 == 0:
            vehicles = traci.vehicle.getIDList()
            print(f"\nStep {step}:")
            print(f"  Vehicles in simulation: {len(vehicles)}")

            # Print phase of first 4 signals
            for tls_id in list(tls_ids)[:4]:
                phase = traci.trafficlight.getPhase(tls_id)
                state = traci.trafficlight.getRedYellowGreenState(tls_id)
                remaining = traci.trafficlight.getNextSwitch(tls_id) \
                            - traci.simulation.getTime()
                print(f"  Signal {tls_id}: "
                      f"phase={phase} "
                      f"state={state[:8]}... "
                      f"switches in {remaining:.0f}s")

    traci.close()
    print("\n=== VERIFICATION COMPLETE ===")
    print("If you saw vehicles > 0 and signals cycling, Phase 1 is done.")

if __name__ == "__main__":
    verify()
