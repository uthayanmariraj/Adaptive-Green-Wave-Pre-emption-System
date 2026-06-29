import traci

sumo_cmd = [
    "sumo-gui",
    "-c", "config/simulation.sumocfg",
    "--start",
    "--delay", "100"
]

traci.start(sumo_cmd)

ambulance_found = False
ambulance_departed = False
departure_time = None
completion_time = None

for step in range(600):
    traci.simulationStep()

    vehicles = traci.vehicle.getIDList()

    # Check if ambulance spawned
    if "AMB-001" in vehicles and not ambulance_departed:
        ambulance_departed = True
        departure_time = step
        pos = traci.vehicle.getPosition("AMB-001")
        speed = traci.vehicle.getSpeed("AMB-001")
        print(f"Step {step}: Ambulance SPAWNED!")
        print(f"  Position: {pos}")
        print(f"  Speed: {speed} m/s")

    # Track ambulance every 30 steps
    if "AMB-001" in vehicles and step % 30 == 0:
        pos = traci.vehicle.getPosition("AMB-001")
        speed = traci.vehicle.getSpeed("AMB-001")
        dist = traci.vehicle.getDistance("AMB-001")
        print(f"Step {step}: AMB pos={pos} "
              f"speed={speed:.1f}m/s "
              f"dist={dist:.0f}m")

    # Check if ambulance completed route
    if ambulance_departed and "AMB-001" not in vehicles:
        completion_time = step
        print(f"\nAmbulance COMPLETED route at step {step}")
        print(f"EVRT (baseline): {completion_time - departure_time}s")
        break

traci.close()

if not ambulance_departed:
    print("ERROR: Ambulance never spawned - check ambulance.rou.xml")
