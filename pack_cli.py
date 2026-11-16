"""PyInstaller 打包入口（命令行版，带控制台）。

打包后是 `jmfav-cli.exe`，用法和 `run.py --cli` 完全一致：
    jmfav-cli.exe -u 用户 -p 密码 --search 秘密
"""

from __future__ import annotations

import os
import sys


def setup_console_utf8() -> None:
    """Windows 控制台默认是 GBK，中文会变乱码，这里切到 UTF-8。"""
    try:
        # 让 Python 的 stdout 用 UTF-8
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    try:
        import ctypes
        # SetConsoleOutputCP(65001) / SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass


def main() -> int:
    setup_console_utf8()
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

    from jmfav.cli import main as cli_main
    return cli_main(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
