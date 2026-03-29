"""
trepel_resonance.py
-------------------
Trepel-resonance engine — the repel + propel feedback loop at the heart of
the Natural Soil Radon EMF signal-tractor system.

Each pulse from the paired poles strengthens the next, creating a standing
electromagnetic wave between them.  The wave levitates the soil sheet upward
without physical hardware contact by tuning the para/diamagnetic properties of
the ionised pore-water and metallic fractions in the liquefied layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Damping coefficient (dimensionless) — soil absorbs a fraction of each pulse
SOIL_DAMPING: float = 0.08

# Amplification factor per iteration when poles are phase-locked
PHASE_LOCK_GAIN: float = 1.15

# Standing-wave node spacing in the soil column (metres)
NODE_SPACING_M: float = 0.12

# Minimum field amplitude (normalised) required for levitation onset
LEVITATION_THRESHOLD: float = 0.65

# Maximum safe standing-wave amplitude before soil disruption risk
MAX_SAFE_AMPLITUDE: float = 2.5


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class StandingWaveSnapshot:
    """State of the trepel-resonance standing wave at one iteration."""
    iteration: int
    amplitude: float          # normalised field amplitude (unitless)
    node_count: int           # number of nodes in soil column
    levitation_force_n: float # estimated upward force per m² (Newtons)
    is_levitating: bool       # True once amplitude ≥ LEVITATION_THRESHOLD
    is_saturated: bool        # True if amplitude ≥ MAX_SAFE_AMPLITUDE

    def __repr__(self) -> str:
        state = "LEVITATING" if self.is_levitating else "BUILDING"
        if self.is_saturated:
            state = "SATURATED"
        return (
            f"StandingWaveSnapshot(iter={self.iteration}, "
            f"amp={self.amplitude:.4f}, nodes={self.node_count}, "
            f"lift={self.levitation_force_n:.2f} N/m², state={state})"
        )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TrepelResonance:
    """
    Simulates the trepel-resonance feedback loop between the two signal poles.

    The loop works as follows:
    1. The PRIMARY pole emits a *repel* pulse that pushes ionised soil
       particles upward.
    2. The SECONDARY pole detects the rising particle cloud and fires a
       *propel* pulse that amplifies and redirects the upward momentum.
    3. Each cycle the combined field amplitude grows (PHASE_LOCK_GAIN) minus
       soil damping (SOIL_DAMPING), creating an exponentially growing but
       self-stabilising standing wave.

    Parameters
    ----------
    soil_column_m :
        Height (metres) of the soil column between underground and aboveground
        poles.
    initial_amplitude :
        Starting normalised field amplitude (default 0.05 — tiny seed signal).
    soil_density_kg_m3 :
        Bulk density of the target soil layer (kg/m³).  Affects levitation
        force calculation.
    """

    def __init__(
        self,
        soil_column_m: float,
        initial_amplitude: float = 0.05,
        soil_density_kg_m3: float = 1_400.0,
    ) -> None:
        if soil_column_m <= 0:
            raise ValueError("soil_column_m must be positive.")
        if initial_amplitude <= 0:
            raise ValueError("initial_amplitude must be positive.")

        self.soil_column_m = soil_column_m
        self.soil_density_kg_m3 = soil_density_kg_m3

        self._amplitude = initial_amplitude
        self._history: list[StandingWaveSnapshot] = []
        self._iteration = 0

    # ------------------------------------------------------------------
    # Core iteration
    # ------------------------------------------------------------------

    def _node_count(self) -> int:
        """Number of standing-wave nodes currently present in the soil column."""
        wavelength = NODE_SPACING_M / max(self._amplitude, 1e-6)
        return max(1, int(self.soil_column_m / wavelength))

    def _levitation_force(self) -> float:
        """
        Estimate upward force per m² on the soil sheet.

        Uses a simplified magneto-mechanical model:
            F = ρ · g · A²  (N/m²)
        where ρ is bulk density, g is gravity, and A is normalised amplitude.
        The formula captures the key dependency: force scales with the square
        of field amplitude.
        """
        g = 9.81  # m/s²
        return self.soil_density_kg_m3 * g * (self._amplitude ** 2)

    def step(self) -> StandingWaveSnapshot:
        """
        Advance the trepel-resonance loop by one repel-propel cycle.

        Returns
        -------
        StandingWaveSnapshot
            State after this iteration.
        """
        self._iteration += 1

        # Repel pulse from underground PRIMARY: adds amplitude proportional
        # to existing field (positive feedback) minus damping.
        repel_delta = self._amplitude * (PHASE_LOCK_GAIN - 1.0)
        damp_loss = self._amplitude * SOIL_DAMPING

        # Propel pulse from aboveground SECONDARY: constructive interference
        # adds a phase-aligned boost once the standing wave is established.
        if self._amplitude >= 0.1:
            propel_boost = 0.05 * math.sin(math.pi * self._iteration / 4)
        else:
            propel_boost = 0.0

        self._amplitude += repel_delta - damp_loss + propel_boost

        # Hard cap — the safety_override module is responsible for clamping
        # anything that exceeds MAX_SAFE_AMPLITUDE; here we track saturation.
        saturated = self._amplitude >= MAX_SAFE_AMPLITUDE

        snap = StandingWaveSnapshot(
            iteration=self._iteration,
            amplitude=self._amplitude,
            node_count=self._node_count(),
            levitation_force_n=self._levitation_force(),
            is_levitating=(self._amplitude >= LEVITATION_THRESHOLD),
            is_saturated=saturated,
        )
        self._history.append(snap)
        return snap

    def run(self, iterations: int) -> list[StandingWaveSnapshot]:
        """
        Run the trepel-resonance loop for *iterations* cycles.

        Stops early if the standing wave saturates (amplitude ≥
        MAX_SAFE_AMPLITUDE) to avoid simulating physically unrealistic states
        beyond that point.

        Returns
        -------
        list[StandingWaveSnapshot]
            Snapshot after each iteration (up to *iterations* or saturation).
        """
        snapshots: list[StandingWaveSnapshot] = []
        for _ in range(iterations):
            snap = self.step()
            snapshots.append(snap)
            if snap.is_saturated:
                break
        return snapshots

    def reset(self, initial_amplitude: float = 0.05) -> None:
        """Reset the standing wave to a new seed amplitude."""
        if initial_amplitude <= 0:
            raise ValueError("initial_amplitude must be positive.")
        self._amplitude = initial_amplitude
        self._iteration = 0
        self._history.clear()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def amplitude(self) -> float:
        """Current normalised standing-wave amplitude."""
        return self._amplitude

    @property
    def is_levitating(self) -> bool:
        """True once amplitude has crossed the levitation threshold."""
        return self._amplitude >= LEVITATION_THRESHOLD

    @property
    def history(self) -> list[StandingWaveSnapshot]:
        """Full iteration history (read-only copy)."""
        return list(self._history)

    def __repr__(self) -> str:
        return (
            f"TrepelResonance(column={self.soil_column_m} m, "
            f"amp={self._amplitude:.4f}, iter={self._iteration})"
        )
