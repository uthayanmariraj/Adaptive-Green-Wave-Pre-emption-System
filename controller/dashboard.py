import streamlit as st
import json
import os
import time

DASHBOARD_IN = "dashboard_data.json"
HOSPITAL_DATA = "hospital_view.json"

st.set_page_config(page_title="Dashboard", layout="wide")
st.title(" Emergency Coordination System")

col1, col2 = st.columns(2)

with col1:
    st.header("Ambulance Interface")
    injury_level = st.select_slider("Injury Severity", 
                                    options=["Minor", "Medium", "Serious", "Critical"], 
                                    value="Medium")
    if st.button("Update Priority Level"):
        with open(DASHBOARD_IN, "w") as f:
            json.dump({"injury_level": injury_level}, f)
        st.success(f"Priority: {injury_level}")

with col2:
    st.header("Hospital Reception")
    placeholder = st.empty()

    while True:
        if os.path.exists(HOSPITAL_DATA):
            try:
                with open(HOSPITAL_DATA, "r") as f:
                    data = json.load(f)
                
                # If we successfully read the data, display it
                with placeholder.container():
                    if data["injury_level"] == "Critical":
                        st.error("🚨 CRITICAL PATIENT EN ROUTE")
                    
                    m1, m2 = st.columns(2)
                    m1.metric("ETA to ER", f"{data['eta']} sec")
                    m2.metric("Distance Left", f"{data['distance']} m")
                    
                    st.info(f"Next Intersection: {data['next_stop']}")
                    
                    total = data.get("total_length", 875.0)
                    progress = max(0.0, min(1.0, (1 - (data['distance'] / total))))
                    st.write(f"Overall Progress: {int(progress * 100)}%")
                    st.progress(progress)
            
            except (json.JSONDecodeError, ValueError):
                # If the file was empty or being written to, just skip this frame
                pass
        else:
            placeholder.warning("Waiting for Ambulance signal...")
        
        time.sleep(0.5)