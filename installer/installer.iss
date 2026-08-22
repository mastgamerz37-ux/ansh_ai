; Script generated for ANSH AI
; Developed by Anshu Dubey
; Website: https://devanshu.page.gd

#define MyAppName "ANSH AI"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Anshu Dubey"
#define MyAppURL "https://devanshu.page.gd"
#define MyAppExeName "ansh.bat"

[Setup]
AppId={{D3FA7B8C-98A1-42FE-B26C-ANSHAI2026}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\ANSH AI
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=..\PRODUCT_KEYS.txt
InfoBeforeFile=..\DOCUMENTATION.md
OutputDir=..\dist
OutputBaseFilename=ANSH_AI_Setup_v2.0.0
SetupIconFile=..\config\ansh.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Start ANSH AI automatically with Windows"; GroupDescription: "Startup:"

[Files]
Source: "..\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".git,dist,build,__pycache__,*.pyc"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\config\ansh.ico"
Name: "{group}\Documentation"; Filename: "{app}\DOCUMENTATION.md"
Name: "{group}\Product Keys"; Filename: "{app}\PRODUCT_KEYS.txt"
Name: "{group}\Developer Portfolio (Anshu Dubey)"; Filename: "{#MyAppURL}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\config\ansh.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\config\ansh.ico"; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall nowait skipifsilent
