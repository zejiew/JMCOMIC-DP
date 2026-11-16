"""从禁漫的长标题里提取「作品名」部分。

禁漫的标题往往长这样：

    [漢化組] [作者 (社團)] 作品名 (原作出處) [語言] [版本]

真正能指代作品的就是"作品名"那一段。本模块把它剥出来，规则是：

1. 按括号切成若干段（支持 [] 【】 () （） 《》）。
2. 从**第一个非括号、且不是纯元数据**的段开始 —— 前面那些 [漢化組]/[作者] 都跳过。
3. 向后只接纳**紧贴**（中间没有空格）的段：
   - 噪声括号（[中國翻譯]、[DL版]、[AI Generated]…）跳过但不打断
   - 圆括号（原作出处，如 (ブルーアーカイブ)）保留
   - 一旦遇到空格就停 —— 空格之后基本都是另一种语言的重复、作者、汉化组
4. 累计已有正文后，再紧贴的**方括号**一律视为元数据并停止。
5. 剩下的再按 `/` `|` 切多语言变体，取中文字符最多的那个。
6. 最后清掉尾部残留的方括号与点缀符。

实测 603 条真实标题，绝大多数能收敛到 30 字以内的干净作品名。
"""

from __future__ import annotations

import re
from typing import List, Tuple

# 括号对
PAIRS = {'(': ')', '[': ']', '【': '】', '（': '）', '《': '》', '〈': '〉', '「': '」', '『': '』'}
CLOSERS = set(PAIRS.values())
SQUARE_OPEN = {'[', '【'}
ROUND_OPEN = {'(', '（', '《', '〈', '「', '『'}

# 元数据关键词：出现即认为是「不是作品名」的括号
NOISE_RE = re.compile(
    r'漢化|汉化|翻譯|翻译|机翻|機翻|字幕|個人|个人|出資|出资|'
    r'AI\s*Generated|AI生成|AI渣翻|AI翻譯|AI汉化|'
    r'^chinese|^中國語|^中国语|^中文|^中字|^cn$|^tw$|^jp$|^kr$|'
    r'^dl版|^digital|無修正|无修正|^全彩|フルカラー|'
    r'^完$|^完結|^完结|^全\d+卷|^全\d+話|單行本|单行本|無碼|无码|修圖|修图|'
    r'^vol\.?\s*\d+$|^c\d{2,3}$|^ff\d{2,6}$|fanbox|^同人志$|^同人誌$|'
    r'^高清|^合集|^總集篇|^总集篇|^單篇|^短篇|^第\d+[卷話话集]|'
    r'^[a-z]{2,4}$',
    re.I,
)

# 允许在正文之后继续追加的「短尾巴」（如 第二部 / EX / Vol.2）
TAIL_OK_RE = re.compile(r'^(第[\d一二三四五六七八九十百]+[部卷話话集篇]|EX|Vol\.?\s*\d+|\d{1,2})$', re.I)


def _normalize_brackets(text: str) -> str:
    """把落单/错配的括号换成正确的配对，方便后续切分。"""
    chars = list(text)
    stack: List[str] = []
    for i, ch in enumerate(chars):
        if ch in PAIRS:
            stack.append(ch)
        elif ch in CLOSERS:
            # 找栈里有没有能配对的
            want = None
            for k in range(len(stack) - 1, -1, -1):
                if PAIRS[stack[k]] == ch:
                    want = k
                    break
            if want is None:
                # 无主右括号 → 换成同形的左括号（当作开启新括号）
                for open_ch, close_ch in PAIRS.items():
                    if close_ch == ch:
                        chars[i] = open_ch
                        stack.append(open_ch)
                        break
            else:
                del stack[want:]
    # 未闭合的左括号直接删掉
    if stack:
        opens = set(stack)
        for i, ch in enumerate(chars):
            if ch in opens:
                chars[i] = ''
                opens.discard(ch)
    return ''.join(chars)


def _spans(text: str) -> List[Tuple[str, int, int, bool]]:
    """切成 [(片段, 起点, 终点, 是否括号)]。"""
    out: List[Tuple[str, int, int, bool]] = []
    buf_start = None
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in PAIRS:
            if buf_start is not None:
                piece = text[buf_start:i]
                if piece.strip():
                    out.append((piece.strip(), buf_start, i, False))
                buf_start = None
            depth, j = [ch], i + 1
            while j < n and depth:
                c2 = text[j]
                if c2 in PAIRS:
                    depth.append(c2)
                elif c2 == PAIRS[depth[-1]]:
                    depth.pop()
                j += 1
            if depth:
                buf_start = i if buf_start is None else buf_start
                i += 1
                continue
            out.append((text[i:j], i, j, True))
            i = j
        else:
            if buf_start is None and not ch.isspace():
                buf_start = i
            i += 1
    if buf_start is not None:
        piece = text[buf_start:]
        if piece.strip():
            out.append((piece.strip(), buf_start, n, False))
    return out


