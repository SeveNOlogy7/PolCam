# PolCam - 偏振相机控制系统 (Polarization Camera Control System)

[English](#english) | [中文](#中文)

## 中文

### 简介
PolCam 是一个用于控制和处理偏振相机图像的Python应用程序。它提供了直观的图形用户界面，支持实时图像采集、偏振图像处理和数据可视化功能。

### 功能特性
- 相机控制
  - 相机连接与断开
  - 单帧图像采集
  - 连续图像采集
  - 实时参数调整（曝光、增益、白平衡）
- 图像处理
  - 偏振图像解码
  - 偏振度计算
  - 多种显示模式（原始图像、彩色图像、灰度图像、偏振度图像）
- 用户界面
  - 实时图像显示
  - 参数实时调节
  - 自适应界面布局

### 安装要求
- Python 3.8+
- DAHENG Galaxy USB3.0 相机驱动
- 相关Python包（详见 `environment.yaml`）

### 快速开始
1. 克隆仓库：
```bash
git clone https://github.com/SeveNOlogy7/PolCam.git
cd PolCam
```

2. 创建并激活conda环境：
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
├── polcam/             # 主要源代码
│   ├── core/           # 核心功能模块
│   ├── gui/            # 图形界面模块
│   └── utils/          # 工具函数
├── tests/              # 单元测试
├── docs/               # 文档
└── examples/           # 示例代码
```

### 开发
- 运行测试：`pytest`
- 代码风格检查：`flake8`
- 类型检查：`mypy`

### 许可证
MIT License

---

## English

### Introduction
PolCam is a Python application for controlling and processing polarization camera images. It provides an intuitive graphical user interface with real-time image acquisition, polarization image processing, and data visualization capabilities.

### Features
- Camera Control
  - Camera connection/disconnection
  - Single frame capture
  - Continuous capture
  - Real-time parameter adjustment (exposure, gain, white balance)
- Image Processing
  - Polarization image demosaicing
  - Degree of polarization calculation
  - Multiple display modes (raw, color, grayscale, polarization)
- User Interface
  - Real-time image display
  - Parameter adjustment
  - Adaptive layout

### Requirements
- Python 3.8+
- DAHENG Galaxy USB3.0 camera drivers
- Python packages (see `environment.yaml`)

### Quick Start
1. Clone repository:
```bash
git clone https://github.com/SeveNOlogy7/PolCam.git
cd PolCam
```

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
├── polcam/             # Main source code
│   ├── core/           # Core functionality
│   ├── gui/            # GUI modules
│   └── utils/          # Utility functions
├── tests/              # Unit tests
├── docs/               # Documentation
└── examples/           # Example code
```

### Development
- Run tests: `pytest`
- Style check: `flake8`
- Type check: `mypy`

### License
MIT License
