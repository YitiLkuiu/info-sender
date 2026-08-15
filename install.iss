[Setup]
AppId={{C8A1F5B2-7D4E-4B9A-8C6D-1E2F3A4B5C6D}
AppName=信息发送助手
AppVersion=1.0
AppPublisher=Eton Leeo
DefaultDirName={localappdata}\Programs\信息发送助手
DefaultGroupName=信息发送助手
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=信息发送助手安装程序
SetupIconFile=app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "dist\MassSender.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\信息发送助手"; Filename: "{app}\MassSender.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\信息发送助手"; Filename: "{app}\MassSender.exe"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce

[Run]
Filename: "{app}\MassSender.exe"; Description: "立即运行信息发送助手"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