def _inner(token: str) -> str:
    return token[1:-1].strip() if len(token) >= 2 else token


def _is_noise(token: str) -> bool:
    body = _inner(token) if token[:1] in PAIRS else token
    return bool(NOISE_RE.search(body.strip()))


def _is_round(token: str) -> bool:
    return token[:1] in ROUND_OPEN


def _cjk_count(text: str) -> int:
    return len(re.findall(r'[\u4e00-\u9fff]', text))


def _has_kana(text: str) -> bool:
    return bool(re.search(r'[\u3040-\u30ff]', text))


def split_variants(core: str) -> List[str]:
    """按 / | ｜ 切多语言变体（不切括号内部）。"""
    parts, buf, depth = [], [], 0
    for ch in core:
        if ch in PAIRS:
            depth += 1
        elif ch in CLOSERS:
            depth = max(0, depth - 1)
        if ch in '/|｜／' and depth == 0:
            piece = ''.join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
            continue
        buf.append(ch)
    piece = ''.join(buf).strip()
    if piece:
        parts.append(piece)
    return parts


def pick_variant(parts: List[str]) -> str:
    """多个语言版本时，优先中文最多的那个。"""
    if not parts:
        return ''
    if len(parts) == 1:
        return parts[0]
    best_i, best_score = 0, -1
    for i, p in enumerate(parts):
        score = _cjk_count(p) * 2 - _kana_count(p)
        if score > best_score:
            best_i, best_score = i, score
    return parts[best_i]


def _kana_count(text: str) -> int:
    return len(re.findall(r'[\u3040-\u30ff]', text))


def extract_core(title: str, max_extend: int = 100) -> str:
    """剥出核心作品名（不去多语言变体）。"""
    text = (title or '').strip()
    if not text:
        return ''

    text = _normalize_brackets(text)
    toks = _spans(text)
    if not toks:
        return text

    # 起点：第一个非括号、非纯元数据的段
    start = None
    for idx, (tok, _s, _e, is_br) in enumerate(toks):
        if is_br:
            continue
        if _is_noise(tok) and len(tok) <= 16:
            continue
        start = idx
        break

    if start is None:
        # 整条都在括号里：挑最长的非噪声括号内容
        cands = [_inner(t) for t, _s, _e, br in toks if br and not _is_noise(t)]
        cands = [c for c in cands if c and re.search(r'[\w\u4e00-\u9fff]', c)]
        return max(cands, key=len) if cands else text

    _t0, s0, e0, _ = toks[start]
    end = e0
    last = start
    prev_end = e0
    acc = text[s0:e0]

    for idx in range(start + 1, len(toks)):
        tok, s, e, is_br = toks[idx]
        if text[prev_end:s] != '':          # 中间有空格/其他字符 → 停
            break
        if end - s0 > max_extend:           # 太长了，不再吞
            break

        if is_br and _is_noise(tok):        # 噪声括号：跳过但不打断
            prev_end = e
            continue

        if is_br:
            if _is_round(tok):
                end, prev_end, last = e, e, idx      # 圆括号=原作出处，保留
                continue
            break                                      # 其它方括号=元数据，停

        # 非括号紧贴文本：已经攒够正文时，只接受很短的续尾
        if len(acc) >= 4 and not TAIL_OK_RE.match(tok):
            if _has_kana(acc) != _has_kana(tok) and len(tok) >= 4:
                break                                  # 语言突变 → 是另一种语言的标题
            if len(tok) >= 6 and _cjk_count(acc) and not _cjk_count(tok):
                break
        end, prev_end, last = e, e, idx
        acc = text[s0:end]

    # 去掉尾部方括号残留
    while last > start:
        tok, _s, _e, is_br = toks[last]
        if is_br and (tok[:1] in SQUARE_OPEN or _is_noise(tok)):
            end = toks[last - 1][2]
            last -= 1
            continue
        break

    return text[s0:end].strip()


_TRAILING_BRACKET_RE = re.compile(r'\s*[\[【][^\[\]【】]{0,50}[\]】]\s*$')
_EDGE_PUNCT_RE = re.compile(r'^[\s\-—–~〜・、,，:：;；!！?？+＋*]+|[\s\-—–~〜・、,，:：;；]+$')


def clean_title(title: str, max_extend: int = 100) -> str:
    """把长标题洗成「作品名」（默认用于文件命名）。"""
    core = extract_core(title, max_extend)
    core = pick_variant(split_variants(core))

    # 多语言选取后可能又露出尾部方括号，再清几轮
    for _ in range(4):
        m = _TRAILING_BRACKET_RE.search(core)
        if not m:
            break
        body = m.group(0).strip()[1:-1]
        if NOISE_RE.search(body):
            core = core[:m.start()].strip()
            continue
        break

    core = _EDGE_PUNCT_RE.sub('', core).strip()
    # 书名号包着的直接留内容
    if len(core) >= 2 and core[0] in '《「『' and core[-1] in '》」』':
        core = core[1:-1].strip()

    return core or (title or '').strip()
