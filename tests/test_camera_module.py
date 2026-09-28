"""
MIT License
Copyright (c) 2024-2026 Junhao Cai
See LICENSE file for full license details.
"""

import pytest
import time
from unittest.mock import MagicMock, patch
import numpy as np
from polcam.core.camera_module import CameraModule, CameraType
from polcam.core.events import EventType

@pytest.fixture
def camera_module():
    with patch('gxipy.DeviceManager') as mock_dm:
        module = CameraModule()
        mock_dm.return_value.update_all_device_list.return_value = (1, ['dev1'])
        
        # 创建模拟设备和远程功能控制
        mock_device = MagicMock()
        mock_remote_feature = MagicMock()
        mock_dm.return_value.open_device_by_index.return_value = mock_device
        mock_device.get_remote_device_feature_control.return_value = mock_remote_feature
        
        # 浮点参数替身要像真机那样"写进去再读回来"。真机实测：超量程或被自动模式接管的
        # 写入会被静默丢掉，回读值才是设备的真实状态，所以不能把 get 钉死在一个常数上。
        float_holdings = {'ExposureTime': 10000.0, 'Gain': 0.0}

        def fake_float_feature(name):
            feature = MagicMock()
            feature.set.side_effect = lambda value: float_holdings.__setitem__(name, float(value))
            feature.get.side_effect = lambda: float_holdings[name]
            return feature

        mock_remote_feature.get_float_feature.side_effect = fake_float_feature
        # EnumFeature.get() 返回 (枚举值, 描述字符串)，替身必须照真实形状给，
        # 给成裸字符串会让“按字符串比较”的错误代码看起来也是对的
        mock_remote_feature.get_enum_feature.return_value.get.return_value = (0, "Off")
        
        yield module

def test_unknown_model_uses_the_device_pixel_formats(camera_module):
    """型号不在映射表时按设备自报的像素格式判断，而不是一律当彩色偏振。

    实测偏振相机的 PixelColorFilter 不可读（InvalidAccess），所以原来那条"按
    PixelColorFilter 推断"的路在偏振机型上永远走不到；PixelFormat 的候选列表是读得到的。
    """
    camera_module.initialize()
    camera_module.start()
    camera_module._camera.PixelColorFilter.is_implemented.return_value = False
    camera_module._bayer_pattern = None

    camera_module._remote_feature.get_enum_feature.return_value.get_range.return_value = [
        {'value': 17301505, 'symbolic': 'Mono8'}, {'value': 17825795, 'symbolic': 'Mono10'}]
    assert camera_module._detect_camera_type("MER9-NEW-99U3M POL") is CameraType.MONO

    camera_module._remote_feature.get_enum_feature.return_value.get_range.return_value = \
        {'BayerRG8': 7, 'Mono8': 1}
    assert camera_module._detect_camera_type("MER9-NEW-99GC POL") is CameraType.COLOR

    camera_module._remote_feature.get_enum_feature.return_value.get_range.return_value = []
    assert camera_module._detect_camera_type("MER9-WEIRD") is CameraType.COLOR


def test_second_connect_keeps_the_live_device(camera_module):
    """已经连着的时候再 connect() 不该去抢下一个索引。

    真机实测：_do_start 会自动连接，此后再 connect() 会拿 index=2 去
    open_device_by_index，只有一台相机时设备层直接报 "invalid index"，而失败路径把正在
    用的那台关掉并置为未连接 —— 一次多余的连接请求就能把好的连接弄断。
    """
    camera_module.initialize()
    camera_module.start()
    assert camera_module.is_connected()
    device = camera_module._camera
    camera_module.device_manager.open_device_by_index.reset_mock()

    assert camera_module.connect() is True
    camera_module.device_manager.open_device_by_index.assert_not_called()
    assert camera_module._camera is device

    # 显式选设备时不能被他挡住：断开后仍然要能重新打开
    camera_module.disconnect()
    assert camera_module.connect() is True


def _device_float_feature(camera_module, held, accepts=True):
    """给一个"写进去能读回来"的浮点参数替身（真机的行为），accepts=False 用来模拟拒绝。"""
    feature = MagicMock()

    def apply(value):
        if accepts:
            held[0] = float(value)

    feature.set.side_effect = apply
    feature.get.side_effect = lambda: held[0]
    camera_module._remote_feature.get_float_feature.side_effect = lambda name: feature
    return feature


