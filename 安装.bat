@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   JM 收藏夹批量下载器 - 安装依赖
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 没找到 python，请先安装 Python 3.9 以上版本
    echo        下载地址: https://www.python.org/downloads/
    echo        安装时记得勾选 "Add Python to PATH"
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] 创建虚拟环境...
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
) else (
    echo [1/3] 虚拟环境已存在，跳过
)

echo.
echo [2/3] 升级 pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q

echo.
echo [3/3] 安装依赖（jmcomic、pillow）...
".venv\Scripts\python.exe" -m pip install -q jmcomic pillow
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，通常是网络问题。
    echo        可以试试国内镜像：
    echo        .venv\Scripts\python.exe -m pip install jmcomic pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
    pause
    exit /b 1
)

echo.
echo ============================================
echo   安装完成！现在双击 "启动.vbs" 就能用了。
echo ============================================
echo.
pause
