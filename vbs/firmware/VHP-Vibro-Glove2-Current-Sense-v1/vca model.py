import numpy as np
import matplotlib.pyplot as plt

# Time parameters
fs = 100_000                # Sample rate (Hz)
T = 0.1                     # Total time: 100 ms (4 cycles of 40Hz)
t = np.linspace(0, T, int(fs * T))
dt = t[1] - t[0]

# Voltage amplitude
V_amp = 2.4  # Peak voltage from user's plot

# Voltage input: 40Hz sine wave (Unipolar 0 to V_amp)
# This matches the single-ended PWM drive seen in the firmware plot
freq = 40 # Hz
V_in = (V_amp / 2) + (V_amp / 2) * np.sin(2 * np.pi * freq * t)

# Voice coil parameters
R = 6.5                    # Ohms
L = 0.35e-3                # Henries
BL = 1.1                   # N/A·m (force constant)
k = 2083                   # N/m (spring)
c = 0.028                  # Ns/m (damping)

# Mass scenarios (kg)
masses = {
    "Unloaded (5g)": 0.005,
    "Loaded (100g)": 0.100,
    "Blocked (no motion)": 1e9 # Effectively infinite
}

# Store results
results = {}

def simulate(mass):
    I = np.zeros_like(t)
    v = np.zeros_like(t) # Velocity
    x = np.zeros_like(t) # Position
    emf = np.zeros_like(t) # Back EMF

    for i in range(1, len(t)):
        # Calculate current
        # V_in = I*R + L*dI/dt + V_emf
        # dI/dt = (V_in - I*R - V_emf) / L
        # V_emf = BL * v
        
        emf[i] = BL * v[i-1] # Use previous velocity for EMF approx
        
        dI_dt = (V_in[i] - I[i-1]*R - emf[i]) / L
        I[i] = I[i-1] + dI_dt * dt
        
        # Calculate mechanical motion
        if mass > 1e6: # Blocked
            v[i] = 0
            x[i] = 0
        else:
            # F = m*a
            # F_mag = BL * I
            # F_spring = k * x
            # F_damping = c * v
            # a = (F_mag - F_spring - F_damping) / m
            
            F_mag = BL * I[i]
            a = (F_mag - k*x[i-1] - c*v[i-1]) / mass
            v[i] = v[i-1] + a * dt
            x[i] = x[i-1] + v[i] * dt

    return I, x, emf

# Run simulations
for label, m in masses.items():
    I_res, x_res, emf_res = simulate(m)
    results[label] = {"I": I_res, "x": x_res, "emf": emf_res}

# Plot input voltage
plt.figure(figsize=(10, 2))
plt.plot(t * 1000, V_in, color='orange')
plt.title(f"Input Voltage ({freq} Hz Sine, 0-{V_amp}V)")
plt.xlabel("Time (ms)")
plt.ylabel("Voltage (V)")
plt.grid(True)
plt.tight_layout()
plt.savefig("model_voltage.png")
# plt.show()

# Plot current
plt.figure(figsize=(10, 3))
for label, res in results.items():
    plt.plot(t * 1000, res["I"] * 1e3, label=label)
plt.title("Current Response")
plt.xlabel("Time (ms)")
plt.ylabel("Current (mA)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("model_current.png")
# plt.show()

# Plot  
plt.figure(figsize=(10, 3))
for label, res in results.items():
    plt.plot(t * 1000, res["x"] * 1e3, label=label)
plt.title("Coil Displacement")
plt.xlabel("Time (ms)")
plt.ylabel("Displacement (mm)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.savefig("model_displacement.png")
# plt.show()

# Plot back-EMF
plt.figure(figsize=(10, 3))
for label, res in results.items():
    plt.plot(t * 1000, res["emf"], label=label)
plt.title("Back-EMF Generated")
plt.xlabel("Time (ms)")
plt.savefig("model_backemf.png")
# plt.show()
plt.ylabel("EMF (V)")
plt.grid(True)
plt.legend()
plt.tight_layout()
plt.show()