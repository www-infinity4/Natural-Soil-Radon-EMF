"""Tests for src/drone_anchor.py."""

import math
import pytest

from src.drone_anchor import (
    HELIX_PITCH_M,
    REVOLUTIONS_PER_STEP,
    AnchorState,
    BurrowStep,
    DroneAnchor,
)


class TestDroneAnchorConstruction:
    def test_valid_construction(self):
        da = DroneAnchor(target_depth_m=1.5)
        assert da.target_depth_m == pytest.approx(1.5)
        assert da.state is AnchorState.READY
        assert da.current_depth_m == pytest.approx(0.0)

    def test_zero_depth_raises(self):
        with pytest.raises(ValueError, match="positive"):
            DroneAnchor(target_depth_m=0.0)

    def test_negative_depth_raises(self):
        with pytest.raises(ValueError, match="positive"):
            DroneAnchor(target_depth_m=-0.5)

    def test_zero_resistance_raises(self):
        with pytest.raises(ValueError, match="positive"):
            DroneAnchor(target_depth_m=1.5, soil_resistance=0.0)

    def test_repr(self):
        da = DroneAnchor(target_depth_m=1.5)
        assert "DroneAnchor" in repr(da)
        assert "READY" in repr(da)


class TestDeployAndBurrow:
    def setup_method(self):
        self.da = DroneAnchor(target_depth_m=1.0)

    def test_deploy_transitions_to_deployed(self):
        self.da.deploy()
        assert self.da.state is AnchorState.DEPLOYED

    def test_deploy_from_non_ready_raises(self):
        self.da.deploy()
        with pytest.raises(RuntimeError, match="READY"):
            self.da.deploy()

    def test_start_burrowing_transitions(self):
        self.da.deploy()
        self.da.start_burrowing()
        assert self.da.state is AnchorState.BURROWING

    def test_burrow_without_burrowing_raises(self):
        self.da.deploy()
        with pytest.raises(RuntimeError, match="start_burrowing"):
            self.da.burrow_step()

    def test_burrow_step_increases_depth(self):
        self.da.deploy()
        self.da.start_burrowing()
        self.da.burrow_step()
        assert self.da.current_depth_m > 0.0

    def test_burrow_step_returns_step_object(self):
        self.da.deploy()
        self.da.start_burrowing()
        step = self.da.burrow_step()
        assert isinstance(step, BurrowStep)

    def test_burrow_step_logs_entry(self):
        self.da.deploy()
        self.da.start_burrowing()
        self.da.burrow_step()
        assert len(self.da.burrow_log) == 1

    def test_burrow_to_target_reaches_anchored(self):
        self.da.deploy()
        self.da.burrow_to_target()
        assert self.da.state is AnchorState.ANCHORED
        assert self.da.current_depth_m == pytest.approx(self.da.target_depth_m)


class TestBurrowToTarget:
    def test_full_sequence(self):
        da = DroneAnchor(target_depth_m=0.5)
        da.deploy()
        steps = da.burrow_to_target()
        assert da.state is AnchorState.ANCHORED
        assert len(steps) > 0
        assert all(isinstance(s, BurrowStep) for s in steps)

    def test_starts_burrowing_if_deployed(self):
        da = DroneAnchor(target_depth_m=0.5)
        da.deploy()
        # Should auto-start burrowing
        da.burrow_to_target()
        assert da.state is AnchorState.ANCHORED

    def test_energy_consumed_positive(self):
        da = DroneAnchor(target_depth_m=0.5)
        da.deploy()
        da.burrow_to_target()
        assert da.total_energy_j > 0.0

    def test_harder_soil_needs_more_steps(self):
        easy = DroneAnchor(target_depth_m=1.0, soil_resistance=0.5)
        hard = DroneAnchor(target_depth_m=1.0, soil_resistance=2.0)
        easy.deploy()
        hard.deploy()
        easy_steps = easy.burrow_to_target()
        hard_steps = hard.burrow_to_target()
        assert len(hard_steps) > len(easy_steps)

    def test_steps_to_target_estimate(self):
        da = DroneAnchor(target_depth_m=1.0)
        estimated = da.steps_to_target()
        da.deploy()
        actual_steps = da.burrow_to_target()
        # Estimate should be close (within ±1) to actual
        assert abs(estimated - len(actual_steps)) <= 1


class TestRetraction:
    def test_retract_from_anchored(self):
        da = DroneAnchor(target_depth_m=0.5)
        da.deploy()
        da.burrow_to_target()
        reverse_steps = da.retract()
        assert da.state is AnchorState.RETRIEVED
        assert da.current_depth_m == pytest.approx(0.0)
        assert reverse_steps > 0

    def test_retract_from_non_anchored_raises(self):
        da = DroneAnchor(target_depth_m=0.5)
        with pytest.raises(RuntimeError, match="ANCHORED"):
            da.retract()

    def test_retract_returns_step_count(self):
        da = DroneAnchor(target_depth_m=0.5)
        da.deploy()
        da.burrow_to_target()
        n = da.retract()
        assert isinstance(n, int)
        assert n == len(da.burrow_log)
