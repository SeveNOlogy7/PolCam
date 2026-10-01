# 能力档位（Capability Tiers）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让应用按「无驱动 / 有驱动未连接 / 未检测到设备 / 已连接」四种状态决定设备写入类控件的可用性，并在控件与引导页上说清当前这台机器能做什么。

**Architecture:** 一个无 Qt、无 SDK 依赖的纯规则模块 `polcam/core/capability.py` 拥有状态定义、判定规则与文案；`CameraControl` 把「档位」落成控件的 enabled + tooltip；`MainWindow` 是唯一的重算者，在启动、连接/断开事件、错误事件和连接失败后调用纯规则并带防抖；`ImageDisplay` 的引导页显示由同一档位生成的能力清单。沿用 `polcam/core/preview.py` 的先例：规则可单独测试，GUI 只做映射。

**Tech Stack:** Python 3.12、Qt（qtpy，PySide6 后端）、pytest，测试入口 `tools/run_tests.py`（每文件一个子进程）。

**Spec:** `docs/adr/0001-capability-tiers-gate-device-writes.md` 与 `CONTEXT.md`（术语：能力档位、设备写入类控件、首次出图路径、能力清单）。

## Global Constraints

- 应用**必须在没有大恒 Galaxy 驱动时也能启动**（产品级要求，`polcam/core/camera_module.py:10-18` 已把 `gxipy` 导入失败降级为 `gx = None`）。
- commit message 一律英文 conventional 前缀，`type`/标题必须如实反映改动内容（git-cliff 用它生成 changelog）。
- 渲染给用户与 changelog 的字符串按现有语言习惯（界面中文，changelog 全英文）。
- 不新增第三方依赖。
- 测试用 `uv run --locked python tools/run_tests.py`；`python` 在 PATH 上是 Microsoft Store 桩，不要用。
- 验收只在 CI 造档：显式设 `camera_module.gx = None` / `camera.sdk_available = False`，**不依赖** `tests/conftest.py:14-25` 的 MagicMock 兜底。真实无驱动环境未跑过，这是 ADR 记录的已知未验证项，不要把它写成"已验证"。
- 「连接相机」按钮在任何档位都必须可点。
- 缩放/框选/复原**不在**设备写入集合内：无设备时它们做软件缩放，是真实可用的能力（`image_toolbar_controller.py:245-249` 已按 `is_connected()` 分叉）。

## 文件结构

| 文件 | 责任 |
| --- | --- |
| Create `polcam/core/capability.py` | 档位枚举、判定纯函数、防抖、面向用户的理由文案与引导页行 |
| Create `tests/test_capability.py` | 纯规则与文案唯一性 |
| Modify `polcam/gui/camera_control.py:142-148` | `set_connected()` → `apply_capability()`，把档位映射到 enabled + tooltip |
| Modify `polcam/gui/camera_control.py:73-75` | 初始状态改由档位驱动 |
| Modify `polcam/gui/main_window.py:291-376` | 唯一的档位重算者与四个触发时机 + 防抖计数 |
| Modify `polcam/gui/image_display.py:750-768` | 引导页新增「这台机器现在能做什么」段 |
| Modify `README.md:148` | 改掉那句假设下载者已有 RAW 文件的兜底话，并补 v1.1.0 的两个新行为 |

---

### Task 1: 纯规则模块 `capability.py`

**Files:**
- Create: `polcam/core/capability.py`
- Test: `tests/test_capability.py`

**Interfaces:**
- Consumes: 无（纯标准库）
- Produces:
  - `CapabilityTier` 枚举，成员 `NO_DRIVER` / `IDLE` / `NO_DEVICE` / `CONNECTED`，属性 `.reason: str`（CONNECTED 为 `""`）
  - `ZERO_ENUMERATIONS_REQUIRED: int = 2`
  - `tier_after_probe(sdk_available: bool, connected: bool, device_count: Optional[int], zero_streak: int) -> Tuple[CapabilityTier, int]`
  - `capability_lines(tier: CapabilityTier, device_count: Optional[int]) -> List[str]`

- [ ] **Step 1: 写失败的测试**

创建 `tests/test_capability.py`：

