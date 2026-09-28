"""波片 + 4 线偏分析位置的 Stokes 测量模型。

这里钉住的是数学事实，不是硬件读数：等自动转角的拨片到货后，用已知旋度的光去校核的
只有"正号算右旋还是左旋"这一个约定，其余判据（秩、哪个分量定得住、条件数）都由测量
矩阵本身决定。
"""

import numpy as np
import pytest

from polcam.core.polarization_model import (
    make_solver,
    measurement_matrix,
    solve_stokes,
)


def test_no_retarder_reduces_to_the_legacy_estimator():
    """Γ=0 时解算式必须退回代码原来那组：S0=ΣI/2、S1=I0-I90、S2=I45-I135。"""
    solver = make_solver([0.0], retardance_deg=0.0)

    assert np.allclose(solver.projector[0], [0.5, 0.5, 0.5, 0.5])
    assert np.allclose(solver.projector[1], [1.0, 0.0, -1.0, 0.0])
    assert np.allclose(solver.projector[2], [0.0, 1.0, 0.0, -1.0])
    # 没有波片就测不到 S3，这一行必须全零，不能给出假值
    assert np.allclose(solver.projector[3], 0.0)
    assert solver.rank == 3
    assert not solver.docp_determined
    assert solver.dolp_determined
    assert solver.unmeasurable == ("S3",)


def test_single_angle_with_qwp_measures_s3_but_loses_a_linear_component():
    """装上 1/4 波片后 S3 定得住，代价是丢掉一个线偏分量。

    算出来这些矩阵的秩：α=0 少 S2、α=45 少 S1、α=22.5 时没有零列但秩仍是 3，
    条件数在 1e16 量级（伪逆会把噪声放大成假信号）。
    """
    at_zero = make_solver([0.0])
    assert at_zero.rank == 3
    assert at_zero.docp_determined
    assert not at_zero.dolp_determined
    assert at_zero.unmeasurable == ("S2",)

    at_45 = make_solver([45.0])
    assert at_45.docp_determined
    assert at_45.unmeasurable == ("S1",)

    at_22_5 = make_solver([22.5])
    assert at_22_5.rank == 3
    assert at_22_5.unmeasurable == ()
    assert at_22_5.condition > 1e12
    assert not at_22_5.dolp_determined


def test_two_angles_determine_everything():
    solver = make_solver([0.0, 45.0])

    assert solver.rank == 4
    assert solver.complete
    assert solver.determined == ("S0", "S1", "S2", "S3")
    assert solver.condition < 5.0


@pytest.mark.parametrize("angles", [(0.0, 45.0), (10.0, 55.0), (0.0, 30.0, 60.0)])
def test_round_trip_recovers_the_input_stokes(angles):
    """连续读数（不量化）必须精确还原四个分量：这是解算式本身的正确性。"""
    true_stokes = np.array([100.0, 30.0, -20.0, 40.0])
    solver = make_solver(list(angles))
    design = np.vstack([measurement_matrix(angle) for angle in angles])
    readings = design @ true_stokes

    recovered = solve_stokes([np.full((2, 2), value) for value in readings], solver)

    for index, name in enumerate(("S0", "S1", "S2", "S3")):
        assert np.allclose(recovered[index], true_stokes[index], atol=1e-9), name


def test_quantized_readings_stay_inside_the_derivable_error_bound():
    """真帧是 uint8，半格量化误差会被伪逆放大，上限就是 |projector| 的行和。

    条件数差的角对（这里用 10°/55°）放大得比 0°/45° 明显，所以拨片给角度时要看这个
    上限而不是只看秩。
    """
    angles = [10.0, 55.0]
    true_stokes = np.array([100.0, 30.0, -20.0, 40.0])
    solver = make_solver(angles)
    design = np.vstack([measurement_matrix(angle) for angle in angles])
    frames = [np.full((2, 2), int(round(value)), dtype=np.uint8)
              for value in design @ true_stokes]

    recovered = [float(frame[0, 0]) for frame in solve_stokes(frames, solver)]
    bound = 0.5 * np.abs(solver.projector).sum(axis=1)

    for index, name in enumerate(("S0", "S1", "S2", "S3")):
        assert abs(recovered[index] - true_stokes[index]) <= bound[index] + 1e-6, name
    assert bound.max() > 0.5, "这组角度确实在放大量化误差，测试才有意义"


def test_solve_stokes_checks_the_number_of_frames():
    solver = make_solver([0.0, 45.0])

    with pytest.raises(ValueError, match="读数有 4 组"):
        solve_stokes([np.zeros((2, 2), dtype=np.uint8) for _ in range(4)], solver)


def test_no_retarder_fill_is_a_minimum_norm_fake_value():
    """秩不够时缺的分量会被填成 0：这是最小范数解，不是测量值。"""
    single = make_solver([0.0])
    design = measurement_matrix(0.0)
    true_stokes = np.array([100.0, 30.0, -20.0, 40.0])
    frames = [np.full((2, 2), int(value), dtype=np.uint8)
              for value in design @ true_stokes]

    recovered = [float(frame[0, 0]) for frame in solve_stokes(frames, single)]

    assert abs(recovered[0] - 100.0) < 1.5
    assert abs(recovered[1] - 30.0) < 1.5
    assert abs(recovered[3] - 40.0) < 1.5
    assert recovered[2] == pytest.approx(0.0), "S2 没定住，伪逆应给出最小范数解"
