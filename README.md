# PolCam - 偏振相机控制系统 (Polarization Camera Control System)

[English](#english) | [中文](#中文)

<p align="center">
  <img src="polcam/resources/icon/icon.svg" alt="PolCam Icon" width="120" />
</p>

## 中文

### 简介

PolCam 是一个用于控制和处理偏振相机图像的Python应用程序。它提供了直观的图形用户界面，支持实时图像采集、偏振图像处理和数据可视化功能。

![PolCam Main Window](images/main_window.png)

### 功能特性

- 相机控制
  - 相机连接与断开
  - 多相机设备选择与连接（支持在弹窗中选择目标设备）
  - 自动相机类型识别（彩色偏振 / 黑白偏振 / 普通彩色）
  - 单帧图像采集
  - 连续图像采集
  - 实时参数调整（曝光、增益、白平衡）
  - ROI 控制（点击放大/缩小、框选放大、视图复原）
- 图像处理
  - 偏振图像解码
  - 偏振度计算
  - 普通彩色相机的 Bayer / PixelFormat 兼容处理
  - 显示模式按相机类型自适应（普通彩色相机仅显示可用模式）
  - 多种显示模式（原始图像、彩色图像、灰度图像、偏振度图像）
- 用户界面
  - 实时图像显示
  - 参数实时调节
  - 图像工具栏支持 ROI 缩放上限控制（最大约 100x）与状态提示
  - 四分图标题在不同分辨率下保持更一致的视觉尺寸
  - 自适应界面布局

### 安装要求

- Python 3.12+
- [DAHENG Galaxy 相机驱动](https://www.daheng-imaging.com/downloads/softwares/)
- 相关Python包（详见 `environment.yaml`）

### 快速开始

1. 克隆仓库：

```bash
git clone https://github.com/SeveNOlogy7/PolCam.git
cd PolCam
```

#### 使用 uv

2. 创建并激活 uv 环境：

```bash
uv sync
```

3. 运行程序：

```bash
uv run python main.py
```

#### 使用 Conda

2. 创建并激活 conda 环境：

```bash
conda env create -f environment.yaml
conda activate polcam
```

3. 运行程序：

```bash
python main.py
```

### 项目结构

```
PolCam/
├── main.py                 # 程序入口
├── pyproject.toml          # 项目配置（uv / 构建）
├── environment.yaml        # Conda 环境定义
├── polcam/                 # 主应用源码
│   ├── core/               # 核心模块（相机、处理、事件、工具栏控制）
│   ├── gui/                # GUI 模块
│   │   └── widgets/        # GUI 子组件
│   ├── resources/          # 图标等资源
│   └── utils/              # 日志等工具
├── gxipy/                  # 相机 Python SDK 封装
└── tests/                  # 测试代码
```

### 开发

#### 使用 uv

- 运行测试：`uv run pytest`
- 代码风格检查：`uv run flake8`
- 类型检查：`uv run mypy .`

#### 使用 Conda

- 运行测试：`pytest`
- 代码风格检查：`flake8`
- 类型检查：`mypy .`

### 许可证

MIT License

---

## English

### Introduction

PolCam is a Python application for controlling and processing polarization camera images. It provides an intuitive graphical user interface with real-time image acquisition, polarization image processing, and data visualization capabilities.

![PolCam Main Window](images/main_window.png)

### Features

- Camera Control
  - Camera connection/disconnection
  - Multi-camera device selection and target-camera connection via dialog
  - Automatic camera type detection (polarization color / polarization mono / normal color)
  - Single frame capture
  - Continuous capture
  - Real-time parameter adjustment (exposure, gain, white balance)
  - ROI control (click zoom in/out, drag-to-zoom, reset view)
- Image Processing
  - Polarization image demosaicing
  - Degree of polarization calculation
  - Bayer / PixelFormat-aware processing for normal color cameras
  - Camera-type-aware display mode filtering (only valid modes are shown)
  - Multiple display modes (raw, color, grayscale, polarization)
- User Interface
  - Real-time image display
  - Parameter adjustment
  - Toolbar zoom guard with max zoom handling (~100x) and status feedback
  - More consistent quad-view title rendering across different subplot sizes
  - Adaptive layout

### Requirements

- Python 3.12+
- [DAHENG Galaxy camera drivers](https://www.daheng-imaging.com/downloads/softwares/)
- Python packages (see `environment.yaml`)

### Quick Start

1. Clone repository:

```bash
git clone https://github.com/SeveNOlogy7/PolCam.git
cd PolCam
```

#### Use uv

2. Create and activate uv environment:

```bash
uv sync
```

3. Run program:

```bash
uv run python main.py
```

#### Use Conda

2. Create and activate conda environment:

```bash
conda env create -f environment.yaml
conda activate polcam
```

3. Run program:

```bash
python main.py
```

### Project Structure

```
PolCam/
├── main.py                 # Application entry point
├── pyproject.toml          # Project config (uv / build)
├── environment.yaml        # Conda environment definition
├── polcam/                 # Main application source
│   ├── core/               # Core modules (camera, processing, events, toolbar control)
│   ├── gui/                # GUI modules
│   │   └── widgets/        # GUI sub-components
│   ├── resources/          # Icons and static resources
│   └── utils/              # Utilities (logging, etc.)
├── gxipy/                  # DAHENG camera Python SDK wrapper
├── gxipy_docs/             # gxipy examples and reference scripts
└── tests/                  # Test suite
```

### Development

#### Use uv

- Run tests: `uv run pytest`
- Style check: `uv run flake8`
- Type check: `uv run mypy .`

#### Use Conda

- Run tests: `pytest`
- Style check: `flake8`
- Type check: `mypy .`

### License

MIT License
