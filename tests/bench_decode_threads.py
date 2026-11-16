"""验证「解码+编码」能否被线程并行加速（PIL 是否释放 GIL）。"""

import io
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

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
    images = list(album[0])[:12]

    raws = []
    for img in images:
        raws.append((client.get_jm_image(img.download_url).content,
                     JmImageTool.get_num_by_detail(img)))

    def work(item):
        content, num = item
        pic = decode_scramble(content, num)
        return encode_image(pic, 'webp', quality=95, method=0)[0]

    for workers in (1, 4, 8):
        t0 = time.time()
        if workers == 1:
            out = [work(x) for x in raws]
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                out = list(pool.map(work, raws))
        cost = time.time() - t0
        print(f'  并发 {workers:>2}: {cost:6.2f}s · {len(out)} 张 · '
              f'{len(out) / cost:5.1f} 张/秒 · 平均 {cost / len(out) * 1000:6.1f}ms/张')


if __name__ == '__main__':
    main()
