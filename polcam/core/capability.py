"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

相机能力档位：当前这台机器能不能向相机下发动作。

规则放在这里而不是 GUI，是因为同一份判定要喂给控件的 enabled、tooltip 和引导页三处，
而它的输入只是三个事实：装没装驱动、连没连上、最近一次枚举到几台。决策见 docs/adr/0001。
"""

from enum import Enum
from typing import List, Optional, Tuple

# 启动时的枚举有瞬态失败（真机实测 update_all_device_list() 会偶发抛错），
# 所以一次 0 不能当成"没有相机"，否则档位会闪一下又跳回来。
ZERO_ENUMERATIONS_REQUIRED = 2


class CapabilityTier(Enum):
    """按"用户下一步该做什么"划分，不是按代码分支划分。"""

    NO_DRIVER = "no_driver"
    IDLE = "idle"
    NO_DEVICE = "no_device"
    CONNECTED = "connected"

    @property
    def reason(self) -> str:
        """禁用设备写入控件时要显示的理由；空串表示这一档不禁用。"""
        return _REASONS[self]

    @property
    def device_writes_allowed(self) -> bool:
        return self is CapabilityTier.CONNECTED


_REASONS = {
    CapabilityTier.NO_DRIVER: "未检测到大恒 Galaxy 驱动，安装驱动后才能采集",
    CapabilityTier.IDLE: "尚未连接相机，点“连接相机”",
    CapabilityTier.NO_DEVICE: "未检测到相机设备，检查 USB 与供电",
    CapabilityTier.CONNECTED: "",
}


def tier_after_probe(
    sdk_available: bool,
    connected: bool,
    device_count: Optional[int],
    zero_streak: int,
) -> Tuple[CapabilityTier, int]:
    """算出档位与新的连续零枚举计数。

    ``device_count`` 为 ``None`` 表示这个会话还没成功枚举过。启动时故意不主动枚举：
    那次调用有耗时也会抖，而用户点"连接相机"时本来就会枚举一遍。所以没探过就停在
    ``IDLE``，不谎报"没检测到相机"。
    """
    if not sdk_available:
        return CapabilityTier.NO_DRIVER, 0
    if connected:
        return CapabilityTier.CONNECTED, 0
    if device_count is None:
        return CapabilityTier.IDLE, zero_streak
    if device_count > 0:
        return CapabilityTier.IDLE, 0
    streak = zero_streak + 1
    if streak >= ZERO_ENUMERATIONS_REQUIRED:
        return CapabilityTier.NO_DEVICE, streak
    return CapabilityTier.IDLE, streak


def capability_lines(tier: CapabilityTier, device_count: Optional[int],
                     pixels_from_file: bool = False) -> List[str]:
    """引导页「这台机器现在能做什么」那一段的行文。

    清单讲的是**此刻**，所以连着相机时采集要出现在"现在就能做"里，而不是只留一句
    "相机已连接"；缩放那条也一样，连着相机改的是设备 ROI，未连接才是软件缩放。
    """
    can = []
    if tier is CapabilityTier.CONNECTED:
        can.append("单帧采集与连续采集")
        can.append("曝光与增益（含单次自动）")
    can += [
        "读取已保存的原始图像",
        "切换显示模式、调亮度对比度锐化、保存处理结果",
    ]
    if tier is CapabilityTier.CONNECTED:
        can.append("缩放与框选（连着相机时改的是设备 ROI）")
    else:
        can.append("缩放与框选（未连接相机时是软件缩放，不改设备）")

    if tier is CapabilityTier.NO_DRIVER:
        cannot = ["采集图像 —— 需要先安装大恒 Galaxy 驱动（README 有下载链接）"]
    elif tier is CapabilityTier.NO_DEVICE:
        cannot = ["采集图像 —— 连续两次枚举都没发现设备，检查 USB 与供电"]
    elif tier is CapabilityTier.CONNECTED:
        cannot = []
    else:
        found = "尚未探测设备数量" if device_count is None else f"发现 {device_count} 台相机"
        cannot = [f"采集图像 —— 还没连接（{found}），点左侧“连接相机”"]

    lines = ["现在就能做："] + [f"· {item}" for item in can]
    if cannot:
        lines.append("接上相机才能做：")
        lines += [f"· {item}" for item in cannot]
    else:
        lines.append("相机已连接，采集与参数写入均可用。")
    return lines


def help_subtitle(tier: CapabilityTier, has_image: bool, pixels_from_file: bool) -> str:
    """引导页副标题：一句关于"此刻屏上有什么"的事实。

    写死成"尚未载入图像"会在连着相机出图时变成假话（真机截图里就是这句最扎眼）。
    """
    if not has_image:
        return "尚未载入图像，可按下面的步骤开始"
    if tier is CapabilityTier.CONNECTED:
        return "相机已连接，屏上正在显示采集到的图像"
    if pixels_from_file:
        return "屏上显示的是导入的图像文件"
    return "相机未连接，屏上仍是上一次采集到的图像"
