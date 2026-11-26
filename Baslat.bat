@echo off
cls
cd /d "%~dp0"

echo W3Schools C++ Cevrimdisi Rehber baslatiliyor...

:: 1. Klasor icinde hazir .venv varsa dogrudan ac
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "uygulama.py"
    exit /b 0
)

:: 2. Anaconda / Miniconda ortam kayit dosyasindan (environments.txt) tam yolu bul
set "CONDA_ACT="
if exist "%USERPROFILE%\.conda\environments.txt" (
    for /f "usebackq delims=" %%L in ("%USERPROFILE%\.conda\environments.txt") do (
        if not defined CONDA_ACT if exist "%%~L\Scripts\activate.bat" set "CONDA_ACT=%%~L\Scripts\activate.bat"
        if not defined CONDA_ACT if exist "%%~L\..\Scripts\activate.bat" set "CONDA_ACT=%%~L\..\Scripts\activate.bat"
        if not defined CONDA_ACT if exist "%%~L\..\..\Scripts\activate.bat" set "CONDA_ACT=%%~L\..\..\Scripts\activate.bat"
    )
)
if defined CONDA_ACT goto :USE_CONDA

:: 3. PATH ve standart klasorlerde Anaconda / Miniconda ara
for /f "delims=" %%i in ('where conda 2^>nul') do (
    if not defined CONDA_ACT if exist "%%~dpiactivate.bat" set "CONDA_ACT=%%~dpiactivate.bat"
    if not defined CONDA_ACT if exist "%%~dpi..\Scripts\activate.bat" set "CONDA_ACT=%%~dpi..\Scripts\activate.bat"
)
if defined CONDA_ACT goto :USE_CONDA

for %%d in (
    "%USERPROFILE%\anaconda3"
    "%USERPROFILE%\miniconda3"
    "%LOCALAPPDATA%\anaconda3"
    "%LOCALAPPDATA%\miniconda3"
    "C:\anaconda3"
    "C:\miniconda3"
    "C:\ProgramData\anaconda3"
    "C:\ProgramData\miniconda3"
    "D:\anaconda3"
    "D:\miniconda3"
    "D:\Anaconda"
    "D:\Miniconda"
    "D:\ProgramData\anaconda3"
    "D:\ProgramData\miniconda3"
    "E:\anaconda3"
    "E:\miniconda3"
) do (
    if not defined CONDA_ACT if exist "%%~d\Scripts\activate.bat" set "CONDA_ACT=%%~d\Scripts\activate.bat"
)
if defined CONDA_ACT goto :USE_CONDA

:: 4. Duz Python veya Kayit Defteri uzerinden kurulu Python/Conda ara
set "SYS_PY="
py -c "import sys" >nul 2>&1 && set "SYS_PY=py"
if defined SYS_PY goto :CHECK_PY_TYPE

python -c "import sys" >nul 2>&1 && set "SYS_PY=python"
if defined SYS_PY goto :CHECK_PY_TYPE

for /f "tokens=2*" %%a in ('reg query "HKCU\Software\Python" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
    if not defined SYS_PY if exist "%%~b" set "SYS_PY=%%~b"
)
if defined SYS_PY goto :CHECK_PY_TYPE

for /f "tokens=2*" %%a in ('reg query "HKLM\Software\Python" /s /v ExecutablePath 2^>nul ^| findstr /i "ExecutablePath"') do (
    if not defined SYS_PY if exist "%%~b" set "SYS_PY=%%~b"
)
if defined SYS_PY goto :CHECK_PY_TYPE

for /d %%d in (
    "%LOCALAPPDATA%\Programs\Python\Python*"
    "C:\Python*"
    "D:\Python*"
    "E:\Python*"
    "C:\Program Files\Python*"
    "D:\Program Files\Python*"
) do (
    if not defined SYS_PY if exist "%%~d\python.exe" set "SYS_PY=%%~d\python.exe"
)
if defined SYS_PY goto :CHECK_PY_TYPE

echo.
echo [HATA] Bilgisayarda Python veya Anaconda bulunamadi!
echo Lutfen python.org adresinden Python 3.10+ kurun veya sadece okumak icin index.html dosyasini acin.
pause
exit /b 1

:CHECK_PY_TYPE
for /f "delims=" %%i in ('"%SYS_PY%" -c "import sys, os; p=sys.prefix; a1=os.path.join(p,'Scripts','activate.bat'); a2=os.path.join(os.path.dirname(os.path.dirname(p)),'Scripts','activate.bat'); print(a1 if os.path.exists(a1) else (a2 if os.path.exists(a2) else ''))" 2^>nul') do set "CONDA_ACT=%%i"
if defined CONDA_ACT goto :USE_CONDA
goto :USE_STD_PYTHON

:USE_CONDA
call "%CONDA_ACT%" base >nul 2>&1
call "%CONDA_ACT%" cpp_paket >nul 2>&1
python -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo Ilk acilis kurulumu yapiliyor ^(Conda ortamina pywebview kuruluyor^)...
    pip install -r requirements.txt
)
for /f "delims=" %%i in ('python -c "import sys, os; pw=os.path.join(os.path.dirname(sys.executable),'pythonw.exe'); print(pw if os.path.exists(pw) else sys.executable)"') do set "PYW_EXE=%%i"
start "" "%PYW_EXE%" "uygulama.py"
exit /b 0

:USE_STD_PYTHON
"%SYS_PY%" -c "import webview" >nul 2>&1
if errorlevel 1 (
    echo Ilk acilis kurulumu yapiliyor ^(.venv ortami olusturuluyor^)...
    "%SYS_PY%" -m venv .venv
    if exist ".venv\Scripts\python.exe" (
        ".venv\Scripts\python.exe" -m pip install --upgrade pip
        ".venv\Scripts\python.exe" -m pip install -r requirements.txt
        start "" ".venv\Scripts\pythonw.exe" "uygulama.py"
        exit /b 0
    ) else (
        "%SYS_PY%" -m pip install -r requirements.txt
    )
)
for /f "delims=" %%i in ('"%SYS_PY%" -c "import sys, os; pw=os.path.join(os.path.dirname(sys.executable),'pythonw.exe'); print(pw if os.path.exists(pw) else sys.executable)"') do set "PYW_EXE=%%i"
start "" "%PYW_EXE%" "uygulama.py"
exit /b 0