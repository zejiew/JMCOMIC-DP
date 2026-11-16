"""边界用例：重名章节、超长章节名、超长标题、中文标点、emoji。"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmAlbumDetail

from jmfav.engine import AlbumStub, JmEngine


class FakeResp:
    def __init__(self, content):
        self.content = content

    def require_success(self):
        return None


def image_bytes(fmt='WEBP'):
    from io import BytesIO
    from PIL import Image
    img = Image.new('RGB', (80, 120), (30, 90, 200))
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class FakeClient:
    def __init__(self, title, episodes, per_photo=2, suffix='.webp'):
        self.title, self.episodes, self.per_photo = title, episodes, per_photo
        self.suffix = suffix
        self.blob = image_bytes('WEBP' if suffix == '.webp' else 'PNG')

    def get_album_detail(self, album_id):
        return JmAlbumDetail(
            album_id=str(album_id), scramble_id='0', name=self.title,
            episode_list=self.episodes,
            page_count=len(self.episodes) * self.per_photo,
            pub_date='', update_date='2024-05-06', likes='0', views='0',
            comment_count=0, works=[], actors=[], authors=['作者'],
            tags=[],
        )

    def check_photo(self, photo):
        photo.page_arr = [f'{i:05d}{self.suffix}' for i in range(1, self.per_photo + 1)]
        photo.data_original_domain = 'cdn.example.com'
        photo.scramble_id = '0'

    def get_jm_image(self, url):
        return FakeResp(self.blob)


def run(title, episodes, suffix='.webp', max_chars=60):
    out = tempfile.mkdtemp(prefix='jmedge-')
    eng = JmEngine(log=lambda s: None)
    eng.client = FakeClient(title, episodes, suffix=suffix)
    r = eng.download_albums([AlbumStub('999', title)], out,
                            max_title_chars=max_chars, skip_existing=False)[0]
    with zipfile.ZipFile(r.path) as zf:
        names = zf.namelist()
    return r, names, out


def main():
    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    # 1. 同名章节必须被区分开，否则 zip 内互相覆盖
    eps = [('1', '1', '同一个名字'), ('2', '2', '同一个名字'), ('3', '3', '同一个名字')]
    r, names, _ = run('重名测试', eps, max_chars=0)
    dirs = sorted({n.split('/')[0] for n in names if '/' in n})
    check('重名章节不冲突', len(dirs) == 3, dirs)
    check('重名章节都有编号', dirs[0].startswith('001'), dirs)

    # 2. 超长章节名要限长（不进 zip 里变成几百字目录）
    long_name = '超长章节标题' * 40
    eps2 = [('1', '1', long_name), ('2', '2', '短')]
    r, names, _ = run('超长章节名', eps2, max_chars=0)
    dirs = [n.split('/')[0] for n in names if '/' in n]
    check('章节名限长', all(len(d) <= 96 for d in dirs), [len(d) for d in dirs])

    # 3. 超长标题截断
    r, names, _ = run('标题' * 100, [('1', '1', 'a')], max_chars=30)
    check('标题截到 30 字', len(os.path.basename(r.path)) == 30 + 4,
          os.path.basename(r.path)[:40])

    # 4. 中文标点与特殊符号保留
    r, _, _ = run('引号「」·波浪～破折—省略…', [('1', '1', 'a')], max_chars=0)
    check('中文标点保留', '「」' in os.path.basename(r.path), os.path.basename(r.path))

    # 5. emoji（非 BMP 字符）不应炸
    r, _, _ = run('标题🎉🎊测试', [('1', '1', 'a')], max_chars=0)
    check('emoji 不炸', r.ok and '测试' in os.path.basename(r.path),
          os.path.basename(r.path))

    # 6. png 原图走 png 输出
    r, names, _ = run('png测试', [('1', '1', 'a')], suffix='.png', max_chars=0)
    check('png 保持 png', all(n.endswith('.png') for n in names), names)

    # 7. 单章不带目录
    r, names, _ = run('单章', [('1', '1', 'a')], max_chars=0)
    check('单章无子目录', all('/' not in n for n in names), names)

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
