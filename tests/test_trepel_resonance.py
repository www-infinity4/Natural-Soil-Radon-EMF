"""Tests for src/trepel_resonance.py."""

import pytest

from src.trepel_resonance import (
    LEVITATION_THRESHOLD,
    MAX_SAFE_AMPLITUDE,
    TrepelResonance,
    StandingWaveSnapshot,
)


class TestTrepelResonanceConstruction:
    def test_valid_construction(self):
        tr = TrepelResonance(soil_column_m=3.0)
        assert tr.soil_column_m == 3.0

    def test_zero_column_raises(self):
        with pytest.raises(ValueError, match="positive"):
            TrepelResonance(soil_column_m=0.0)

    def test_negative_column_raises(self):
        with pytest.raises(ValueError, match="positive"):
            TrepelResonance(soil_column_m=-1.0)

    def test_zero_initial_amplitude_raises(self):
        with pytest.raises(ValueError, match="positive"):
            TrepelResonance(soil_column_m=3.0, initial_amplitude=0.0)

    def test_repr(self):
        tr = TrepelResonance(soil_column_m=3.0)
        assert "TrepelResonance" in repr(tr)


class TestTrepelResonanceStep:
    def setup_method(self):
        self.tr = TrepelResonance(soil_column_m=3.0, initial_amplitude=0.05)

    def test_step_returns_snapshot(self):
        snap = self.tr.step()
        assert isinstance(snap, StandingWaveSnapshot)

    def test_amplitude_increases_after_step(self):
        initial = self.tr.amplitude
        self.tr.step()
        assert self.tr.amplitude > initial

    def test_snapshot_iteration_increments(self):
        s1 = self.tr.step()
        s2 = self.tr.step()
        assert s2.iteration == s1.iteration + 1

    def test_levitation_force_positive(self):
        self.tr.step()
        snap = self.tr.history[-1]
        assert snap.levitation_force_n > 0

    def test_node_count_at_least_one(self):
        snap = self.tr.step()
        assert snap.node_count >= 1

    def test_history_grows(self):
        for _ in range(5):
            self.tr.step()
        assert len(self.tr.history) == 5


class TestTrepelResonanceRun:
    def test_run_returns_list(self):
        tr = TrepelResonance(soil_column_m=3.0)
        snaps = tr.run(10)
        assert isinstance(snaps, list)
        assert len(snaps) <= 10

    def test_run_stops_early_on_saturation(self):
        # Very high initial amplitude should saturate quickly
        tr = TrepelResonance(soil_column_m=3.0, initial_amplitude=2.4)
        snaps = tr.run(100)
        # Must have stopped before 100 iterations
        assert len(snaps) < 100
        assert snaps[-1].is_saturated

    def test_run_achieves_levitation(self):
        tr = TrepelResonance(soil_column_m=3.0, initial_amplitude=0.05)
        snaps = tr.run(60)
        assert tr.is_levitating, "Expected levitation within 60 iterations"

    def test_run_snapshots_monotone_amplitude(self):
        # Amplitude should generally increase (ignoring tiny oscillations
        # from propel_boost; just check overall trend start-to-end)
        tr = TrepelResonance(soil_column_m=3.0)
        snaps = tr.run(20)
        assert snaps[-1].amplitude > snaps[0].amplitude

    def test_run_levitation_flag_set_correctly(self):
        tr = TrepelResonance(soil_column_m=3.0)
        snaps = tr.run(60)
        for snap in snaps:
            assert snap.is_levitating == (snap.amplitude >= LEVITATION_THRESHOLD)

    def test_run_saturation_flag_set_correctly(self):
        tr = TrepelResonance(soil_column_m=3.0, initial_amplitude=2.4)
        snaps = tr.run(10)
        for snap in snaps:
            assert snap.is_saturated == (snap.amplitude >= MAX_SAFE_AMPLITUDE)


class TestTrepelResonanceReset:
    def test_reset_clears_history(self):
        tr = TrepelResonance(soil_column_m=3.0)
        tr.run(10)
        tr.reset(initial_amplitude=0.05)
        assert len(tr.history) == 0

    def test_reset_restores_amplitude(self):
        tr = TrepelResonance(soil_column_m=3.0)
        tr.run(10)
        tr.reset(initial_amplitude=0.07)
        assert tr.amplitude == pytest.approx(0.07)

    def test_reset_zero_amplitude_raises(self):
        tr = TrepelResonance(soil_column_m=3.0)
        with pytest.raises(ValueError, match="positive"):
            tr.reset(initial_amplitude=0.0)

    def test_run_after_reset(self):
        tr = TrepelResonance(soil_column_m=3.0)
        tr.run(5)
        tr.reset()
        snaps = tr.run(5)
        assert len(snaps) == 5