def test_out_of_range_exposure_reports_the_device_range_not_a_modal(camera_module):
    """超范围写入要说清范围并走状态栏，不该把 SDK 原文塞进错误弹窗。

    真机实测：量程 20us-1s，写 19us 抛
    OutOfRange{-11}{Value 19.0 must be greater than or equal 20.0}。
    """
    camera_module.initialize()
    camera_module.start()
    feature = MagicMock()
    feature.set.side_effect = RuntimeError(
        "FloatFeature_s.set:{-11}{Value 19.000000 must be greater than or equal 20.000000.}")
    feature.get_range.return_value = {'min': 20.0, 'max': 1000000.0, 'inc': 0.0, 'unit': 'us'}
    camera_module._remote_feature.get_float_feature.side_effect = lambda name: feature
    published = {}

    def record(event_type, data=None):
        published.setdefault(event_type, []).append(data)

    camera_module.publish_event = record

    camera_module.set_exposure_time(19.0)

    assert EventType.STATUS_MESSAGE_UPDATE in published
    message = published[EventType.STATUS_MESSAGE_UPDATE][0]['message']
    assert "20.0" in message and "1000000.0" in message, message
    assert EventType.ERROR_OCCURRED not in published, "可预见的拒绝不该弹模态框"
    assert camera_module.get_last_exposure() == 10000.0, "写没成就该保持原值，别记一个假值"


def test_write_owned_by_auto_exposure_names_the_auto_mode(camera_module):
    """自动曝光接管时写曝光抛的是 InvalidAccess，得告诉用户先关自动。"""
    camera_module.initialize()
    camera_module.start()
    feature = MagicMock()
    feature.set.side_effect = RuntimeError("FloatFeature_s.set:{-8}{Node is not writable.}")
    camera_module._remote_feature.get_float_feature.side_effect = lambda name: feature
    camera_module._remote_feature.get_enum_feature.return_value.get.return_value = (1, "Continuous")
    messages = []

    def record(event_type, data=None):
        if event_type == EventType.STATUS_MESSAGE_UPDATE:
            messages.append((data or {}).get('message', ''))

    camera_module.publish_event = record

    camera_module.set_exposure_time(20000.0)

    assert messages and "自动曝光" in messages[0] and "Continuous" in messages[0], messages


def test_reconnect_skips_parameters_the_device_refuses(camera_module):
    """重连时不要硬写被自动模式接管的参数：每次重连冒一条"设不成"的提示是噪音。"""
    camera_module.initialize()
    camera_module.start()
    camera_module._last_params['exposure'] = 20000.0
    feature = MagicMock()
    feature.is_writable.return_value = False

    def explode(value):
        raise AssertionError("不可写的参数不该被写")

    feature.set.side_effect = explode
    camera_module._remote_feature.get_float_feature.side_effect = lambda name: feature
    published = []
    camera_module.publish_event = lambda event_type, data=None: published.append(event_type)

    camera_module._restore_cached_parameters()

    assert EventType.STATUS_MESSAGE_UPDATE not in published
    assert EventType.ERROR_OCCURRED not in published


def test_accepted_exposure_write_publishes_no_complaint(camera_module):
    camera_module.initialize()
    camera_module.start()
    held = [10000.0]
    _device_float_feature(camera_module, held, accepts=True)
    published = []
    camera_module.publish_event = lambda event_type, data=None: published.append(event_type)

    camera_module.set_exposure_time(20000.0)

    assert camera_module.get_last_exposure() == 20000.0
    assert published == [EventType.PARAMETER_CHANGED]


def test_grab_timeout_follows_exposure_but_stays_under_the_join_budget(camera_module):
    """500ms 曝光不该用 100ms 轮询；但等待窗口必须留在停流预算之内。"""
    camera_module._last_params['exposure'] = 10000.0
    assert camera_module._grab_timeout_ms() == camera_module.GRAB_TIMEOUT_MS

    camera_module._last_params['exposure'] = 500000.0
    assert camera_module._grab_timeout_ms() == 550

    camera_module._last_params['exposure'] = 1000000.0
    timeout = camera_module._grab_timeout_ms()
    assert timeout == 1050, "1s 曝光留 50ms 余量"
    assert timeout / 1000.0 < camera_module.STREAM_JOIN_TIMEOUT_S
    camera_module._last_params['exposure'] = 5000000.0
    assert camera_module._grab_timeout_ms() == camera_module.GRAB_TIMEOUT_MAX_MS


