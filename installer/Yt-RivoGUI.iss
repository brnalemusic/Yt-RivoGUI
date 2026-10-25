; ---------------------------------------------------------------------------
;  Yt-RivoGUI - branded per-user installer
;
;  Compile with:
;    ISCC.exe /DMyAppVersion=0.0.4.0 Yt-RivoGUI.iss
;
;  The script intentionally uses a fixed AppId so the updater can locate the
;  uninstall entry at Software\Microsoft\Windows\CurrentVersion\Uninstall\
;  Yt-RivoGUI_is1.
; ---------------------------------------------------------------------------

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0.0"
#endif

#define MyAppName "Yt-RivoGUI"
#define MyAppDisplayName "yt-rivogui"
#define MyAppPublisher "brnalemusic"
#define MyAppURL "https://github.com/brnalemusic/Yt-RivoGUI"
#define MyAppExeName "Yt-RivoGUI.exe"
#define MyAppMutex "Yt-RivoGUI.SingleInstance"

[Setup]
AppId=Yt-RivoGUI
AppName={#MyAppDisplayName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppDisplayName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppComments=minimalist media downloader
AppCopyright=unlicense
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=yt-rivogui setup
VersionInfoProductName={#MyAppDisplayName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=unlicense

; Per-user installation: no UAC prompt, no elevation.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppDisplayName}
UsePreviousAppDir=yes
UsePreviousLanguage=yes
DisableProgramGroupPage=yes
AllowNoIcons=yes
CreateUninstallRegKey=yes
Uninstallable=yes
UninstallDisplayName={#MyAppDisplayName}
UninstallDisplayIcon={app}\{#MyAppExeName}
AppMutex={#MyAppMutex}
SetupMutex=Yt-RivoGUI.Setup
RestartApplications=no

; Branding: dark emerald wizard, custom artwork, monospaced-friendly spacing.
WizardStyle=modern dark includetitlebar
WizardSizePercent=130
WizardKeepAspectRatio=yes
WizardImageFile=assets\wizard-large.png
WizardSmallImageFile=assets\wizard-small.png
WizardBackImageFile=assets\wizard-back.png
WizardBackColor=#0D1117
WizardImageBackColor=#0D1117
WizardSmallImageBackColor=#0D1117
WizardBackImageOpacity=100
SetupIconFile=..\app\assets\Yt-RivoGUI-Logo.ico
DefaultDialogFontName=Consolas
ShowLanguageDialog=auto
DisableWelcomePage=no
DisableFinishedPage=no
DisableReadyPage=no

; Packaging
OutputDir=..\dist\gui
OutputBaseFilename=Yt-RivoGUI-Setup-v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
SetupLogging=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartIfNeededByRun=no
ArchiveExtraction=enhanced/nopassword

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\gui\Yt-RivoGUI.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{cm:AppComment}"
Name: "{group}\{cm:UninstallProgram,{#MyAppDisplayName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppDisplayName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{cm:AppComment}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\App Paths\{#MyAppExeName}"; ValueType: string; ValueName: "Path"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallLocation"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppDisplayName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\bin"
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}\updates"
Type: files; Name: "{localappdata}\{#MyAppName}\updater.log"

; Keep the two supported languages fully aligned. Every string is lowercase,
; matching the desktop application's monospace design language.
[Messages]
en.SetupAppTitle=setup
en.SetupWindowTitle=setup - %1
en.UninstallAppTitle=uninstall
en.UninstallAppFullTitle=uninstall %1
en.ButtonBack=< &back
en.ButtonNext=&next >
en.ButtonInstall=&install
en.ButtonOK=ok
en.ButtonCancel=cancel
en.ButtonFinish=&finish
en.ButtonBrowse=&browse...
en.ButtonWizardBrowse=&browse...
en.ButtonNewFolder=&create new folder
en.ButtonYes=&yes
en.ButtonNo=&no
en.ClickNext=click next to continue, or cancel to exit setup.
en.BeveledLabel=yt-rivogui
en.SelectLanguageTitle=select language
en.SelectLanguageLabel=select the language to use during the installation.
en.WelcomeLabel1=welcome to the [name] setup wizard
en.WelcomeLabel2=this will install [name/ver] for your user account.%n%nno administrator rights are required. ffmpeg and ffprobe are downloaded automatically when missing, so media conversion works out of the box.%n%nthe installer never changes your downloads folder.
en.SelectDirDesc=where should [name] be installed?
en.SelectDirLabel3=setup will install [name] into the following folder.
en.SelectDirBrowseLabel=to continue, click next. to select a different folder, click browse.
en.SelectTasksDesc=which additional tasks should be performed?
en.SelectTasksLabel2=select the additional tasks you would like setup to perform while installing [name], then click next.
en.ReadyLabel1=setup is now ready to begin installing [name] on your computer.
en.ReadyLabel2a=click install to continue with the installation, or click back to review or change any settings.
en.ReadyLabel2b=click install to continue with the installation.
en.ReadyMemoUserInfo=user information:
en.ReadyMemoDir=destination location:
en.ReadyMemoType=setup type:
en.ReadyMemoComponents=selected components:
en.ReadyMemoGroup=start menu folder:
en.ReadyMemoTasks=additional tasks:
en.PreparingDesc=setup is preparing to install [name] on your computer.
en.InstallingLabel=please wait while setup installs [name] on your computer.
en.FinishedHeadingLabel=completing the [name] setup wizard
en.FinishedLabelNoIcons=setup has finished installing [name] on your computer.
en.FinishedLabel=setup has finished installing [name] on your computer.%n%nthe app may be launched from the start menu or from the optional desktop shortcut.
en.ClickFinish=click finish to exit setup.
en.ConfirmUninstall=are you sure you want to completely remove %1 and all of its components?
en.UninstallStatusLabel=please wait while %1 is removed from your computer.
en.UninstalledAll=%1 was successfully removed from your computer.
en.UninstalledMost=%1 uninstall complete.%n%nsome elements could not be removed. they can be removed manually.
en.UninstalledAndNeedsRestart=to complete the uninstallation of %1, your computer must be restarted.%n%nwould you like to restart now?
en.ErrorTitle=error
en.SetupAlreadyRunning=setup is already running.
en.SetupAppRunningError=setup detected that %1 is currently running.%n%nclose all instances of it, then click ok to continue, or cancel to exit.
en.UninstallAppRunningError=the uninstaller detected that %1 is currently running.%n%nclose all instances of it, then click ok to continue, or cancel to exit.
en.ExitSetupTitle=exit setup
en.ExitSetupMessage=setup is not complete. if you exit now, the program will not be installed.%n%nyou may run setup again at another time to complete the installation.%n%nexit setup?
en.CannotInstallToNetworkDrive=setup cannot install to a network drive.
en.CannotInstallToUNCPath=setup cannot install to a unc path.
en.CannotContinue=setup cannot continue. please click cancel to exit.
en.ErrorCloseApplications=setup could not automatically close all applications. close every app using files that setup needs to update, then try again.
en.ErrorCreatingDir=setup could not create the directory "%1".
en.ErrorExecutingProgram=could not start the program:%n%1

pt.SetupAppTitle=instalador
pt.SetupWindowTitle=instalador - %1
pt.UninstallAppTitle=desinstalar
pt.UninstallAppFullTitle=desinstalar %1
pt.ButtonBack=< &voltar
pt.ButtonNext=&avançar >
pt.ButtonInstall=&instalar
pt.ButtonOK=ok
pt.ButtonCancel=cancelar
pt.ButtonFinish=&concluir
pt.ButtonBrowse=&procurar...
pt.ButtonWizardBrowse=&procurar...
pt.ButtonNewFolder=&criar nova pasta
pt.ButtonYes=&sim
pt.ButtonNo=&não
pt.ClickNext=clique em avançar para continuar ou em cancelar para sair do instalador.
pt.BeveledLabel=yt-rivogui
pt.SelectLanguageTitle=selecionar idioma
pt.SelectLanguageLabel=selecione o idioma a usar durante a instalação.
pt.WelcomeLabel1=bem-vindo ao assistente de instalação do [name]
pt.WelcomeLabel2=isto instalará o [name/ver] para a sua conta de usuário.%n%nnenhum privilégio de administrador é necessário. o ffmpeg e o ffprobe são baixados automaticamente quando estiverem ausentes, para que a conversão de mídia funcione de imediato.%n%no instalador não altera a sua pasta de downloads.
pt.SelectDirDesc=onde o [name] deve ser instalado?
pt.SelectDirLabel3=o instalador instalará o [name] na seguinte pasta.
pt.SelectDirBrowseLabel=para continuar, clique em avançar. para escolher outra pasta, clique em procurar.
pt.SelectTasksDesc=quais tarefas adicionais devem ser executadas?
pt.SelectTasksLabel2=selecione as tarefas adicionais que o instalador deve executar enquanto instala o [name] e clique em avançar.
pt.ReadyLabel1=o instalador está pronto para começar a instalar o [name] no seu computador.
pt.ReadyLabel2a=clique em instalar para continuar ou em voltar para revisar ou alterar as configurações.
pt.ReadyLabel2b=clique em instalar para continuar com a instalação.
pt.ReadyMemoUserInfo=informações do usuário:
pt.ReadyMemoDir=local de destino:
pt.ReadyMemoType=tipo de instalação:
pt.ReadyMemoComponents=componentes selecionados:
pt.ReadyMemoGroup=pasta do menu iniciar:
pt.ReadyMemoTasks=tarefas adicionais:
pt.PreparingDesc=o instalador está se preparando para instalar o [name] no seu computador.
pt.InstallingLabel=aguarde enquanto o instalador instala o [name] no seu computador.
pt.FinishedHeadingLabel=concluindo o assistente de instalação do [name]
pt.FinishedLabelNoIcons=o instalador concluiu a instalação do [name] no seu computador.
pt.FinishedLabel=o instalador concluiu a instalação do [name] no seu computador.%n%no aplicativo pode ser aberto pelo menu iniciar ou pelo atalho opcional da área de trabalho.
pt.ClickFinish=clique em concluir para sair do instalador.
pt.ConfirmUninstall=tem certeza de que deseja remover completamente o %1 e todos os seus componentes?
pt.UninstallStatusLabel=aguarde enquanto o %1 é removido do seu computador.
pt.UninstalledAll=o %1 foi removido com sucesso do seu computador.
pt.UninstalledMost=a desinstalação do %1 foi concluída.%n%nalguns elementos não puderam ser removidos. eles podem ser removidos manualmente.
pt.UninstalledAndNeedsRestart=para concluir a desinstalação do %1, o computador precisa ser reiniciado.%n%ndeseja reiniciar agora?
pt.ErrorTitle=erro
pt.SetupAlreadyRunning=o instalador já está em execução.
pt.SetupAppRunningError=o instalador detectou que o %1 está em execução.%n%nfeche todas as instâncias, depois clique em ok para continuar ou em cancelar para sair.
pt.UninstallAppRunningError=o desinstalador detectou que o %1 está em execução.%n%nfeche todas as instâncias, depois clique em ok para continuar ou em cancelar para sair.
pt.ExitSetupTitle=sair do instalador
pt.ExitSetupMessage=a instalação não foi concluída. se sair agora, o programa não será instalado.%n%nvocê pode executar o instalador novamente mais tarde para concluir a instalação.%n%nsair do instalador?
pt.CannotInstallToNetworkDrive=o instalador não pode instalar em uma unidade de rede.
pt.CannotInstallToUNCPath=o instalador não pode instalar em um caminho unc.
pt.CannotContinue=o instalador não pode continuar. clique em cancelar para sair.
pt.ErrorCloseApplications=o instalador não conseguiu fechar todos os aplicativos automaticamente. feche todos os aplicativos que usam arquivos que o instalador precisa atualizar e tente novamente.
pt.ErrorCreatingDir=o instalador não conseguiu criar a pasta "%1".
pt.ErrorExecutingProgram=não foi possível iniciar o programa:%n%1

[CustomMessages]
en.CreateDesktopIcon=create a &desktop shortcut
en.AdditionalIcons=additional shortcuts
en.AppComment=minimalist media downloader
en.LaunchProgram=launch %1
en.UninstallProgram=uninstall %1
en.ffmpegDownloadTitle=media tools
en.ffmpegDownloadDesc=downloading ffmpeg and ffprobe so video and audio conversion work out of the box. this needs an internet connection and can be cancelled.
pt.CreateDesktopIcon=criar atalho na &área de trabalho
pt.AdditionalIcons=atalhos adicionais
pt.AppComment=downloader minimalista de mídia
pt.LaunchProgram=abrir o %1
pt.UninstallProgram=desinstalar o %1
pt.ffmpegDownloadTitle=ferramentas de mídia
pt.ffmpegDownloadDesc=baixando ffmpeg e ffprobe para que a conversão de vídeo e áudio funcione de imediato. isto precisa de conexão com a internet e pode ser cancelado.

[Code]
const
  FFmpegArchiveName = 'ffmpeg-release-essentials.7z';
  FFmpegChecksumName = 'ffmpeg-essentials.sha256';
  FFmpegDefaultUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z';
  FFmpegDefaultChecksumUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z.sha256';

var
  FFmpegDownloadPage: TDownloadWizardPage;
  FFmpegDownloadAttempted: Boolean;

function FFmpegEnvValue(const Name: String): String;
begin
  Result := Trim(GetEnv(Name));
end;

function FFmpegTargetDir: String;
begin
  Result := ExpandConstant('{app}\bin');
end;

function FFmpegStageDir: String;
begin
  Result := ExpandConstant('{tmp}\ffmpeg-stage');
end;

function FFmpegArchivePath: String;
begin
  Result := ExpandConstant('{tmp}\') + FFmpegArchiveName;
end;

function FFmpegAlreadyAvailable: Boolean;
var
  SearchPath: String;
begin
  Result := FileExists(AddBackslash(FFmpegTargetDir) + 'ffmpeg.exe')
    and FileExists(AddBackslash(FFmpegTargetDir) + 'ffprobe.exe');
  if Result then begin
    Log('ffmpeg: found in ' + FFmpegTargetDir);
    exit;
  end;

  SearchPath := GetEnv('PATH');
  Result := (FileSearch('ffmpeg.exe', SearchPath) <> '')
    and (FileSearch('ffprobe.exe', SearchPath) <> '');
  if Result then
    Log('ffmpeg: found on path');
end;

function FFmpegShouldDownload: Boolean;
begin
  if FFmpegEnvValue('YTRIVO_SKIP_FFMPEG') = '1' then begin
    Log('ffmpeg: skipped by YTRIVO_SKIP_FFMPEG');
    Result := False;
    exit;
  end;

  if FFmpegEnvValue('YTRIVO_FFMPEG_FORCE') = '1' then begin
    Log('ffmpeg: forced by YTRIVO_FFMPEG_FORCE');
    Result := True;
    exit;
  end;

  Result := not FFmpegAlreadyAvailable;
end;

function FFmpegIsHex(const Value: String): Boolean;
var
  Index: Integer;
begin
  Result := Length(Value) = 64;
  if not Result then
    exit;

  for Index := 1 to Length(Value) do begin
    if Pos(LowerCase(Value[Index]), '0123456789abcdef') = 0 then begin
      Result := False;
      exit;
    end;
  end;
end;

function FFmpegChecksumFromFile(const FileName: String): String;
var
  Lines: TArrayOfString;
  Index: Integer;
  Value: String;
begin
  Result := '';
  if not LoadStringsFromFile(FileName, Lines) then
    exit;

  for Index := 0 to GetArrayLength(Lines) - 1 do begin
    Value := LowerCase(Trim(Lines[Index]));
    if FFmpegIsHex(Value) then begin
      Result := Value;
      exit;
    end;
  end;
end;

function FFmpegResolveChecksum: String;
var
  OverrideValue: String;
  ChecksumPath: String;
  ChecksumUrl: String;
begin
  OverrideValue := LowerCase(FFmpegEnvValue('YTRIVO_FFMPEG_SHA256'));
  if OverrideValue <> '' then begin
    if FFmpegIsHex(OverrideValue) then
      Result := OverrideValue
    else begin
      Log('ffmpeg: invalid YTRIVO_FFMPEG_SHA256');
      Result := '';
    end;
    exit;
  end;

  ChecksumUrl := FFmpegEnvValue('YTRIVO_FFMPEG_CHECKSUM_URL');
  if ChecksumUrl = '' then
    ChecksumUrl := FFmpegDefaultChecksumUrl;

  ChecksumPath := ExpandConstant('{tmp}\') + FFmpegChecksumName;
  DeleteFile(ChecksumPath);
  try
    DownloadTemporaryFile(ChecksumUrl, FFmpegChecksumName, '', nil);
    Result := FFmpegChecksumFromFile(ChecksumPath);
    if Result = '' then
      Log('ffmpeg: checksum file is empty or invalid');
  except
    Log('ffmpeg: checksum download failed: ' + GetExceptionMessage);
    Result := '';
  end;
end;

function FFmpegArchiveUrl: String;
begin
  Result := FFmpegEnvValue('YTRIVO_FFMPEG_URL');
  if Result = '' then
    Result := FFmpegDefaultUrl;
end;

function FFmpegDownload(const Url, Checksum: String): Boolean;
begin
  DeleteFile(FFmpegArchivePath);

  if WizardSilent then begin
    try
      DownloadTemporaryFile(Url, FFmpegArchiveName, Checksum, nil);
      Result := True;
    except
      Log('ffmpeg: silent download failed: ' + GetExceptionMessage);
      Result := False;
    end;
    exit;
  end;

  if FFmpegDownloadPage = nil then begin
    FFmpegDownloadPage := CreateDownloadPage(
      CustomMessage('ffmpegDownloadTitle'),
      CustomMessage('ffmpegDownloadDesc'),
      nil);
    FFmpegDownloadPage.ShowBaseNameInsteadOfUrl := True;
  end;

  FFmpegDownloadPage.Clear;
  FFmpegDownloadPage.Add(Url, FFmpegArchiveName, Checksum);
  FFmpegDownloadPage.Show;
  try
    try
      FFmpegDownloadPage.Download;
      Result := True;
    except
      if FFmpegDownloadPage.AbortedByUser then
        Log('ffmpeg: download cancelled by user')
      else
        Log('ffmpeg: download failed: ' + GetExceptionMessage);
      Result := False;
    end;
  finally
    FFmpegDownloadPage.Hide;
  end;
end;

function FFmpegFindFile(const Directory, FileName: String): String;
var
  FindRec: TFindRec;
  Candidate: String;
begin
  Result := '';
  if not FindFirst(AddBackslash(Directory) + '*', FindRec) then
    exit;

  try
    repeat
      Candidate := AddBackslash(Directory) + FindRec.Name;
      if (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then begin
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') then begin
          Result := FFmpegFindFile(Candidate, FileName);
          if Result <> '' then
            exit;
        end;
      end else if SameText(FindRec.Name, FileName) then begin
        Result := Candidate;
        exit;
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

function FFmpegExtractAndStage: Boolean;
var
  ArchivePath: String;
  ExtractDir: String;
  StageDir: String;
  SourceFile: String;
begin
  Result := False;
  ArchivePath := FFmpegArchivePath;
  ExtractDir := ExpandConstant('{tmp}\ffmpeg-unpacked');
  StageDir := FFmpegStageDir;

  DelTree(ExtractDir, True, True, True);
  DelTree(StageDir, True, True, True);

  if not ForceDirectories(ExtractDir) then begin
    Log('ffmpeg: could not create ' + ExtractDir);
    exit;
  end;

  try
    ExtractArchive(ArchivePath, ExtractDir, '', True, nil);
  except
    Log('ffmpeg: extraction failed: ' + GetExceptionMessage);
    exit;
  end;

  SourceFile := FFmpegFindFile(ExtractDir, 'ffmpeg.exe');
  if SourceFile = '' then begin
    Log('ffmpeg: ffmpeg.exe not found in archive');
    exit;
  end;

  if not ForceDirectories(StageDir) then begin
    Log('ffmpeg: could not create ' + StageDir);
    exit;
  end;

  if not CopyFile(SourceFile, AddBackslash(StageDir) + 'ffmpeg.exe', False) then begin
    Log('ffmpeg: could not stage ffmpeg.exe');
    exit;
  end;

  SourceFile := FFmpegFindFile(ExtractDir, 'ffprobe.exe');
  if SourceFile = '' then begin
    Log('ffmpeg: ffprobe.exe not found in archive');
    exit;
  end;

  if not CopyFile(SourceFile, AddBackslash(StageDir) + 'ffprobe.exe', False) then begin
    Log('ffmpeg: could not stage ffprobe.exe');
    exit;
  end;

  Result := True;
end;

procedure FFmpegInstallStaged;
var
  StageDir: String;
  TargetDir: String;
begin
  StageDir := FFmpegStageDir;
  if not (FileExists(AddBackslash(StageDir) + 'ffmpeg.exe')
    and FileExists(AddBackslash(StageDir) + 'ffprobe.exe')) then
    exit;

  TargetDir := FFmpegTargetDir;
  if not ForceDirectories(TargetDir) then begin
    Log('ffmpeg: could not create ' + TargetDir);
    exit;
  end;

  if CopyFile(AddBackslash(StageDir) + 'ffmpeg.exe', AddBackslash(TargetDir) + 'ffmpeg.exe', False)
    and CopyFile(AddBackslash(StageDir) + 'ffprobe.exe', AddBackslash(TargetDir) + 'ffprobe.exe', False) then
    Log('ffmpeg: installed to ' + TargetDir)
  else
    Log('ffmpeg: could not copy binaries to ' + TargetDir);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Checksum: String;
begin
  Result := True;
  if (CurPageID <> wpReady) or FFmpegDownloadAttempted then
    exit;

  FFmpegDownloadAttempted := True;
  if not FFmpegShouldDownload then
    exit;

  Log('ffmpeg: download required');
  Checksum := FFmpegResolveChecksum;
  if Checksum = '' then begin
    Log('ffmpeg: skipping download because no checksum is available');
    exit;
  end;

  if not FFmpegDownload(FFmpegArchiveUrl, Checksum) then begin
    Log('ffmpeg: setup will continue without the media tools');
    exit;
  end;

  if FFmpegExtractAndStage then
    Log('ffmpeg: media tools staged for installation')
  else
    Log('ffmpeg: staging failed; setup will continue without the media tools');
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    FFmpegInstallStaged;
end;
