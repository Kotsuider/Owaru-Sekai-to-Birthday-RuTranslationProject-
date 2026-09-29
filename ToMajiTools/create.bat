@echo off
chcp 65001 >nul
for %%f in ("scenario\*.mjo") do (
    echo Disassembling: %%~nxf
    maji.exe disassemble "%%f"
)
pause