def test_silent_starvation_is_said_once_and_resets_on_a_frame(camera_module):
    """采集开着却一帧不来（实测触发模式为 On 就是这样），要说一次而不是永远不说。"""
    camera_module.initialize()
    camera_module.start()
    published = []
    camera_module.publish_event = lambda event_type, data=None: published.append(event_type)
    camera_module._is_streaming = True

    empty = MagicMock()
    empty.get_numpy_array.return_value = None
    camera_module._camera.data_stream[0].get_image.return_value = empty
    camera_module._last_frame_at = time.perf_counter() - 10.0

    camera_module._stream_once()
    camera_module._stream_once()
    assert published.count(EventType.STATUS_MESSAGE_UPDATE) == 1, "重复刷屏或干脆不说都不对"

    filled = MagicMock()
    filled.get_numpy_array.return_value = np.zeros((8, 8), dtype=np.uint8)
    camera_module._camera.data_stream[0].get_image.return_value = filled
    camera_module._stream_once()
    assert EventType.FRAME_CAPTURED in published

    camera_module._camera.data_stream[0].get_image.return_value = empty
    camera_module._last_frame_at = time.perf_counter() - 10.0
    camera_module._stream_once()
    assert published.count(EventType.STATUS_MESSAGE_UPDATE) == 2


def test_to_pipeline_uint8_downshifts_wide_frames(camera_module):
    """10bit 帧必须在进应用的那一刻降到 8bit。

    实测这台相机 PixelFormat 可选 Mono8/Mono10，Mono10 下 get_numpy_array() 返回右对齐
    的 uint16（取值 0..1022）。降到 uint8 之前，偏振参数计算直接 TypeError，而
    astype(uint8) 会按 256 回绕。
    """
    camera_module._pixel_format_name = "Mono10"
    frame = np.array([[0, 511], [1022, 255]], dtype=np.uint16)

    result = camera_module._to_pipeline_uint8(frame)

    assert result.dtype == np.uint8
    assert result.tolist() == [[0, 127], [255, 63]]


def test_to_pipeline_uint8_leaves_uint8_and_none(camera_module):
    assert camera_module._to_pipeline_uint8(None) is None
    frame = np.zeros((4, 4), dtype=np.uint8)
    assert camera_module._to_pipeline_uint8(frame) is frame


def test_set_roi_keeps_the_device_height_increment(camera_module):
    """黑白偏振相机的纵向 ROI 不必按 4 对齐，按设备步进走。

    实测 MER2-502-79U3M-HS POL 的 Width 步进是 8、Height 步进是 2，MPFA 周期只有 2，
    所以固定按 4 对齐会白丢一半纵向分辨率。
    """
    camera_module.initialize()
    camera_module.start()
    from polcam.core.camera_module import CameraType
    camera_module._camera_type = CameraType.MONO

    def int_feature(minimum, maximum, increment, value):
        feature = MagicMock()
        feature.get_range.return_value = {'min': minimum, 'max': maximum,
                                         'inc': increment, 'value': value}
        feature.get.return_value = value
        return feature

    camera = camera_module._camera
    camera.SensorWidth.get.return_value = 2448
    camera.SensorHeight.get.return_value = 2048
    camera.Width = int_feature(8, 2448, 8, 2448)
    camera.Height = int_feature(4, 2048, 2, 2048)
    camera.OffsetX = int_feature(0, 0, 8, 0)
    camera.OffsetY = int_feature(0, 0, 2, 0)

    assert camera_module.set_roi(0, 0, 1024, 1002) is True

    # 宽度仍是设备的 8 步进，高度回到 2 步进：1002 是合法值，旧代码会砍成 1000
    assert camera.Height.set.call_args.args[0] == 1002
    assert camera.Width.set.call_args.args[0] == 1024


def test_connect_publishes_device_ranges(camera_module):
    """连接事件要带上相机的真实量程，面板才有依据设置滑条。"""
    remote = MagicMock()
    remote.get_float_feature.return_value.get_range.return_value = {
        'min': 30.0, 'max': 800000.0, 'inc': 0.0, 'unit': 'us'}
    camera_module._remote_feature = remote

    assert camera_module.get_parameter_range("ExposureTime") == {
        'min': 30.0, 'max': 800000.0, 'unit': 'us'}

    remote.get_float_feature.return_value.get_range.side_effect = OSError
    assert camera_module.get_parameter_range("Gain") is None

    camera_module._remote_feature = None
    assert camera_module.get_parameter_range("ExposureTime") is None


def test_module_lifecycle(camera_module):
    """测试模块生命周期"""
    # 测试初始化
    assert camera_module.initialize()
    assert camera_module.is_initialized()
    
    # 测试启动
    assert camera_module.start()
    assert camera_module.is_running()
    assert camera_module.is_connected()
    
    # 测试停止
    assert camera_module.stop()
    assert not camera_module.is_running()
    
    # 测试销毁
    assert camera_module.destroy()
    assert not camera_module.is_initialized()
    assert not camera_module.is_connected()

def test_camera_streaming(camera_module):
    """测试图像采集功能"""
    # 初始化并启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 测试开始采集
    camera_module.start_streaming()
    assert camera_module.is_streaming()
    
    # 测试停止采集
    camera_module.stop_streaming()
    assert not camera_module.is_streaming()
    
    # 清理
    camera_module.destroy()

