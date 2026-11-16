"""从用户输入里解析本子车号。

支持这些写法：

    123456                                  纯数字
    JM123456 / jm123456                     带 JM 前缀
    https://18comic.vip/album/123456/       网页链接
    https://www.cdngwc.cc/album?id=123456   带 ?id= 的链接（API 域名）
    https://18comic.org/comic/123456        另一种路径
    【123456】 / (123456)                   从标题里粘出来
    https://18comic.vip/photo/987654        章节链接（也能拿到所属本子）
    jmcomic 的 id 列表里混着中文，取最长数字串
"""

from __future__ import annotations

import re

# 明确指向本子的路径
_ALBUM_PATH_RE = re.compile(
    r'/(?:album|comic|photo)/(\d+)', re.I)
# ?id= 或 &id=
_ID_PARAM_RE = re.compile(r'[?&]id=(\d+)', re.I)
# JM 前缀
_JM_PREFIX_RE = re.compile(r'\bJM\s*[-_]?\s*(\d{3,})', re.I)
# 纯数字（允许前后有括号/空格/方括号）
_PURE_NUM_RE = re.compile(r'^\s*[\[\(【（]?\s*(\d{3,})\s*[\]\)】）]?\s*$')
# 兜底：最长的一串数字
_ANY_NUM_RE = re.compile(r'\d{3,}')


def parse_album_id(text: str) -> str:
    """把各种写法统一成纯数字 ID；解析不出来就抛 ValueError。"""
    raw = (text or '').strip()
    if not raw:
        raise ValueError('请输入车号或链接')

    for pattern in (_ALBUM_PATH_RE, _ID_PARAM_RE, _JM_PREFIX_RE, _PURE_NUM_RE):
        m = pattern.search(raw)
        if m:
            return m.group(1)

    nums = _ANY_NUM_RE.findall(raw)
    if nums:
        return max(nums, key=len)

    raise ValueError(f'没识别出车号：{raw[:60]}')


def try_parse_album_id(text: str) -> str:
    """解析失败返回空串（不抛异常）。"""
    try:
        return parse_album_id(text)
    except ValueError:
        return ''


def parse_album_ids(text: str) -> list:
    """解析一批 ID（换行/逗号/空格分隔，可混链接），保持顺序并去重。"""
    out = []
    for chunk in re.split(r'[\s,，;；、]+', text or ''):
        chunk = chunk.strip()
        if not chunk:
            continue
        aid = try_parse_album_id(chunk)
        if aid and aid not in out:
            out.append(aid)
    return out


def looks_like_id(text: str) -> bool:
    """输入像是车号（而不是搜索关键词）。"""
    raw = (text or '').strip()
    if not raw:
        return False
    if _PURE_NUM_RE.match(raw) or _JM_PREFIX_RE.search(raw):
        return True
    if _ALBUM_PATH_RE.search(raw) or _ID_PARAM_RE.search(raw):
        return True
    return False