```python
"""能力档位的纯规则。GUI 侧的映射在 tests/test_gui.py。"""

from polcam.core.capability import (
    ZERO_ENUMERATIONS_REQUIRED,
    CapabilityTier,
    capability_lines,
    tier_after_probe,
)


def test_no_driver_wins_over_everything_else():
    # 没驱动时 connected/device_count 都不可能是真值，但规则不许依赖这个前提
    tier, streak = tier_after_probe(False, True, 1, 0)
    assert tier is CapabilityTier.NO_DRIVER


def test_connected_short_circuits_probe_state():
    tier, streak = tier_after_probe(True, True, None, 1)
    assert tier is CapabilityTier.CONNECTED
    assert streak == 0, "连上了就不该留着旧的零计数"


def test_never_enumerated_is_idle_not_no_device():
    tier, streak = tier_after_probe(True, False, None, 0)
    assert tier is CapabilityTier.IDLE
    assert streak == 0


def test_a_single_zero_enumeration_does_not_claim_no_device():
    # 枚举本身有瞬态失败，一次 0 就下结论会闪
    tier, streak = tier_after_probe(True, False, 0, 0)
    assert tier is CapabilityTier.IDLE
    assert streak == 1


def test_two_consecutive_zero_enumerations_report_no_device():
    assert ZERO_ENUMERATIONS_REQUIRED == 2
    _, streak = tier_after_probe(True, False, 0, 0)
    tier, streak = tier_after_probe(True, False, 0, streak)
    assert tier is CapabilityTier.NO_DEVICE


def test_a_positive_count_resets_the_streak_back_to_idle():
    tier, streak = tier_after_probe(True, False, 1, 5)
    assert tier is CapabilityTier.IDLE
    assert streak == 0


def test_each_tier_tells_a_different_story():
    reasons = [t.reason for t in CapabilityTier if t is not CapabilityTier.CONNECTED]
    assert len(set(reasons)) == len(reasons)
    assert all(r for r in reasons)
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --locked python tools/run_tests.py -k capability -q`
Expected: 收集失败 / `ModuleNotFoundError: No module named 'polcam.core.capability'`

- [ ] **Step 3: 写最小实现**

创建 `polcam/core/capability.py`：

```python
"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

相机能力档位：一台机器现在能不能向相机下发动作。

规则放这儿而不是 GUI，是因为它同时被控件的 enabled、tooltip 和引导页三处读，
而它唯一的输入是三个布尔/整数事实。决策记录见 docs/adr/0001。
"""

from enum import Enum
from typing import List, Optional, Tuple

# 枚举有瞬态失败（真机测过：启动时枚举可能抛错），所以一次 0 不能当成"没有相机"
ZERO_ENUMERATIONS_REQUIRED = 2


class CapabilityTier(Enum):
    """按"用户该怎么修"划分的四态，不是按代码分支划分。"""

    NO_DRIVER = "no_driver"
    IDLE = "idle"
    NO_DEVICE = "no_device"
    CONNECTED = "connected"

    @property
    def reason(self) -> str:
        """禁用设备写入控件时显示的理由；空串表示不该禁用。"""
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
    """由"是否装了驱动 / 是否已连接 / 最近一次枚举到几台"算出档位。

    ``device_count`` 为 ``None`` 表示这个会话还没成功枚举过 —— 启动时不主动枚举，
    因为 ``update_all_device_list()`` 有耗时也会抖，而那件事用户自己点"连接相机"就会做。
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


def capability_lines(tier: CapabilityTier, device_count: Optional[int]) -> List[str]:
    """引导页「这台机器现在能做什么」那一段的行文。"""
    can = [
        "读取已保存的原始图像",
        "切换显示模式、调亮度对比度锐化、保存处理结果",
        "缩放与框选（未连接相机时按软件缩放，不改设备）",
    ]
    if tier is CapabilityTier.NO_DRIVER:
        cannot = ["采集图像 —— 需要先安装大恒 Galaxy 驱动（README 有下载链接）"]
    elif tier is CapabilityTier.NO_DEVICE:
        cannot = ["采集图像 —— 连续两次枚举都没有发现设备，检查 USB 与供电"]
    elif tier is CapabilityTier.CONNECTED:
        cannot = []
    else:
        found = "未发现设备" if device_count == 0 else f"发现 {device_count if device_count is not None else '?'} 台相机"
        cannot = [f"采集图像 —— 尚未连接（{found}），点左侧“连接相机”"]
    lines = [f"现在就能做：（{'、'.join(can[:1])} 等）"] if False else []
    lines = ["现在就能做："] + [f"· {item}" for item in can]
    if cannot:
        lines.append("接上相机才能做：")
        lines += [f"· {item}" for item in cannot]
    else:
        lines.append("相机已连接，采集与参数写入均可用。")
    return lines
```

写完把上面那行 `if False else []` 的残留删掉——它只是起草时的折行痕迹，正确形态是直接从 `lines = ["现在就能做："]` 开始：

