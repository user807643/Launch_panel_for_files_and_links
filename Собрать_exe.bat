@echo off
chcp 866 >nul
setlocal

set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"

if not exist "%PY%" (
    echo [ОШИБКА] Не найден Python: %PY%
    echo Укажите правильный путь в переменной PY в этом файле.
    pause
    exit /b 1
)

echo [1/3] Проверка tkinter...
"%PY%" -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [ОШИБКА] В этом Python нет tkinter, собрать программу нельзя.
    pause
    exit /b 1
)

echo [2/3] Проверка PyInstaller...
"%PY%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller не найден, устанавливаю...
    "%PY%" -m pip install pyinstaller
    if errorlevel 1 (
        echo [ОШИБКА] Не удалось установить PyInstaller.
        pause
        exit /b 1
    )
)

echo [3/3] Сборка ЗапускПрограмм.exe...
"%PY%" -m PyInstaller --noconfirm --clean --onefile --noconsole ^
    --name "ЗапускПрограмм" ^
    --distpath "dist" --workpath "build" --specpath "build" ^
    "ЗапускПрограмм.py"

if errorlevel 1 (
    echo [ОШИБКА] Сборка не удалась.
    pause
    exit /b 1
)

echo.
echo Готово: dist\ЗапускПрограмм.exe
echo Рядом с .exe программа создаст settings.json со списком кнопок.
echo.
pause
