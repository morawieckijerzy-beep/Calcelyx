@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
python -m pytest -q
if errorlevel 1 exit /b 1
python -m PyInstaller --noconfirm --clean --windowed --name Calcelyx --paths src --collect-all customtkinter --collect-all reportlab --collect-all pypdfium2 --add-data "data;data" run_app.py
if errorlevel 1 exit /b 1
copy /y "README.md" "dist\Calcelyx\README.md" >nul
copy /y "README_PL.md" "dist\Calcelyx\README_PL.md" >nul
copy /y "RELEASE_NOTES.md" "dist\Calcelyx\RELEASE_NOTES.md" >nul
copy /y "AUTHORS.md" "dist\Calcelyx\AUTHORS.md" >nul
copy /y "THIRD-PARTY-NOTICES.txt" "dist\Calcelyx\THIRD-PARTY-NOTICES.txt" >nul
copy /y "LICENSE" "dist\Calcelyx\LICENSE" >nul
copy /y "docs\RAPORT_TESTOW_ISO_29119_25010.md" "dist\Calcelyx\RAPORT_TESTOW.md" >nul
copy /y "data\Calcelyx_Price_List_EN.xlsx" "dist\Calcelyx\Calcelyx_Price_List_EN.xlsx" >nul
copy /y "data\Calcelyx_Cennik_PL.xlsx" "dist\Calcelyx\Calcelyx_Cennik_PL.xlsx" >nul
echo Ready: dist\Calcelyx\Calcelyx.exe

