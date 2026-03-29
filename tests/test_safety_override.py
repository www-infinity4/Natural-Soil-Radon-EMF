"""Tests for src/safety_override.py."""

import pytest

from src.safety_override import (
    RADON_CRITICAL_BQ_M3,
    RADON_SAFE_BQ_M3,
    RADON_WARNING_BQ_M3,
    REVERSAL_PULSE_STRENGTH,
    SAFE_SEQUESTRATION_DEPTH_M,
    OverrideAction,
    RadonLevel,
    SafetyOverride,
)


class TestRadonLevelClassification:
    def test_safe_below_warning(self):
        assert SafetyOverride.classify(50.0) is RadonLevel.SAFE

    def test_safe_at_zero(self):
        assert SafetyOverride.classify(0.0) is RadonLevel.SAFE

    def test_warning_at_boundary(self):
        assert SafetyOverride.classify(RADON_WARNING_BQ_M3) is RadonLevel.WARNING

    def test_warning_above_boundary(self):
        assert SafetyOverride.classify(RADON_WARNING_BQ_M3 + 1) is RadonLevel.WARNING

    def test_critical_at_boundary(self):
        assert SafetyOverride.classify(RADON_CRITICAL_BQ_M3) is RadonLevel.CRITICAL

    def test_critical_above_boundary(self):
        assert SafetyOverride.classify(RADON_CRITICAL_BQ_M3 + 100) is RadonLevel.CRITICAL

    def test_just_below_warning(self):
        assert SafetyOverride.classify(RADON_WARNING_BQ_M3 - 0.1) is RadonLevel.SAFE


class TestSafetyOverrideConstruction:
    def test_default_construction(self):
        so = SafetyOverride()
        assert so.baseline_depth_m == pytest.approx(1.5)
        assert so.override_count == 0
        assert so.last_action is None

    def test_custom_depth(self):
        so = SafetyOverride(baseline_depth_m=2.0)
        assert so.baseline_depth_m == pytest.approx(2.0)

    def test_zero_depth_raises(self):
        with pytest.raises(ValueError, match="positive"):
            SafetyOverride(baseline_depth_m=0.0)

    def test_negative_depth_raises(self):
        with pytest.raises(ValueError, match="positive"):
            SafetyOverride(baseline_depth_m=-1.0)

    def test_repr(self):
        so = SafetyOverride()
        assert "SafetyOverride" in repr(so)


class TestSafetyOverrideEvaluate:
    def setup_method(self):
        self.so = SafetyOverride(baseline_depth_m=1.5)

    def test_safe_reading_no_pulse(self):
        action = self.so.evaluate(50.0)
        assert not action.pulse_fired
        assert action.radon_level is RadonLevel.SAFE
        assert action.pulse_strength == pytest.approx(0.0)
        assert not action.ions_reversed

    def test_safe_reading_no_depth_change(self):
        action = self.so.evaluate(50.0)
        assert action.projected_new_depth_m == pytest.approx(1.5)

    def test_warning_fires_pulse(self):
        action = self.so.evaluate(RADON_WARNING_BQ_M3 + 50.0)
        assert action.pulse_fired
        assert action.ions_reversed

    def test_critical_fires_full_strength_pulse(self):
        action = self.so.evaluate(RADON_CRITICAL_BQ_M3 + 10.0)
        assert action.pulse_strength == pytest.approx(REVERSAL_PULSE_STRENGTH)

    def test_warning_partial_pulse_below_max(self):
        action = self.so.evaluate(RADON_WARNING_BQ_M3 + 1.0)
        assert action.pulse_strength < REVERSAL_PULSE_STRENGTH

    def test_pulse_increases_depth(self):
        action = self.so.evaluate(RADON_CRITICAL_BQ_M3)
        assert action.projected_new_depth_m > self.so.baseline_depth_m

    def test_critical_depth_deeper_than_warning_depth(self):
        warning_action = SafetyOverride(1.5).evaluate(RADON_WARNING_BQ_M3 + 1.0)
        critical_action = SafetyOverride(1.5).evaluate(RADON_CRITICAL_BQ_M3)
        assert (
            critical_action.projected_new_depth_m
            >= warning_action.projected_new_depth_m
        )

    def test_override_count_increments_on_pulse(self):
        self.so.evaluate(RADON_CRITICAL_BQ_M3)
        assert self.so.override_count == 1
        self.so.evaluate(RADON_CRITICAL_BQ_M3)
        assert self.so.override_count == 2

    def test_override_count_not_incremented_on_safe(self):
        self.so.evaluate(10.0)
        assert self.so.override_count == 0

    def test_last_action_stored(self):
        action = self.so.evaluate(50.0)
        assert self.so.last_action is action

    def test_negative_reading_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            self.so.evaluate(-1.0)

    def test_repr_on_action(self):
        action = self.so.evaluate(50.0)
        assert "OverrideAction" in repr(action)

    def test_projected_depth_above_safe_sequestration(self):
        action = self.so.evaluate(RADON_CRITICAL_BQ_M3)
        assert action.projected_new_depth_m >= SAFE_SEQUESTRATION_DEPTH_M