```python
    lines = ["现在就能做："] + [f"· {item}" for item in can]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run --locked python tools/run_tests.py -k capability -q`
Expected: `9 passed`

- [ ] **Step 5: 提交**

```bash
git add polcam/core/capability.py tests/test_capability.py
git commit -m "feat: model the camera capability tiers as a pure rule"
```

---

### Task 2: 把档位映射到 `CameraControl` 的控件

**Files:**
- Modify: `polcam/gui/camera_control.py:142-148`（`set_connected` → `apply_capability`）
- Modify: `polcam/gui/camera_control.py:73-75`（初始状态由档位驱动）
- Modify: `polcam/gui/camera_control.py:277-280`（`handle_stream_state` 与档位协同）
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `CapabilityTier`、`tier.reason`、`tier.device_writes_allowed`（Task 1）
- Produces: `CameraControl.apply_capability(tier: CapabilityTier) -> None`、`CameraControl.capability_tier -> CapabilityTier`（只读属性）。**`set_connected()` 被删除**，调用方在 Task 3 迁移。

- [ ] **Step 1: 写失败的测试**

在 `tests/test_gui.py` 末尾追加（该文件已 `from polcam.gui.camera_control import CameraControl`，若无则补这行 import）：

```python
def test_no_driver_tiers_disable_every_device_write(qtbot):
    from polcam.core.capability import CapabilityTier

    control = CameraControl()
    qtbot.addWidget(control)
    control.apply_capability(CapabilityTier.NO_DRIVER)

    assert not control.capture_btn.isEnabled()
    assert not control.stream_btn.isEnabled()
    assert not control.exposure_control.value_spin.isEnabled()
    assert not control.exposure_control.auto_check.isEnabled()
    assert not control.exposure_control.once_btn.isEnabled()
    assert not control.gain_control.value_spin.isEnabled()
    assert not control.gain_control.once_btn.isEnabled()
    assert not control.wb_control.once_btn.isEnabled()


def test_the_connect_button_stays_clickable_in_every_tier(qtbot):
    from polcam.core.capability import CapabilityTier

    control = CameraControl()
    qtbot.addWidget(control)
    for tier in CapabilityTier:
        control.apply_capability(tier)
        assert control.connect_btn.isEnabled(), f"{tier.name} 不该锁住“连接相机”"


def test_a_disabled_control_says_why(qtbot):
    from polcam.core.capability import CapabilityTier

    control = CameraControl()
    qtbot.addWidget(control)
    control.apply_capability(CapabilityTier.NO_DEVICE)
    assert "USB" in control.capture_btn.toolTip()
    assert control.exposure_control.value_spin.toolTip()

    control.apply_capability(CapabilityTier.CONNECTED)
    assert control.capture_btn.toolTip() == ""


def test_connecting_reenables_the_writes_and_relables_the_button(qtbot):
    from polcam.core.capability import CapabilityTier

    control = CameraControl()
    qtbot.addWidget(control)
    control.apply_capability(CapabilityTier.IDLE)
    control.apply_capability(CapabilityTier.CONNECTED)

    assert control.capture_btn.isEnabled()
    assert control.stream_btn.isEnabled()
    assert control.exposure_control.value_spin.isEnabled()
    assert control.connect_btn.text() == "断开相机"


def test_streaming_still_outranks_the_tier_for_the_capture_button(qtbot):
    """连续采集中单帧采集会被设备拒掉，这条既有约束不能因为档位而失效。"""
    from polcam.core.capability import CapabilityTier

    control = CameraControl()
    qtbot.addWidget(control)
    control.apply_capability(CapabilityTier.CONNECTED)
    control.handle_stream_state(True)

    assert not control.capture_btn.isEnabled()
    assert control.stream_btn.isEnabled(), "停止采集必须还能点"

    control.handle_stream_state(False)
    assert control.capture_btn.isEnabled()


def test_an_auto_mode_reenable_does_not_override_the_tier(qtbot):
    """enable_exposure_controls 这类瞬时门不能把禁用的档位重新点亮。"""
    from polcam.core.capability import CapabilityTier

    control = CameraControl()
    qtbot.addWidget(control)
    control.apply_capability(CapabilityTier.NO_DRIVER)
    control.enable_exposure_controls(True)

    assert not control.exposure_control.value_spin.isEnabled()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --locked python tools/run_tests.py tests/test_gui.py -k "tier or device_write or capability or capture_button" -q`
Expected: FAIL —`AttributeError: 'CameraControl' object has no attribute 'apply_capability'`

- [ ] **Step 3: 写最小实现**

