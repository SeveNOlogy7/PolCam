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
    def device_writes_allowed(self) -> bool:
        return self is CapabilityTier.CONNECTED


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
