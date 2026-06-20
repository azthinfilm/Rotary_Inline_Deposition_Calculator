import streamlit as st
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Mandatory for Streamlit Cloud to prevent server crashes
import matplotlib.pyplot as plt # <--- EXACTLY LIKE THIS (NO 's' AT THE END)
from matplotlib.patches import Rectangle, Circle
import os

# ==========================================
# 1. PAGE CONFIG & SESSION STATE
# ==========================================
st.set_page_config(page_title="AZ Thin Film | Inline Simulator", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    h1, h2, h3 { color: #1E3A8A; font-family: 'Helvetica Neue', sans-serif; }
    .stMetric { border-left: 4px solid #1E3A8A; padding-left: 15px; background-color: #ffffff; padding: 10px; border-radius: 5px; box-shadow: 0px 2px 4px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# Initialize global variables in Session State so they persist across pages
def init_state(key, default):
    if key not in st.session_state:
        st.session_state[key] = default

# Layout Geometry
init_state('t2t_gap', 200.0)
init_state('tts', 100.0)
init_state('t_thick', 10.0)
init_state('t_length', 1000.0)
init_state('sub_width', 600.0)

# Process & Power
init_state('mat_a', 'Ti')
init_state('mat_b', 'Ti')
init_state('ps_type', 'Bi-Polar Pulse DC')
init_state('ps_freq', 40.0)
init_state('power_kw', 10.0)
init_state('sub_vel', 20.0)

# Gas & Pumping
init_state('gas_main', 'Ar')
init_state('flow_main', 150.0)
init_state('gas_react', 'N2')
init_state('flow_react', 50.0)
init_state('manifold', 'Both')
init_state('num_zones', 3)
init_state('pump_speed', 500.0)

# Magnetics & Plume
init_state('mag_ang_a', 15.0)
init_state('mag_ang_b', -15.0)
init_state('b_avg', 400.0)
init_state('ta_ratio', 1.25)
init_state('plume_override', False)
init_state('plume_n', 1.5)

TUBE_OD = 132.5
TUBE_ID = 125.0

# ==========================================
# 2. SIDEBAR NAVIGATION WIZARD
# ==========================================
st.sidebar.markdown("<h2 style='color:#1E3A8A; text-align:center;'>AZ Thin Film</h2>", unsafe_allow_html=True)
if os.path.exists("logo.png"): st.sidebar.image("logo.png")
st.sidebar.markdown("### Process Setup Wizard")

page = st.sidebar.radio("Navigate Design Steps:", [
    "1. Chamber & Target Layout",
    "2. Process Settings & Gas",
    "3. Magnetics & Plume",
    "4. Summary & Final Simulation"
])
st.sidebar.divider()
st.sidebar.info("Variables are saved automatically as you move between screens.")

def apply_watermark(fig):
    fig.text(0.5, 0.02, "Simulation provided by AZ Thin Film Research | www.azthinfilm.com", ha='center', fontsize=8, color='gray')

# ==========================================
# PAGE 1: CHAMBER & TARGET LAYOUT
# ==========================================
if page == "1. Chamber & Target Layout":
    st.title("Step 1: Chamber Geometry & Target Layout")
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.session_state.t2t_gap = st.slider("Target-to-Target Axis Distance (mm)", 100.0, 500.0, st.session_state.t2t_gap, 10.0)
        st.session_state.tts = st.slider("Target-to-Substrate Distance (TTS) (mm)", 50.0, 300.0, st.session_state.tts, 5.0)
        st.session_state.t_thick = st.slider("Target Material Thickness (mm)", 1.0, 30.0, float(st.session_state.t_thick), 1.0)
        st.session_state.t_length = st.slider("Target Length (mm)", 300.0, 4000.0, float(st.session_state.t_length), 100.0)
        st.session_state.sub_width = st.slider("Substrate Width (mm)", 100.0, 3000.0, float(st.session_state.sub_width), 50.0)
        
        tot_od = TUBE_OD + 2*st.session_state.t_thick
        st.info(f"Standard {TUBE_OD}mm OD / {TUBE_ID}mm ID Base Tube.\n\n**Total Target OD:** {tot_od:.1f} mm")

    with col2:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 8), gridspec_kw={'height_ratios': [1.5, 1]})
        
        # 2D Machine Direction View
        ax1.set_title("2D Target & Substrate Layout (Machine Direction)", fontweight="bold")
        ax1.axhline(0, color='gray', lw=4, label="Substrate Translation Plane")
        ax1.plot([-st.session_state.sub_width/2, st.session_state.sub_width/2], [0, 0], color='cyan', lw=6)
        
        cx_L, cx_R = -st.session_state.t2t_gap/2, st.session_state.t2t_gap/2
        cy = st.session_state.tts + (tot_od/2)
        
        for cx, label in [(cx_L, "Target L"), (cx_R, "Target R")]:
            ax1.add_patch(Circle((cx, cy), tot_od/2, fill=False, ec='#1E3A8A', lw=3))
            ax1.add_patch(Circle((cx, cy), TUBE_OD/2, fill=True, color='lightgray'))
            ax1.add_patch(Circle((cx, cy), TUBE_ID/2, fill=True, color='white'))
            ax1.plot([cx], [cy], 'k+', markersize=8)
            ax1.text(cx, cy + tot_od/2 + 10, label, ha='center', fontweight='bold')
            
        ax1.set_aspect('equal')
        ax1.set_xlim(-max(st.session_state.t2t_gap, st.session_state.sub_width)/2 - 100, max(st.session_state.t2t_gap, st.session_state.sub_width)/2 + 100)
        ax1.set_ylim(-20, cy + tot_od/2 + 40)
        ax1.set_xlabel("Cross-Web Axis (mm)")
        ax1.set_ylabel("Vertical Axis (mm)")
        
        # Rough Geometric Cross-Substrate Profile
        x_rough = np.linspace(-st.session_state.sub_width/2*1.2, st.session_state.sub_width/2*1.2, 200)
        gamma = st.session_state.tts
        dep_l = gamma**2 / ((x_rough - cx_L)**2 + gamma**2)
        dep_r = gamma**2 / ((x_rough - cx_R)**2 + gamma**2)
        
        ax2.set_title("Rough Geometric Cross-Substrate Deposition Proxy", fontweight="bold")
        ax2.plot(x_rough, dep_l, 'r--', label='Target L Proxy')
        ax2.plot(x_rough, dep_r, 'b--', label='Target R Proxy')
        ax2.plot(x_rough, dep_l + dep_r, 'k-', lw=2, label='Combined')
        ax2.axvspan(-st.session_state.sub_width/2, st.session_state.sub_width/2, color='gray', alpha=0.2, label='Substrate Width')
        ax2.set_xlabel("Cross-Web Axis (mm)")
        ax2.set_ylabel("Relative Flux Intensity")
        ax2.legend()
        
        apply_watermark(fig)
        st.pyplot(fig)

# ==========================================
# PAGE 2: PROCESS SETTINGS & GAS
# ==========================================
elif page == "2. Process Settings & Gas":
    st.title("Step 2: Power, Velocity & Gases")
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.subheader("Process & Material Settings")
        st.session_state.mat_a = st.selectbox("Left Target Material", ["Ti", "Al", "Si", "Nb", "Cu", "Cr"], index=["Ti", "Al", "Si", "Nb", "Cu", "Cr"].index(st.session_state.mat_a))
        st.session_state.mat_b = st.selectbox("Right Target Material", ["Ti", "Al", "Si", "Nb", "Cu", "Cr"], index=["Ti", "Al", "Si", "Nb", "Cu", "Cr"].index(st.session_state.mat_b))
        st.session_state.sub_vel = st.slider("Substrate Velocity (mm/s)", 1.0, 150.0, float(st.session_state.sub_vel))
        
        st.session_state.ps_type = st.selectbox("Power Supply Architecture", ["DC", "Pulsed DC", "AC", "Bi-Polar Pulse DC", "HiPIMS"], index=["DC", "Pulsed DC", "AC", "Bi-Polar Pulse DC", "HiPIMS"].index(st.session_state.ps_type))
        if st.session_state.ps_type in ["Pulsed DC", "AC", "Bi-Polar Pulse DC", "HiPIMS"]:
            st.session_state.ps_freq = st.slider("Operating Frequency (kHz)", 10.0, 350.0, float(st.session_state.ps_freq))
        
        # Max Power based on length (approx ~20 kW/m limit)
        max_power = float((st.session_state.t_length / 1000.0) * 20.0)
        safe_val = min(st.session_state.power_kw, max_power * 1.5)
        st.session_state.power_kw = st.slider(f"Operating Power (kW) [Thermal Limit ~{max_power:.1f} kW]", 1.0, max_power*1.5, float(safe_val))
        
        st.subheader("Gases & Pumping")
        g1, g2 = st.columns(2)
        st.session_state.gas_main = g1.text_input("Main Gas", st.session_state.gas_main)
        st.session_state.flow_main = g1.number_input("Main Flow (sccm)", 0.0, 1000.0, float(st.session_state.flow_main))
        st.session_state.gas_react = g2.text_input("Reactive Gas", st.session_state.gas_react)
        st.session_state.flow_react = g2.number_input("Reactive Flow (sccm)", 0.0, 1000.0, float(st.session_state.flow_react))
        
        st.session_state.manifold = st.selectbox("Gas Manifold Position", ["Between Targets", "Outside Targets", "Both"])
        st.session_state.num_zones = st.number_input("Number of MFCs (Zones)", 1, 10, int(st.session_state.num_zones))
        st.session_state.pump_speed = st.slider("Estimated Pumping Speed (L/s)", 100.0, 3000.0, float(st.session_state.pump_speed), 100.0)

    with col2:
        fig = plt.figure(figsize=(10, 8))
        gs = fig.add_gridspec(2, 1, height_ratios=[2, 1])
        ax_sys = fig.add_subplot(gs[0])
        ax_wave = fig.add_subplot(gs[1])
        
        # Substrate
        ax_sys.add_patch(Rectangle((-st.session_state.sub_width/2, -10), st.session_state.sub_width, 10, color='gray'))
        ax_sys.arrow(0, -5, 50, 0, width=2, head_width=8, color='cyan')
        ax_sys.text(0, -25, f"Velocity: {st.session_state.sub_vel} mm/s", ha='center')
        
        # Targets
        c_l, c_r = -st.session_state.t2t_gap/2, st.session_state.t2t_gap/2
        tot_od = TUBE_OD + 2*st.session_state.t_thick
        z_t = st.session_state.tts + tot_od/2
        
        ax_sys.add_patch(Circle((c_l, z_t), tot_od/2, color='#1E3A8A'))
        ax_sys.text(c_l, z_t, st.session_state.mat_a, color='white', ha='center', va='center')
        ax_sys.add_patch(Circle((c_r, z_t), tot_od/2, color='#FF4B4B'))
        ax_sys.text(c_r, z_t, st.session_state.mat_b, color='white', ha='center', va='center')
        
        # Gas Manifolds
        if "Outside" in st.session_state.manifold or "Both" in st.session_state.manifold:
            ax_sys.add_patch(Rectangle((c_l - tot_od, z_t), 10, -50, color='green'))
            ax_sys.add_patch(Rectangle((c_r + tot_od - 10, z_t), 10, -50, color='green'))
        if "Between" in st.session_state.manifold or "Both" in st.session_state.manifold:
            ax_sys.add_patch(Rectangle((-5, z_t), 10, -50, color='green'))
            
        # Power Supply Dynamic Wiring
        ps = st.session_state.ps_type
        if ps in ["AC", "Bi-Polar Pulse DC"]:
            ax_sys.add_patch(Rectangle((-80, z_t + tot_od + 20), 160, 40, color='gold', ec='black'))
            ax_sys.text(0, z_t + tot_od + 40, f"1x {ps} PS\n({st.session_state.power_kw} kW)", ha='center', va='center', fontweight='bold')
            ax_sys.plot([-40, c_l], [z_t + tot_od + 20, z_t], 'k-', lw=3)
            ax_sys.plot([40, c_r], [z_t + tot_od + 20, z_t], 'k-', lw=3)
        else:
            ax_sys.add_patch(Rectangle((-120, z_t + tot_od + 20), 100, 40, color='gold', ec='black'))
            ax_sys.text(-70, z_t + tot_od + 40, f"PS 1 ({ps})\n{st.session_state.power_kw/2:.1f} kW", ha='center', va='center', fontweight='bold')
            ax_sys.plot([-70, c_l], [z_t + tot_od + 20, z_t], 'k-', lw=3)
            
            ax_sys.add_patch(Rectangle((20, z_t + tot_od + 20), 100, 40, color='gold', ec='black'))
            ax_sys.text(70, z_t + tot_od + 40, f"PS 2 ({ps})\n{st.session_state.power_kw/2:.1f} kW", ha='center', va='center', fontweight='bold')
            ax_sys.plot([70, c_r], [z_t + tot_od + 20, z_t], 'k-', lw=3)

        ax_sys.set_aspect('equal')
        ax_sys.set_xlim(-max(st.session_state.t2t_gap, st.session_state.sub_width)/2 - 80, max(st.session_state.t2t_gap, st.session_state.sub_width)/2 + 80)
        ax_sys.set_ylim(-40, z_t + tot_od + 80)
        ax_sys.axis('off')
        
        # Waveform Visualizer
        t = np.linspace(0, 4*np.pi, 400)
        ax_wave.set_title(f"Expected Target Voltage Phase Timing ({ps})", fontweight='bold')
        if ps == "AC":
            ax_wave.plot(t, np.sin(t), 'r', label="Cathode A Voltage")
            ax_wave.plot(t, np.sin(t + np.pi), 'b--', label="Cathode B Voltage")
        elif ps == "Bi-Polar Pulse DC":
            ax_wave.plot(t, np.sign(np.sin(t)), 'r', drawstyle='steps-pre', label="Cathode A Phase")
            ax_wave.plot(t, np.sign(np.sin(t + np.pi)), 'b--', drawstyle='steps-pre', label="Cathode B Phase")
        elif ps == "Pulsed DC":
            ax_wave.plot(t, np.where(np.sin(t*2)>0, 1, 0), 'r', drawstyle='steps-pre', label="Cathode A & B")
        elif ps == "HiPIMS":
            ax_wave.plot(t, np.where(np.mod(t, 2*np.pi)<0.5, 5, 0), 'r', label="Cathode A & B")
        else:
            ax_wave.plot(t, np.ones_like(t), 'r', label="Cathode A & B (DC)")
            
        ax_wave.set_yticks([])
        ax_wave.set_xlabel("Time (µs)")
        ax_wave.legend(loc="upper right", fontsize=8)
        apply_watermark(fig)
        st.pyplot(fig)

# ==========================================
# PAGE 3: MAGNETICS & PLUME
# ==========================================
elif page == "3. Magnetics & Plume":
    st.title("Step 3: Magnetics & Sputter Angle")
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.session_state.mag_ang_a = st.slider("Left Magnet Bar Angle (deg)", -45.0, 45.0, float(st.session_state.mag_ang_a), help="Positive points inwards toward the center gap")
        st.session_state.mag_ang_b = st.slider("Right Magnet Bar Angle (deg)", -45.0, 45.0, float(st.session_state.mag_ang_b), help="Negative points inwards toward the center gap")
        st.session_state.b_avg = st.slider("Average Straightaway B-Field (Gauss)", 150.0, 1000.0, float(st.session_state.b_avg))
        st.session_state.ta_ratio = st.slider("Turnaround to Straightaway Ratio", 0.5, 2.5, float(st.session_state.ta_ratio))
        
        st.divider()
        st.subheader("Plasma Plume Profiler")
        # AI Collimation estimator
        est_n = 1.0
        if st.session_state.ps_type == "HiPIMS": est_n += 1.5
        elif st.session_state.ps_type in ["AC", "Bi-Polar Pulse DC"]: est_n += 0.3
        elif st.session_state.ps_type == "Pulsed DC": est_n += 0.1
        if "O2" in st.session_state.gas_react or "N2" in st.session_state.gas_react: est_n += 0.1
        
        st.session_state.plume_override = st.checkbox("Override Equation Estimation?", st.session_state.plume_override)
        if st.session_state.plume_override:
            st.session_state.plume_n = st.slider("Manual Plume Shape Factor (Cos^n)", 0.5, 5.0, float(st.session_state.plume_n))
        else:
            st.session_state.plume_n = est_n
            st.info(f"💡 **AI Auto-Estimation:** Based on {st.session_state.ps_type} and {st.session_state.gas_react}, Plume Collimation Exponent is estimated at **Cos^{est_n:.2f}(\u03B8)**.")

    with col2:
        fig, ax = plt.subplots(figsize=(8, 5))
        c_l, c_r = -st.session_state.t2t_gap/2, st.session_state.t2t_gap/2
        tot_r = (TUBE_OD + 2*st.session_state.t_thick)/2
        z_t = st.session_state.tts + tot_r
        
        ax.axhline(0, color='cyan', lw=4, label="Substrate Translation Path")
        
        for cx, ang, color in [(c_l, st.session_state.mag_ang_a, 'red'), (c_r, st.session_state.mag_ang_b, 'blue')]:
            ax.add_patch(Circle((cx, z_t), tot_r, fill=False, ec='#1E3A8A', lw=2))
            
            # Pointing vector
            ang_rad = np.radians(-90 + ang)
            px = cx + tot_r * np.cos(ang_rad)
            pz = z_t + tot_r * np.sin(ang_rad)
            ax.plot([cx, px], [z_t, pz], color='k', lw=3)
            
            # Draw Plasma Plume Lobe relative to collimation factor
            angles = np.linspace(ang_rad - np.pi/2, ang_rad + np.pi/2, 100)
            r_lobe = 80 * np.maximum(0, np.cos(angles - ang_rad))**st.session_state.plume_n
            lobe_x = px + r_lobe * np.cos(angles)
            lobe_z = pz + r_lobe * np.sin(angles)
            ax.fill(lobe_x, lobe_z, color=color, alpha=0.3)
            
        ax.set_aspect('equal')
        ax.set_xlim(-st.session_state.t2t_gap - 150, st.session_state.t2t_gap + 150)
        ax.set_ylim(-20, z_t + tot_r + 20)
        ax.set_xlabel("Cross-Web Axis (mm)")
        ax.set_ylabel("Vertical Axis (mm)")
        ax.set_title("Magnet Bar Directionality Vectors")
        apply_watermark(fig)
        st.pyplot(fig)

# ==========================================
# PAGE 4: FINAL SIMULATION SUMMARY
# ==========================================
elif page == "4. Summary & Final Simulation":
    st.title("Step 4: Process Summary & Linear Deposition Simulation")
    
    st.markdown("### Process Setup Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hardware Layout", f"Gap: {st.session_state.t2t_gap}mm", f"TTS: {st.session_state.tts}mm")
    c2.metric("Power & Velocity", f"{st.session_state.power_kw}kW ({st.session_state.ps_type})", f"{st.session_state.sub_vel} mm/s")
    c3.metric("Gas Network", f"{st.session_state.flow_main} {st.session_state.gas_main} + {st.session_state.flow_react} {st.session_state.gas_react}", f"{st.session_state.num_zones} Zones | Pump: {st.session_state.pump_speed}L/s")
    c4.metric("Magnetic Setup", f"A: {st.session_state.mag_ang_a}° | B: {st.session_state.mag_ang_b}°", f"Plume Factor: Cos^{st.session_state.plume_n:.2f}")
    st.divider()
    
    with st.spinner("Calculating 3D Multiphysics Field & Kinematic Machine Integration..."):
        # Setup kinematic mesh grid (X is cross-web, Y is machine travel)
        x_grid = np.linspace(-st.session_state.sub_width/2 - 100, st.session_state.sub_width/2 + 100, 150)
        y_grid = np.linspace(-st.session_state.t2t_gap - st.session_state.tts*3, st.session_state.t2t_gap + st.session_state.tts*3, 150)
        X, Y = np.meshgrid(x_grid, y_grid)
        
        def calculate_flux(y_pos, tilt_deg):
            tilt_rad = np.radians(tilt_deg)
            flux = np.zeros_like(X)
            tube_x = np.linspace(-st.session_state.t_length/2, st.session_state.t_length/2, 60)
            n_col = st.session_state.plume_n
            tts = st.session_state.tts
            
            ny = np.sin(tilt_rad)
            nz = -np.cos(tilt_rad) # Normal pointing down toward substrate at Z=0
            
            for tx in tube_x:
                u = 2.0 * tx / st.session_state.t_length
                # Turnaround strength dog-boning modification at the ends
                intensity = 1.0 + (st.session_state.ta_ratio - 1.0) * (abs(u)**6)
                
                dx_real = X - tx
                dy_real = Y - y_pos
                dz_real = tts
                
                dist = np.sqrt(dx_real**2 + dy_real**2 + dz_real**2)
                
                # Dot product for emission angle
                cos_emit = np.clip((dy_real*ny + dz_real*nz) / dist, 0, 1)
                cos_sub = dz_real / dist
                
                flux += intensity * (cos_emit**n_col) * cos_sub / (dist**2)
            return flux

        # Left target is at Y = -t2t_gap/2. Right is at Y = +t2t_gap/2
        flux_L = calculate_flux(-st.session_state.t2t_gap/2, st.session_state.mag_ang_a)
        flux_R = calculate_flux(st.session_state.t2t_gap/2, st.session_state.mag_ang_b)
        
        # Kinematic translation pass (Scale by power and velocity)
        dy = y_grid[1] - y_grid[0]
        # Calculate time spent over each dy element: dt = dy / sub_vel
        dt = dy / st.session_state.sub_vel
        # Apply pseudo-yield coefficient
        yield_proxy = 10000.0 * st.session_state.power_kw 
        
        accum_L = np.sum(flux_L, axis=0) * yield_proxy * dt
        accum_R = np.sum(flux_R, axis=0) * yield_proxy * dt
        accum_total = accum_L + accum_R
        
        # Mask data explicitly to Substrate Width
        sub_mask = (x_grid >= -st.session_state.sub_width/2) & (x_grid <= st.session_state.sub_width/2)
        mean_thk = np.mean(accum_total[sub_mask])
        unif = (np.max(accum_total[sub_mask]) - np.min(accum_total[sub_mask])) / (2 * mean_thk) * 100 if mean_thk > 0 else 0
        
    c1, c2 = st.columns([2, 1])
    with c1:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(x_grid, accum_total, color='black', lw=3, label='Combined Final Profile')
        ax.plot(x_grid, accum_L, color='red', ls='--', label=f'Target L ({st.session_state.mat_a})')
        ax.plot(x_grid, accum_R, color='blue', ls='--', label=f'Target R ({st.session_state.mat_b})')
        
        ax.axvspan(-st.session_state.sub_width/2, st.session_state.sub_width/2, color='gray', alpha=0.15, label='Substrate Envelope')
        
        ax.set_title("Machine-Direction Integrated Cross-Web Uniformity", fontweight='bold')
        ax.set_xlabel("Cross-Web Position X (mm)")
        ax.set_ylabel("Accumulated Dose (nm proxy)")
        ax.grid(True, linestyle=':', alpha=0.7)
        ax.legend(loc='lower center', ncol=4, bbox_to_anchor=(0.5, -0.3))
        apply_watermark(fig)
        st.pyplot(fig)
        
    with c2:
        st.success("Simulation Complete")
        st.metric("Predicted Substrate Uniformity", f"± {unif:.2f} %")
        st.metric("Predicted Pass Average Dose", f"{mean_thk:.2f} nm")
        
        if unif > 5.0:
            st.error("⚠️ **Uniformity > 5%**: Adjust Magnet Bar Angles inwards or increase Target Tube Length relative to the Substrate Width.")
        elif unif > 2.0:
            st.warning("✅ **Uniformity < 5%**: Acceptable profile.")
        else:
            st.info("⭐ **Uniformity < 2%**: Excellent baseline process design parameters.")
