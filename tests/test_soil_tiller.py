"""Tests for src/soil_tiller.py — the top-level controller."""

import pytest

from src.gas_fallback import SoilGasReading
from src.soil_tiller import SoilTiller, TillerPhase, TillingSession


class TestSoilTillerHappyPath:
    """Verify a complete successful tilling session."""

    def setup_method(self):
        self.tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(radon_bq_m3=100.0),
            radon_monitor_readings=[50.0, 80.0, 50.0],  # all safe
        )

    def test_run_returns_session(self):
        session = self.tiller.run()
        assert isinstance(session, TillingSession)

    def test_session_succeeds(self):
        session = self.tiller.run()
        assert session.succeeded

    def test_levitation_achieved(self):
        session = self.tiller.run()
        assert session.levitation_achieved

    def test_selected_gas_is_radon(self):
        session = self.tiller.run()
        from src.gas_fallback import GroundGas
        assert session.selected_gas is GroundGas.RADON

    def test_phase_log_contains_complete(self):
        session = self.tiller.run()
        assert TillerPhase.COMPLETE in session.phase_log

    def test_phase_log_ordered(self):
        session = self.tiller.run()
        log = session.phase_log
        expected_phases = [
            TillerPhase.ANCHORING,
            TillerPhase.GAS_SELECTION,
            TillerPhase.BEACON_SYNC,
            TillerPhase.TREPEL_RESONANCE,
            TillerPhase.TILLING,
            TillerPhase.RETRACTING,
            TillerPhase.COMPLETE,
        ]
        # All expected phases present in order
        it = iter(log)
        for phase in expected_phases:
            assert any(p is phase for p in log), f"{phase} missing from log"

    def test_no_fault(self):
        session = self.tiller.run()
        assert session.fault_reason is None

    def test_sync_state_populated(self):
        session = self.tiller.run()
        assert session.sync_state is not None
        assert session.sync_state.is_synced

    def test_resonance_snapshots_populated(self):
        session = self.tiller.run()
        assert len(session.resonance_snapshots) > 0

    def test_override_actions_for_safe_readings(self):
        session = self.tiller.run()
        # All readings were safe, so no pulses should have fired
        assert all(not a.pulse_fired for a in session.override_actions)

    def test_session_accessible_via_property(self):
        self.tiller.run()
        assert self.tiller.session is not None

    def test_repr(self):
        assert "SoilTiller" in repr(self.tiller)


class TestSoilTillerWithOverride:
    """Verify safety-override path fires during tilling."""

    def test_override_fires_on_critical_reading(self):
        from src.safety_override import RADON_CRITICAL_BQ_M3
        tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(radon_bq_m3=100.0),
            radon_monitor_readings=[RADON_CRITICAL_BQ_M3 + 10.0],
        )
        session = tiller.run()
        assert session.levitation_achieved
        assert any(a.pulse_fired for a in session.override_actions)

    def test_safety_hold_in_phase_log_when_override_fires(self):
        from src.safety_override import RADON_CRITICAL_BQ_M3
        tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(radon_bq_m3=100.0),
            radon_monitor_readings=[RADON_CRITICAL_BQ_M3 + 10.0],
        )
        session = tiller.run()
        assert TillerPhase.SAFETY_HOLD in session.phase_log


class TestSoilTillerFaultPaths:
    """Verify fault handling when sub-systems fail."""

    def test_no_gas_causes_fault(self):
        tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(),  # all zeros
        )
        session = tiller.run()
        assert not session.succeeded
        assert TillerPhase.FAULT in session.phase_log
        assert session.fault_reason is not None

    def test_fault_session_not_levitating(self):
        tiller = SoilTiller(
            gas_reading=SoilGasReading(),  # no gas
        )
        session = tiller.run()
        assert not session.levitation_achieved

    def test_methane_fallback_succeeds(self):
        from src.gas_fallback import GroundGas
        tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(
                radon_bq_m3=0.0,
                methane_ppm=50.0,
            ),
        )
        session = tiller.run()
        assert session.succeeded
        assert session.selected_gas is GroundGas.METHANE

    def test_co2_fallback_succeeds(self):
        from src.gas_fallback import GroundGas
        tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(
                radon_bq_m3=0.0,
                methane_ppm=0.0,
                co2_ppm=2000.0,
            ),
        )
        session = tiller.run()
        assert session.succeeded
        assert session.selected_gas is GroundGas.CO2

    def test_helium_fallback_succeeds(self):
        from src.gas_fallback import GroundGas
        tiller = SoilTiller(
            anchor_depth_m=1.5,
            soil_column_m=3.0,
            gas_reading=SoilGasReading(
                radon_bq_m3=0.0,
                methane_ppm=0.0,
                co2_ppm=0.0,
                helium_ppm=0.05,
            ),
        )
        session = tiller.run()
        assert session.succeeded
        assert session.selected_gas is GroundGas.HELIUM

    def test_session_repr(self):
        tiller = SoilTiller(
            gas_reading=SoilGasReading(radon_bq_m3=100.0),
        )
        session = tiller.run()
        assert "TillingSession" in repr(session)
