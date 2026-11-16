"""路径选择（GUI 与 CLI 共用，避免 CLI 被迫加载 tkinter）。

规则：
- 程序目录：开发时是项目根，打包后是 exe 所在目录。
- 配置文件：优先放在程序目录；如果那儿不可写（例如放在 Program Files），
  自动退到 ``%APPDATA%\\JmDownloader\\config.json``，不因为写不了配置就崩。
- 默认下载目录：程序目录下的 ``downloads``；程序目录不可写时退到"下载"文件夹。
"""

from __future__ import annotations

import os
import sys

APP_NAME = 'JmDownloader'


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def app_dir() -> str:
    """程序所在目录（打包成 exe 后跟 exe 走）。"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(path: str) -> bool:
    """判断目录能不能写（真正去写一个探针文件，比 os.access 可靠）。"""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, f'.write_test_{os.getpid()}')
        with open(probe, 'w', encoding='utf-8') as fp:
            fp.write('x')
        os.remove(probe)
        return True
    except OSError:
        return False


def data_dir() -> str:
    """配置 / cookies 的落盘目录。"""
    prefer = app_dir()
    if _writable(prefer):
        return prefer

    base = os.environ.get('APPDATA') or os.path.expanduser('~')
    fallback = os.path.join(base, APP_NAME)
    try:
        os.makedirs(fallback, exist_ok=True)
    except OSError:
        fallback = os.path.expanduser('~')
    return fallback


def default_output_dir() -> str:
    """默认下载目录。"""
    local = os.path.join(app_dir(), 'downloads')
    if _writable(local):
        return local

    # 退到系统「下载」文件夹
    home = os.path.expanduser('~')
    downloads = os.path.join(home, 'Downloads')
    return downloads if os.path.isdir(downloads) else os.path.join(home, 'JM下载')


CONFIG_PATH = os.path.join(data_dir(), 'config.json')
DEFAULT_OUTPUT = default_output_dir()