`polcam/gui/camera_control.py` 顶部 import 段加：

```python
from ..core.capability import CapabilityTier
```

`setup_ui()` 末尾那段初始状态（73-75 行）替换为：

```python
        # 初始档位由 MainWindow 在窗口建好后立即下发；这里先给一个与安全默认一致的
        # 内部状态，避免任何控件在收到档位之前自己决定自己可点。
        self._tier = CapabilityTier.IDLE
        self._streaming = False
        self.apply_capability(self._tier)
```

把 142-148 行的 `set_connected` 整体换成：

```python
    @property
    def capability_tier(self) -> CapabilityTier:
        return self._tier

    def apply_capability(self, tier: CapabilityTier) -> None:
        """按能力档位决定设备写入类控件是否可用，并把理由写进 tooltip。

        集合的边界见 docs/adr/0001：会向相机下发动作的才归它管，
        “连接相机”永远可点（用户插好线要能直接重试），
        缩放/框选/复原也不在内（未连接时它们做软件缩放）。
        """
        self._tier = tier
        self._sync_device_write_controls()
        self.connect_btn.setText("断开相机" if tier is CapabilityTier.CONNECTED else "连接相机")

    def _sync_device_write_controls(self) -> None:
        available = self._tier.device_writes_allowed
        reason = self._tier.reason

        self.exposure_control.set_enabled(available)
        self.gain_control.set_enabled(available)
        self.wb_control.once_btn.setEnabled(available)

        self.stream_btn.setEnabled(available)
        self.capture_btn.setEnabled(available and not self._streaming)

        for widget in (
            self.capture_btn, self.stream_btn,
            self.exposure_control.value_spin, self.exposure_control.auto_check,
            self.exposure_control.once_btn,
            self.gain_control.value_spin, self.gain_control.auto_check,
            self.gain_control.once_btn,
            self.wb_control.once_btn,
        ):
            widget.setToolTip("" if widget.isEnabled() else reason)
```

`handle_stream_state`（277-280 行）里那行直接写 `capture_btn.setEnabled(not streaming)` 换成走同一个同步点：

```python
    def handle_stream_state(self, streaming: bool):
        """处理连续采集状态改变"""
        self._streaming = streaming
        self._sync_device_write_controls()
        self.stream_btn.setText("停止采集" if streaming else "连续采集")
```

`enable_exposure_controls` / `enable_gain_controls` / `enable_wb_controls` 三个瞬时门改成只在档位允许时才生效，否则保持禁用（替换这三个方法体）：

```python
    def enable_exposure_controls(self, enabled: bool):
        """设置曝光相关控件的启用状态（能力档位不允许时永远不亮）"""
        self.exposure_control.set_enabled(enabled and self._tier.device_writes_allowed)
        self._sync_device_write_controls()

    def enable_gain_controls(self, enabled: bool):
        """设置增益相关控件的启用状态"""
        self.gain_control.set_enabled(enabled and self._tier.device_writes_allowed)
        self._sync_device_write_controls()

    def enable_wb_controls(self, enabled: bool):
        """设置白平衡控制组
        注：只影响单次白平衡按钮，不影响自动模式开关"""
        self.wb_control.once_btn.setEnabled(
            enabled and self._tier.device_writes_allowed
        )
        self._sync_device_write_controls()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run --locked python tools/run_tests.py tests/test_gui.py -q`
Expected: 新增 6 条通过；此时会有 4 条既有失败（`set_connected` 已删）——那是 Task 3 的活，先在 Step 5 之前确认失败信息只是 `AttributeError: set_connected`：

```bash
uv run --locked python tools/run_tests.py tests/test_gui.py -q 2>&1 | grep -c "set_connected"
```
Expected: ≥ 1（说明剩下的失败都来自这个改名，不是别的问题）

- [ ] **Step 5: 提交**

```bash
git add polcam/gui/camera_control.py tests/test_gui.py
git commit -m "feat: gate device-writing controls by the capability tier"
```

（此提交单独不可验证——`main_window` 与既有测试仍在调 `set_connected`。Task 3 第一件事就是把它接回来，所以 Task 2 和 Task 3 之间不跑全量。）

---

### Task 3: `MainWindow` 成为唯一的档位重算者

