# Natural Soil Radon EMF — Signal Tractor System

> Conversion of naturally occurring soil gas into ionised, para/diamagnetic
> states that till the ground via electromagnetic perturbation — no moving
> parts, no fuel burn, zero soil compaction.

---

## Concept

Every agricultural acre already has trace **Rn-222** seeping from uranium
decay in the bedrock and soil matrix.  The Signal Tractor doesn't create
radon; it tunes into it.  A buried underground pole (PRIMARY beacon) excites
existing radon atoms via targeted EM resonance, liberating alpha-particle
energy without letting the gas migrate upward.  That stripped radiation
ionises the pore water and metallic fractions, turning the liquefied layer
into a self-amplifying para/diamagnetic slurry that an overhead pole
(SECONDARY beacon) yanks upward — tilling the soil in perfectly
disturbance-free sheets.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  SoilTiller  (top-level controller)                              │
│                                                                  │
│  1. DroneAnchor   ─── deploy + burrow PRIMARY spike to depth    │
│  2. GasFallback   ─── select best ionisable ground gas          │
│  3. RadonBeacon   ─── synchronise PRIMARY ↔ SECONDARY poles     │
│  4. TrepelResonance ─ grow standing wave until levitation       │
│  5. SafetyOverride ── monitor radon; fire reversal pulse        │
│  6. DroneAnchor   ─── retract spike at end of session           │
└──────────────────────────────────────────────────────────────────┘
```

### Modules

| Module | Responsibility |
|---|---|
| `src/radon_beacon.py` | Beacon + dual-pole sync at Rn-222 alpha energy (~5.5 MeV) |
| `src/trepel_resonance.py` | Trepel-resonance standing-wave feedback loop |
| `src/safety_override.py` | Real-time radon monitoring + polarity-reversal pulse |
| `src/gas_fallback.py` | Auto-switch to CH₄ / CO₂ / He when radon is insufficient |
| `src/drone_anchor.py` | Drone-deployed self-anchoring spike lifecycle |
| `src/soil_tiller.py` | Orchestrates all modules for one complete tilling session |

---

## Key Concepts

### Beacon + Dual-Pole Sync
The underground PRIMARY pole pulses a low-energy carrier wave tuned to
radon's natural decay signature (≈ 5.5 MeV alpha energy).  The aboveground
SECONDARY pole listens and replies on the exact harmonic frequency — so both
poles "talk" and the magnetic flux grows exponentially in the zone between
them.

### Trepel-Resonance
The **repel + propel** feedback loop.  Each pulse from the PRIMARY repels
ionised soil particles upward; the SECONDARY detects the rising cloud and
fires a propel pulse that amplifies the upward momentum.  The resulting
constructive interference creates a standing wave that levitates the soil
sheet without any physical contact.

### Safety Override
If radon starts migrating too high (detected via real-time ion feedback from
the poles), the system fires a heavy non-ionising (pure-magnetic) pulse.
That pulse reverses the radon-ion polarity mid-flight, shoving the charged
particles back into deeper soil horizons where they harmlessly decay into
stable daughters.  Think of it as a **force-field umbrella**.

### Fallback Gases
When local radon is too low the beacon auto-switches to the next most
abundant ground gas — methane pockets, CO₂ from microbial activity, or even
trace helium from alpha decay.  Priority order:

```
Rn-222 (preferred) → CH₄ → CO₂ → He-4
```

### Drone-Deployed Self-Anchoring
The PRIMARY pole is a helical spike released by a drone.  On command it spins
its electromagnetic tip, burrowing into the soil under EM torque.  At
end-of-session the motor reverses and the spike extracts itself for reuse.
The SECONDARY pole is drone-mounted and hovers above the field — no ground
contact needed.

---

## Quick Start

```python
from src.soil_tiller import SoilTiller
from src.gas_fallback import SoilGasReading

tiller = SoilTiller(
    anchor_depth_m=1.5,
    soil_column_m=3.0,
    gas_reading=SoilGasReading(radon_bq_m3=80.0),
    radon_monitor_readings=[50.0, 60.0, 45.0],
)

session = tiller.run()
print(session)
# TillingSession(SUCCESS, gas=RADON, levitated=True, overrides=0)
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

133 tests across all modules.

---

## Project Structure

```
Natural-Soil-Radon-EMF/
├── src/
│   ├── __init__.py
│   ├── radon_beacon.py
│   ├── trepel_resonance.py
│   ├── safety_override.py
│   ├── gas_fallback.py
│   ├── drone_anchor.py
│   └── soil_tiller.py
├── tests/
│   ├── test_radon_beacon.py
│   ├── test_trepel_resonance.py
│   ├── test_safety_override.py
│   ├── test_gas_fallback.py
│   ├── test_drone_anchor.py
│   └── test_soil_tiller.py
└── README.md
```
<script src="https://www-infinity4.github.io/Mint-For-Infinity/infinity-wallet-menu.js" defer></script>
