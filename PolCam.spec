# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：uv run pyinstaller PolCam.spec

datas 里的 pyproject.toml 不是冗余：polcam/__init__.py 从 sys._MEIPASS 读版本号，
那是版本的唯一真相来源。漏掉它 About 对话框会退化成 0.0.0+unknown。
"""

from pathlib import Path
import tomllib

ROOT = Path(SPECPATH)

# 从 pyproject.toml 取版本，写进 exe 的文件属性，这样发布出去的二进制
# 在资源管理器里就能看出是哪个版本，不必启动后点「关于」。
_version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
_parts = (_version.split(".") + ["0", "0", "0", "0"])[:4]
_num = tuple(int(p) if p.isdigit() else 0 for p in _parts)

_version_file = Path(SPECPATH) / "build" / "version_info.txt"
_version_file.parent.mkdir(parents=True, exist_ok=True)
_version_file.write_text(
    f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={_num}, prodvers={_num}, mask=0x3f, flags=0x0, OS=0x40004,
    fileType=0x1, subtype=0x0, date=(0, 0, 0, 0)
  ),
  kids=[
    StringFileInfo([StringTable('080404b0', [
      StringStruct('CompanyName', 'Junhao Cai'),
      StringStruct('FileDescription', 'PolCam 偏振相机控制系统'),
      StringStruct('FileVersion', '{_version}'),
      StringStruct('OriginalFilename', 'PolCam.exe'),
      StringStruct('ProductName', 'PolCam'),
      StringStruct('ProductVersion', '{_version}'),
    ])]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
""",
    encoding="utf-8",
)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "polcam" / "resources"), "polcam/resources"),
        (str(ROOT / "pyproject.toml"), "."),
    ],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PolCam",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # 无控制台。启动异常靠 ~/PolCam/logs 下的日志排查，应用本身会写。
    console=False,
    disable_windowed_traceback=False,
    version=str(_version_file),
    icon=str(ROOT / "polcam" / "resources" / "icon" / "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="PolCam",
)
