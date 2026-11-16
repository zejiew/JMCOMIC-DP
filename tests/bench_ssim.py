"""用 SSIM/PSNR 量化不同重编码参数相对原图的画质损失。"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption, JmImageTool
from PIL import Image

from jmfav.codec import decode_scramble


def psnr(a: Image.Image, b: Image.Image) -> float:
    import math
    from PIL import ImageChops
    diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    hist = diff.histogram()
    sq = 0
    for band in range(3):
        for v in range(256):
            count = hist[band * 256 + v]
            sq += count * (v ** 2)
    mse = sq / (a.size[0] * a.size[1] * 3)
    if mse == 0:
        return 99.0
    return 10 * math.log10((255 ** 2) / mse)


def ssim_simple(a: Image.Image, b: Image.Image) -> float:
    """简化版 SSIM（全局，不做分块高斯窗），够用来比较相对高低。"""
    import numpy as np
    x = np.asarray(a.convert('L'), dtype=np.float64)
    y = np.asarray(b.convert('L'), dtype=np.float64)
    mx, my = x.mean(), y.mean()
    vx, vy = x.var(), y.var()
    cxy = ((x - mx) * (y - my)).mean()
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    return ((2 * mx * my + c1) * (2 * cxy + c2)) / ((mx ** 2 + my ** 2 + c1) * (vx + vy + c2))


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    client.check_photo(album[0])
    images = list(album[0])[:4]

    refs, orig_size = [], 0
    for img in images:
        raw = client.get_jm_image(img.download_url).content
        orig_size += len(raw)
        refs.append(decode_scramble(raw, JmImageTool.get_num_by_detail(img)))

    print(f'{"参数":<20}{"PSNR":>8}{"SSIM":>9}{"体积比":>10}')
    for label, fmt, kw in (
        ('webp q85', 'WEBP', {'quality': 85, 'method': 0}),
        ('webp q90', 'WEBP', {'quality': 90, 'method': 0}),
        ('webp q92', 'WEBP', {'quality': 92, 'method': 0}),
        ('webp q95', 'WEBP', {'quality': 95, 'method': 0}),
        ('webp lossless', 'WEBP', {'lossless': True}),
        ('jpeg q92', 'JPEG', {'quality': 92}),
        ('png', 'PNG', {'compress_level': 1}),
    ):
        ps, ss, size = [], [], 0
        for pic in refs:
            buf = io.BytesIO()
            pic.save(buf, format=fmt, **kw)
            size += buf.tell()
            back = Image.open(io.BytesIO(buf.getvalue()))
            ps.append(psnr(pic, back))
            ss.append(ssim_simple(pic, back))
        print(f'{label:<20}{sum(ps) / len(ps):>8.2f}{sum(ss) / len(ss):>9.5f}'
              f'{size / orig_size * 100:>9.0f}%')


if __name__ == '__main__':
    main()
