"""实时预览的分辨率档位。

连续流下屏上只有那么大一块控件，按全传感器分辨率解算是白算：实测偏振参数图
2448x2048 要 280 ms，而 1224x1024 只要 84 ms。档位只作用于**连续流预览**，
停止后的显示、单帧、图库、区域放大重算与一切保存路径都按原始档走。

合并的单位是 2x2 MPFA 超胞（不是普通降采样）：一个预览像素是 f² 个超胞里同一
偏振方向的平均，所以偏振信息保留、噪声按 f 降，代价是空间细节按 f 损失。
"""
from enum import Enum
from typing import Optional, Tuple

MIN_FACTOR = 1
MAX_FACTOR = 4
FACTOR_LADDER = (1, 2, 4)

# 中间档之间降档（4→2）需要目标档已经有这一成余量，升档不等。回到全量不看余量：
# 用户拿"足够小的 ROI"换帧率，反过来放大到源图真的装得下视图，就该看到真像素。
DOWN_SHIFT_MARGIN = 1.1


class PreviewQuality(Enum):
    """用户在设置里选的预览质量。"""

    AUTO = "auto"          # 跟着控件尺寸走
    NATIVE = "native"      # 不合并，与今天逐帧一致
    BALANCED = "balanced"  # 2x2 超胞合并
    FLUID = "fluid"        # 4x4 超胞合并

    @property
    def label(self) -> str:
        return {
            PreviewQuality.AUTO: "自动挡（按窗口大小）",
            PreviewQuality.NATIVE: "原始（不合并）",
            PreviewQuality.BALANCED: "均衡（2×2 超胞合并）",
            PreviewQuality.FLUID: "流畅（4×4 超胞合并）",
        }[self]

    @property
    def factor(self) -> Optional[int]:
        """固定档的合并倍数；自动挡返回 None，表示由视图决定。"""
        return {
            PreviewQuality.NATIVE: MIN_FACTOR,
            PreviewQuality.BALANCED: 2,
            PreviewQuality.FLUID: MAX_FACTOR,
        }.get(self)

    @staticmethod
    def from_name(name) -> "PreviewQuality":
        """把 settings.ini 里存的字符串装回来。

        存的是名字而不是整数：整数会跟着枚举顺序漂移，老配置在新版本里读出别的档。
        认不出来的值回落到均衡，而不是自动挡——默认值变了要能被人看出来，
        静默自动更糟。
        """
        if isinstance(name, str):
            try:
                return PreviewQuality(name.lower())
            except ValueError:
                return PreviewQuality.BALANCED
        return PreviewQuality.BALANCED


def required_factor(source_wh: Tuple[int, int], view_wh: Tuple[int, int],
                    tiles_across: int = 1) -> Optional[float]:
    """屏上要放得下源图，需要合并多少倍；尺寸不可信时返回 None。

    tiles_across 是四分图那一族的"一格分到几分之一控件"，单图传 1。
    """
    source_w, source_h = source_wh
    view_w, view_h = view_wh
    if source_w <= 0 or source_h <= 0 or view_w <= 0 or view_h <= 0:
        return None
    across = max(1, int(tiles_across))
    tile_w = max(1, view_w // across)
    tile_h = max(1, view_h // across)
    return max(source_w / tile_w, source_h / tile_h)


def _snap(need: float) -> int:
    for factor in FACTOR_LADDER:
        if need <= factor:
            return factor
    return MAX_FACTOR


def pick_preview_factor(quality: PreviewQuality, source_wh: Tuple[int, int],
                        view_wh: Tuple[int, int], previous: Optional[int] = None,
                        tiles_across: int = 1) -> int:
    """这一帧该按哪一档解算。

    滞回只做一半：**升档立即生效**（控件变小、帧率吃紧时画质先让路），**降档要余量**
    （画面在一帧之间忽清忽糊比缓存重算更难看）。回全量是唯一不看余量的降档 ——
    源图装得进视图就该给全细节。代价是控件尺寸正好等于源图尺寸时可能在 1 与 2 之间
    闪一下，那正是"到底要不要全画幅"的分界，用户看得见也在调。
    """
    fixed = quality.factor
    if fixed is not None:
        return fixed

    need = required_factor(source_wh, view_wh, tiles_across)
    if need is None:
        # 控件还没布局好（0 尺寸）或尺寸不可信：宁可按今天的方式全量解算
        return MIN_FACTOR

    ideal = _snap(need)
    if ideal >= (previous or MIN_FACTOR):
        return ideal
    if ideal == MIN_FACTOR:
        return MIN_FACTOR
    if need * DOWN_SHIFT_MARGIN <= ideal:
        return ideal
    return previous