**Files:**
- Modify: `polcam/gui/main_window.py:291-376`（`handle_connect` 的 5 个 `set_connected` 调用点）
- Modify: `polcam/gui/main_window.py` 的 `_gui_event_handlers`（70-71 行附近）与 `__init__` 尾部
- Modify: `tests/test_gui.py:42`、`:58`、`:387`、`:1012`（改用 `apply_capability`）
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `tier_after_probe()`、`CameraControl.apply_capability()`、`CameraModule.sdk_available`（`camera_module.py:161-163`）、`camera.enumerate_devices()`
- Produces: `MainWindow.refresh_capability(device_count: Optional[int] = None) -> CapabilityTier`、`MainWindow.capability_tier -> CapabilityTier`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_gui.py` 追加（`main_window` 夹具沿用该文件既有的构造方式：`QSettings` 指向临时文件、`camera` 为 MagicMock）：

```python
def _set_probe_facts(main_window, *, sdk_available, device_count, connected):
    """把三档的输入事实钉住，不碰真实的 SDK 对象。"""
    main_window.camera.sdk_available = sdk_available
    main_window.camera.is_connected.return_value = connected
    main_window.camera.enumerate_devices.return_value = (device_count, [])


def test_startup_without_a_driver_lands_on_no_driver(main_window):
    _set_probe_facts(main_window, sdk_available=False, device_count=None, connected=False)

    tier = main_window.refresh_capability()

    assert tier is CapabilityTier.NO_DRIVER
    assert not main_window.camera_control.capture_btn.isEnabled()
    assert "驱动" in main_window.camera_control.capture_btn.toolTip()


def test_startup_with_a_driver_but_no_probe_is_idle(main_window):
    _set_probe_facts(main_window, sdk_available=True, device_count=1, connected=False)

    tier = main_window.refresh_capability()

    assert tier is CapabilityTier.IDLE
    assert main_window.camera.connect_btn.isEnabled()


def test_one_failed_enumeration_keeps_idle_and_two_report_no_device(main_window):
    _set_probe_facts(main_window, sdk_available=True, device_count=0, connected=False)

    assert main_window.refresh_capability(device_count=0) is CapabilityTier.IDLE
    assert main_window.refresh_capability(device_count=0) is CapabilityTier.NO_DEVICE


def test_a_connect_success_promotes_and_a_disconnect_demotes(main_window):
    _set_probe_facts(main_window, sdk_available=True, device_count=1, connected=True)
    assert main_window.refresh_capability() is CapabilityTier.CONNECTED

    main_window.camera.is_connected.return_value = False
    assert main_window.refresh_capability() is CapabilityTier.IDLE


def test_the_capture_error_downgrades_the_live_view(main_window):
    """拔线时按钮必须自己变灰，不能等用户再撞一次 SDK。"""
    _set_probe_facts(main_window, sdk_available=True, device_count=1, connected=True)
    main_window.refresh_capability()
    assert main_window.camera_control.capture_btn.isEnabled()

    main_window.camera.is_connected.return_value = False
    main_window._on_error({"error": "device lost"})

    assert not main_window.camera_control.capture_btn.isEnabled()


def test_connecting_through_the_panel_reports_no_device_after_two_probes(main_window):
    """走真实的连接按钮路径：两次都是 0 才把 tooltip 改成 USB 那句。"""
    main_window.camera.sdk_available = True
    main_window.camera.enumerate_devices.return_value = (0, [])

    main_window.handle_connect(True)
    assert main_window.capability_tier is CapabilityTier.IDLE

    main_window.handle_connect(True)
    assert main_window.capability_tier is CapabilityTier.NO_DEVICE
    assert "USB" in main_window.camera_control.capture_btn.toolTip()
```

同一次改动里迁移 4 处既有调用（`tests/test_gui.py:42`、`:58`、`:387`、`:1012`）：

```python
    control.set_connected(True)   →   control.apply_capability(CapabilityTier.CONNECTED)
    control.set_connected(False)  →   control.apply_capability(CapabilityTier.IDLE)
```

并在该文件 import 段补 `from polcam.core.capability import CapabilityTier`（若尚未存在）。

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --locked python tools/run_tests.py tests/test_gui.py -k "capability or tier or probe or no_device or downgrades" -q`
Expected: FAIL —`AttributeError: 'MainWindow' object has no attribute 'refresh_capability'`

- [ ] **Step 3: 写最小实现**

`polcam/gui/main_window.py` 顶部 import 段加：

```python
from ..core.capability import CapabilityTier, capability_lines, tier_after_probe
from typing import Optional
```

（`Optional` 若已从 `typing` 导入则不要重复。）

在 `__init__` 里建立状态，并在窗口建好后立刻定档（放在 `self.preview_quality = ...` 那组初始化之后即可，务必早于任何一帧到达）：

