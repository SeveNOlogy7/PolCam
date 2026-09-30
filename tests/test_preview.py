"""预览档位的纯规则测试。

为什么要滞回：换一次档，缓存键（含 preview_factor）整批失效，正在看的内容会被重算；
而"控件尺寸差一两个像素"这种抖动不该让画面在 2× 和 4× 之间来回跳。
规则：升档（画质让位给帧率）立即生效；降档（要更细）要求目标档已有 1.1× 余量
——余量取这么小是刻意的：1.5 会让"刚放大到超过 1:1"这种明显该给全量的情形也被挡住。
"""
import pytest

from polcam.core.preview import PreviewQuality, pick_preview_factor


def test_named_levels_ignore_the_view():
    assert pick_preview_factor(PreviewQuality.NATIVE, (2448, 2048), (900, 700)) == 1
    assert pick_preview_factor(PreviewQuality.BALANCED, (2448, 2048), (900, 700)) == 2
    assert pick_preview_factor(PreviewQuality.FLUID, (2448, 2048), (900, 700)) == 4
    # 显式档在"已经够细"的场景下也不自动升到全量：那是自动挡的事
    assert pick_preview_factor(PreviewQuality.BALANCED, (608, 512), (1200, 900)) == 2


def test_auto_picks_the_smallest_level_that_fits():
    # need = max(2448/1224, 2048/1024) = 2 → f=2 刚好铺满
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (1224, 1024)) == 2
    # 缩到 1:1 以内 → 回到全量
    assert pick_preview_factor(PreviewQuality.AUTO, (1224, 1024), (1300, 1100)) == 1
    # 需要 4 才装得下
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (500, 400)) == 4
    # 再小也不给第 5 档：4 是上限
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (100, 80)) == 4


def test_auto_uses_the_tighter_dimension():
    # 宽够（2448/1300=1.88→2）但高不够（2048/300=6.8→4）→ 取 4
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (1300, 300)) == 4


def test_quad_view_shares_the_screen_between_two_tiles():
    # 四分图横向两张：每张只分到控件宽度的一半
    as_single = pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (1300, 1100))
    as_quad = pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (1300, 1100), tiles_across=2)
    assert as_single == 2
    assert as_quad == 4


def test_upshift_is_immediate():
    # 上一帧还是全量，视图一变小就该立刻降画质
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (600, 500), previous=1) == 4


def test_middle_levels_need_margin_before_relaxing_but_full_detail_does_not():
    """4→2 要余量，回到全量不要。

    控件尺寸在两档边界上抖一抖就让画面一帧清一帧糊，比多算一帧难看得多，所以中间档
    降档要求目标档已有 1.1× 余量；而"源图真的装得下视图"是用户放大到位想要真像素的
    那一刻，设门槛等于违约（真机场景：硬件放大到 608x512 装进 650x550 的一格）。
    """
    # need=1.98：f=2 名义上够了，但只差 1.1× 余量的门槛，所以稳定停在 4
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (1235, 1034), previous=4) == 4
    # 视图明显变大（need=1.205 ≤ 2/1.1）才允许 4→2
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (2040, 1700), previous=4) == 2
    # 装得下就立刻给全细节，不管上一档是 2 还是 4
    assert pick_preview_factor(PreviewQuality.AUTO, (1224, 1024), (1300, 1100), previous=2) == 1
    assert pick_preview_factor(PreviewQuality.AUTO, (1224, 1024), (1600, 1400), previous=4) == 1


def test_garbage_view_sizes_fall_back_to_full_resolution():
    # 控件还没布局好（0 尺寸）时绝不能降采样：那会把画面糊掉又没有任何收益
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (0, 0)) == 1
    assert pick_preview_factor(PreviewQuality.AUTO, (2448, 2048), (900, 0)) == 1
    assert pick_preview_factor(PreviewQuality.AUTO, (0, 0), (900, 700)) == 1
    # 显式档不看尺寸，也不因为尺寸是 0 就改成 1
    assert pick_preview_factor(PreviewQuality.BALANCED, (2448, 2048), (0, 0)) == 2


def test_quality_is_a_stored_name_not_a_number():
    # 存进 settings.ini 的必须是名字：把档位存成整数会让老配置在新版本里读出别的档
    assert PreviewQuality.from_name("balanced") is PreviewQuality.BALANCED
    assert PreviewQuality.from_name("BALANCED") is PreviewQuality.BALANCED
    assert PreviewQuality.from_name(None) is PreviewQuality.BALANCED
    assert PreviewQuality.from_name("nonsense") is PreviewQuality.BALANCED
    assert [q.value for q in PreviewQuality] == ["auto", "native", "balanced", "fluid"]
    assert PreviewQuality.BALANCED.factor == 2
