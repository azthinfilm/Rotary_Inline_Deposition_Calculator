import streamlit as st
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Mandatory for Streamlit Cloud to prevent server crashes
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import os

# ==========================================
# 1. PAGE CONFIG & SESSION STATE
# ==========================================
st.set_page_config(page_title="AZ Thin Film | Inline Simulator", layout="wide")

st.markdown("""
    <style>
    h1, h2, h3 { color: #1E3A8A; font-family: 'Helvetica Neue', sans-serif; }
    .stMetric { border-left: 4px solid #1E3A8A; padding-left: 15px; padding-top: 10px; padding-bottom: 10px; border-radius: 5px; background-color: rgba(30, 58, 138, 0.05); }
    </style>
""", unsafe_allow_html=True)

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

# Magnetics & Electrodynamics
init_state('mag_ang_a', 15.0)
init_state('mag_ang_b', -15.0)
init_state('ta_ratio', 1.25)
init_state('leg_offset', 18.0) # Angle between center and straightaways
init_state('hall_drift', 15.0) # E x B drift intensity %
init_state('anode_bias', 0.0)  # L/R asymmetry
init_state('plume_override', False)
init_state('plume_n', 1.5)

TUBE_OD = 132.5
TUBE_ID = 125.0

# ==========================================
# 2. CORE MULTIPHYSICS ENGINE
# ==========================================
@st.cache_data
def calc_kinematic_profile(L, W, gap, tts, t_thick, ang_a, ang_b, ta_ratio, leg_offset_deg, hall_pct, bias_pct, n_col):
    """Core Dual-Leg 3D Flux Engine with ExB Drift & Uniformity Evaluation."""
    hall = hall_pct / 100.0
    bias = bias_pct / 100.0
    
    x_grid = np.linspace(-W/2 - 200, W/2 + 200, 100)
    y_grid = np.linspace(-gap - tts*3, gap + tts*3, 100)
    X, Y = np.meshgrid(x_grid, y_grid)
    
    tube_x = np.linspace(-L/2, L/2, 80)
    u_arr = 2.0 * tube_x / L # Normalized target length (-1 to 1)
    
    R_tube = (TUBE_OD + 2*t_thick) / 2.0

    def target_flux(t_y, ang_center):
        flux = np.zeros_like(X)
        erosion_profile = np.zeros_like(tube_x)

        # Iterate over the TWO straightaways (legs) of the magnetic racetrack
        # sign_v = 1 (Inner/Forward Leg), -1 (Outer/Backward Leg)
        for sign_v in [1, -1]: 
            # Plasma steers locally based on the leg position
            leg_ang = np.radians(ang_center + sign_v * leg_offset_deg)
            ny = np.sin(leg_ang)
            nz = -np.cos(leg_ang)
            
            emit_y = t_y + R_tube * np.sin(leg_ang)
            emit_z = tts + R_tube - R_tube * np.cos(leg_ang)

            # Electrodynamic Plasma Density Modifications
            # 1. Turnaround Dog-boning (spike at ends u = +/- 1)
            ta_boost = np.maximum(0, ta_ratio - 1.0) * (np.abs(u_arr)**6)
            
            # 2. Hall Current (ExB drift builds up in opposite directions for each leg)
            # 3. Anode Bias (One leg sees higher equipotential relative to ground)
            intensity = np.maximum(0.01, 1.0 + ta_boost + sign_v * hall * u_arr + sign_v * bias)
            erosion_profile += intensity

            # Vectorized 3D Projection
            for i, tx in enumerate(tube_x):
                dx = X - tx
                dy = Y - emit_y
                dz_vec = -emit_z # Vector points downwards to substrate at Z=0
                
                dist = np.sqrt(dx**2 + dy**2 + dz_vec**2)
                
                # N_emit dot Vector / dist
                cos_emit = np.clip((dy*ny + dz_vec*nz) / dist, 0, 1)
                
                # Substrate normal is straight up. Dot product with incoming ray isolates Z.
                cos_sub = emit_z / dist
                
                flux += intensity[i] * (cos_emit**n_col) * cos_sub / (dist**2)

        return flux, erosion_profile

    # Generate full spatial field
    flux_A, erosion_A = target_flux(-gap/2, ang_a)
    flux_B, erosion_B = target_flux(gap/2, ang_b)

    # Machine Direction (Y) Kinematic Integration
    dy = y_grid[1] - y_grid[0]
    accum_A = np.sum(flux_A, axis=0) * dy
    accum_B = np.sum(flux_B, axis=0) * dy

    return x_grid, accum_A, accum_B, tube_x, erosion_A, erosion_B