def test_parameter_control(camera_module):
    """测试参数控制"""
    # 初始化并启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 测试曝光控制
    camera_module.set_exposure_time(20000.0)
    assert camera_module.get_last_exposure() == 20000.0
    
    # 测试增益控制
    camera_module.set_gain(10.0)
    assert camera_module.get_last_gain() == 10.0
    
    # 清理
    camera_module.destroy()

def test_event_emission(camera_module):
    """测试事件发送"""
    events_received = []
    
    def on_event(event):
        events_received.append(event)
    
    # 订阅事件
    camera_module.subscribe_event(EventType.CAMERA_CONNECTED, on_event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 初始化并启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证连接事件 - 确保至少接收到了CAMERA_CONNECTED事件
    assert any(event.type == EventType.CAMERA_CONNECTED for event in events_received)
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试参数改变事件
    camera_module.set_exposure_time(20000.0)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数改变事件
    exposure_events = [
        event for event in events_received 
        if event.type == EventType.PARAMETER_CHANGED 
        and event.data.get("parameter") == "exposure"
    ]
    assert len(exposure_events) == 1
    assert exposure_events[0].data["value"] == 20000.0
    
    # 清理
    camera_module.destroy()

def test_frame_capture(camera_module):
    """测试图像采集"""
    # 初始化并启动模块，确保相机连接
    camera_module.initialize()
    camera_module.start()
    
    # 模拟图像数据
    mock_frame = np.zeros((1000, 1000), dtype=np.uint8)
    mock_image = MagicMock()
    mock_image.get_numpy_array.return_value = mock_frame
    mock_stream = MagicMock()
    mock_stream.get_image.return_value = mock_image
    
    # 为相机对象添加数据流
    camera_module._camera.data_stream = [mock_stream]
    
    frames_received = []
    def on_frame(event):
        frames_received.append(event.data["frame"])
    
    # 订阅帧捕获事件
    camera_module.subscribe_event(EventType.FRAME_CAPTURED, on_frame)
    
    # 启动采集
    camera_module.start_streaming()
    
    # 等待接收帧
    time.sleep(0.2)
    
    # 验证接收到的帧
    assert len(frames_received) > 0
    assert isinstance(frames_received[0], np.ndarray)
    assert frames_received[0].shape == (1000, 1000)
    
    # 停止采集并清理
    camera_module.stop_streaming()
    camera_module.destroy()

def test_error_handling(camera_module):
    """测试错误处理"""
    errors_received = []
    
    def on_error(event):
        errors_received.append(event)
    
    camera_module.subscribe_event(EventType.ERROR_OCCURRED, on_error)
    
    # 确保模块已初始化
    camera_module.initialize()
    
    # 模拟设备打开失败
    with patch.object(camera_module.device_manager, 'open_device_by_index') as mock_open:
        mock_open.side_effect = Exception("模拟设备打开失败")
        
        # 尝试连接
        success = camera_module.connect()
        assert not success
        
        # 等待事件处理
        time.sleep(0.1)
        
        # 验证错误事件
        assert len(errors_received) > 0
        error_events = [e for e in errors_received if e.type == EventType.ERROR_OCCURRED]
        assert len(error_events) == 1
        assert "模拟设备打开失败" in error_events[0].data["error"]
        
    # 清理
    camera_module.destroy()

def test_parameter_validation(camera_module):
    """测试参数验证和边界条件"""
    camera_module.initialize()
    camera_module.start()
    
    # 测试正常范围的参数
    camera_module.set_exposure_time(10000.0)
    assert camera_module.get_last_exposure() == 10000.0
    
    camera_module.set_gain(10.0)
    assert camera_module.get_last_gain() == 10.0
    
    # 清理
    camera_module.destroy()

def test_streaming_lifecycle(camera_module):
    """测试流采集的生命周期"""
    camera_module.initialize()
    camera_module.start()
    
    # 测试启动流采集
    camera_module.start_streaming()
    assert camera_module.is_streaming()
    
    # 测试重复启动
    camera_module.start_streaming()  # 不应该有影响
    assert camera_module.is_streaming()
    
    # 测试停止流采集
    camera_module.stop_streaming()
    assert not camera_module.is_streaming()
    
    # 测试重复停止
    camera_module.stop_streaming()  # 不应该有影响
    assert not camera_module.is_streaming()
    
    # 清理
    camera_module.destroy()

def test_module_state(camera_module):
    """测试模块状态管理"""
    # 测试初始状态
    assert not camera_module.is_initialized()
    assert not camera_module.is_running()
    assert not camera_module.is_connected()
    assert not camera_module.is_streaming()
    
    # 测试初始化后的状态
    camera_module.initialize()
    assert camera_module.is_initialized()
    assert not camera_module.is_running()
    
    # 测试启动后的状态
    camera_module.start()
    assert camera_module.is_initialized()
    assert camera_module.is_running()
    assert camera_module.is_connected()
    
    # 测试停止后的状态
    camera_module.stop()
    assert camera_module.is_initialized()
    assert not camera_module.is_running()
    
    # 测试销毁后的状态
    camera_module.destroy()
    assert not camera_module.is_initialized()
    assert not camera_module.is_running()
    assert not camera_module.is_connected()

def test_auto_exposure_control(camera_module):
    """测试自动曝光控制"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    def on_event(event):
        events_received.append(event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 测试自动曝光开关
    camera_module.set_exposure_auto(True)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数变化事件
    exposure_auto_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "exposure_auto")
    ]
    assert len(exposure_auto_events) == 1
    assert exposure_auto_events[0].data["value"] is True
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试单次自动曝光
    camera_module.set_exposure_once()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证曝光值变化事件
    exposure_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "exposure")
    ]
    assert len(exposure_events) == 1
    assert isinstance(exposure_events[0].data["value"], (int, float))
    
    # 清理
    camera_module.destroy()

def test_auto_gain_control(camera_module):
    """测试自动增益控制"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    def on_event(event):
        events_received.append(event)
    camera_module.subscribe_event(EventType.PARAMETER_CHANGED, on_event)
    
    # 测试自动增益开关
    camera_module.set_gain_auto(True)
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证参数变化事件
    gain_auto_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "gain_auto")
    ]
    assert len(gain_auto_events) == 1
    assert gain_auto_events[0].data["value"] is True
    
    # 清除已接收的事件
    events_received.clear()
    
    # 测试单次自动增益
    camera_module.set_gain_once()
    
    # 等待事件处理
    time.sleep(0.1)
    
    # 验证增益值变化事件
    gain_events = [
        e for e in events_received 
        if (e.type == EventType.PARAMETER_CHANGED and 
            e.data.get("parameter") == "gain")
    ]
    assert len(gain_events) == 1
    assert isinstance(gain_events[0].data["value"], (int, float))
    
    # 清理
    camera_module.destroy()

