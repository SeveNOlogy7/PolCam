"""能力档位的措辞。句子在 gui/capability_text.py（lupdate 只认 translate() 里的字面量），
所以这里测的是"用户看见的那句话"，纯规则在 tests/test_capability.py。"""

from polcam.core.capability import CapabilityTier
from polcam.gui.capability_text import capability_lines, help_subtitle, reason


def test_each_tier_tells_a_different_story():
    reasons = [reason(t) for t in CapabilityTier if t is not CapabilityTier.CONNECTED]
    assert len(set(reasons)) == len(reasons)
    assert all(reasons)
    assert reason(CapabilityTier.CONNECTED) == ""


def test_the_reasons_point_at_different_fixes():
    assert "驱动" in reason(CapabilityTier.NO_DRIVER)
    assert "USB" in reason(CapabilityTier.NO_DEVICE)
    assert "连接" in reason(CapabilityTier.IDLE)


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


def test_the_subtitle_describes_what_is_actually_on_screen():
    """副标题讲的是此刻，不是"默认还没图"。连着相机出图时那句必须跟着变。"""
    assert "尚未载入图像" in help_subtitle(CapabilityTier.CONNECTED, False, False)
    assert "采集到的图像" in help_subtitle(CapabilityTier.CONNECTED, True, False)
    assert "导入的图像文件" in help_subtitle(CapabilityTier.IDLE, True, True)
    assert "上一次采集" in help_subtitle(CapabilityTier.IDLE, True, False)


def test_the_idle_line_quotes_the_device_count_it_actually_saw():
    lines = capability_lines(CapabilityTier.IDLE, 2)
    assert any("2 台" in line for line in lines), lines
    lines = capability_lines(CapabilityTier.IDLE, None)
    assert any("尚未探测设备数量" in line for line in lines), lines
