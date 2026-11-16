"""体积与质量权衡：对比「原图大小」与不同重编码参数产出的体积。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption, JmImageTool

from jmfav.codec import decode_scramble, encode_image


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    client.check_photo(album[0])
    images = list(album[0])[:8]

    samples = []
    for img in images:
        raw = client.get_jm_image(img.download_url).content
        samples.append((raw, JmImageTool.get_num_by_detail(img)))

    orig = sum(len(r) for r, _ in samples) / len(samples)
    print(f'原图平均 {orig / 1024:.0f}KB × {len(samples)} 张')
    print(f'{"参数":<22}{"平均体积":>10}{"相对原图":>10}{"总大小(52页)":>14}')

    for label, fmt, kw in (
        ('webp q95 m0', 'webp', {'quality': 95, 'method': 0}),
        ('webp q92 m0', 'webp', {'quality': 92, 'method': 0}),
        ('webp q90 m0', 'webp', {'quality': 90, 'method': 0}),
        ('webp q88 m0', 'webp', {'quality': 88, 'method': 0}),
        ('webp q85 m0', 'webp', {'quality': 85, 'method': 0}),
        ('jpeg q92', 'jpeg', {'quality': 92}),
    ):
        sizes = []
        for raw, num in samples:
            pic = decode_scramble(raw, num)
            data, _ = encode_image(pic, fmt, **kw)
            sizes.append(len(data))
        avg = sum(sizes) / len(sizes)
        print(f'{label:<22}{avg / 1024:>8.0f}KB{avg / orig * 100:>9.0f}%'
              f'{avg * 52 / 1024 / 1024:>12.1f}MB')


if __name__ == '__main__':
    main()
