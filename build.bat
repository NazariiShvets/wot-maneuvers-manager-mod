@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Build one WoT mod from .\packages\<folder>\
rem Usage: build.bat -v ^<version^> [-p ^<package-folder^>]
rem Default -p: wot-maneuvers-manager-mod

set "SEVENZIP=C:\Program Files\7-Zip\7z.exe"
set "PACKAGE=wot-maneuvers-manager-mod"
set "v="

cd /d "%~dp0" || exit /b 1

:parse
if "%~1"=="" goto after_parse
if /I "%~1"=="-v" (
  if "%~2"=="" (echo [ERROR] Missing value for -v & exit /b 1)
  set "v=%~2"
  shift & shift & goto parse
)
if /I "%~1"=="-p" (
  if "%~2"=="" (echo [ERROR] Missing value for -p & exit /b 1)
  set "PACKAGE=%~2"
  shift & shift & goto parse
)
echo Usage: %~nx0 -v ^<version^> [-p ^<package-folder^>]
echo Default -p: wot-maneuvers-manager-mod
exit /b 1

:after_parse
if not defined v (
  echo [ERROR] Version is required. Use -v ^<version^>.
  exit /b 1
)

set "PKG_ROOT=packages\%PACKAGE%"
if not exist "%PKG_ROOT%\res" (
  echo [ERROR] Package not found or missing res\: %PKG_ROOT%
  exit /b 1
)
if not exist "%PKG_ROOT%\meta.xml" (
  echo [ERROR] meta.xml not found: %PKG_ROOT%\meta.xml
  exit /b 1
)
if not exist "%PKG_ROOT%\build.cfg" (
  echo [ERROR] build.cfg not found: %PKG_ROOT%\build.cfg
  exit /b 1
)

set "MOD_ENTRY="
set "AUTH_ORIGIN="
for /f "usebackq tokens=1,* delims==" %%a in ("%PKG_ROOT%\build.cfg") do (
  if /I "%%a"=="MOD_ENTRY" set "MOD_ENTRY=%%b"
  if /I "%%a"=="AUTH_ORIGIN" set "AUTH_ORIGIN=%%b"
)
if not defined MOD_ENTRY (
  echo [ERROR] MOD_ENTRY missing in %PKG_ROOT%\build.cfg
  exit /b 1
)

set "META_FILE=%CD%\%PKG_ROOT%\meta.xml"
for /f "usebackq delims=" %%i in (`powershell -NoProfile -Command "([xml](Get-Content -LiteralPath '%META_FILE%' -Raw -Encoding UTF8)).mod.name"`) do set "MOD_NAME=%%i"
if not defined MOD_NAME (
  echo [ERROR] Could not read ^<name^> from meta.xml
  exit /b 1
)

if not exist "%SEVENZIP%" (
  echo [ERROR] 7-Zip not found at "%SEVENZIP%".
  exit /b 1
)
if not exist "C:\Python27\python.exe" (
  echo [ERROR] Python 2.7 not found at "C:\Python27\python.exe".
  exit /b 1
)

if exist "build" rmdir /S /Q "build"
mkdir "build"
xcopy "%PKG_ROOT%\res" "build\res" /E /I /Y >nul

set "configPath=%CD%\build\res\scripts\client\gui\mods\%MOD_ENTRY%"
if exist "%configPath%" (
  powershell -NoProfile -Command ^
    "(Get-Content '%configPath%' -Raw -Encoding utf8) " ^
    "-replace '\{\{VERSION\}\}','%v%' " ^
    "-replace '\{\{AUTH_ORIGIN\}\}','%AUTH_ORIGIN%' | " ^
    "Set-Content '%configPath%' -Encoding utf8"
) else (
  echo [WARN] %configPath% not found.
)

C:\Python27\python.exe -m compileall "build"
if errorlevel 1 (
  echo [ERROR] Python compile failed.
  exit /b 1
)

py -3 "%CD%\tools\compile_gettext_mo.py" "%CD%\build"
if errorlevel 1 (
  echo [ERROR] Gettext mo compile failed.
  exit /b 1
)

if exist "as3\build.bat" (
  pushd "as3"
  del /Q /F "bin\*.swf" 2>nul
  call build.bat
  xcopy "bin\*.swf" "..\build\res\gui\flash\" /Y /I >nul
  popd
)

powershell -NoProfile -Command ^
  "$m = Get-Content '%CD%\%PKG_ROOT%\meta.xml' -Raw -Encoding utf8; " ^
  "$m = $m -replace '\{\{VERSION\}\}','%v%'; " ^
  "Set-Content '%CD%\build\meta.xml' $m -Encoding utf8"

cd build
if errorlevel 1 (
  echo [ERROR] Failed to enter build\.
  exit /b 1
)

set "folder=%MOD_NAME%_%v%.wotmod"
if exist "%folder%" del /Q "%folder%"

"%SEVENZIP%" a -tzip -mx=0 "%folder%" ".\*.pyc" -r >nul
if errorlevel 1 (echo [ERROR] 7-Zip failed packing pyc. & cd .. & exit /b 1)
"%SEVENZIP%" a -tzip -mx=0 "%folder%" ".\*.swf" -r >nul
if errorlevel 1 (echo [ERROR] 7-Zip failed packing swf. & cd .. & exit /b 1)
"%SEVENZIP%" a -tzip -mx=0 "%folder%" ".\meta.xml" >nul
if errorlevel 1 (echo [ERROR] 7-Zip failed packing meta.xml. & cd .. & exit /b 1)
"%SEVENZIP%" a -tzip -mx=0 "%folder%" ".\*.png" -r >nul
if errorlevel 1 (echo [ERROR] 7-Zip failed packing png. & cd .. & exit /b 1)
dir /s /b "*.mo" >nul 2>&1
if not errorlevel 1 (
  "%SEVENZIP%" a -tzip -mx=0 "%folder%" ".\*.mo" -r >nul
  if errorlevel 1 (echo [ERROR] 7-Zip failed packing mo. & cd .. & exit /b 1)
)
dir /s /b "*.json" >nul 2>&1
if not errorlevel 1 (
  "%SEVENZIP%" a -tzip -mx=0 "%folder%" ".\*.json" -r >nul
  if errorlevel 1 (echo [ERROR] 7-Zip failed packing json. & cd .. & exit /b 1)
)

cd ..

if not exist "dist" mkdir "dist"
copy /Y "build\%folder%" "dist\%folder%" >nul
if errorlevel 1 (
  echo [ERROR] Failed to copy output wotmod to dist\.
  exit /b 1
)
rmdir /S /Q "build"

echo Done: dist\%folder%  (package: %PACKAGE%)
endlocal
exit /b 0
