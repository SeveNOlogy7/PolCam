"""能力档位的纯规则。控件映射在 tests/test_gui.py。"""

from polcam.core.capability import (
    ZERO_ENUMERATIONS_REQUIRED,
    CapabilityTier,
    capability_lines,
    tier_after_probe,
)


def test_no_driver_wins_over_everything_else():
    # 没驱动时 connected 与 device_count 都不可能是真值，但规则不许依赖这个前提
    tier, streak = tier_after_probe(False, True, 1, 0)
    assert tier is CapabilityTier.NO_DRIVER
    assert streak == 0


def test_connected_short_circuits_probe_state():
    tier, streak = tier_after_probe(True, True, None, 1)
    assert tier is CapabilityTier.CONNECTED
    assert streak == 0, "连上了就不该留着旧的零计数"


def test_never_enumerated_is_idle_not_no_device():
    tier, streak = tier_after_probe(True, False, None, 0)
    assert tier is CapabilityTier.IDLE
    assert streak == 0


def test_a_single_zero_enumeration_does_not_claim_no_device():
    # 枚举本身有瞬态失败（真机测过），一次 0 就下结论会闪
    tier, streak = tier_after_probe(True, False, 0, 0)
    assert tier is CapabilityTier.IDLE
    assert streak == 1


def test_two_consecutive_zero_enumerations_report_no_device():
    assert ZERO_ENUMERATIONS_REQUIRED == 2
    _, streak = tier_after_probe(True, False, 0, 0)
    tier, streak = tier_after_probe(True, False, 0, streak)
    assert tier is CapabilityTier.NO_DEVICE
    assert streak == 2


def test_a_positive_count_resets_the_streak_back_to_idle():
    tier, streak = tier_after_probe(True, False, 1, 5)
    assert tier is CapabilityTier.IDLE
    assert streak == 0


def test_only_connected_allows_device_writes():
    assert CapabilityTier.CONNECTED.device_writes_allowed
    for tier in (CapabilityTier.NO_DRIVER, CapabilityTier.IDLE, CapabilityTier.NO_DEVICE):
        assert not tier.device_writes_allowed


def test_each_tier_tells_a_different_story():
    reasons = [t.reason for t in CapabilityTier if t is not CapabilityTier.CONNECTED]
    assert len(set(reasons)) == len(reasons)
    assert all(reasons)
    assert CapabilityTier.CONNECTED.reason == ""


def test_the_reasons_point_at_different_fixes():
    assert "驱动" in CapabilityTier.NO_DRIVER.reason
    assert "USB" in CapabilityTier.NO_DEVICE.reason
    assert "连接" in CapabilityTier.IDLE.reason


def test_guide_lines_state_the_next_step_for_every_tier():
    for tier in CapabilityTier:
        lines = capability_lines(tier, 1)
        assert lines, f"{tier.name} 不能给出空的引导行"
        assert all(isinstance(line, str) and line for line in lines)


def test_guide_lines_quote_the_detected_device_count():
    lines = "\n".join(capability_lines(CapabilityTier.IDLE, 2))
    assert "2" in lines


def test_guide_lines_do_not_ask_the_user_to_connect_when_connected():
    lines = "\n".join(capability_lines(CapabilityTier.CONNECTED, 1))
    assert "已连接" in lines
    assert "点" not in lines