def test_parameter_persistence(camera_module):
    """测试参数持久化"""
    camera_module.initialize()
    camera_module.start()
    
    # 设置参数
    test_exposure = 15000.0
    test_gain = 5.0
    
    camera_module.set_exposure_time(test_exposure)
    camera_module.set_gain(test_gain)
    
    # 验证最后设置的参数值
    assert camera_module.get_last_exposure() == test_exposure
    assert camera_module.get_last_gain() == test_gain
    
    # 模拟断开重连
    camera_module.stop()
    camera_module.start()
    
    # 验证参数是否保持
    assert camera_module.get_last_exposure() == test_exposure
    assert camera_module.get_last_gain() == test_gain
    
    # 清理
    camera_module.destroy()

def test_error_event_emission(camera_module):
    """测试错误事件发送"""
    # 记录错误事件
    errors_received = []
    def on_error(event):
        if event.type == EventType.ERROR_OCCURRED:
            errors_received.append(event)
    
    # 订阅错误事件
    camera_module.subscribe_event(EventType.ERROR_OCCURRED, on_error)
    
    # 初始化和启动模块
    camera_module.initialize()
    camera_module.start()
    
    # 模拟远程特性对象
    mock_feature = MagicMock()
    mock_feature.set = MagicMock(side_effect=Exception("模拟设置参数失败"))
    
    # 替换get_float_feature方法
    camera_module._remote_feature.get_float_feature = MagicMock(return_value=mock_feature)
    
    # 尝试设置参数
    camera_module.set_exposure_time(10000.0)
    
    # 等待事件处理
    time.sleep(0.2)
    
    # 验证错误事件
    error_events = [
        e for e in errors_received 
        if e.type == EventType.ERROR_OCCURRED and 
        "模拟设置参数失败" in str(e.data.get("error", ""))
    ]
    assert len(error_events) > 0
    
    # 检查错误内容
    error_event = error_events[0]
    assert error_event.data["source"] == "camera"
    assert "模拟设置参数失败" in error_event.data["error"]
    
    # 清理
    camera_module.destroy()

