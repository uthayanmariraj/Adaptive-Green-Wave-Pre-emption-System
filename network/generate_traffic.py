import subprocess
import os

sumo_tools = os.path.join(os.environ.get('SUMO_HOME', 'C:/Program Files (x86)/Eclipse/Sumo'), "tools")

subprocess.run([
    "python",
    os.path.join(sumo_tools, "randomTrips.py"),
    "-n", "network/grid.net.xml",
    "-o", "network/grid.rou.xml",
    "-e", "3600",
    "--period", "0.4",
    "--vehicle-class", "passenger",
    "--validate",
    "--min-distance", "200",
    "--fringe-factor", "10"
], check=True)

print("Traffic generated successfully")