```python
        self._capability_tier = CapabilityTier.IDLE
        self._zero_enum_streak = 0
        self._last_device_count: Optional[int] = None
        self._device_count_probed_this_session = False
```

新增两个方法（放在 `handle_connect` 之前）：

```python
    @property
    def capability_tier(self) -> CapabilityTier:
        return self._capability_tier

    def refresh_capability(self, device_count: Optional[int] = None) -> CapabilityTier:
        """唯一的能力档位重算点。

        启动时不主动枚举：update_all_device_list() 有耗时也会抖，而这件事用户点
        “连接相机”时自然会做。所以没探过设备就停在 IDLE，不谎报“没检测到相机”。
        """
        if device_count is None and self._device_count_probed_this_session:
            device_count = self._last_device_count
        try:
            connected = bool(self.camera.is_connected())
        except Exception:
            connected = False

        tier, streak = tier_after_probe(
            sdk_available=getattr(self.camera, "sdk_available", True),
            connected=connected,
            device_count=device_count,
            zero_streak=self._zero_enum_streak,
        )
        self._zero_enum_streak = streak
        self._last_device_count = device_count if device_count is not None else self._last_device_count
        if device_count is not None:
            self._device_count_probed_this_session = True

        if tier is not self._capability_tier:
            self._capability_tier = tier
            self._logger.info(f"相机能力档位: {tier.value}")
        self.camera_control.apply_capability(tier)
        self.image_display.set_capability_lines(capability_lines(tier, self._last_device_count))
        return tier
```

`handle_connect` 里五处 `set_connected(...)` 全部删除，改成在既有分支的末尾统一走 `refresh_capability`。具体：

- 293-305 的无驱动分支：删掉 `self.camera_control.set_connected(False)` 与 `self.status_indicator.setEnabled(False)` 那两行的重复劳动，保留弹窗与 `connect_btn.setChecked(False)`，末尾加：

```python
                self.refresh_capability()
                return
```

- 315-321 的 `device_count == 0` 分支：把 `set_connected(False)` 换成

```python
                self.refresh_capability(device_count=0)
                return
```

并把那句 `QtWidgets.QMessageBox.warning(self, "错误", "未找到相机设备")` 改成只在**已经第二次探到 0** 时才弹窗，避免闪：

```python
            if device_count == 0:
                self.refresh_capability(device_count=0)
                if self.capability_tier is CapabilityTier.NO_DEVICE:
                    QtWidgets.QMessageBox.warning(self, "未找到相机设备", _NO_DEVICE_HINT)
                else:
                    self.status_label.setText("未检测到相机设备，正在重试")
                self.camera_control.connect_btn.setChecked(False)
                return
```

模块级常量放在 `CAMERA_ERROR_DIALOG_INTERVAL_S` 附近：

```python
_NO_DEVICE_HINT = (
    "连续两次枚举都没有发现相机设备。\n"
    "请检查 USB 线与供电，或确认大恒 Galaxy 其他工具没有占用该设备。"
)
```

- 344-349 成功分支：`self.camera_control.set_connected(True)` → `self.refresh_capability()`
- 350-356 失败分支：`self.camera_control.set_connected(False)` → `self.refresh_capability()`
- 370 断开支：`self.camera_control.set_connected(False)` → `self.refresh_capability()`

事件挂钩（`_gui_event_handlers`，70-77 行）已有 `CAMERA_CONNECTED` / `CAMERA_DISCONNECTED` / `ERROR_OCCURRED`，在三个既有处理函数的**末尾**各加一行，不新增订阅：

```python
        self.refresh_capability()
```

（`_on_camera_connected`、`_on_camera_disconnected`、`_on_error`。`_on_error` 里放在 debounce 判断之外——降级与是否弹框是两件事。）

最后，在窗口构造的末尾（`self.show()` 之前的初始化尾部）打第一档：

```python
        self.refresh_capability()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run --locked python tools/run_tests.py tests/test_gui.py -q`
Expected: 全绿（含 Task 2 迁来的 6 条与 4 处既有调用）

- [ ] **Step 5: 提交**

```bash
git add polcam/gui/main_window.py tests/test_gui.py
git commit -m "feat: recalculate the capability tier from camera events"
```

---

### Task 4: 引导页说清「这台机器现在能做什么」

**Files:**
- Modify: `polcam/gui/image_display.py:750-768`（`HELP_SECTIONS`）
- Modify: `polcam/gui/image_display.py:770-840`（`_create_help_overlay` 里为该段留一个可更新的标签）
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `capability_lines()`（Task 1）、`MainWindow.refresh_capability()`（Task 3）
- Produces: `ImageDisplay.set_capability_lines(lines: Sequence[str]) -> None`、`ImageDisplay.capability_lines() -> List[str]`

