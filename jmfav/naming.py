"""文件命名：标题截断 + Windows 非法字符处理。

设计要点：
1. 标题超过最大字数时，直接截断到最大字数（不留省略号）。
2. Windows 不允许 ``<>:"/\\|?*`` 与 ASCII 控制字符，替换为全角同形字符，
   既保住可读性，又不会让文件名变成一串下划线。
3. 末尾的点和空格会被 Windows 吃掉，统一清理。
4. 再按整条路径长度（含输出目录）做一次兜底收缩，避免超过 260 字符上限。
"""

from __future__ import annotations

import os
import re
from typing import Tuple

# 非法字符 → 全角同形字符（可读性优于下划线）
_ILLEGAL_MAP = {
    '<': '＜',
    '>': '＞',
    ':': '：',
    '"': '＂',
    '/': '／',
    '\\': '＼',
    '|': '｜',
    '?': '？',
    '*': '＊',
}

# Windows 保留设备名（不区分大小写，扩展名也受限）
_RESERVED = {
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
}

_WS_RE = re.compile(r'[\s\u3000]+')

DEFAULT_FALLBACK = '未命名'


def sanitize_filename(name: str) -> str:
    """把任意字符串变成 Windows 上合法的文件名片段（不截断）。"""
    if not name:
        return ''

    chars = []
    for ch in str(name):
        if ch in _ILLEGAL_MAP:
            chars.append(_ILLEGAL_MAP[ch])
        elif ord(ch) < 32 or ord(ch) == 127:
            chars.append(' ')
        else:
            chars.append(ch)

    text = ''.join(chars)
    # 折叠空白，去掉首尾空白
    text = _WS_RE.sub(' ', text).strip()
    # Windows 不接受结尾的点和空格
    text = text.rstrip(' .')
    if not text:
        return ''

    # 保留设备名：加下划线前缀破解
    stem = text.split('.')[0].upper()
    if stem in _RESERVED:
        text = f'_{text}'

    return text


def truncate_title(title: str, max_chars: int) -> Tuple[str, bool]:
    """按「字符数」截断标题。

    :param title: 原始标题
    :param max_chars: 最大字符数；<= 0 表示不限制
    :return: (截断后的标题, 是否发生了截断)
    """
    text = (title or '').strip()
    if max_chars is None or max_chars <= 0:
        return text, False
    if len(text) <= max_chars:
        return text, False

    cut = text[:max_chars]
    # 截断点别留下结尾的点、空格、开括号
    cut = cut.rstrip(' .(（[【《<「『-—_·')
    if not cut:
        cut = text[:max_chars]
    return cut, True


def fit_to_path_limit(name: str, output_dir: str, ext: str = '.zip',
                      limit: int = 240) -> str:
    """按整条绝对路径长度压缩文件名，保证 ``输出目录/文件名.zip`` 不超限。"""
    base = os.path.abspath(output_dir or '.')
    # 预留 1 个分隔符
    budget = limit - len(base) - len(ext) - 1
    if budget < 8:
        budget = 8
    if len(name) <= budget:
        return name
    return name[:budget].rstrip(' .')


def build_archive_name(title: str,
                       max_chars: int = 60,
                       template: str = '{title}',
                       album_id: str = '',
                       author: str = '',
                       date: str = '',
                       output_dir: str = '',
                       ext: str = '.zip',
                       name_mode: str = 'smart',
                       raw_title: str = '') -> str:
    """生成压缩包主文件名（不含扩展名）。

    :param title: 已提取好的「作品名」
    :param max_chars: 最多保留几个字，超出截断；0 表示不限制
    :param template: 命名模板，可用 {title} {id} {author} {date}
    :param name_mode: ``smart`` = 用提取出来的作品名（默认）；
                      ``full`` = 用原样完整标题
    :param raw_title: 原始完整标题（``name_mode='full'`` 时使用）

    规则：先按 ``max_chars`` 截断，再套模板，最后做非法字符与路径长度兜底。
    """
    fallback = f'JM{album_id}' if album_id else DEFAULT_FALLBACK

    source = (raw_title or title or '') if name_mode == 'full' else (title or raw_title or '')
    cleaned = sanitize_filename(source)
    short_title, _ = truncate_title(cleaned, max_chars)
    if not short_title:
        short_title = fallback

    values = {
        'title': short_title,
        'author': sanitize_filename(author or ''),
        'id': str(album_id or ''),
        'date': date or '',
    }

    try:
        name = (template or '{title}').format(**values)
    except (KeyError, IndexError, ValueError):
        # 模板写错时退回纯标题，绝不因为模板问题搞丢文件
        name = short_title

    name = sanitize_filename(name)
    if not name:
        name = fallback

    if output_dir:
        name = fit_to_path_limit(name, output_dir, ext=ext)
        name = sanitize_filename(name) or fallback

    return name
