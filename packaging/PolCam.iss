; PolCam Windows 安装脚本（Inno Setup 6）
;
; 由 .github/workflows/release.yml 调用：
;   iscc /DMyAppVersion=1.0.0 packaging\PolCam.iss
; 输入是 PyInstaller onedir 产物 dist\PolCam\，输出到 dist\installer\。
; 相对路径都相对本文件所在的 packaging\ 目录解析。

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0+unknown"
#endif

#define MyAppName "PolCam"
#define MyAppPublisher "Junhao Cai"
#define MyAppURL "https://github.com/SeveNOlogy7/PolCam"
#define MyAppExeName "PolCam.exe"

[Setup]
; AppId 是升级与卸载识别的主键。发布之后绝不能改，否则新版本会被当成
; 另一个程序并存，旧版本也无法覆盖安装。
AppId={{B11230F2-3C3C-4384-AF50-32F1CEA0FF50}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=PolCam-{#MyAppVersion}-win64
SetupIconFile=..\polcam\resources\icon\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 实验室电脑经常没有管理员权限：默认装进当前用户，需要时在提示里允许提权。
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; PyInstaller onedir 的布局是硬要求：PolCam.exe 必须和 _internal\ 同级，
; 把 _internal 的内容摊平到 {app} 会让 exe 启动即弹 Error。
Source: "..\dist\PolCam\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\PolCam\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; \
  Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
  Flags: nowait postinstall skipifsilent
