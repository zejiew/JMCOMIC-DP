"""程序入口：双击即可打开图形界面。

- 若同目录下存在 ``.venv``，会自动用 venv 里的 Python 重新启动（免得用错解释器）。
- ``--cli`` 参数走命令行模式。
"""

from __future__ import annotations

import os
import sys


def ensure_venv() -> None:
    """如果当前不是在项目的 .venv 里跑，就用 .venv 的解释器重启自己。"""
    if os.environ.get('JMFAV_NO_VENV') == '1':
        return
    if getattr(sys, 'frozen', False):
        return

    root = os.path.dirname(os.path.abspath(__file__))
    venv_py = os.path.join(root, '.venv', 'Scripts', 'python.exe')
    if not os.path.exists(venv_py):
        return
    if os.path.normcase(sys.executable) == os.path.normcase(venv_py):
        return

    os.environ['JMFAV_NO_VENV'] = '1'
    os.execv(venv_py, [venv_py, os.path.abspath(__file__), *sys.argv[1:]])


def main() -> int:
    ensure_venv()
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    if '--cli' in sys.argv:
        from jmfav.cli import main as cli_main
        argv = [a for a in sys.argv[1:] if a != '--cli']
        return cli_main(argv)

    from jmfav.gui import main as gui_main
    gui_main()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
