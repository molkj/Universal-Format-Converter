; 文件转换助手 - Inno Setup 安装脚本
; 编译: ISCC.exe installer\setup.iss

#define MyAppName "文件转换助手"
#define MyAppVersion "1.25.1"
#define MyAppPublisher "molkj"
#define MyAppExeName "文件转换助手.exe"

[Setup]
; 应用标识（卸载/升级唯一键，勿随意改）
AppId={{8F3B2C1A-5D4E-4F6A-9B2C-3A1D8E7F6B5A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
; 允许用户改安装目录
DisableDirPage=no
; 输出配置
OutputDir=..\build\installer
OutputBaseFilename=文件转换助手-Setup-v{#MyAppVersion}
SetupIconFile=..\assets\app.ico
; 压缩与固态（onefile exe 已 UPX，这里用最大压缩）
Compression=lzma2/max
SolidCompression=yes
; 架构
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 权限：per-user 安装，免管理员/UAC 弹窗（工具定位免安装绿色版，per-user 更友好）
PrivilegesRequired=lowest
; 中文语言
WizardStyle=modern
; 卸载图标
UninstallDisplayIcon={app}\{#MyAppExeName}
; 安装后自动运行选项
CloseApplications=yes

[Languages]
; 使用脚本同目录的简体中文文件（Inno Setup 6 官方版不内置中文）
Name: "chinesesimp"; MessagesFile: "ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务:"; Flags: checkedonce
Name: "sendto"; Description: "添加到「发送到」菜单（右键文件可发送转换）"; GroupDescription: "附加任务:"; Flags: unchecked

[Files]
; 主程序与文档
Source: "..\build\dist-v125\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; 发送到菜单快捷方式（右键任意文件 → 发送到 → 文件转换助手）
Name: "{userappdata}\Microsoft\Windows\SendTo\{#MyAppName}.lnk"; Filename: "{app}\{#MyAppExeName}"; Tasks: sendto

[Registry]
; 版本信息写入注册表便于检测
Root: HKA; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
; 安装完成后运行
Filename: "{app}\{#MyAppExeName}"; Description: "立即运行 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\{#MyAppName}"
