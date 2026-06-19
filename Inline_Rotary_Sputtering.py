import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# ----------------------------------------------------------------
# Page Configuration & Theme
# ----------------------------------------------------------------
st.set_page_config(
    page_title="AZ Twin-Cathode Uniformity Solver",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Inline Thin Film Deposition Uniformity Simulator")
st.markdown("### Production Solver: Twin Cylindrical Rotary Cathodes")
st.markdown("---")

# ----------------------------------------------------------------
# Sidebar Inputs (Process Configurations)
# ----------------------------------------------------------------
st.sidebar.header("1. Global Material & Tool Geometry")

material = st.sidebar.selectbox(
    "Target Material",
    ["Chromium (Cr)", "Aluminum (Al)", "Titanium (Ti)", "Copper (Cu)"]
)

power_type = st.sidebar.selectbox(
    "Power Supply Type",
    ["DC Sputtering", "HiPIMS", "RF Sputtering"]
)

sub_speed = st.sidebar.number_input("Substrate Translation Speed (mm/s)", min_value=0.1, max_value=200.0, value=10.0, step=0.5)
h_dist = st.sidebar.number_input("Target-to-Substrate Distance (mm)", min_value=10.0, max_value=500.0, value=150.0, step=5.0)
tgt_length = st.sidebar.number_input("Target Length (mm)", min_value=100.0, max_value=3000.0, value=1000.0, step=50.0)
sub_width = st.sidebar.number_input("Substrate Width (mm)", min_value=50.0, max_value=2500.0, value=800.0, step=50.0)

st.sidebar.header("2. Cathode 1 Settings")
c1_bias = st.sidebar.slider("Cathode 1 Profile Bias", min_value=-1.0, max_value=1.0, value=0.0, step=0.1, 
                            help="Negative = Center Heavy, Positive = Edge Heavy")
c1_skew = st.sidebar.number_input("Cathode 1 Alignment Skew / Offset (mm)", min_value=-200.0, max_value=200.0, value=0.0, step=1.0)

st.sidebar.header("3. Cathode 2 Settings")
c2_bias = st.sidebar.slider("Cathode 2 Profile Bias", min_value=-1.0, max_value=1.0, value=0.0, step=0.1,
                            help="Negative = Center Heavy, Positive = Edge Heavy")
c2_skew = st.sidebar.number_input("Cathode 2 Alignment Skew / Offset (mm)", min_value=-200.0, max_value=200.0, value=0.0, step=1.0)

# ----------------------------------------------------------------
# Simulation Mathematical Physics Engine
# ----------------------------------------------------------------

# Material relative yield coefficients
material_yields = {"Chromium (Cr)": 1.0, "Aluminum (Al)": 1.2, "Titanium (Ti)": 0.6, "Copper (Cu)": 2.1}
base_yield = material_yields[material]

# Power supply exponent adjustments (Gas scattering approximation effects)
# Higher exponents represent narrower/more forward-directed flux distributions
power_exponents = {"DC Sputtering": 2.0, "HiPIMS": 3.5, "RF Sputtering": 1.5}
n_exponent = power_exponents[power_type]

# Discretize substrate coordinates across its width (X-axis)
x_sub = np.linspace(-sub_width / 2, sub_width / 2, 300)

def calculate_cathode_flux(bias, skew, length, distance, exponent, base_rate):
    """
    Numerically integrates elemental point sources along a line source to get cross-web flux profile.
    """
    num_elements = 150
    # Discretize the target length axis
    y_tgt = np.linspace(-length / 2 + skew, length / 2 + skew, num_elements)
    dy = length / num_elements
    
    # Pre-allocate array for accumulated flux arriving across the web width
    total_flux = np.zeros_like(x_sub)
    
    # Emission profile normalization factor along target length based on profile bias
    for y_t in y_tgt:
        # Normalized relative distance from target element center
        norm_pos = (y_t - skew) / (length / 2)
        
        if bias >= 0:
            flux_weight = 1.0 + bias * (norm_pos ** 2)
        else:
            flux_weight = 1.0 + abs(bias) * (1.0 - (norm_pos ** 2))
            
        # Distance calculation matrix from target element to substrate cross-web plane
        # Assumes inline movement automatically integrates out variations along the translation axis
        r = np.sqrt(x_sub**2 + y_t**2 + distance**2)
        cos_theta = distance / r
        
        # Sputtered Flux distribution model proportional to cos^n(theta) / r^2
        elemental_flux = flux_weight * (cos_theta ** exponent) / (r ** 2)
        total_flux += elemental_flux * dy
        
    # Scale profile matching translation speed dynamics
    return total_flux * base_rate * (1000.0 / sub_speed)

# Calculate individual flux components
flux_c1 = calculate_cathode_flux(c1_bias, c1_skew, tgt_length, h_dist, n_exponent, base_yield * 4500)
flux_c2 = calculate_cathode_flux(c2_bias, c2_skew, tgt_length, h_dist, n_exponent, base_yield * 4500)
combined_flux = flux_c1 + flux_c2

# Calculate industrial peak-to-peak uniformity percentage metric
max_f = np.max(combined_flux)
min_f = np.min(combined_flux)
mean_f = np.mean(combined_flux)
uniformity_pct = ((max_f - min_f) / (max_f + min_f)) * 100.0

# ----------------------------------------------------------------
# Main Dashboard UI Layout & Visual Presentation
# ----------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Peak Thickness", f"{max_f:.2f} nm")
with col2:
    st.metric("Mean Thickness", f"{mean_f:.2f} nm")
with col3:
    st.metric("Total Cross-Web Variation", f"± {uniformity_pct:.2f} %")
with col4:
    if uniformity_pct <= 1.0:
        st.success("TARGET ACHIEVED: Sub-1% Run")
    elif uniformity_pct <= 3.0:
        st.warning("ACCEPTABLE: Within Standard Industrial Spec")
    else:
        st.error("OUT OF SPEC: Uniformity Requires Optimization")

st.markdown("---")

# Setup Matplotlib Plots
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
plt.style.use('dark_background')
fig.patch.set_facecolor('#0e1117')
ax1.set_facecolor('#0e1117')
ax2.set_facecolor('#0e1117')

# Left Plot: Individual Sputter Sources Uniformity Profiles
ax1.plot(x_sub, flux_c1, 'cyan', linestyle='--', label='Cathode 1 Profile')
ax1.plot(x_sub, flux_c2, 'magenta', linestyle='--', label='Cathode 2 Profile')
ax1.set_xlabel('Cross-Web Position on Substrate (mm)', color='white')
ax1.set_ylabel('Deposition Rate / Total Thickness (nm)', color='white')
ax1.set_title('Individual Cathode Flux Emission Signatures', color='white')
ax1.grid(True, color='#444444', linestyle=':')
ax1.legend()

# Right Plot: Cumulative Thickness Map Profile Across Web
ax2.plot(x_sub, combined_flux, '#00ff00', linewidth=2.5, label='Combined Net Distribution')
ax2.axhline(mean_f, color='orange', linestyle=':', label='Mean Net Value')
ax2.fill_between(x_sub, min_f, max_f, color='green', alpha=0.15, label='Peak-to-Peak Window')
ax2.set_xlabel('Cross-Web Position on Substrate (mm)', color='white')
ax2.set_ylabel('Total Accumulated Coating Profile (nm)', color='white')
ax2.set_title('Net Combined Layer Uniformity Profile Across Web', color='white')
ax2.grid(True, color='#444444', linestyle=':')
ax2.legend()

st.pyplot(fig)

# ----------------------------------------------------------------
# Technical Documentation Section
# ----------------------------------------------------------------
with st.expander("Review Simulation Engine Core Physics Equations"):
    st.markdown("""
    This solver calculates the cross-web thickness profile across a translating substrate vector. 
    The mathematical model treats the cylindrical magnetron target as a linear compilation of individual point emission sources, calculating the localized differential thickness contribution via:
    """)
    st.code("dI = (Flux_Weight * cos^n(theta)) / R^2", language="python")
    st.markdown("""
    * **Profile Bias Adjustment:** Manipulates magnet pack erosion assumptions. Edge heavy distributions prioritize the outer integration coordinates, while center heavy distributions scale down outer boundaries.
    * **Uniformity Performance Metric:** Calculated utilizing the standard peak-to-peak semiconductor metric formula: `((Max - Min) / (Max + Min)) * 100`.
    """)
