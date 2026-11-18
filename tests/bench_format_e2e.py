"""端到端对比：不同图片格式对整本下载耗时与体积的影响。"""

import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmOption

from jmfav.engine import AlbumStub, JmEngine


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    client = option.new_jm_client(impl='api')
    album = client.get_album_detail(album_id)
    print(f'{album.title} | {album.page_count} 页\n')

    engine = JmEngine(log=lambda s: None)
    engine.client = client

    for fmt in ('jpeg', 'webp'):
        out = tempfile.mkdtemp(prefix='jmfmt-')
        t0 = time.time()
        r = engine.download_albums([AlbumStub(album_id, album.title)], out,
                                   image_threads=12, skip_existing=False,
                                   image_format=fmt,
                                   split_chapters=False)[0]
        cost = time.time() - t0
        size = sum(os.path.getsize(p) for p in (r.paths or [r.path])) / 1024 / 1024
        print(f'  {fmt:<6} {cost:6.2f}s · {r.images / cost:5.1f} 张/秒 · {size:5.1f}MB')
        shutil.rmtree(out, ignore_errors=True)


if __name__ == '__main__':
    main()
