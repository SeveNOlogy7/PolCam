"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.

能力档位要说给用户的句子。

`core/capability.py` 只讲事实（哪个档位、几台设备、屏上像素从哪来），措辞在这里 ——
理由不是分层洁癖：Qt Linguist 只认**直接写在 `translate()` 实参里的字面量**（连
`tr = QCoreApplication.translate` 这种 shorthand 都不认），句子留在 core 里就进不了
目录，切语言时那几行会永远停在中文。
"""
from typing import List, Optional

from qtpy import QtCore

from ..core.capability import CapabilityTier

CONTEXT = "capability"


def reason(tier: CapabilityTier) -> str:
    """禁用设备写入控件时要显示的理由；空串表示这一档不禁用。

    四个档的理由必须各不相同：用户的修法各不相同，写成一句等于没写。
    """
    if tier is CapabilityTier.NO_DRIVER:
        return QtCore.QCoreApplication.translate(
            CONTEXT, "未检测到大恒 Galaxy 驱动，安装驱动后才能采集")
    if tier is CapabilityTier.NO_DEVICE:
        return QtCore.QCoreApplication.translate(
            CONTEXT, "未检测到相机设备，检查 USB 与供电")
    if tier is CapabilityTier.CONNECTED:
        return ""
    return QtCore.QCoreApplication.translate(CONTEXT, "尚未连接相机，点“连接相机”")


def capability_lines(tier: CapabilityTier, device_count: Optional[int],
                     pixels_from_file: bool = False) -> List[str]:
    """引导页「这台机器现在能做什么」那一段。

    清单讲的是**此刻**，所以连着相机时采集要出现在"现在就能做"里，而不是只留一句
    "相机已连接"；缩放那条也一样，连着相机改的是设备 ROI，未连接才是软件缩放。
    """
    lines = [QtCore.QCoreApplication.translate(CONTEXT, "现在就能做：")]
    if tier is CapabilityTier.CONNECTED:
        lines.append("· " + QtCore.QCoreApplication.translate(CONTEXT, "单帧采集与连续采集"))
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "曝光与增益（含单次自动）"))
    lines.append("· " + QtCore.QCoreApplication.translate(CONTEXT, "读取已保存的原始图像"))
    lines.append("· " + QtCore.QCoreApplication.translate(
        CONTEXT, "切换显示模式、调亮度对比度锐化、保存处理结果"))
    if tier is CapabilityTier.CONNECTED:
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "缩放与框选（连着相机时改的是设备 ROI）"))
    else:
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "缩放与框选（未连接相机时是软件缩放，不改设备）"))

    if tier is CapabilityTier.CONNECTED:
        lines.append(QtCore.QCoreApplication.translate(
            CONTEXT, "相机已连接，采集与参数写入均可用。"))
        return lines

    lines.append(QtCore.QCoreApplication.translate(CONTEXT, "接上相机才能做："))
    if tier is CapabilityTier.NO_DRIVER:
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "采集图像 —— 需要先安装大恒 Galaxy 驱动（README 有下载链接）"))
    elif tier is CapabilityTier.NO_DEVICE:
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "采集图像 —— 连续两次枚举都没发现设备，检查 USB 与供电"))
    elif device_count is None:
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "采集图像 —— 还没连接（尚未探测设备数量），点左侧“连接相机”"))
    else:
        # %1 而不是 f-string：f-string 不是字面量，lupdate 扫不到整句
        lines.append("· " + QtCore.QCoreApplication.translate(
            CONTEXT, "采集图像 —— 还没连接（发现 %1 台相机），点左侧“连接相机”"
            ).replace("%1", str(device_count)))
    return lines


def help_subtitle(tier: CapabilityTier, has_image: bool, pixels_from_file: bool) -> str:
    """引导页副标题：一句关于"此刻屏上有什么"的事实。

    写死成"尚未载入图像"会在连着相机出图时变成假话（真机截图里就是这句最扎眼）。
    """
    if not has_image:
        return QtCore.QCoreApplication.translate(CONTEXT, "尚未载入图像，可按下面的步骤开始")
    if tier is CapabilityTier.CONNECTED:
        return QtCore.QCoreApplication.translate(
            CONTEXT, "相机已连接，屏上正在显示采集到的图像")
    if pixels_from_file:
        return QtCore.QCoreApplication.translate(CONTEXT, "屏上显示的是导入的图像文件")
    return QtCore.QCoreApplication.translate(CONTEXT, "相机未连接，屏上仍是上一次采集到的图像")
