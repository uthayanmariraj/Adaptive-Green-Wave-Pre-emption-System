import sumolib
import os

def create_ambulance_route():
    net = sumolib.net.readNet("network/grid.net.xml")
    
    # bottom-left corner node
    nodes = net.getNodes()
    nodes = sorted(nodes, key=lambda n: (n.getCoord()[0], n.getCoord()[1]))
    bl_node = nodes[0]
    
    # top-right corner node
    tr_node = nodes[-1]
    
    # find outgoing edge from bl_node that isn't a turnaround
    origin_edges = bl_node.getOutgoing()
    origin_edge = None
    for e in origin_edges:
        if not e.getID().startswith(":"):
            origin_edge = e.getID()
            break
            
    # find incoming edge to tr_node
    dest_edges = tr_node.getIncoming()
    dest_edge = None
    for e in dest_edges:
        if not e.getID().startswith(":"):
            dest_edge = e.getID()
            break

    print(f"Ambulance route: {origin_edge} → {dest_edge}")
    print("Expected signals on route: approximately 4")

    # write XML
    xml_content = f"""<routes>
    <vType id="ambulance"
           vClass="emergency"
           color="1,0,0"
           maxSpeed="16.7"
           accel="2.6"
           decel="4.5"
           length="6.5"
           guiShape="emergency"/>

    <route id="amb_route" edges="A0B0 B0B1 B1C1 C1C2 C2D2 D2D3"/>
    <vehicle id="AMB-001" type="ambulance" depart="250" route="amb_route" departSpeed="0"/>
</routes>
"""

    os.makedirs("ambulance", exist_ok=True)
    with open("ambulance/ambulance.rou.xml", "w") as f:
        f.write(xml_content)
        
    print("ambulance.rou.xml created.")

if __name__ == "__main__":
    create_ambulance_route()
