"""内存编解码下的线程数扫描（新引擎）。"""

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
    print(f'{album.title} | {album.page_count} 页')

    engine = JmEngine(log=lambda s: None)
    engine.client = client

    for threads in (4, 8, 12, 16):
        out = tempfile.mkdtemp(prefix='jmbench-')
        t0 = time.time()
        r = engine.download_albums([AlbumStub(album_id, album.title)], out,
                                   image_threads=threads, skip_existing=False,
                                   split_chapters=False)[0]
        cost = time.time() - t0
        size = sum(os.path.getsize(p) for p in (r.paths or [r.path])) / 1024 / 1024
        print(f'  线程 {threads:>2}: {cost:6.2f}s · {r.images:>3} 张 · '
              f'{r.images / cost:5.1f} 张/秒 · {size:5.1f}MB')
        shutil.rmtree(out, ignore_errors=True)


if __name__ == '__main__':
    main()
