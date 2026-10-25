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
en.WelcomeLabel2=this will install [name/ver] for your user account.%n%nno administrator rights are required. ffmpeg and ffprobe must be available on your path for media conversion.%n%nthe installer never changes your downloads folder.
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
pt.WelcomeLabel2=isto instalará o [name/ver] para a sua conta de usuário.%n%nnenhum privilégio de administrador é necessário. o ffmpeg e o ffprobe precisam estar disponíveis no path para a conversão de mídia.%n%no instalador não altera a sua pasta de downloads.
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
pt.CreateDesktopIcon=criar atalho na &área de trabalho
pt.AdditionalIcons=atalhos adicionais
pt.AppComment=downloader minimalista de mídia
pt.LaunchProgram=abrir o %1
pt.UninstallProgram=desinstalar o %1