- [ ] **Step 1: 写失败的测试**

在 `tests/test_gui.py` 追加：

```python
def test_the_guide_page_carries_a_capability_section(qtbot, main_window):
    main_window.camera.sdk_available = False
    main_window.refresh_capability()

    lines = main_window.image_display.capability_lines()
    assert lines
    assert any("驱动" in line for line in lines), "引导页要说出当前这一档"


def test_the_guide_section_matches_the_tier_without_rebuilding_the_widget(qtbot, main_window):
    main_window.camera.sdk_available = True
    main_window.camera.is_connected.return_value = False
    idle = main_window.refresh_capability() and main_window.image_display.capability_lines()

    main_window.camera.is_connected.return_value = True
    main_window.refresh_capability()
    connected = main_window.image_display.capability_lines()

    assert idle != connected
    assert any("已连接" in line for line in connected)


def test_the_capability_widget_survives_a_window_resize(qtbot, main_window):
    """引导页在 QScrollArea 里，窗口小应当滚动而不是把字裁掉。"""
    from qtpy import QtWidgets

    main_window.refresh_capability()
    scroller = main_window.image_display.help_view.findChild(QtWidgets.QScrollArea)
    assert scroller is not None
    assert scroller.horizontalScrollBarPolicy() == QtWidgets.QScrollBar.ScrollBarAlwaysOff
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run --locked python tools/run_tests.py tests/test_gui.py -k capability_section or capability_lines or capability_widget -q`
Expected: FAIL —`AttributeError: 'ImageDisplay' object has no attribute 'set_capability_lines'`

- [ ] **Step 3: 写最小实现**

`polcam/gui/image_display.py`：`HELP_SECTIONS` 保持原样（那是与设备无关的通用说明），在 `_create_help_overlay()` 里 `column` 构建完三段之后、`return page` 之前插入这段（变量名沿用该方法里已有的 `content` / `column` / `make_label`）：

```python
        # 能力清单是当前机器的事实，不是固定文案，所以单独留一个标签，
        # 档位变化时只换文本，不重建控件。
        cap_title = make_label("这台机器现在能做什么", Styles.get_bold_font(Styles.FONT_MEDIUM))
        column.addWidget(cap_title)
        self._capability_label = make_label("", Styles.get_font(Styles.FONT_MEDIUM))
        self._capability_label.setWordWrap(True)
        self._capability_label.setTextFormat(QtCore.Qt.PlainText)
        column.addWidget(self._capability_label)
        self._capability_lines: List[str] = []
```

同文件加两个方法（放在 `show_help_view` 之前）：

```python
    def set_capability_lines(self, lines: Sequence[str]) -> None:
        """更新引导页的能力清单。不要求引导页此刻可见——它随时可能被再次打开。"""
        self._capability_lines = list(lines)
        if hasattr(self, "_capability_label"):
            self._capability_label.setText("\n".join(self._capability_lines))

    def capability_lines(self) -> List[str]:
        return list(getattr(self, "_capability_lines", []))
```

`Sequence` / `List` 从 `typing` 导入（该文件若已导入 `List` 就只补 `Sequence`）。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run --locked python tools/run_tests.py tests/test_gui.py -q`
Expected: 全绿

- [ ] **Step 5: 提交**

```bash
git add polcam/gui/image_display.py tests/test_gui.py
git commit -m "feat: state on the guide page what this machine can do"
```

---

### Task 5: 文档与全量验证

**Files:**
- Modify: `README.md:148`
- Modify: `README.md` 功能特性段（`### 图像处理` / `### 用户界面` 附近）
- Test: 全量套件

**Interfaces:**
- Consumes: Task 1–4 的行为
- Produces: 与实际能力一致的对外说明

- [ ] **Step 1: 改 README 那句误导的兜底话**

`README.md:148` 原文：

```markdown
另外：本机没装大恒 Galaxy 驱动也能启动，此时相机连接与采集不可用，但仍可通过工具栏读取已保存的原始图像做处理。
```

替换为（中文段；要点是**别假设读者手里已经有 PolCam 的 RAW 文件**）：

```markdown
另外：本机没装大恒 Galaxy 驱动也能启动。此时相机连接与采集不可用，应用会直接把单帧采集、连续采集、曝光/增益等按钮禁用并在悬停时说明原因，你仍然可以读取图像文件、切换显示模式、调节亮度对比度锐化并保存处理结果——但**本软件不附带示例图像**，没有相机就没有偏振数据可看。

运行中的能力边界会同时显示在工具栏「帮助」打开的引导页上（“这台机器现在能做什么”），它随连接状态变化。
```

