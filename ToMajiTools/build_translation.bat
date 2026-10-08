@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

pushd "%~dp0"

if not exist "st" (
    echo [ERROR] Pristine folder 'st' not found.
    echo Please place original files in 'st' and run disassemble_st.bat first.
    popd
    pause
    exit /b 1
)

set "TL_SOURCE="
if exist "Owari" (
    set "TL_SOURCE=Owari"
) else if exist "Owari.xlsx" (
    set "TL_SOURCE=Owari.xlsx"
) else if exist "..\Owari.xlsx" (
    set "TL_SOURCE=..\Owari.xlsx"
)

if "%TL_SOURCE%"=="" (
    echo [ERROR] Translation source 'Owari' folder or 'Owari.xlsx' not found.
    popd
    pause
    exit /b 1
)

echo ============================================================
echo   Building translation for Owari no Sekai to Birthday
echo   Source: %TL_SOURCE%
echo ============================================================
echo.

echo [1/6] Preparing clean scenario directory from st...
if not exist "scenario" mkdir "scenario"
copy /Y "st\*.mjil" "scenario\" >nul
copy /Y "st\*.mjres" "scenario\" >nul
echo Clean disassemblies copied from st to scenario.
python patch_furigana.py "scenario"
if errorlevel 1 (
    echo [ERROR] Furigana patching failed!
    popd
    pause
    exit /b 1
)

echo.
echo [2/6] Inserting translations into .mjres...
python mjres_tool.py insert "%TL_SOURCE%" -o "scenario"
if errorlevel 1 (
    echo [ERROR] Translation insertion failed!
    popd
    pause
    exit /b 1
)

echo.
echo [3/6] Applying line wrapping...
python wrap_mjres.py "scenario"
if errorlevel 1 (
    echo [ERROR] Line wrapping failed!
    popd
    pause
    exit /b 1
)

echo.
echo [4/6] Sanitizing Unicode characters for CP932...
python sanitize_mjres.py "scenario"
if errorlevel 1 (
    echo [ERROR] Sanitization failed!
    popd
    pause
    exit /b 1
)

echo.
echo [5/6] Assembling scripts via maji.exe...
set /a count_assembled=0
for %%F in (scenario\*.mjil) do (
    maji.exe assemble "%%F"
    if errorlevel 1 (
        echo [ERROR] Assembly failed for %%~nxF!
        popd
        pause
        exit /b 1
    )
    set /a count_assembled+=1
)
echo Successfully assembled: !count_assembled! scripts.

echo.
echo [6/6] Packaging to scenario_tl...
if not exist "scenario_tl" mkdir "scenario_tl"

copy /Y "scenario\*.mjo" "scenario_tl\" >nul

if exist "Owari\Other_tr\*.mail" copy /Y "Owari\Other_tr\*.mail" "scenario_tl\" >nul
if exist "Owari\Other_tr\*.blog" copy /Y "Owari\Other_tr\*.blog" "scenario_tl\" >nul
if exist "Owari\Other_tr\*.profile" copy /Y "Owari\Other_tr\*.profile" "scenario_tl\" >nul

if exist "st\*.cfg" copy /Y "st\*.cfg" "scenario_tl\" >nul
if exist "st\*.winmerge" copy /Y "st\*.winmerge" "scenario_tl\" >nul

if exist "message_box.mjo" copy /Y "message_box.mjo" "scenario_tl\message_box.mjo" >nul
if exist "config.mjo" copy /Y "config.mjo" "scenario_tl\config.mjo" >nul

echo.
echo ============================================================
echo   BUILD COMPLETED SUCCESSFULLY!
echo   Output folder: scenario_tl
echo.
echo   To install in game:
echo   Pack all files inside 'scenario_tl' into 'scenario.arc'
echo   using GARbro (Archive type: Majiro ARC).
echo ============================================================
echo.

popd
exit /b 0