def test_streaming_events(camera_module):
    """测试流采集相关事件"""
    camera_module.initialize()
    camera_module.start()
    
    # 记录事件
    events_received = []
    event_order = []  # 记录事件顺序
    
    def on_event(event):
        events_received.append(event)
        event_order.append(event.type)
    
    # 先订阅事件
    camera_module.subscribe_event(EventType.PROCESSING_STARTED, on_event)
    camera_module.subscribe_event(EventType.PROCESSING_COMPLETED, on_event)
    camera_module.subscribe_event(EventType.FRAME_CAPTURED, on_event)
    
    # 设置模拟图像数据
    mock_frame = np.zeros((1000, 1000), dtype=np.uint8)
    mock_image = MagicMock()
    mock_image.get_numpy_array.return_value = mock_frame
    mock_stream = MagicMock()
    mock_stream.get_image.return_value = mock_image
    camera_module._camera.data_stream = [mock_stream]
    
    # 启动流采集
    camera_module.start_streaming()
    
    # 等待足够长的时间以接收多个帧
    time.sleep(0.5)
    
    # 停止流采集
    camera_module.stop_streaming()
    
    # 额外等待以确保所有事件都被处理
    time.sleep(0.2)
    
    # 打印事件顺序以帮助调试
    print(f"事件顺序: {[e.name for e in event_order]}")
    
    # 验证基本事件存在
    assert any(e.type == EventType.PROCESSING_STARTED for e in events_received), "缺少处理开始事件"
    assert any(e.type == EventType.FRAME_CAPTURED for e in events_received), "缺少帧捕获事件"
    assert any(e.type == EventType.PROCESSING_COMPLETED for e in events_received), "缺少处理完成事件"
    
    # 验证事件顺序
    start_index = event_order.index(EventType.PROCESSING_STARTED)
    complete_index = event_order.index(EventType.PROCESSING_COMPLETED)
    assert start_index == 0, "处理开始事件应该是第一个事件"
    assert complete_index == len(event_order) - 1, "处理完成事件应该是最后一个事件"
    
    # 验证帧事件在开始和完成事件之间
    frame_events = [e for e in events_received if e.type == EventType.FRAME_CAPTURED]
    assert len(frame_events) > 0, "应该至少捕获一帧"
    for frame_event in frame_events:
        assert "frame" in frame_event.data, "帧事件缺少frame数据"
        assert "timestamp" in frame_event.data, "帧事件缺少timestamp数据"
        assert isinstance(frame_event.data["frame"], np.ndarray), "帧数据类型错误"
    
    # 清理
    camera_module.destroy()


def test_camera_module_degrades_without_galaxy_sdk():
    """缺少 Galaxy SDK 时相机模块应整体降级而不是抛错，保证应用仍可启动使用。"""
    module = CameraModule()
    module.device_manager = None

    assert module.sdk_available is False
    assert module.initialize() is False
    assert module.enumerate_devices() == (0, [])
    assert module.connect() is False
    assert module.is_connected() is False
    assert module.start() is False

def test_connect_failure_closes_the_opened_device(camera_module):
    """连接中途失败时，已经独占打开的设备必须被关掉。

    异常处理里只把 _camera 置 None，独占句柄就这么泄漏到进程结束；_device_indices
    里那格也永远占着，下一次连接会跳号。而 _running 从没被置起来，所以
    BaseModule.stop() 直接 early-return，不会有人去 disconnect()。
    """
    assert camera_module.initialize()
    device = camera_module.device_manager.open_device_by_index.return_value
    device.get_remote_device_feature_control.side_effect = RuntimeError("feature control 挂了")

    assert camera_module.connect() is False
    assert device.close_device.called, "失败路径没有关闭已打开的设备"
    assert camera_module._device_indices == []

def test_start_streaming_reports_success_and_failure(camera_module):
    """启动采集要把成败告诉调用方。

    以前它既 return None 又吞掉异常，调用方无从知道有没有真的开起来；
    MainWindow 因此会在失败时照样进入“连续采集中”。
    """
    assert camera_module.initialize()
    assert camera_module.connect()
    assert camera_module.start_streaming() is True
    assert camera_module.is_streaming() is True
    assert camera_module.stop_streaming() is not False

    camera_module._camera.stream_on.side_effect = RuntimeError("设备已断开")
    assert camera_module.start_streaming() is False
    assert camera_module.is_streaming() is False


def test_start_streaming_without_a_camera_reports_failure(camera_module):
    """没设备时同样是失败，而不是静默无声。"""
    assert camera_module.initialize()
    assert camera_module.start_streaming() is False

