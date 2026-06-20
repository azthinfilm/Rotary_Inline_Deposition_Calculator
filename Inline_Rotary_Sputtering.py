import streamlit as st
import numpy as np
import matplotlib
matplotlib.use("Agg") # Force headless rendering to prevent Linux web server crashes
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from matplotlib.ticker import MaxNLocator
from scipy.interpolate import RectBivariateSpline
import os

# ==========================================
# 1. UI ARCHITECTURE & AZ BRANDING
# ==========================================
st.set_page_config(page_title="AZ Thin Film | Inline Multiphysics Sim", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC; }
    h1, h2, h3, h4 { color: #1E3A8A; font-family: 'Helvetica Neue', sans-serif; }
    .stMetric { border-left: 4px solid #1E3A8A; padding-left: 15px; background-color: #ffffff; padding: 10px; border-radius: 5px; box-shadow: 0px 2px 4px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

st.sidebar.markdown("<h2 style='color:#1E3A8A; text-align:center;'>AZ Thin Film Research</h2>", unsafe_allow_html=True)
if os.path.exists("logo.png"):
    st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.markdown("---")

# ==========================================
# 2. ENGINEERING INPUTS (SIDEBAR)
# ==========================================
st.sidebar.header("1. Target Materials & Power")
mat_A = st.sidebar.selectbox("Cathode A Material", ["Ti", "Al", "Si", "Nb", "Cu"])
mat_B = st.sidebar.selectbox("Cathode B Material", ["Ti", "Al", "Si", "Nb", "Cu"], index=1)
power_supply = st.sidebar.selectbox("Power Supply Type", ["DC", "Pulsed DC", "AC (Dual)", "HiPIMS"])
total_power = st.sidebar.slider("Power per Cathode (kW)", 2.0, 40.0, 10.0, step=0.5)

st.sidebar.header("2. Reactive Berg Model")
pressure = st.sidebar.slider("Process Pressure (mTorr)", 0.5, 15.0, 3.0, step=0.5)
reactive_flow = st.sidebar.slider("Reactive Gas Flow (sccm)", 0, 150, 45)
pump_speed = st.sidebar.slider("Pumping Speed (L/s)", 100, 2000, 500)

st.sidebar.header("3. Inline Geometry")
sub_width = st.sidebar.slider("Substrate Cross-Web Width (mm)", 100, 1000, 400)
t_length = st.sidebar.slider("Target Length (X-Axis) (mm)", 300, 1500, 600)
c_spacing = st.sidebar.slider("Cathode Gap (Y-Axis) (mm)", 100, 300, 150)
t_to_s = st.sidebar.slider("Target-to-Substrate Dist (mm)", 50, 200, 100)
sub_speed = st.sidebar.slider("Linear Travel Speed (mm/s)", 1.0, 100.0, 20.0)

st.sidebar.header("4. Magnetic Field Control")
b_straight = st.sidebar.slider("Straightaway B-Field (Gauss)", 200, 1000, 400)
b_turn_ratio = st.sidebar.slider("Turnaround Strength Multiplier", 0.5, 2.0, 1.25, 
                                 help=">1.0 intensifies plasma at the tube ends (dog-boning).")
sputter_angle = st.sidebar.slider("Inward Sputter Angle (deg)", -20, 45, 15, 
                                  help="Positive angle points Cathode A and B inwards toward each other.")

# Empirical Material Properties Proxy (Relative Yield, Reactive Affinity, Bulk Density)
MAT_PROPS = {
    "Ti": {"yield": 0.5, "affinity": 1.5, "rho": 4.50},
    "Al": {"yield": 1.2, "affinity": 1.2, "rho": 2.70},
    "Si": {"yield": 0.4, "affinity": 0.9, "rho": 2.33},
    "Nb": {"yield": 0.6, "affinity": 1.4, "rho": 8.57},
    "Cu": {"yield": 2.0, "affinity": 0.2, "rho": 8.96}
}

# ==========================================
# 3. MULTIPHYSICS SOLVERS
# ==========================================
@st.cache_data
def calculate_berg_hysteresis(flow, pump, press, power, m1, m2):
    """Steady-State proxy for Reactive Target Poisoning."""
    avg_affinity = (MAT_PROPS[m1]["affinity"] + MAT_PROPS[m2]["affinity"]) / 2.0
    # Phenomenological critical poisoning point
    q_crit = (pump * press * 0.02) + (power * avg_affinity * 1.5) 
    
    # Logistic transition mimicking the S-curve
    theta_t = 1.0 / (1.0 + np.exp(-(flow - q_crit) / max(2.0, pump/200.0)))
    
    # Deposition rate dynamically collapses from metallic to compound phase
    rate_multiplier = 1.0 - (0.85 * theta_t) 
    return theta_t, rate_multiplier, q_crit

@st.cache_data
def calculate_plasma_impedance(power, press, b_field, supply):
    """Phenomenological V-I solver based on ExB electron confinement."""
    # V scales with sqrt of power, inversely with B-field and Pressure
    v_base = 350.0 * (power / 10.0)**0.4
    v_conf = v_base * (400.0 / b_field)**0.5 * (3.0 / press)**0.15 
    
    if supply == "HiPIMS":
        v_conf *= 1.8 # Massive density pulse pushes V up, Z drops transiently
    elif supply == "AC (Dual)":
        v_conf *= 0.95 
        
    current = (power * 1000.0) / v_conf
    impedance = v_conf / current
    return v_conf, current, impedance

def estimate_thornton_szm(voltage, press, ts_dist, supply):
    """Thornton Structure Zone Estimator based on adatom kinetic energy proxy."""
    pd_product = press * (ts_dist / 10.0) # mTorr * cm
    energy_proxy = (voltage / 10.0) / max(pd_product, 0.5)
    
    if supply == "HiPIMS":
        energy_proxy *= 2.5 # Ionization fraction boosts adatom bombardment
        
    if energy_proxy > 80:
        return "Zone T (Dense, Smooth, Compressive)", 98.5
    elif energy_proxy > 30:
        return "Zone 2 (Columnar, Crystalline)", 88.0
    else:
        return "Zone 1 (Porous, Voided, Tensile)", 72.0

# ==========================================
# 4. CONTINUOUS 3D POINT CLOUD ENGINE
# ==========================================
@st.cache_data
def compute_static_flux_field(t_len, c_gap, t2s, angle_deg, b_ratio, ps_type, m1, m2):
    """Generates the static 2D cross-web interference matrix from unrolled 3D cylinders."""
    x_grid = np.linspace(-t_len*0.8, t_len*0.8, 120) # Cross-Web Axis
    y_grid = np.linspace(-c_gap*2, c_gap*2, 100)     # Machine Direction Axis
    X, Y = np.meshgrid(x_grid, y_grid)
    
    n_collimation = 2.0 if ps_type == "HiPIMS" else 1.0 # Cosine exponent
    
    def calculate_plume(y_pos, tilt_deg, material):
        tilt_rad = np.radians(tilt_deg)
        flux = np.zeros_like(X)
        y_scale = MAT_PROPS[material]["yield"]
        
        # Discretize target into points along the X-axis
        tube_x = np.linspace(-t_len/2, t_len/2, 60)
        R_tube = 45.0
        
        for tx in tube_x:
            # Turnaround Dog-bone polynomial modifier at target ends
            u = 2.0 * tx / t_len 
            intensity = 1.0 + (b_ratio - 1.0) * (abs(u)**6)
            
            # Represent two parallel legs of the racetrack (offset +/- 20 deg from tilt)
            for leg_offset in [np.radians(20), np.radians(-20)]:
                leg_angle = tilt_rad + leg_offset
                
                emit_y = y_pos + R_tube * np.sin(leg_angle)
                emit_z = R_tube - R_tube * np.cos(leg_angle)
                
                # Normal Vectors rotated by tilt
                ny = np.sin(leg_angle)
                nz = -np.cos(leg_angle)
                
                dx = X - tx
                dy = Y - emit_y
                dz = t2s - emit_z
                
                dist_sq = dx**2 + dy**2 + dz**2
                dist = np.sqrt(dist_sq)
                
                cos_emit = np.clip((dy*ny + dz*nz) / dist, 0, 1)
                cos_sub = dz / dist
                
                flux += intensity * (cos_emit**n_collimation) * cos_sub / dist_sq * y_scale
                
        return flux

    # Generate Cathode A (Negative Y, Tilted Inward) & Cathode B (Positive Y, Tilted Inward)
    flux_A = calculate_plume(-c_gap/2, angle_deg, m1)
    flux_B = calculate_plume(c_gap/2, -angle_deg, m2) 
    
    return x_grid, y_grid, flux_A, flux_B

# ==========================================
# 5. EXECUTE PHYSICS ENGINE
# ==========================================
theta_t, rate_mult, q_crit = calculate_berg_hysteresis(reactive_flow, pump_speed, pressure, total_power, mat_A, mat_B)
voltage, current, impedance = calculate_plasma_impedance(total_power, pressure, b_straight, power_supply)
structure, density = estimate_thornton_szm(voltage, pressure, t_to_s, power_supply)

x_grid, y_grid, flux_A, flux_B = compute_static_flux_field(t_length, c_spacing, t_to_s, sputter_angle, b_turn_ratio, power_supply, mat_A, mat_B)

# Apply dynamic Berg poisoning rate drop to the absolute flux arrays
scalar = (total_power * 10.0) * rate_mult
flux_A_scaled = (flux_A / np.max(flux_A + flux_B)) * scalar
flux_B_scaled = (flux_B / np.max(flux_A + flux_B)) * scalar
total_flux_2d = flux_A_scaled + flux_B_scaled

# KINEMATIC INTEGRATION: Substrate translates linearly through the Y-Axis plume
# We sum the flux along the Machine Direction (Y) to get Accumulated Cross-Web Thickness (X)
dy = y_grid[1] - y_grid[0]
accum_A = np.sum(flux_A_scaled, axis=0) * (dy / sub_speed)
accum_B = np.sum(flux_B_scaled, axis=0) * (dy / sub_speed)
accum_total = accum_A + accum_B

# Isolate data exclusively on the specified substrate width
sub_mask = (x_grid >= -sub_width/2) & (x_grid <= sub_width/2)
accum_sub = accum_total[sub_mask]
mean_thk = np.mean(accum_sub)
uniformity = (np.max(accum_sub) - np.min(accum_sub)) / (2 * mean_thk) * 100

homogeneity = np.mean(accum_A[sub_mask] / (accum_total[sub_mask] + 1e-9))

# ==========================================
# 6. DASHBOARD & VISUALIZATION
# ==========================================
# Core Diagnostics Metrics
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Plasma Impedance", f"{impedance:.1f} Ω", f"{int(voltage)} V | {current:.1f} A")
m2.metric("Target Mode", "Poisoned" if theta_t > 0.8 else "Transition" if theta_t > 0.2 else "Metallic", f"{theta_t*100:.1f}% Covered")
m3.metric("Dyn. Pass Dep Rate", f"{mean_thk:.1f} nm/pass")
m4.metric("Est. Film Density", f"{density:.1f} %")
m5.metric("Cross-Web Uniformity", f"± {uniformity:.2f} %", delta="Target < 5%", delta_color="inverse")

st.info(f"**Thornton Structure Zone Estimate:** {structure}  |  **Film Core Homogeneity:** {homogeneity*100:.1f}% `{mat_A}` / {(1-homogeneity)*100:.1f}% `{mat_B}`")
st.divider()

col_plot1, col_plot2 = st.columns([1.2, 1])

with col_plot1:
    st.subheader("Kinematic Cross-Web Accumulation")
    fig1, ax1 = plt.subplots(figsize=(8, 5))
    
    ax1.plot(x_grid, accum_total, color='#1E3A8A', lw=3, label='Combined Total Profile')
    ax1.plot(x_grid, accum_A, color='#FF4B4B', lw=2, linestyle='-.', label=f'Cathode A ({mat_A})')
    ax1.plot(x_grid, accum_B, color='#00CC96', lw=2, linestyle='-.', label=f'Cathode B ({mat_B})')
    
    # Substrate Indicator Overlay
    ax1.axvspan(-sub_width/2, sub_width/2, color='gray', alpha=0.1, label="Substrate Width")
    
    ax1.set_xlabel("Cross-Web Translation Axis (X mm)")
    ax1.set_ylabel("Accumulated Linear Dose (nm)")
    ax1.grid(True, linestyle=':', alpha=0.7)
    ax1.legend(loc="lower center", ncol=2)
    
    # Mandatory Watermarking
    fig1.text(0.5, -0.05, "Simulation provided by AZ Thin Film Research | www.azthinfilm.com", ha='center', fontsize=8, color='gray')
    st.pyplot(fig1)

with col_plot2:
    st.subheader("Berg Reactive Process Window")
    fig2, ax2 = plt.subplots(figsize=(6, 5))
    
    flows = np.linspace(0, 150, 100)
    rates = [calculate_berg_hysteresis(f, pump_speed, pressure, total_power, mat_A, mat_B)[1] * 100 for f in flows]
    
    ax2.plot(flows, rates, color="#1E3A8A", lw=2.5, label="Deposition Rate Hysteresis")
    
    # Highlight specific operating setpoint on the curve
    ax2.scatter([reactive_flow], [rate_mult*100], color='gold', edgecolor='black', s=100, zorder=5, label="Current Setpoint")
    
    # Annotate Hysteresis Cliff
    ax2.axvspan(q_crit - 10, q_crit + 10, color="gray", alpha=0.2, label="Instability Zone")
    
    ax2.set_xlabel("Reactive Gas Flow (sccm)")
    ax2.set_ylabel("Relative Dep Rate Yield (%)")
    ax2.legend(loc="lower left", fontsize=9)
    ax2.grid(True, linestyle=':', alpha=0.7)
    
    fig2.text(0.5, -0.05, "Simulation provided by AZ Thin Film Research | www.azthinfilm.com", ha='center', fontsize=8, color='gray')
    st.pyplot(fig2)