# ==========================================
# 3. SIDEBAR NAVIGATION
# ==========================================
st.sidebar.markdown("<h2 style='color:#1E3A8A; text-align:center;'>AZ Thin Film</h2>", unsafe_allow_html=True)
if os.path.exists("logo.png"): st.sidebar.image("logo.png")
st.sidebar.markdown("### Process Setup Wizard")

page = st.sidebar.radio("Navigate Design Steps:", [
    "1. Chamber & Target Layout",
    "2. Process Settings & Gas",
    "3. Magnetics & Plume Physics",
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
        st.session_state.t_length = st.slider("Target Tube Length (Cross-Web Axis X) (mm)", 300.0, 4000.0, float(st.session_state.t_length), 100.0)
        st.session_state.sub_width = st.slider("Substrate Width (Cross-Web Axis X) (mm)", 100.0, 3000.0, float(st.session_state.sub_width), 50.0)
        st.session_state.t2t_gap = st.slider("Target-to-Target Gap (Machine Direction Y) (mm)", 100.0, 500.0, float(st.session_state.t2t_gap), 10.0)
        st.session_state.tts = st.slider("Target-to-Substrate Distance (TTS) (mm)", 50.0, 300.0, float(st.session_state.tts), 5.0)
        st.session_state.t_thick = st.slider("Target Material Thickness (mm)", 1.0, 30.0, float(st.session_state.t_thick), 1.0)
        
        tot_od = TUBE_OD + 2*st.session_state.t_thick
        st.info(f"Standard {TUBE_OD}mm OD / {TUBE_ID}mm ID Base Tube.\n\n**Total Target OD:** {tot_od:.1f} mm")

    with col2:
        fig = plt.figure(figsize=(9, 11))
        gs = fig.add_gridspec(3, 1, height_ratios=[1.5, 1, 1], hspace=0.35)
        ax_top, ax_cross, ax_proxy = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
        
        # Plot 1: Top-Down View (X-Y Plane)
        ax_top.set_title("Top-Down Chamber Layout (X-Y Plane)", fontweight="bold")
        ax_top.add_patch(Rectangle((-st.session_state.sub_width/2, -st.session_state.t2t_gap - 100), st.session_state.sub_width, st.session_state.t2t_gap*2 + 200, color='gray', alpha=0.3, label="Substrate Envelope"))
        
        y_L, y_R = -st.session_state.t2t_gap/2, st.session_state.t2t_gap/2
        ax_top.add_patch(Rectangle((-st.session_state.t_length/2, y_L - tot_od/2), st.session_state.t_length, tot_od, facecolor='#1E3A8A', edgecolor='black', lw=1.5, label="Target 1"))
        ax_top.add_patch(Rectangle((-st.session_state.t_length/2, y_R - tot_od/2), st.session_state.t_length, tot_od, facecolor='#FF4B4B', edgecolor='black', lw=1.5, label="Target 2"))
        
        ax_top.arrow(0, -st.session_state.t2t_gap, 0, st.session_state.t2t_gap*1.5, width=10, head_width=40, color='cyan', alpha=0.8)
        ax_top.text(0, st.session_state.t2t_gap*0.8, "Machine Travel Direction", color='teal', fontweight='bold', ha='center')
        
        ax_top.set_aspect('equal')
        pad_x = max(st.session_state.t_length, st.session_state.sub_width) / 2 + 100
        ax_top.set_xlim(-pad_x, pad_x); ax_top.set_ylim(-st.session_state.t2t_gap - 150, st.session_state.t2t_gap + 150)
        ax_top.set_xlabel("Cross-Web Axis X (mm)"); ax_top.set_ylabel("Machine Direction Y (mm)")
        ax_top.legend(loc='upper right', fontsize=8)
        
        # Plot 2: Cross-Section Layout
        ax_cross.set_title("Machine Direction Cross-Section (Y-Z Plane)", fontweight="bold")
        ax_cross.axhline(0, color='cyan', lw=4, label="Substrate Translation Plane (Z=0)")
        cy = st.session_state.tts + (tot_od/2)
        for y_pos, label, col in [(y_L, "Target 1", "#1E3A8A"), (y_R, "Target 2", "#FF4B4B")]:
            ax_cross.add_patch(Circle((y_pos, cy), tot_od/2, fill=False, ec=col, lw=3))
            ax_cross.add_patch(Circle((y_pos, cy), TUBE_OD/2, fill=True, color='lightgray'))
            ax_cross.text(y_pos, cy + tot_od/2 + 15, label, ha='center', fontweight='bold')
            
        ax_cross.set_xlim(-st.session_state.t2t_gap*1.2, st.session_state.t2t_gap*1.2); ax_cross.set_ylim(-20, cy + tot_od/2 + 50)
        ax_cross.set_aspect('equal'); ax_cross.set_xlabel("Machine Direction Y (mm)"); ax_cross.set_ylabel("Vertical Z (mm)")
        
        # Plot 3: 1D Cross-Substrate Profile
        ax_proxy.set_title("Analytical Cross-Web Deposition Proxy", fontweight="bold")
        x_grid = np.linspace(-pad_x, pad_x, 300)
        L, H = st.session_state.t_length, st.session_state.tts
        dep_proxy = np.arctan((L/2 - x_grid)/H) + np.arctan((L/2 + x_grid)/H)
        dep_proxy = dep_proxy / np.max(dep_proxy)
        
        ax_proxy.plot(x_grid, dep_proxy, color='black', lw=3, label="1D Line Source Deposition Proxy")
        ax_proxy.axvspan(-st.session_state.sub_width/2, st.session_state.sub_width/2, color='gray', alpha=0.2, label='Substrate Envelope')
        ax_proxy.plot([-L/2, L/2], [1.05, 1.05], color='#1E3A8A', lw=4, label='Physical Target Extents')
        ax_proxy.set_xlabel("Cross-Web Axis X (mm)"); ax_proxy.set_ylabel("Relative Intensity")
        ax_proxy.set_ylim(0, 1.2); ax_proxy.legend(loc='lower center', ncol=3, fontsize=8); ax_proxy.grid(True, linestyle='--', alpha=0.5)
        
        apply_watermark(fig)
        st.pyplot(fig)

# ==========================================
# PAGE 2: PROCESS SETTINGS & GAS
# ==========================================
elif page == "2. Process Settings & Gas":
    st.title("Step 2: Power, Velocity & Gases")
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        st.subheader("Process Settings")
        st.session_state.mat_a = st.selectbox("Target 1 Material", ["Ti", "Al", "Si", "Nb", "Cu", "Cr"], index=["Ti", "Al", "Si", "Nb", "Cu", "Cr"].index(st.session_state.mat_a))
        st.session_state.mat_b = st.selectbox("Target 2 Material", ["Ti", "Al", "Si", "Nb", "Cu", "Cr"], index=["Ti", "Al", "Si", "Nb", "Cu", "Cr"].index(st.session_state.mat_b))
        st.session_state.sub_vel = st.slider("Substrate Travel Velocity (mm/s)", 1.0, 150.0, float(st.session_state.sub_vel))
        
        st.session_state.ps_type = st.selectbox("Power Supply Architecture", ["DC", "Pulsed DC", "AC", "Bi-Polar Pulse DC", "HiPIMS"], index=["DC", "Pulsed DC", "AC", "Bi-Polar Pulse DC", "HiPIMS"].index(st.session_state.ps_type))
        if st.session_state.ps_type in ["Pulsed DC", "AC", "Bi-Polar Pulse DC", "HiPIMS"]:
            st.session_state.ps_freq = st.slider("Operating Frequency (kHz)", 10.0, 350.0, float(st.session_state.ps_freq))
        
        max_power = float((st.session_state.t_length / 1000.0) * 20.0)
        safe_val = min(st.session_state.power_kw, max_power * 1.5)
        st.session_state.power_kw = st.slider(f"Operating Power (kW) [Thermal Limit ~{max_power:.1f} kW]", 1.0, max_power*1.5, float(safe_val))
        
        st.subheader("Gases & Pumping")
        g1, g2 = st.columns(2)
        st.session_state.gas_main = g1.text_input("Main Gas", st.session_state.gas_main)
        st.session_state.flow_main = g1.number_input("Main Flow (sccm)", 0.0, 1000.0, float(st.session_state.flow_main))
        st.session_state.gas_react = g2.text_input("React. Gas", st.session_state.gas_react)
        st.session_state.flow_react = g2.number_input("React. Flow (sccm)", 0.0, 1000.0, float(st.session_state.flow_react))
        
        st.session_state.manifold = st.selectbox("Gas Manifold Position", ["Between Targets", "Outside Targets", "Both"])
        st.session_state.num_zones = st.number_input("Number of MFCs (Zones along Target Length)", 1, 10, int(st.session_state.num_zones))
        st.session_state.pump_speed = st.slider("Estimated Pumping Speed (L/s)", 100.0, 3000.0, float(st.session_state.pump_speed), 100.0)

    with col2:
        fig = plt.figure(figsize=(10, 11))
        gs = fig.add_gridspec(2, 1, height_ratios=[2.5, 1], hspace=0.3)
        ax_sys, ax_wave = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
        
        # Top-Down P&ID Blueprint
        ax_sys.set_title("Electrical & Gas Flow Blueprint (Top-Down X-Y Plane)", fontweight='bold')
        L, gap = st.session_state.t_length, st.session_state.t2t_gap
        tot_od = TUBE_OD + 2*st.session_state.t_thick
        
        ax_sys.add_patch(Rectangle((-st.session_state.sub_width/2, -gap - 100), st.session_state.sub_width, gap*2 + 200, color='lightgray', alpha=0.3))
        ax_sys.arrow(0, -gap*0.8, 0, gap*1.6, width=L*0.02, head_width=L*0.06, color='black', alpha=0.3)
        
        ax_sys.add_patch(Rectangle((-L/2, -gap/2 - tot_od/2), L, tot_od, facecolor='#1E3A8A', edgecolor='black'))
        ax_sys.text(0, -gap/2, f"Target 1 ({st.session_state.mat_a})", color='white', ha='center', va='center', fontweight='bold')
        ax_sys.add_patch(Rectangle((-L/2, gap/2 - tot_od/2), L, tot_od, facecolor='#FF4B4B', edgecolor='black'))
        ax_sys.text(0, gap/2, f"Target 2 ({st.session_state.mat_b})", color='white', ha='center', va='center', fontweight='bold')
        
        zones = np.linspace(-L/2, L/2, st.session_state.num_zones + 2)[1:-1]
        if "Outside" in st.session_state.manifold or "Both" in st.session_state.manifold:
            ax_sys.plot([-L/2, L/2], [-gap/2 - tot_od/2 - 20, -gap/2 - tot_od/2 - 20], color='green', lw=3)
            ax_sys.scatter(zones, np.full_like(zones, -gap/2 - tot_od/2 - 20), color='white', edgecolor='green', zorder=5)
            ax_sys.plot([-L/2, L/2], [gap/2 + tot_od/2 + 20, gap/2 + tot_od/2 + 20], color='green', lw=3)
            ax_sys.scatter(zones, np.full_like(zones, gap/2 + tot_od/2 + 20), color='white', edgecolor='green', zorder=5)
            
        if "Between" in st.session_state.manifold or "Both" in st.session_state.manifold:
            ax_sys.plot([-L/2, L/2], [0, 0], color='green', lw=3)
            ax_sys.scatter(zones, np.full_like(zones, 0), color='white', edgecolor='green', zorder=5)
            
        ps_x = -L/2 - 150
        bbox_style = dict(boxstyle="round,pad=0.6", fc="gold", ec="black", lw=2)
        if st.session_state.ps_type in ["AC", "Bi-Polar Pulse DC"]:
            ax_sys.annotate(f"Shared {st.session_state.ps_type} PS\n({st.session_state.power_kw} kW)", xy=(ps_x, 0), ha="right", va="center", fontweight='bold', bbox=bbox_style)
            ax_sys.plot([ps_x + 10, -L/2], [0, -gap/2], 'k-', lw=3); ax_sys.plot([ps_x + 10, -L/2], [0, gap/2], 'k-', lw=3)
        else:
            ax_sys.annotate(f"PS 1\n{st.session_state.power_kw/2:.1f} kW", xy=(ps_x, -gap/2), ha="right", va="center", fontweight='bold', bbox=bbox_style)
            ax_sys.plot([ps_x + 10, -L/2], [-gap/2, -gap/2], 'k-', lw=3)
            ax_sys.annotate(f"PS 2\n{st.session_state.power_kw/2:.1f} kW", xy=(ps_x, gap/2), ha="right", va="center", fontweight='bold', bbox=bbox_style)
            ax_sys.plot([ps_x + 10, -L/2], [gap/2, gap/2], 'k-', lw=3)

        x_limit_R, x_limit_L = max(L/2, st.session_state.sub_width/2) + 100, -L/2 - 400
        ax_sys.set_aspect('equal'); ax_sys.set_xlim(x_limit_L, x_limit_R); ax_sys.set_ylim(-gap - 100, gap + 100)
        ax_sys.axis('off')
        
        # Timing Waveform
        t = np.linspace(0, 4*np.pi, 400)
        ax_wave.set_title(f"Target Voltage Phase Timing ({st.session_state.ps_type})", fontweight='bold')
        if st.session_state.ps_type == "AC":
            ax_wave.plot(t, np.sin(t), 'r', lw=2, label="Target 1 Voltage")
            ax_wave.plot(t, np.sin(t + np.pi), 'b--', lw=2, label="Target 2 Voltage")
        elif st.session_state.ps_type == "Bi-Polar Pulse DC":
            ax_wave.plot(t, np.sign(np.sin(t)), 'r', lw=2, drawstyle='steps-pre', label="Target 1 Phase")
            ax_wave.plot(t, np.sign(np.sin(t + np.pi)), 'b--', lw=2, drawstyle='steps-pre', label="Target 2 Phase")
        else:
            ax_wave.plot(t, np.ones_like(t), 'purple', lw=2, label="Targets 1 & 2 (DC)")
            
        ax_wave.set_yticks([]); ax_wave.set_xlabel("Time (µs)"); ax_wave.legend(loc="upper right", fontsize=9)
        apply_watermark(fig); plt.tight_layout(); st.pyplot(fig)

# ==========================================
# PAGE 3: MAGNETICS & PLUME PHYSICS
# ==========================================
elif page == "3. Magnetics & Plume Physics":
    st.title("Step 3: Advanced Magnetics & Dual-Leg Racetrack Physics")
    st.markdown("Tune the magnetic trap and observe the real-time trade-offs between **Cross-Web Uniformity**, **Plasma ExB Steering**, and **Target Utilization**.")
    
    col1, col2 = st.columns([1, 1.6])
    with col1:
        st.subheader("1. Base Magnetics")
        st.session_state.mag_ang_a = st.slider("Target 1 Center Angle (deg)", -45.0, 45.0, float(st.session_state.mag_ang_a), help="Overall steering direction.")
        st.session_state.mag_ang_b = st.slider("Target 2 Center Angle (deg)", -45.0, 45.0, float(st.session_state.mag_ang_b), help="Overall steering direction.")
        st.session_state.leg_offset = st.slider("Dual-Leg Angle Separation (± deg)", 5.0, 45.0, float(st.session_state.leg_offset), help="Angle spanning between the two straightaways.")
        
        st.session_state.ta_ratio = st.slider("Turnaround Strength Multiplier", 0.5, 3.0, float(st.session_state.ta_ratio), 
                                              help="Increases plasma density at the ends. Flattens cross-web uniformity but digs deep dog-bone trenches (lowers utilization).")
        
        st.subheader("2. Electrodynamics (ExB Plasma Physics)")
        st.session_state.hall_drift = st.slider("ExB Hall Current Drift Build-up (%)", 0.0, 50.0, float(st.session_state.hall_drift), 
                                                help="Simulates Townsend avalanche along the straightaways. Leg 1 drifts right, Leg 2 drifts left.")
        st.session_state.anode_bias = st.slider("Asymmetric Anode Bias (%)", -50.0, 50.0, float(st.session_state.anode_bias), 
                                                help="Shifts overall plasma density heavily onto the Inner or Outer leg due to adjacent chamber grounds.")
        
        st.subheader("3. Plasma Plume Collimation")
        est_n = 1.0 + (1.5 if st.session_state.ps_type == "HiPIMS" else 0.3 if st.session_state.ps_type in ["AC", "Bi-Polar Pulse DC"] else 0.1)
        st.session_state.plume_override = st.checkbox("Override AI Collimation?", st.session_state.plume_override)
        if st.session_state.plume_override:
            st.session_state.plume_n = st.slider("Shape Factor (Cos^n)", 0.5, 5.0, float(st.session_state.plume_n))
        else:
            st.session_state.plume_n = est_n
            st.info(f"💡 AI Plume Collimation Estimate: **Cos^{est_n:.2f}(\u03B8)**")

    with col2:
        fig = plt.figure(figsize=(10, 14))
        gs = fig.add_gridspec(3, 1, height_ratios=[1.2, 1, 1], hspace=0.35)
        ax_plume, ax_erosion, ax_unif = fig.add_subplot(gs[0]), fig.add_subplot(gs[1]), fig.add_subplot(gs[2])
        
        # 1. Dual-Lobe Plume Profile (Y-Z Plane)
        y_L, y_R = -st.session_state.t2t_gap/2, st.session_state.t2t_gap/2
        tot_r = (TUBE_OD + 2*st.session_state.t_thick)/2
        z_t = st.session_state.tts + tot_r
        
        ax_plume.axhline(0, color='cyan', lw=4, alpha=0.5, label="Substrate Translation Path")
        
        for cy, ang, color in [(y_L, st.session_state.mag_ang_a, '#1E3A8A'), (y_R, st.session_state.mag_ang_b, '#FF4B4B')]:
            ax_plume.add_patch(Circle((cy, z_t), tot_r, fill=False, ec='black', lw=2))
            
            # Center vector
            ang_rad = np.radians(-90 + ang)
            ax_plume.plot([cy, cy + tot_r*np.cos(ang_rad)], [z_t, z_t + tot_r*np.sin(ang_rad)], color='k', lw=2, linestyle=':')
            
            # Draw Two Lobes per target (sign_v dictates inner vs outer leg)
            for sign_v in [1, -1]:
                leg_ang = ang_rad + sign_v * np.radians(st.session_state.leg_offset)
                angles = np.linspace(leg_ang - np.pi/2, leg_ang + np.pi/2, 100)
                
                # Visualize Anode Bias impact on lobe size
                bias_mod = max(0.1, 1.0 + sign_v * (st.session_state.anode_bias / 100.0))
                r_lobe = 100 * bias_mod * np.maximum(0, np.cos(angles - leg_ang))**st.session_state.plume_n
                
                ax_plume.fill(cy + tot_r * np.cos(leg_ang) + r_lobe * np.cos(angles), 
                              z_t + tot_r * np.sin(leg_ang) + r_lobe * np.sin(angles), color=color, alpha=0.35)
                ax_plume.plot([cy, cy + tot_r*np.cos(leg_ang)], [z_t, z_t + tot_r*np.sin(leg_ang)], color='k', lw=1.5)

        ax_plume.set_aspect('equal')
        ax_plume.set_xlim(-st.session_state.t2t_gap - 150, st.session_state.t2t_gap + 150)
        ax_plume.set_ylim(-20, z_t + tot_r + 40)
        ax_plume.set_title("Dual-Leg Racetrack Plume Profile (Machine-Direction Y-Z Plane)", fontweight="bold")
        ax_plume.set_xlabel("Machine Direction Y (mm)")
        ax_plume.set_ylabel("Vertical Z (mm)")
        
        # 2. Fast Kinematic Simulation
        with st.spinner("Calculating Live Dual-Leg Electrodynamics..."):
            x_grid, acc_A, acc_B, tube_x, ero_A, ero_B = calc_kinematic_profile(
                st.session_state.t_length, st.session_state.sub_width, st.session_state.t2t_gap, 
                st.session_state.tts, st.session_state.t_thick, st.session_state.mag_ang_a, st.session_state.mag_ang_b, 
                st.session_state.ta_ratio, st.session_state.leg_offset, st.session_state.hall_drift, 
                st.session_state.anode_bias, st.session_state.plume_n
            )
            
        acc_total = acc_A + acc_B
        sub_mask = (x_grid >= -st.session_state.sub_width/2) & (x_grid <= st.session_state.sub_width/2)
        mean_thk = np.mean(acc_total[sub_mask])
        unif = (np.max(acc_total[sub_mask]) - np.min(acc_total[sub_mask])) / (2 * mean_thk) * 100 if mean_thk > 0 else 0
        
        # 3. Target Erosion Profile & Utilization
        utilization_A = np.mean(ero_A) / np.max(ero_A) * 100
        
        # Reconstruct the physical legs purely for visual dashed breakdown on the plot
        u_arr = 2.0 * tube_x / st.session_state.t_length
        ta_boost = np.maximum(0, st.session_state.ta_ratio - 1.0) * (np.abs(u_arr)**6)
        hall_factor = st.session_state.hall_drift / 100.0
        bias_factor = st.session_state.anode_bias / 100.0
        
        I_LegA = np.maximum(0, 1.0 + ta_boost + hall_factor * u_arr + bias_factor)
        I_LegB = np.maximum(0, 1.0 + ta_boost - hall_factor * u_arr - bias_factor)
        
        ax_erosion.set_title(f"Target Erosion Profile | Target Utilization: {utilization_A:.1f}%", fontweight="bold")
        ax_erosion.plot(tube_x, I_LegA, color='green', ls='--', label="Leg 1 (ExB Drift Right)")
        ax_erosion.plot(tube_x, I_LegB, color='purple', ls='--', label="Leg 2 (ExB Drift Left)")
        ax_erosion.plot(tube_x, ero_A, color='black', lw=3, label=f"Rotary Circumferential Wear")
        ax_erosion.fill_between(tube_x, 0, ero_A, color='gray', alpha=0.2)
        
        ax_erosion.set_xlim(-st.session_state.t_length/2 - 50, st.session_state.t_length/2 + 50)
        ax_erosion.set_ylim(0, np.max(ero_A) * 1.25)
        ax_erosion.set_xlabel("Target Length (Cross-Web X mm)")
        ax_erosion.set_ylabel("Relative Erosion Depth")
        ax_erosion.legend(loc='lower center', ncol=3, fontsize=9)
        ax_erosion.grid(True, linestyle=':', alpha=0.7)
        
        # 4. Instant Uniformity Profile
        ax_unif.plot(x_grid, acc_total, color='black', lw=3, label="Combined Pass")
        ax_unif.plot(x_grid, acc_A, color='#1E3A8A', ls='--', label="Target 1")
        ax_unif.plot(x_grid, acc_B, color='#FF4B4B', ls='--', label="Target 2")
        ax_unif.axvspan(-st.session_state.sub_width/2, st.session_state.sub_width/2, color='gray', alpha=0.15, label='Substrate Envelope')
        ax_unif.set_title(f"Live Kinematic Cross-Web Uniformity Preview: ± {unif:.2f}%", fontweight="bold")
        ax_unif.set_xlabel("Cross-Web X (mm)")
        ax_unif.set_ylabel("Relative Flux Dose")
        ax_unif.legend(loc='lower center', ncol=4, fontsize=9)
        ax_unif.grid(True, linestyle=':', alpha=0.7)
        
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
    c4.metric("Electrodynamics", f"T1: {st.session_state.mag_ang_a}° | T2: {st.session_state.mag_ang_b}°", f"TA Ratio: {st.session_state.ta_ratio}")
    st.divider()
    
    with st.spinner("Calculating Full 3D Dual-Leg Integration across Linear Translation Vector..."):
        x_grid, acc_A, acc_B, tube_x, ero_A, ero_B = calc_kinematic_profile(
            st.session_state.t_length, st.session_state.sub_width, st.session_state.t2t_gap, 
            st.session_state.tts, st.session_state.t_thick, st.session_state.mag_ang_a, st.session_state.mag_ang_b, 
            st.session_state.ta_ratio, st.session_state.leg_offset, st.session_state.hall_drift, 
            st.session_state.anode_bias, st.session_state.plume_n
        )
        
        # Convert to real units (nm proxy)
        dt = 1.0 / st.session_state.sub_vel
        yield_proxy = 10000.0 * st.session_state.power_kw 
        
        accum_L = acc_A * yield_proxy * dt
        accum_R = acc_B * yield_proxy * dt
        accum_total = accum_L + accum_R
        
        sub_mask = (x_grid >= -st.session_state.sub_width/2) & (x_grid <= st.session_state.sub_width/2)
        mean_thk = np.mean(accum_total[sub_mask])
        unif = (np.max(accum_total[sub_mask]) - np.min(accum_total[sub_mask])) / (2 * mean_thk) * 100 if mean_thk > 0 else 0
        util_A = np.mean(ero_A) / np.max(ero_A) * 100
        
    c1, c2 = st.columns([2, 1])
    with c1:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(x_grid, accum_total, color='black', lw=3, label='Combined Final Profile')
        ax.plot(x_grid, accum_L, color='#1E3A8A', ls='--', label=f'Target 1 ({st.session_state.mat_a})')
        ax.plot(x_grid, accum_R, color='#FF4B4B', ls='--', label=f'Target 2 ({st.session_state.mat_b})')
        
        ax.axvspan(-st.session_state.sub_width/2, st.session_state.sub_width/2, color='gray', alpha=0.15, label='Substrate Envelope')
        ax.set_title("Machine-Direction Integrated Cross-Web Uniformity", fontweight='bold')
        ax.set_xlabel("Cross-Web Axis X (mm)")
        ax.set_ylabel("Accumulated Dose (nm proxy)")
        ax.grid(True, linestyle=':', alpha=0.7)
        ax.legend(loc='lower center', ncol=4, bbox_to_anchor=(0.5, -0.3))
        apply_watermark(fig)
        st.pyplot(fig)
        
    with c2:
        st.success("Simulation Complete")
        st.metric("Substrate Uniformity", f"± {unif:.2f} %")
        st.metric("Calculated Average Dose", f"{mean_thk:.2f} nm")
        st.metric("Target Utilization (Yield)", f"{util_A:.1f} %")
        
        if unif > 5.0:
            st.error("⚠️ **Uniformity > 5%**: Adjust Magnet Bar Angles inwards or increase the Turnaround Ratio (at the expense of target life).")
        elif unif > 2.0:
            st.warning("✅ **Uniformity < 5%**: Acceptable profile.")
        else:
            st.info("⭐ **Uniformity < 2%**: Excellent baseline process design parameters.")
