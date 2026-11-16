"""更大范围的参数扫描：找「体积接近原图」的编码参数。"""

import io
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption, JmImageTool

from jmfav.codec import decode_scramble


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    client.check_photo(album[0])
    images = list(album[0])[:6]

    pics, orig = [], 0
    for img in images:
        raw = client.get_jm_image(img.download_url).content
        orig += len(raw)
        pics.append(decode_scramble(raw, JmImageTool.get_num_by_detail(img)))
    orig /= len(images)
    print(f'原图平均 {orig / 1024:.0f}KB')
    print(f'{"参数":<26}{"体积":>9}{"比例":>8}{"耗时":>10}')

    cases = []
    for q in (60, 70, 75, 80, 82, 85, 88, 92, 95):
        cases.append((f'webp q{q} m0', 'WEBP', {'quality': q, 'method': 0}))
    for m in (4, 6):
        cases.append((f'webp q80 m{m}', 'WEBP', {'quality': 80, 'method': m}))
    for q in (80, 85, 90):
        cases.append((f'jpeg q{q} 420', 'JPEG', {'quality': q, 'subsampling': 2}))
    cases.append(('jpeg q85 444', 'JPEG', {'quality': 85, 'subsampling': 0}))

    for label, fmt, kw in cases:
        sizes, cost = [], 0.0
        for pic in pics:
            t0 = time.time()
            buf = io.BytesIO()
            pic.save(buf, format=fmt, **kw)
            cost += time.time() - t0
            sizes.append(buf.tell())
        avg = sum(sizes) / len(sizes)
        print(f'{label:<26}{avg / 1024:>7.0f}KB{avg / orig * 100:>7.0f}%'
              f'{cost / len(pics) * 1000:>8.0f}ms')


if __name__ == '__main__':
    main()