- [ ] **Step 2: 补上 v1.1.0 两个没人写的用户可见行为**

在 `### 图像处理` 列表末尾追加两行：

```markdown
  - 实时预览分辨率档（原始 / 均衡 2×2 合并 / 流畅 4×4 合并 / 自动挡），连续采集时按窗口大小解算，保存结果仍用全分辨率
  - 连接时把链路带宽上限提升到设备允许的最大值（实测本机 300 → 400 MB/s，帧率 60 → 79 fps）
```

英文段（`## English` 下的对应列表）同步加等价两句，用英文写。

- [ ] **Step 3: 跑全量测试**

Run: `uv run --locked python tools/run_tests.py -q`
Expected: `all 21 test files passed`（新增 `tests/test_capability.py` 之后是 21 个文件；以实际输出为准）

- [ ] **Step 4: 真机验证（有相机这台机器）**

Run: `uv run --locked python -` 之后在脚本里按现有探针风格起窗口，依次断言并打印计数：

```python
# .probe/capability_check.py（本地，不入库）
# 1) 启动即 IDLE：采集灰、连接可点、tooltip 是“尚未连接”
# 2) 点连接 → CONNECTED：采集亮、tooltip 清空、引导页出现“相机已连接”
# 3) 连续采集中 capture_btn 仍灰（stream  outranks tier）
# 4) 断开 → 回到 IDLE
# 5) 交替 6 轮 连接/断开 + 中途缩放 + 中途改曝光，断言 0 条 WARNING/ERROR 日志
```

Expected: 每步断言成立，且第 5 步 6 轮里 `采集错误=0`、日志里 `WARNING`/`ERROR` 行数为 0。

- [ ] **Step 5: 提交**

```bash
git add README.md
git commit -m "docs: state what the app can do without a camera attached"
```

---

## Self-Review

**1. Spec coverage（对 `docs/adr/0001`）**

| ADR 条目 | 落在哪个任务 |
| --- | --- |
| 三档（无驱动/无设备/已连接）各自给原因 | Task 1（四态 + 文案唯一性）；"有设备但未连接"命名为 `IDLE`，用的是通用文案"尚未连接相机，点连接相机"，不谎报没设备——这是对 ADR 措辞的一处收窄，需要补一句进 ADR |
| 被占用不做档 | Task 1 未给它任何状态；Task 3 Step 3 的 `_NO_DEVICE_HINT` 只把"可能被别的程序占用"作为**提示**而非判定 |
| 只锁设备写入类 | Task 2 Step 3 的控件清单；缩放明确排除并在注释里写明理由 |
| 连接相机永不禁用 | Task 2 `test_the_connect_button_stays_clickable_in_every_tier` |
| 事件驱动 + 防抖 | Task 3 `test_one_failed_enumeration_keeps_idle_and_two_report_no_device`、`test_the_capture_error_downgrades_the_live_view` |
| tooltip + 引导页，不占状态栏 | Task 2 tooltip、Task 4 引导页；全程未新增状态栏文本 |
| 不打包样例、改 README 148 行 | Task 5 |
| 已知未验证：真实无驱动环境没跑过 | Task 5 Step 4 只做"有相机这台机器"，报告里必须继续标为未验证 |

缺口：ADR 的"硬件 ROI 缩放"被本计划从设备写入集合里移出（未连接时缩放走软件路径，是真实能力）。要么接受这个偏离并在 ADR 补一行，要么改需求。**建议在 Task 5 之前先与用户确认。**

**2. Placeholder scan**：Task 5 Step 4 的真机脚本只给了断言清单没给完整代码——因为 `.probe/` 探针按仓库惯例不入库且需沿用现有探针的窗口构造样板；执行到该步时按 `.probe/soak_preview.py` 的现成骨架写，并把打印出的实际计数贴回报告。这是本计划唯一一处刻意留白。

**3. 类型一致性**：`apply_capability(tier)`（Task 2 定义，Task 3 调用）、`refresh_capability(device_count=None) -> CapabilityTier`（Task 3）、`set_capability_lines(lines)` / `capability_lines()`（Task 4，Task 3 调用）、`tier_after_probe(...) -> (CapabilityTier, int)` 与 `capability_lines(tier, device_count) -> List[str]`（Task 1，Task 3 调用）、`CapabilityTier.device_writes_allowed`（Task 1 定义，Task 2/3 读）——签名在各任务间一致。
