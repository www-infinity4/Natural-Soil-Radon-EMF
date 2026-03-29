"""
drone_anchor.py
---------------
Drone-deployed self-anchoring spike system for the Natural Soil Radon EMF
signal-tractor.

The underground PRIMARY pole must be physically positioned in the soil column
before the beacon handshake can begin.  This module models the drop-and-burrow
sequence:

    1. DEPLOYED  — drone hovers over target coordinates and releases the spike.
    2. BURROWING — the spike's helical tip spins under electromagnetic torque,
                   driving it into the soil to the target depth.
    3. ANCHORED  — spike is locked at depth; beacon pairing can proceed.
    4. RETRACTING — end-of-session retrieval: reversed torque extracts the spike.

The aboveground SECONDARY pole is drone-mounted and does not need anchoring;
it hovers or is attached to a drone frame above the field.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Torque applied per burrowing step (N·m)
BURROW_TORQUE_NM: float = 12.5
# Helical pitch of the spike tip (metres per revolution)
HELIX_PITCH_M: float = 0.04
# Number of revolutions per burrowing step
REVOLUTIONS_PER_STEP: int = 5
# Soil resistance factor — harder soils require more steps per metre
SOIL_RESISTANCE: float = 1.0  # dimensionless; scale up for clay, down for sand
# Energy consumed per burrowing step (Joules) — drawn from trepel-resonance
ENERGY_PER_STEP_J: float = 8.0


# ---------------------------------------------------------------------------
# Enumerations & data classes
# ---------------------------------------------------------------------------

class AnchorState(Enum):
    """Lifecycle states of the drone-deployed spike."""
    READY = auto()         # manufactured / pre-drop
    DEPLOYED = auto()      # released from drone, falling to soil surface
    BURROWING = auto()     # helical tip driving downward
    ANCHORED = auto()      # locked at target depth
    RETRACTING = auto()    # being retrieved at end of session
    RETRIEVED = auto()     # above ground; ready for reuse


@dataclass
class BurrowStep:
    """One step in the burrowing sequence."""
    step_number: int
    depth_m: float         # cumulative depth after this step
    revolutions: int       # cumulative revolutions
    energy_used_j: float   # cumulative energy consumed
    state: AnchorState

    def __repr__(self) -> str:
        return (
            f"BurrowStep(step={self.step_number}, depth={self.depth_m:.3f} m, "
            f"rev={self.revolutions}, energy={self.energy_used_j:.1f} J, "
            f"state={self.state.name})"
        )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class DroneAnchor:
    """
    Manages the full lifecycle of a drone-deployed self-anchoring spike.

    Parameters
    ----------
    target_depth_m :
        Desired anchoring depth in metres (positive = below surface).
    soil_resistance :
        Dimensionless soil resistance factor.  1.0 = typical loam;
        >1 = clay-heavy; <1 = sandy/loose.
    """

    def __init__(
        self,
        target_depth_m: float,
        soil_resistance: float = SOIL_RESISTANCE,
    ) -> None:
        if target_depth_m <= 0:
            raise ValueError("target_depth_m must be positive.")
        if soil_resistance <= 0:
            raise ValueError("soil_resistance must be positive.")

        self.target_depth_m = target_depth_m
        self.soil_resistance = soil_resistance

        self._state = AnchorState.READY
        self._current_depth_m: float = 0.0
        self._total_revolutions: int = 0
        self._total_energy_j: float = 0.0
        self._burrow_log: list[BurrowStep] = []
        self._step_counter: int = 0

    # ------------------------------------------------------------------
    # State machine transitions
    # ------------------------------------------------------------------

    def deploy(self) -> None:
        """Release the spike from the drone onto the soil surface."""
        if self._state is not AnchorState.READY:
            raise RuntimeError(
                f"Cannot deploy from state {self._state.name}. "
                "Spike must be READY."
            )
        self._state = AnchorState.DEPLOYED
        self._current_depth_m = 0.0

    def start_burrowing(self) -> None:
        """Engage helical tip motor to begin downward penetration."""
        if self._state is not AnchorState.DEPLOYED:
            raise RuntimeError(
                f"Cannot start burrowing from state {self._state.name}. "
                "Spike must be DEPLOYED."
            )
        self._state = AnchorState.BURROWING

    # ------------------------------------------------------------------
    # Burrowing mechanics
    # ------------------------------------------------------------------

    def _depth_per_step(self) -> float:
        """Depth gained per burrowing step (metres)."""
        return (HELIX_PITCH_M * REVOLUTIONS_PER_STEP) / self.soil_resistance

    def burrow_step(self) -> BurrowStep:
        """
        Execute one burrowing step: spin the helical tip and advance depth.

        Returns
        -------
        BurrowStep
            Description of this step.
        """
        if self._state is not AnchorState.BURROWING:
            raise RuntimeError(
                f"Cannot burrow from state {self._state.name}. "
                "Call start_burrowing() first."
            )

        self._step_counter += 1
        self._current_depth_m += self._depth_per_step()
        self._total_revolutions += REVOLUTIONS_PER_STEP
        self._total_energy_j += ENERGY_PER_STEP_J

        # Clamp depth to target
        if self._current_depth_m >= self.target_depth_m:
            self._current_depth_m = self.target_depth_m
            self._state = AnchorState.ANCHORED

        step = BurrowStep(
            step_number=self._step_counter,
            depth_m=self._current_depth_m,
            revolutions=self._total_revolutions,
            energy_used_j=self._total_energy_j,
            state=self._state,
        )
        self._burrow_log.append(step)
        return step

    def burrow_to_target(self) -> list[BurrowStep]:
        """
        Continuously execute burrowing steps until the target depth is reached.

        Convenience method that runs :meth:`burrow_step` in a loop.
        Returns all steps taken.
        """
        if self._state is AnchorState.DEPLOYED:
            self.start_burrowing()
        steps: list[BurrowStep] = []
        while self._state is AnchorState.BURROWING:
            steps.append(self.burrow_step())
        return steps

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retract(self) -> int:
        """
        Reverse the helical motor and extract the spike from the soil.

        Returns the number of reverse-steps required (same as the forward
        count, assuming symmetric soil resistance).
        """
        if self._state is not AnchorState.ANCHORED:
            raise RuntimeError(
                f"Cannot retract from state {self._state.name}. "
                "Spike must be ANCHORED."
            )
        self._state = AnchorState.RETRACTING
        steps_needed = self._step_counter
        self._current_depth_m = 0.0
        self._state = AnchorState.RETRIEVED
        return steps_needed

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def state(self) -> AnchorState:
        """Current lifecycle state of the spike."""
        return self._state

    @property
    def current_depth_m(self) -> float:
        """Current penetration depth (metres below surface)."""
        return self._current_depth_m

    @property
    def total_energy_j(self) -> float:
        """Total electromagnetic energy consumed for burrowing (Joules)."""
        return self._total_energy_j

    @property
    def burrow_log(self) -> list[BurrowStep]:
        """Full burrowing step log (read-only copy)."""
        return list(self._burrow_log)

    def steps_to_target(self) -> int:
        """Estimate how many burrowing steps are needed to reach target depth."""
        remaining = max(0.0, self.target_depth_m - self._current_depth_m)
        return math.ceil(remaining / self._depth_per_step())

    def __repr__(self) -> str:
        return (
            f"DroneAnchor(target={self.target_depth_m} m, "
            f"current={self._current_depth_m:.3f} m, "
            f"state={self._state.name})"
        )
