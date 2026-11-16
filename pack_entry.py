"""PyInstaller 打包入口（GUI 版，无控制台窗口）。

启动流程：
1. ``--splash`` 由 PyInstaller 的 bootloader 负责，在 Python 起来之前就显示
   （单文件 exe 解压自身要两三秒，那段时间全靠它给反馈）。
2. 主窗口建好后关掉 splash 并把自己提到前台，任务栏也要有图标。
3. 任何异常都弹窗（打包后没有控制台，否则错误信息无处可看）。
"""

from __future__ import annotations

import os
import sys
import traceback


def _show_fatal(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('JM 下载器 启动失败', message)
        root.destroy()
    except Exception:
        pass


def _close_splash() -> None:
    """PyInstaller 的 splash 只能在 pyi_splash 模块可用时关闭。"""
    try:
        import pyi_splash  # type: ignore  # noqa: F401
        pyi_splash.close()
    except Exception:
        pass


def _set_taskbar_icon(app) -> None:
    """让任务栏显示我们自己的图标（否则是 python 的默认图标）。"""
    candidates = []
    base = getattr(sys, '_MEIPASS', None)
    if base:
        candidates.append(os.path.join(base, 'icon.ico'))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico'))

    for path in candidates:
        if os.path.exists(path):
            try:
                app.iconbitmap(default=path)
                return
            except Exception:
                continue


def main() -> int:
    try:
        from jmfav.gui import JmApp

        app = JmApp()

        app.after(60, _close_splash)
        _set_taskbar_icon(app)

        app.lift()
        app.focus_force()
        app.mainloop()
        return 0
    except Exception:
        _close_splash()
        detail = traceback.format_exc()
        _show_fatal(
            '程序启动失败，请把下面的信息发给开发者：\n\n'
            + detail[-1500:]
        )
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
