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


def run(title, episodes, suffix='.webp', max_chars=60, split=False):
    out = tempfile.mkdtemp(prefix='jmedge-')
    eng = JmEngine(log=lambda s: None)
    eng.client = FakeClient(title, episodes, suffix=suffix)
    r = eng.download_albums([AlbumStub('999', title)], out,
                            max_title_chars=max_chars, skip_existing=False,
                            split_chapters=split)[0]
    with zipfile.ZipFile(r.paths[0] if r.paths else r.path) as zf:
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

    # 3. 超长标题截断（作者前缀 [作者] 不占字数上限，作品名本身截到 30 字）
    r, names, _ = run('标题' * 100, [('1', '1', 'a')], max_chars=30)
    stem = os.path.basename(r.path)[:-len('.zip')]
    check('标题截到 30 字', stem == '[作者] ' + '标题' * 15, stem)

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

    # 8. 分章模式：每章一个包、编号补零、包里不带子目录
    eps8 = [(str(i), str(i), f'第{i}话') for i in range(1, 4)]
    r, names, out8 = run('分章', eps8, max_chars=0, split=True)
    files = sorted(f for f in os.listdir(out8) if f.endswith('.zip'))
    check('分章生成 3 个包', len(files) == 3 and r.ok and len(r.paths) == 3,
          f'{files} paths={len(r.paths)}')
    check('分章包名带补零编号', files[0].startswith('001 ') and
          files[2].startswith('003 '), files)
    check('分章包名带作品名', all('分章' in f for f in files), files)
    check('分章包内无子目录', all('/' not in n for n in names), names)
    check('分章计数是总张数', r.images == 6, str(r.images))

    # 8b. 章节名是空串（禁漫上很常见）时，包名至少还有编号与作品名
    eps8b = [('1', '1', ''), ('2', '2', ''), ('3', '3', '')]
    r, _, out8b = run('无名章节', eps8b, max_chars=0, split=True)
    files = sorted(f for f in os.listdir(out8b) if f.endswith('.zip'))
    check('空章节名也能认', len(files) == 3 and all('无名章节' in f for f in files),
          files)

    # 9. 分章模式：同名章节不会互相覆盖
    eps9 = [('1', '1', '同名'), ('2', '2', '同名')]
    r, _, out9 = run('重名分章', eps9, max_chars=0, split=True)
    files = [f for f in os.listdir(out9) if f.endswith('.zip')]
    check('重名章节各自成包', len(files) == 2, files)

    # 10. 分章模式：另一本书占了同名（无法认领），必须让路而不是跳过
    r, _, out10 = run('甲', [('1', '1', '第1话'), ('2', '2', '第2话')],
                      max_chars=0, split=True)
    first = os.path.join(out10, '001 [作者] 甲 第1话.zip')
    check('第一本生成 001', os.path.exists(first), sorted(os.listdir(out10)))
    # 把标记改成别人的书号，模拟「同名不同本」
    with zipfile.ZipFile(first, 'a') as zf:
        zf.comment = b'jmsrc:{"album_id":"888888"}'
    eng = JmEngine(log=lambda s: None)
    eng.client = FakeClient('甲', [('1', '1', '第1话'), ('2', '2', '第2话')])
    r10 = eng.download_albums([AlbumStub('999', '甲')], out10,
                              max_title_chars=0, skip_existing=True,
                              split_chapters=True)[0]
    # 换了个书号（888888 → 999），认领不上，必须重下而不是当成自己的跳过
    check('异本同名重下', not r10.skipped and r10.images == 4,
          f'skipped={r10.skipped} images={r10.images}')

    # 11. 分章模式：同一本书重下 → 全部跳过（包括刚重下的那个副本）
    r11 = eng.download_albums([AlbumStub('999', '甲')], out10,
                              max_title_chars=0, skip_existing=True,
                              split_chapters=True)[0]
    check('同本重下跳过', r11.skipped and r11.ok, f'skipped={r11.skipped}')

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