def test_one_shot_detects_completion_with_the_real_sdk_shape(camera_module):
    """ExposureAuto/GainAuto 的 get() 返回 (值, 字符串) 元组，判据得取字符串那一项。

    直接和 "Off" 比永远不相等，于是一次性自动调整不管多做完了，都要把 5 秒超时烧满。
    """
    import time

    assert camera_module.initialize()
    assert camera_module.connect()
    feature = camera_module._remote_feature.get_enum_feature.return_value
    feature.get.return_value = (1, "Off")

    started = time.perf_counter()
    camera_module.set_exposure_once()
    exposure_wait = time.perf_counter() - started
    assert exposure_wait < 1.0, f"单次自动曝光没识别到完成，等了 {exposure_wait:.1f}s"

    started = time.perf_counter()
    camera_module.set_gain_once()
    gain_wait = time.perf_counter() - started
    assert gain_wait < 1.0, f"单次自动增益没识别到完成，等了 {gain_wait:.1f}s"

def _streaming_probe(stream_block=None, stream_off_error=None, grab_block=None):
    """造一个只带假设备的 CameraModule，绕开 connect 直接看线程生命周期。"""
    import queue
    import threading
    from unittest.mock import MagicMock

    from polcam.core.camera_module import CameraModule

    module = CameraModule()
    module.initialize()
    state = {"in_get": 0, "peak": 0, "off_while_reading": 0, "close_while_reading": 0}
    lock = threading.Lock()

    device = MagicMock()

    def get_image(timeout=None):
        with lock:
            state["in_get"] += 1
            state["peak"] = max(state["peak"], state["in_get"])
        if grab_block is not None:
            grab_block.wait(5.0)
        with lock:
            state["in_get"] -= 1
        return None

    device.data_stream = [MagicMock()]
    device.data_stream[0].get_image.side_effect = get_image

    def stream_off():
        if state["in_get"] > 0:
            with lock:
                state["off_while_reading"] += 1
        if stream_off_error is not None:
            raise stream_off_error
        return True

    def close_device():
        if state["in_get"] > 0:
            with lock:
                state["close_while_reading"] += 1
        return True

    device.stream_off.side_effect = stream_off
    device.close_device.side_effect = close_device
    module._camera = device
    module._frame_queue = queue.Queue(10)
    module.publish_event = lambda *a, **k: None
    return module, state


def test_stop_streaming_never_closes_the_handle_under_a_reader():
    """抓帧线程还在 get_image 里时不能关数据流/关设备。

    stop_streaming 以前只 join(1.0) 就往下走，而 get_image 默认等 1000ms ——
    两边预算相等就是掷硬币，输了就是在有人读的时候拆原生句柄。
    """
    import threading

    release = threading.Event()
    module, state = _streaming_probe(grab_block=release)
    assert module.start_streaming() is True

    module.stop_streaming()
    assert state["off_while_reading"] == 0, "在读者仍在 get_image 时调用了 stream_off"
    assert module.is_streaming() is True, "没停成功却报告已经停下来了"

    release.set()
    threading.Event().wait(0.4)


def test_restart_does_not_stack_readers_on_one_stream():
    """停/起重启不能攒出第二个同时读数据流的线程。"""
    import threading
    import time

    release = threading.Event()
    module, state = _streaming_probe(grab_block=release)
    for _ in range(3):
        module.start_streaming()
        time.sleep(0.05)
        module.stop_streaming()
    release.set()
    time.sleep(0.3)
    assert state["peak"] == 1, f"同时有 {state['peak']} 个线程在 get_image"


def test_streaming_state_recovers_when_stream_off_raises():
    """stream_off 抛错不能把采集状态永久卡住。

    以前 _is_streaming 停不下来地留在 True，之后每次 start_streaming 都早退，
    按钮写着「停止采集」而再也不会有帧。
    """
    module, _state = _streaming_probe(stream_off_error=RuntimeError("关流失败"))
    assert module.start_streaming() is True
    assert module.stop_streaming() is False
    assert module.start_streaming() is True, "上一次没关干净之后就再也起不来了"
    module.stop_streaming()


def test_stream_thread_does_not_pin_the_camera_module():
    """抓帧线程不能把 CameraModule 钉在内存里。

    线程以前以 target=self._streaming_task 启动，绑定方法本身就是一份强引用：
    模块永远回收不掉、设备句柄跟着永远留着，线程也没有退出条件。
    """
    import time
    import weakref

    module, _state = _streaming_probe()
    assert module.start_streaming() is True
    module_ref = weakref.ref(module)

    del module

    deadline = time.time() + 5.0
    while time.time() < deadline and module_ref() is not None:
        time.sleep(0.05)

    assert module_ref() is None, "抓帧线程钉住了 CameraModule，设备句柄一起泄漏"


