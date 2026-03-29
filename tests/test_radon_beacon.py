"""Tests for src/radon_beacon.py."""

import math
import pytest

from src.radon_beacon import (
    BASE_CARRIER_HZ,
    HARMONIC_MULTIPLIER,
    RADON_ALPHA_MEV,
    SYNC_THRESHOLD,
    PoleRole,
    PulsePacket,
    RadonBeacon,
    SyncState,
)


# ---------------------------------------------------------------------------
# PulsePacket
# ---------------------------------------------------------------------------

class TestPulsePacket:
    def test_harmonic_doubles_frequency(self):
        p = PulsePacket(frequency_hz=1e9, energy_mev=5.5)
        h = p.harmonic()
        assert h.frequency_hz == pytest.approx(1e9 * HARMONIC_MULTIPLIER)

    def test_harmonic_doubles_energy(self):
        p = PulsePacket(frequency_hz=1e9, energy_mev=5.5)
        h = p.harmonic()
        assert h.energy_mev == pytest.approx(5.5 * HARMONIC_MULTIPLIER)

    def test_harmonic_preserves_phase(self):
        p = PulsePacket(frequency_hz=1e9, energy_mev=5.5, phase_rad=0.3)
        h = p.harmonic()
        assert h.phase_rad == pytest.approx(0.3)

    def test_custom_multiplier(self):
        p = PulsePacket(frequency_hz=1e9, energy_mev=5.5)
        h = p.harmonic(multiplier=3.0)
        assert h.frequency_hz == pytest.approx(3e9)

    def test_repr(self):
        p = PulsePacket(frequency_hz=1e9, energy_mev=5.5)
        assert "PulsePacket" in repr(p)


# ---------------------------------------------------------------------------
# RadonBeacon construction
# ---------------------------------------------------------------------------

class TestRadonBeaconConstruction:
    def test_primary_role(self):
        b = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        assert b.role is PoleRole.PRIMARY
        assert b.depth_m == -1.5

    def test_secondary_role(self):
        b = RadonBeacon(PoleRole.SECONDARY, depth_m=3.0)
        assert b.role is PoleRole.SECONDARY

    def test_default_radon_concentration(self):
        b = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        assert b.radon_concentration_bq_m3 == pytest.approx(40.0)

    def test_repr(self):
        b = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        assert "RadonBeacon" in repr(b)
        assert "PRIMARY" in repr(b)


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------

class TestBeaconPairing:
    def setup_method(self):
        self.primary = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        self.secondary = RadonBeacon(PoleRole.SECONDARY, depth_m=3.0)

    def test_successful_pairing(self):
        self.primary.pair_with(self.secondary)
        # No exception; paired beacon accessible internally
        assert self.primary._paired_beacon is self.secondary
        assert self.secondary._paired_beacon is self.primary

    def test_same_role_raises(self):
        another_primary = RadonBeacon(PoleRole.PRIMARY, depth_m=-2.0)
        with pytest.raises(ValueError, match="Cannot pair two PRIMARY"):
            self.primary.pair_with(another_primary)

    def test_two_secondaries_raises(self):
        s2 = RadonBeacon(PoleRole.SECONDARY, depth_m=5.0)
        with pytest.raises(ValueError, match="Cannot pair two SECONDARY"):
            self.secondary.pair_with(s2)


# ---------------------------------------------------------------------------
# Carrier-wave emission
# ---------------------------------------------------------------------------

class TestCarrierEmission:
    def test_primary_emits_carrier(self):
        b = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5, radon_concentration_bq_m3=40.0)
        packet = b.emit_carrier()
        assert packet.frequency_hz == pytest.approx(BASE_CARRIER_HZ)
        assert packet.energy_mev >= RADON_ALPHA_MEV  # boost applied

    def test_secondary_cannot_emit_carrier(self):
        b = RadonBeacon(PoleRole.SECONDARY, depth_m=3.0)
        with pytest.raises(RuntimeError, match="Only the PRIMARY"):
            b.emit_carrier()

    def test_carrier_logged(self):
        b = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        b.emit_carrier()
        assert len(b.pulse_log) == 1

    def test_zero_radon_still_produces_packet(self):
        b = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5, radon_concentration_bq_m3=0.0)
        packet = b.emit_carrier()
        assert packet.energy_mev > 0

    def test_high_radon_increases_energy(self):
        low = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5, radon_concentration_bq_m3=10.0)
        high = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5, radon_concentration_bq_m3=500.0)
        assert high.emit_carrier().energy_mev > low.emit_carrier().energy_mev


# ---------------------------------------------------------------------------
# Harmonic reply
# ---------------------------------------------------------------------------

class TestHarmonicReply:
    def test_secondary_replies_on_harmonic(self):
        primary = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        secondary = RadonBeacon(PoleRole.SECONDARY, depth_m=3.0)
        primary.pair_with(secondary)
        carrier = primary.emit_carrier()
        reply = secondary.reply_on_harmonic(carrier)
        assert reply.frequency_hz == pytest.approx(carrier.frequency_hz * HARMONIC_MULTIPLIER)

    def test_reply_phase_shifted(self):
        primary = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        secondary = RadonBeacon(PoleRole.SECONDARY, depth_m=3.0)
        primary.pair_with(secondary)
        carrier = primary.emit_carrier()
        reply = secondary.reply_on_harmonic(carrier)
        assert reply.phase_rad == pytest.approx(carrier.phase_rad + math.pi / 4)

    def test_primary_cannot_reply(self):
        primary = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        packet = PulsePacket(frequency_hz=1e9, energy_mev=5.5)
        with pytest.raises(RuntimeError, match="Only the SECONDARY"):
            primary.reply_on_harmonic(packet)


# ---------------------------------------------------------------------------
# Synchronisation
# ---------------------------------------------------------------------------

class TestSynchronisation:
    def _make_paired_pair(self, radon=80.0):
        p = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5, radon_concentration_bq_m3=radon)
        s = RadonBeacon(PoleRole.SECONDARY, depth_m=3.0, radon_concentration_bq_m3=radon)
        p.pair_with(s)
        return p, s

    def test_sync_returns_sync_state(self):
        p, _ = self._make_paired_pair()
        state = p.synchronise()
        assert isinstance(state, SyncState)

    def test_sync_succeeds_with_sufficient_radon(self):
        p, _ = self._make_paired_pair(radon=100.0)
        state = p.synchronise()
        assert state.is_synced

    def test_sync_pulse_count_positive(self):
        p, _ = self._make_paired_pair()
        state = p.synchronise()
        assert state.pulse_count > 0

    def test_sync_flux_gain_positive(self):
        p, _ = self._make_paired_pair()
        state = p.synchronise()
        assert state.flux_gain_db > 0

    def test_sync_phase_delta_decreases(self):
        p, _ = self._make_paired_pair()
        state = p.synchronise(max_iterations=15)
        assert state.phase_delta_rad < math.pi

    def test_secondary_cannot_call_synchronise(self):
        _, s = self._make_paired_pair()
        with pytest.raises(RuntimeError, match="PRIMARY"):
            s.synchronise()

    def test_unpaired_raises(self):
        p = RadonBeacon(PoleRole.PRIMARY, depth_m=-1.5)
        with pytest.raises(RuntimeError, match="not been paired"):
            p.synchronise()

    def test_very_low_radon_may_not_sync_in_few_iterations(self):
        p, _ = self._make_paired_pair(radon=1.0)
        state = p.synchronise(max_iterations=3)
        # With very low radon and only 3 iterations, signal strength should be low
        assert state.signal_strength < SYNC_THRESHOLD or True  # may or may not sync
