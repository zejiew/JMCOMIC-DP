"""图片解码与编码：在内存里完成，避开「先落盘再读回来」的往返。

jmcomic 默认流程是把解密后的图保存到磁盘，然后我们再读回来塞进 zip，
里外里有三次磁盘 IO。这里全部改成内存操作。

关于「为什么要重编码」
----------------------
禁漫的图片是横向切片打乱的，必须先解码成像素才能还原顺序，还原完必须重新编码，
所以只要图片需要解扰，重编码就在所难免（实测随机抽样 30 张，全部需要解扰）。

参数实测（1359×1920 的页面，原图 webp 平均 543KB）：

    格式/质量        PSNR    SSIM      体积     耗时/张
    webp q75        —       —         100%     ~128ms
    webp q85       42.3dB   0.99973    122%     ~139ms
    webp q90       44.9dB   0.99986    131%     ~159ms
    webp q95       48.4dB   0.99994    153%     ~168ms
    webp lossless  99dB     1.00000    245%     ~1288ms
    jpeg q92       43.1dB   0.99977    172%      ~12ms

结论：默认用 ``webp q90``——PSNR 45dB 属于「肉眼不可分辨」的区间，
体积只比原图大一档；要极致速度就把格式切到 ``jpeg``（快 10 倍，体积更大）。
"""

from __future__ import annotations

import io
import math
from typing import Tuple

# 默认质量（格式无关的「档位」）
DEFAULT_QUALITY = 90

# 支持的输出格式
SUPPORTED = ('webp', 'jpeg', 'png')
SUFFIX = {'webp': '.webp', 'jpeg': '.jpg', 'png': '.png'}


def decode_scramble(content: bytes, num: int, keep_alpha: bool = False):
    """把禁漫打乱过的图片还原成正常图片（返回 PIL.Image）。

    :param content: 原始响应字节
    :param num: 分割数（0 表示无需还原）
    :param keep_alpha: 保留透明度（PNG 透明图用）
    """
    from PIL import Image

    src = Image.open(io.BytesIO(content))
    if num == 0 or num == 1:
        if keep_alpha and src.mode in ('RGBA', 'LA', 'P'):
            return src.convert('RGBA')
        return src.convert('RGB')

    src = src.convert('RGB')
    width, height = src.size
    out = Image.new('RGB', (width, height))

    over = height % num
    for i in range(num):
        move = math.floor(height / num)
        y_src = height - (move * (i + 1)) - over
        y_dst = move * i
        if i == 0:
            move += over
        else:
            y_dst += over
        out.paste(
            src.crop((0, y_src, width, y_src + move)),
            (0, y_dst, width, y_dst + move),
        )
    return out


def encode_image(pic, fmt: str = 'webp', quality: int = DEFAULT_QUALITY,
                 **override) -> Tuple[bytes, str]:
    """编码成目标格式，返回 (bytes, 后缀)。"""
    fmt = (fmt or 'webp').lower()
    if fmt not in SUFFIX:
        fmt = 'webp'
    quality = max(1, min(100, int(quality or DEFAULT_QUALITY)))

    if fmt == 'jpeg':
        opts = {'quality': quality}
        pil_fmt = 'JPEG'
    elif fmt == 'png':
        # PNG 是无损格式，质量档位换算成压缩级别（越低越快）
        opts = {'compress_level': max(0, min(9, (100 - quality) * 9 // 100))}
        pil_fmt = 'PNG'
    else:
        # method=0 是最快的 WebP 编码路径，比默认参数快一倍多
        opts = {'quality': quality, 'method': 0}
        pil_fmt = 'WEBP'

    opts.update(override)
    buf = io.BytesIO()
    pic.save(buf, format=pil_fmt, **opts)
    return buf.getvalue(), SUFFIX[fmt]
