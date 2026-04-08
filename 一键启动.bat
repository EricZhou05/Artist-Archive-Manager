@echo off

title Artist-Archive-Manager
:: 强制使用 UTF-8 编码显示，解决 .bat 运行时的乱码
chcp 65001 > nul

cd /d "%~dp0"

:: 检查并创建虚拟环境
if not exist "venv\Scripts\python.exe" (
    echo [INFO] 正在初始化环境，请稍候...
    python -m venv venv
    .\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    .\venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
)

:menu
cls
echo ========================================================
echo                   插画整理工具箱
echo               Artist-Archive-Manager
echo ========================================================
echo.
echo   [1] 画廊命名格式化 - archive_namer.py
echo   [2] 漏解压检测     - compare_archives.py
echo   [3] 压缩包批量解压 - decrypt_zip.py
echo   [4] 重复转发检测   - messages_dedupe.py
echo   [5] 图片位置归一   - extract_images.py
echo   [6] PSD批量转PNG   - psd_to_png.py
echo   [7] PDF批量转PNG   - pdf_to_png.py
echo   [8] 独有文件检测   - unique_detector.py
echo.
echo   [0] 退出
echo ========================================================
echo.
set /p choice="请输入数字键选择启动哪个脚本 (0-8): "

if "%choice%"=="1" goto run_1
if "%choice%"=="2" goto run_2
if "%choice%"=="3" goto run_3
if "%choice%"=="4" goto run_4
if "%choice%"=="5" goto run_5
if "%choice%"=="6" goto run_6
if "%choice%"=="7" goto run_7
if "%choice%"=="8" goto run_8
if "%choice%"=="0" exit

echo [ERROR] 无效的输入，请重新输入...
timeout /t 2 > nul
goto menu

:run_1
set SCRIPT=archive_namer.py
goto execute

:run_2
set SCRIPT=compare_archives.py
goto execute

:run_3
set SCRIPT=decrypt_zip.py
goto execute

:run_4
set SCRIPT=messages_dedupe.py
goto execute

:run_5
set SCRIPT=extract_images.py
goto execute

:run_6
set SCRIPT=psd_to_png.py
goto execute

:run_7
set SCRIPT=pdf_to_png.py
goto execute

:run_8
set SCRIPT=unique_detector.py
goto execute

:execute
echo.
echo [INFO] 正在启动 %SCRIPT% ...
echo --------------------------------------------------------
.\venv\Scripts\python.exe "%SCRIPT%"
echo --------------------------------------------------------
echo.
echo [OK] 任务结束，按任意键退出...
pause > nul
