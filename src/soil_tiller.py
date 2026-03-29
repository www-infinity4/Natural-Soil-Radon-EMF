"""
soil_tiller.py
--------------
Top-level controller for the Natural Soil Radon EMF signal-tractor system.

Orchestrates the full tilling sequence:
    1. Deploy and anchor the underground PRIMARY spike (DroneAnchor).
    2. Select the best available ground gas (GasFallback).
    3. Synchronise the dual-pole beacon (RadonBeacon).
    4. Run the trepel-resonance standing wave until the soil sheet levitates
       (TrepelResonance).
    5. Monitor radon in real time and fire safety overrides if needed
       (SafetyOverride).
    6. Retract the spike at end of session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from .drone_anchor import AnchorState, DroneAnchor
from .gas_fallback import GasFallback, GroundGas, SoilGasReading
from .radon_beacon import PoleRole, RadonBeacon, SyncState
from .safety_override import OverrideAction, SafetyOverride
from .trepel_resonance import StandingWaveSnapshot, TrepelResonance


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TillerPhase(Enum):
    """High-level operational phase of the soil tiller."""
    IDLE = auto()
    ANCHORING = auto()
    GAS_SELECTION = auto()
    BEACON_SYNC = auto()
    TREPEL_RESONANCE = auto()
    TILLING = auto()
    SAFETY_HOLD = auto()
    RETRACTING = auto()
    COMPLETE = auto()
    FAULT = auto()


# ---------------------------------------------------------------------------
# Session report
# ---------------------------------------------------------------------------

@dataclass
class TillingSession:
    """Summary of one complete tilling session."""
    phase_log: list[TillerPhase] = field(default_factory=list)
    selected_gas: GroundGas = GroundGas.NONE
    sync_state: Optional[SyncState] = None
    resonance_snapshots: list[StandingWaveSnapshot] = field(default_factory=list)
    override_actions: list[OverrideAction] = field(default_factory=list)
    levitation_achieved: bool = False
    fault_reason: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """True if the session completed without fault."""
        return self.levitation_achieved and self.fault_reason is None

    def __repr__(self) -> str:
        status = "SUCCESS" if self.succeeded else "FAULT"
        return (
            f"TillingSession({status}, gas={self.selected_gas.name}, "
            f"levitated={self.levitation_achieved}, "
            f"overrides={len(self.override_actions)})"
        )


# ---------------------------------------------------------------------------
# Main controller
# ---------------------------------------------------------------------------

class SoilTiller:
    """
    Top-level controller that wires all subsystems together and runs the
    complete soil-tilling sequence.

    Parameters
    ----------
    anchor_depth_m :
        Target depth for the underground PRIMARY spike (metres).
    soil_column_m :
        Distance from the underground spike to the aboveground SECONDARY pole
        (metres).  This is the active resonance zone.
    gas_reading :
        Initial subsurface gas concentrations used to select the bootstrap gas.
    radon_monitor_readings :
        Sequence of live radon readings (Bq/m³) fed into the safety monitor
        during the tilling phase.  In a real deployment these come from the
        ion-feedback sensors.
    soil_resistance :
        Dimensionless soil resistance factor passed to DroneAnchor.
    max_resonance_iterations :
        Maximum trepel-resonance cycles before declaring a fault.
    """

    def __init__(
        self,
        anchor_depth_m: float = 1.5,
        soil_column_m: float = 3.0,
        gas_reading: Optional[SoilGasReading] = None,
        radon_monitor_readings: Optional[list[float]] = None,
        soil_resistance: float = 1.0,
        max_resonance_iterations: int = 40,
    ) -> None:
        self.anchor_depth_m = anchor_depth_m
        self.soil_column_m = soil_column_m
        self.gas_reading = gas_reading or SoilGasReading(radon_bq_m3=40.0)
        self.radon_monitor_readings = radon_monitor_readings or []
        self.soil_resistance = soil_resistance
        self.max_resonance_iterations = max_resonance_iterations

        # Sub-systems (lazily constructed during run())
        self._anchor: Optional[DroneAnchor] = None
        self._primary: Optional[RadonBeacon] = None
        self._secondary: Optional[RadonBeacon] = None
        self._resonance: Optional[TrepelResonance] = None
        self._safety: Optional[SafetyOverride] = None
        self._gas_selector = GasFallback()

        self._phase = TillerPhase.IDLE
        self._session: Optional[TillingSession] = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self) -> TillingSession:
        """
        Execute the complete tilling sequence and return a session summary.

        The sequence is:
            IDLE → ANCHORING → GAS_SELECTION → BEACON_SYNC
            → TREPEL_RESONANCE → TILLING → RETRACTING → COMPLETE
        """
        session = TillingSession()
        self._session = session

        try:
            self._phase_anchoring(session)
            self._phase_gas_selection(session)
            self._phase_beacon_sync(session)
            self._phase_trepel_resonance(session)
            self._phase_tilling(session)
            self._phase_retracting(session)
            self._transition(TillerPhase.COMPLETE, session)
        except _TillerFault as exc:
            self._transition(TillerPhase.FAULT, session)
            session.fault_reason = str(exc)

        return session

    # ------------------------------------------------------------------
    # Phase implementations
    # ------------------------------------------------------------------

    def _phase_anchoring(self, session: TillingSession) -> None:
        self._transition(TillerPhase.ANCHORING, session)
        self._anchor = DroneAnchor(
            target_depth_m=self.anchor_depth_m,
            soil_resistance=self.soil_resistance,
        )
        self._anchor.deploy()
        self._anchor.burrow_to_target()
        if self._anchor.state is not AnchorState.ANCHORED:
            raise _TillerFault("Spike failed to reach target depth.")

    def _phase_gas_selection(self, session: TillingSession) -> None:
        self._transition(TillerPhase.GAS_SELECTION, session)
        result = self._gas_selector.select(self.gas_reading)
        session.selected_gas = result.selected_gas
        if not result.is_usable:
            raise _TillerFault(
                "No ionisable ground gas detected. "
                "Cannot bootstrap trepel-resonance."
            )

    def _phase_beacon_sync(self, session: TillingSession) -> None:
        self._transition(TillerPhase.BEACON_SYNC, session)
        radon_conc = self.gas_reading.radon_bq_m3

        # When radon is below the minimum usable level a fallback gas drives
        # ionisation.  The beacon poles still "talk" the same way — the
        # selected gas's ionisation yield is used to compute an effective
        # radon-equivalent concentration so the sync threshold can be reached.
        if radon_conc < 20.0:
            fallback = self._gas_selector.last_selection()
            if fallback is not None and fallback.is_usable:
                radon_conc = max(radon_conc, 100.0 * fallback.ionisation_yield)

        self._primary = RadonBeacon(
            role=PoleRole.PRIMARY,
            depth_m=-self.anchor_depth_m,
            radon_concentration_bq_m3=radon_conc,
        )
        self._secondary = RadonBeacon(
            role=PoleRole.SECONDARY,
            depth_m=self.soil_column_m,
            radon_concentration_bq_m3=radon_conc,
        )
        self._primary.pair_with(self._secondary)
        sync = self._primary.synchronise()
        session.sync_state = sync

        if not sync.is_synced:
            raise _TillerFault(
                f"Beacon synchronisation failed "
                f"(signal strength {sync.signal_strength:.3f} < threshold)."
            )

    def _phase_trepel_resonance(self, session: TillingSession) -> None:
        self._transition(TillerPhase.TREPEL_RESONANCE, session)
        self._resonance = TrepelResonance(soil_column_m=self.soil_column_m)
        snaps = self._resonance.run(self.max_resonance_iterations)
        session.resonance_snapshots = snaps
        if not self._resonance.is_levitating:
            raise _TillerFault(
                "Trepel-resonance did not reach levitation threshold within "
                f"{self.max_resonance_iterations} iterations."
            )
        session.levitation_achieved = True

    def _phase_tilling(self, session: TillingSession) -> None:
        self._transition(TillerPhase.TILLING, session)
        self._safety = SafetyOverride(baseline_depth_m=self.anchor_depth_m)

        for reading_bq in self.radon_monitor_readings:
            action = self._safety.evaluate(reading_bq)
            session.override_actions.append(action)
            if action.pulse_fired:
                # Briefly transition to SAFETY_HOLD to record the event
                self._transition(TillerPhase.SAFETY_HOLD, session)
                self._transition(TillerPhase.TILLING, session)

    def _phase_retracting(self, session: TillingSession) -> None:
        self._transition(TillerPhase.RETRACTING, session)
        if self._anchor and self._anchor.state is AnchorState.ANCHORED:
            self._anchor.retract()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _transition(self, phase: TillerPhase, session: TillingSession) -> None:
        self._phase = phase
        session.phase_log.append(phase)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def phase(self) -> TillerPhase:
        """Current operational phase."""
        return self._phase

    @property
    def session(self) -> Optional[TillingSession]:
        """Most recent session summary (or None before first run)."""
        return self._session

    def __repr__(self) -> str:
        return (
            f"SoilTiller(depth={self.anchor_depth_m} m, "
            f"column={self.soil_column_m} m, phase={self._phase.name})"
        )


# ---------------------------------------------------------------------------
# Internal exception
# ---------------------------------------------------------------------------

class _TillerFault(Exception):
    """Raised internally when a phase cannot proceed."""
