"""偏振仪器的 Stokes 测量模型：波片（可选）+ 4 个线偏分析位置。

约定（本模块内部自洽，符号约定一旦和拨片标定对上就固定下来）：

    Stokes  S = (S0, S1, S2, S3)
    相干矩阵 C = [[S0+S1, S2+iS3], [S2-iS3, S0-S1]] / 2
    快轴在 α、延迟量 Γ 的波片 Jones 阵： R(-α)·diag(1, e^{iΓ})·R(α)
    在 θ 处的理想线偏器测得：            I(θ) = Tr(Pθ · J C J†),  Pθ = uθ uθᵀ

于是一组 (α, Γ) 给出一个 4x4 的测量矩阵 A，满足 d = A·S，d = (I0, I45, I90, I135)。
Γ=0 时 A 退化成的解算式就是代码里原来那组（S0=(ΣI)/2、S1=I0-I90、S2=I45-I135），
这条等价关系由测试钉住。

单个 α 时 A 的秩只有 3 —— 少掉的不是一个分量而是"一个自由度"：实测 α=0 时 S2 整列为零、
α=45 时 S1 整列为零、α=15/22.5/30/60 时没有零列但条件数在 1e16 量级（伪逆会把噪声放大成
假信号）。所以"装了波片"不等于"四个 Stokes 都能测"：要么按 determined 判据只报定住的
分量（单个 α=0 已经能定住 S3，所以带符号 DoCP 有意义，而 DoLP 只是部分量），要么像自动
转角的拨片那样给多个 α 各采一帧，把行数叠到 4N 再最小二乘（实测两个角度条件数 2~3.7）。

符号约定：本模块里 S3 = 2·Im(Ex·conj(Ey))，α=0 的 QWP 给出 S3 ∝ I045 - I135。真正的
旋向标签（正号算右旋还是左旋）要等拨片到货用已知旋度的光标定，届时改这一个约定即可，
不要改各处散布的公式。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

ANALYZER_ANGLES_DEG = (0.0, 45.0, 90.0, 135.0)
# 4 个分析位置在 8bit 帧上能表示的最小非零列，用来判断某个 Stokes 分量是不是根本没被测到
RANK_TOLERANCE = 1e-9


def _coherency(stokes: np.ndarray) -> np.ndarray:
    s0, s1, s2, s3 = stokes
    return 0.5 * np.array([[s0 + s1, s2 + 1j * s3],
                           [s2 - 1j * s3, s0 - s1]], dtype=np.complex128)


def measurement_matrix(fast_axis_deg: float = 0.0,
                       retardance_deg: float = 90.0,
                       analyzer_angles_deg: Sequence[float] = ANALYZER_ANGLES_DEG) -> np.ndarray:
    """一组 (快轴角度, 延迟量) 下，4 个线偏位置的测量矩阵 A（d = A·S）。

    逐列构造：喂进第 k 个单位 Stokes，量到的 4 个强度就是 A 的第 k 列，因为整个链路
    对相干矩阵是线性的。
    """
    alpha = np.deg2rad(fast_axis_deg)
    gamma = np.deg2rad(retardance_deg)
    rotator = np.array([[np.cos(alpha), np.sin(alpha)],
                        [-np.sin(alpha), np.cos(alpha)]], dtype=np.complex128)
    jones = rotator.conj().T @ np.diag([1.0 + 0.0j, np.exp(1j * gamma)]) @ rotator

    matrix = np.zeros((len(analyzer_angles_deg), 4), dtype=np.float64)
    for column in range(4):
        basis = np.zeros(4)
        basis[column] = 1.0
        coherent = jones @ _coherency(basis) @ jones.conj().T
        for row, theta_deg in enumerate(analyzer_angles_deg):
            theta = np.deg2rad(theta_deg)
            direction = np.array([np.cos(theta), np.sin(theta)], dtype=np.complex128)
            projector = np.outer(direction, direction.conj())
            matrix[row, column] = float(np.real(np.trace(projector @ coherent)))
    return matrix


def design_matrix(fast_axis_degrees: Sequence[float],
                  retardance_deg: float = 90.0,
                  analyzer_angles_deg: Sequence[float] = ANALYZER_ANGLES_DEG) -> np.ndarray:
    """多个快轴角度时把每组的 4 行叠起来（4N x 4），一次最小二乘解全部 Stokes。"""
    if not len(fast_axis_degrees):
        raise ValueError("至少要给一个快轴角度")
    return np.vstack([measurement_matrix(angle, retardance_deg, analyzer_angles_deg)
                      for angle in fast_axis_degrees])


@dataclass(frozen=True)
class StokesSolver:
    """把某组 (α...) 的读数投影回 Stokes 的东西，连同这次测量能不能测全的判断。

    projector 是设计矩阵的伪逆（4x4N），所以调用方对图像栈做一次 tensordot 就够了，
    不用逐像素 lstsq。rank/determined 说明这次配置到底定住了哪几个分量：秩不到 4 时
    伪逆给的是最小范数解，那个"没定住"的分量是算出来的假值，不能当测量结果用。
    """

    fast_axis_degrees: tuple
    retardance_deg: float
    projector: np.ndarray
    rank: int
    condition: float
    determined: tuple  # 这一组配置真正定住的 Stokes 分量名
    unmeasurable: tuple  # 整列都是零、完全没进探测器的分量名

    def is_determined(self, name: str) -> bool:
        return name in self.determined

    @property
    def complete(self) -> bool:
        return self.rank == 4

    @property
    def docp_determined(self) -> bool:
        """带符号的 DoCP 要 S3 定住才有意义。"""
        return self.is_determined("S3")

    @property
    def dolp_determined(self) -> bool:
        """DoLP/AoLP 要 S1 和 S2 同时定住，缺一个就只是部分量。"""
        return self.is_determined("S1") and self.is_determined("S2")


STOKES_NAMES = ("S0", "S1", "S2", "S3")


def _determined_components(design: np.ndarray, rank: int) -> tuple:
    """某列去掉后秩会下降，就说明那个分量真的被这组配置定住了。"""
    determined = []
    for column, name in enumerate(STOKES_NAMES):
        reduced = np.delete(design, column, axis=1)
        if int(np.linalg.matrix_rank(reduced, tol=RANK_TOLERANCE)) < rank:
            determined.append(name)
    return tuple(determined)


def make_solver(fast_axis_degrees: Sequence[float],
                retardance_deg: float = 90.0,
                analyzer_angles_deg: Sequence[float] = ANALYZER_ANGLES_DEG) -> StokesSolver:
    design = design_matrix(fast_axis_degrees, retardance_deg, analyzer_angles_deg)
    projector = np.linalg.pinv(design, rcond=RANK_TOLERANCE)
    rank = int(np.linalg.matrix_rank(design, tol=RANK_TOLERANCE))
    # 哪一列在整个设计矩阵里都是零，就是完全没有被测到的分量
    column_norms = np.linalg.norm(design, axis=0)
    unmeasurable = tuple(name for name, norm in zip(STOKES_NAMES, column_norms)
                         if norm <= RANK_TOLERANCE)
    condition = float(np.linalg.cond(design)) if rank else float("inf")
    return StokesSolver(
        fast_axis_degrees=tuple(float(angle) for angle in fast_axis_degrees),
        retardance_deg=float(retardance_deg),
        projector=projector,
        rank=rank,
        condition=condition,
        determined=_determined_components(design, rank),
        unmeasurable=unmeasurable,
    )


def solve_stokes(intensities: Sequence[np.ndarray], solver: StokesSolver) -> tuple:
    """把每个分析位置一张图（4 张 x 角度数）投影成 (S0, S1, S2, S3) 四张图。

    Args:
        intensities: 长度 = 4 * len(solver.fast_axis_degrees) 的图像栈，顺序和
            design_matrix 的行一致（先按角度、每个角度内按 0/45/90/135）
        solver: make_solver 的结果
    Returns:
        (S0, S1, S2, S3) 四个 float64 数组
    """
    stack = np.stack([np.asarray(frame, dtype=np.float64) for frame in intensities])
    if stack.shape[0] != solver.projector.shape[1]:
        raise ValueError(
            f"读数有 {stack.shape[0]} 组，但解算器按 {solver.projector.shape[1]} 组建模")
    solved = np.tensordot(solver.projector, stack, axes=([1], [0]))
    return tuple(solved[i] for i in range(4))
