"""
safety_override.py
------------------
Safety override sub-system for the Natural Soil Radon EMF signal-tractor.

The dual poles monitor radon-ion flux in real time.  If radon concentration
climbs above safe thresholds the override fires a heavy, non-ionising
(pure-magnetic) pulse that reverses the polarity of the radon ions mid-flight,
shoving them back into deeper soil horizons or locking them in place where they
harmlessly decay into stable daughters.

Think of it as a force-field umbrella: the stronger non-ionising signal acts as
an invisible lid that deflects excess radon atoms downward.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Thresholds (Bq/m³)
# ---------------------------------------------------------------------------

# EU action level for indoor radon (reference baseline)
RADON_SAFE_BQ_M3: float = 100.0
# Warning: radon migration has begun, prepare override pulse
RADON_WARNING_BQ_M3: float = 200.0
# Critical: immediate reversal pulse required
RADON_CRITICAL_BQ_M3: float = 400.0

# Non-ionising reversal pulse strength (normalised 0-1)
REVERSAL_PULSE_STRENGTH: float = 0.85

# Depth (m) below which reversed radon is considered safely sequestered
SAFE_SEQUESTRATION_DEPTH_M: float = 3.0


# ---------------------------------------------------------------------------
# Enumerations & data classes
# ---------------------------------------------------------------------------

class RadonLevel(Enum):
    """Radon activity classification."""
    SAFE = auto()
    WARNING = auto()
    CRITICAL = auto()


@dataclass
class OverrideAction:
    """Result of a single safety-override evaluation."""
    radon_level: RadonLevel
    measured_bq_m3: float
    pulse_fired: bool
    pulse_strength: float          # 0 if no pulse fired
    projected_new_depth_m: float   # estimated sequestration depth after pulse
    ions_reversed: bool

    def __repr__(self) -> str:
        action = "PULSE_FIRED" if self.pulse_fired else "NO_ACTION"
        return (
            f"OverrideAction({action}, level={self.radon_level.name}, "
            f"measured={self.measured_bq_m3:.1f} Bq/m³, "
            f"new_depth={self.projected_new_depth_m:.2f} m)"
        )


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class SafetyOverride:
    """
    Real-time radon safety monitor and polarity-reversal actuator.

    The poles continuously report ion-flux readings.  This class evaluates
    each reading and, when thresholds are exceeded, calculates the correct
    reversal pulse and returns the action taken.

    Parameters
    ----------
    baseline_depth_m :
        Current depth of the radon source / pore layer (metres below surface).
    """

    def __init__(self, baseline_depth_m: float = 1.5) -> None:
        if baseline_depth_m <= 0:
            raise ValueError("baseline_depth_m must be positive.")
        self.baseline_depth_m = baseline_depth_m
        self._override_count: int = 0
        self._last_action: Optional[OverrideAction] = None

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify(measured_bq_m3: float) -> RadonLevel:
        """Return the :class:`RadonLevel` for a measured activity value."""
        if measured_bq_m3 < RADON_WARNING_BQ_M3:
            return RadonLevel.SAFE
        if measured_bq_m3 < RADON_CRITICAL_BQ_M3:
            return RadonLevel.WARNING
        return RadonLevel.CRITICAL

    # ------------------------------------------------------------------
    # Reversal-pulse calculation
    # ------------------------------------------------------------------

    def _reversal_depth(self, measured_bq_m3: float) -> float:
        """
        Estimate the post-reversal sequestration depth.

        Higher activity → stronger pulse → deeper re-sequestration.
        The model uses a logarithmic response to avoid unrealistically large
        depths for extreme inputs.
        """
        excess = max(0.0, measured_bq_m3 - RADON_SAFE_BQ_M3)
        push_depth = SAFE_SEQUESTRATION_DEPTH_M * (
            1.0 + 0.5 * math.log1p(excess / RADON_SAFE_BQ_M3)
        )
        return self.baseline_depth_m + push_depth

    # ------------------------------------------------------------------
    # Main evaluation entry point
    # ------------------------------------------------------------------

    def evaluate(self, measured_bq_m3: float) -> OverrideAction:
        """
        Evaluate one real-time radon measurement and decide whether to fire
        a reversal pulse.

        Parameters
        ----------
        measured_bq_m3 :
            Live radon activity reading from the ion-feedback sensors (Bq/m³).

        Returns
        -------
        OverrideAction
            A record describing what action (if any) was taken.
        """
        if measured_bq_m3 < 0:
            raise ValueError("measured_bq_m3 must be non-negative.")

        level = self.classify(measured_bq_m3)
        pulse_fired = level in (RadonLevel.WARNING, RadonLevel.CRITICAL)

        if pulse_fired:
            self._override_count += 1
            # Critical level gets full-strength pulse; warning gets a partial
            # pulse scaled by how far above the warning threshold we are.
            if level is RadonLevel.CRITICAL:
                strength = REVERSAL_PULSE_STRENGTH
            else:
                fraction = (measured_bq_m3 - RADON_WARNING_BQ_M3) / (
                    RADON_CRITICAL_BQ_M3 - RADON_WARNING_BQ_M3
                )
                strength = REVERSAL_PULSE_STRENGTH * 0.5 * (1.0 + fraction)
            new_depth = self._reversal_depth(measured_bq_m3)
            ions_reversed = True
        else:
            strength = 0.0
            new_depth = self.baseline_depth_m
            ions_reversed = False

        action = OverrideAction(
            radon_level=level,
            measured_bq_m3=measured_bq_m3,
            pulse_fired=pulse_fired,
            pulse_strength=strength,
            projected_new_depth_m=new_depth,
            ions_reversed=ions_reversed,
        )
        self._last_action = action
        return action

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def override_count(self) -> int:
        """Number of reversal pulses fired so far."""
        return self._override_count

    @property
    def last_action(self) -> Optional[OverrideAction]:
        """Most recent :class:`OverrideAction` (or None if never evaluated)."""
        return self._last_action

    def __repr__(self) -> str:
        return (
            f"SafetyOverride(baseline={self.baseline_depth_m} m, "
            f"overrides_fired={self._override_count})"
        )
