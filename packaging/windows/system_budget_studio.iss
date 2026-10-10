; Inno Setup script: per-user installer for System Budget Studio, no administrator rights.
; Build:  iscc /DAppVersion=0.1.0 /DBundleDir=dist\system-budget-studio /DOutputDir=dist packaging\windows\system_budget_studio.iss
; Silent install:    setup.exe /VERYSILENT /CURRENTUSER /DIR="C:\Some\Folder"
; Silent uninstall:  "<folder>\unins000.exe" /VERYSILENT
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef BundleDir
  #define BundleDir "..\..\dist\system-budget-studio"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{6C3E1A52-6C58-4B79-9E5B-5D0F3A4B7D11}
AppName=System Budget Studio
AppVersion={#AppVersion}
AppPublisher=System Budget Studio
; "lowest": installs for the current user only ({autopf} becomes %LOCALAPPDATA%\Programs).
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline
; announce a changed PATH so that terminals opened afterwards see it
ChangesEnvironment=yes
DefaultDirName={autopf}\System Budget Studio
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir={#OutputDir}
OutputBaseFilename=system-budget-studio-{#AppVersion}-windows-x64-setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=System Budget Studio
UninstallDisplayIcon={app}\system-budget-studio.exe
WizardStyle=modern

[InstallDelete]
; an upgrade replaces the whole library folder, so no file of an older version stays behind
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\System Budget Studio"; Filename: "{app}\system-budget-studio.exe"

[Tasks]
Name: "addtopath"; Description: "Add the command-line tool &budget to my PATH"; Flags: unchecked

[Registry]
; per-user PATH entry (HKCU), only when the task is ticked; removed again on uninstall
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
    ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsPath(ExpandConstant('{app}'))

[Code]
function NeedsPath(Dir: string): Boolean;
var
  Existing: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Existing) then
    Existing := '';
  Result := Pos(';' + Lowercase(Dir) + ';', ';' + Lowercase(Existing) + ';') = 0;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Existing, Dir, Rest, Entry, Result: string;
  P: Integer;
begin
  if CurUninstallStep <> usPostUninstall then Exit;
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', Existing) then Exit;
  Dir := Lowercase(ExpandConstant('{app}'));
  Rest := Existing;
  Result := '';
  { rebuild the list without the entry that is exactly our folder }
  while Rest <> '' do
  begin
    P := Pos(';', Rest);
    if P = 0 then
    begin
      Entry := Rest;
      Rest := '';
    end
    else
    begin
      Entry := Copy(Rest, 1, P - 1);
      Rest := Copy(Rest, P + 1, Length(Rest));
    end;
    if (Entry <> '') and (Lowercase(Entry) <> Dir) then
    begin
      if Result <> '' then Result := Result + ';';
      Result := Result + Entry;
    end;
  end;
  if Result <> Existing then
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Result);
end;
