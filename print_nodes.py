import xml.etree.ElementTree as ET

tree = ET.parse('network/grid.net.xml')
nodes = {n.get('id'): (float(n.get('x')), float(n.get('y'))) for n in tree.getroot().findall('junction') if n.get('type') != 'internal'}

for q in sorted(nodes.keys()):
    print(f"{q}: {nodes[q]}")