def test_a_transient_probe_failure_does_not_block_connecting(camera_module):
    """启动时枚举抖一下，不该让整场会话再也连不上相机。

    _do_initialize 探一次设备列表，结果丢掉不用（注释本来就写着"设备检测移到连接时"），
    可它异常时返回 False —— _initialized 就此一直是 False，BaseModule.start() 在
    connect() 之前便短路，而 MainWindow 不看 initialize() 的返回值，也没人重试。相机还
    在上电、USB 还在重枚举的时候，正是最容易抖的时候。
    """
    camera_module.device_manager.update_all_device_list.side_effect = OSError("设备还没就绪")

    assert camera_module.initialize() is True, "一次瞬时的枚举失败被判成了 SDK 不可用"

    camera_module.device_manager.update_all_device_list.side_effect = None
    assert camera_module.start() is True
    assert camera_module.is_connected()


def test_repeated_grab_errors_stop_the_loop_instead_of_spinning_forever(camera_module, monkeypatch):
    """连续采集一直报错时要收手，不能每秒十条错误地空转。

    _stream_once 的 except 分支只发了事件再 sleep(0.1)，既不计数也不退出：线一断就是
    ~10 次/秒的 ERROR_OCCURRED，而 GUI 那边每条都会弹一个模态框。
    """
    monkeypatch.setattr(CameraModule, "STREAM_ERROR_LIMIT", 3)
    camera_module._stop_flag = False
    boom = MagicMock(side_effect=OSError("device gone"))
    camera_module._camera = MagicMock()
    camera_module._camera.data_stream = [MagicMock(get_image=boom)]
    errors = []
    camera_module.subscribe_event(EventType.ERROR_OCCURRED, lambda event: errors.append(event))

    for _ in range(10):
        camera_module._stream_once()

    # 回调是总线线程在跑的，先等它把这批事件收完再判断上限
    deadline = time.time() + 2.0
    while len(errors) < 3 and time.time() < deadline:
        time.sleep(0.02)
    time.sleep(0.2)

    assert len(errors) == 3, f"错误没被限流：一条路发了 {len(errors)} 次"
    assert camera_module._stop_flag is True, "连续失败到达上限后循环该退出"


def test_a_good_frame_clears_the_error_budget(camera_module, monkeypatch):
    """偶发一两次失败不该累计到停流，成功一帧就把计数清掉。"""
    monkeypatch.setattr(CameraModule, "STREAM_ERROR_LIMIT", 3)
    image = MagicMock()
    image.get_numpy_array.return_value = None
    flaky = MagicMock(side_effect=[OSError("抖了一下"), image, OSError("又抖了一下"), image])
    camera_module._camera = MagicMock()
    camera_module._camera.data_stream = [MagicMock(get_image=flaky)]

    for _ in range(4):
        camera_module._stream_once()

    assert camera_module._stop_flag is False


def test_restarting_after_an_error_burst_starts_reading_frames_again(camera_module, monkeypatch):
    """错误爆发把流停掉之后，重新点"连续采集"要真的重新开始取帧。

    STREAM_ERROR_LIMIT 的守卫写在 _stream_once 开头，而清零在它下面；
    start_streaming() 只复位 _stop_flag，于是重启后的线程每一轮都在守卫处返回——
    既不报错也不退，还跳过了所有退避 sleep。实测：0.05 秒空转 395002 次，
    一次都没碰 get_image，这一场会话的采图就此废掉。
    """
    monkeypatch.setattr(CameraModule, "STREAM_ERROR_LIMIT", 3)
    calls = []
    stream = MagicMock()

    def raising_get_image(**kwargs):
        calls.append(1)
        raise OSError("device gone")

    stream.get_image.side_effect = raising_get_image
    camera_module._camera = MagicMock()
    camera_module._camera.data_stream = [stream]

    while camera_module._stream_error_count < 3:
        camera_module._stream_once()
    assert camera_module._stop_flag is True

    assert camera_module.start_streaming() is True
    camera_module.stop_streaming()

    before = len(calls)
    camera_module._stream_once()
    assert len(calls) > before, "重启采集后 _stream_once 仍在守卫处直接返回"


def test_a_failed_connect_does_not_leave_the_chosen_device_for_next_time(camera_module):
    """这次连接失败之后，不能把用户选的设备留给下一次完全无关的连接。

    _target_device_index 只在成功路径上"用后清除"，而 SDK 不可用、枚举到 0 台这两个
    提前 return 都不清。于是瞬时枚举失败把索引留在字段里，等用户再点连接时如果只枚举到
    一台，MainWindow 走的单相机分支根本不会指定目标设备 —— 那次连接就会去开用户没选的
    那台，并按它的 Bayer/像素格式跑整条处理链。
    """
    camera_module.device_manager.update_all_device_list.return_value = (0, [])
    camera_module.set_target_device_index(2)

    assert camera_module.connect() is False

    camera_module.device_manager.update_all_device_list.return_value = (1, [{"model_name": "只有一台"}])
    assert camera_module.connect() is True
    camera_module.device_manager.open_device_by_index.assert_called_with(1)
