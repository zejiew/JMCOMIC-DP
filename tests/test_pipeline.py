"""离线端到端测试：不联网，用假 client 验证下载→打包→命名整条链路。"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jmcomic import JmAlbumDetail, JmPhotoDetail

from jmfav.engine import JmEngine


class FakeResp:
    def __init__(self, content):
        self.content = content

    def require_success(self):
        return None


def make_image_bytes(width=120, height=180, fmt='WEBP') -> bytes:
    from io import BytesIO
    from PIL import Image
    img = Image.new('RGB', (width, height))
    # 画点东西，避免全纯色编码出极小的字节
    for y in range(height):
        for x in range(0, width, 7):
            img.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    buf = BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class FakeClient:
    """模拟 jmcomic client 的少数接口。"""

    def __init__(self, title, photos, per_photo):
        self.title = title
        self.per_photo = per_photo
        self.photo_count = photos
        self.requested = []
        self.jpeg = make_image_bytes(fmt='WEBP')

    def get_album_detail(self, album_id):
        episodes = [(str(1000 + i), str(i + 1), f'第{i + 1}话')
                    for i in range(self.photo_count)]
        album = JmAlbumDetail(
            album_id=str(album_id),
            scramble_id='220980',
            name=self.title,
            episode_list=episodes,
            page_count=self.photo_count * self.per_photo,
            pub_date='2024-01-01',
            update_date='2024-02-02',
            likes='1K',
            views='2K',
            comment_count=0,
            works=[],
            actors=[],
            authors=['测试作者'],
            tags=[],
        )
        return album

    def check_photo(self, photo):
        photo.page_arr = [f'{i:05d}.webp' for i in range(1, self.per_photo + 1)]
        photo.data_original_domain = 'cdn.example.com'
        photo.scramble_id = '220980'

    def is_api(self):
        return True

    def get_jm_image(self, img_url):
        self.requested.append(img_url)
        return FakeResp(self.jpeg)


def run(title, photos=2, per_photo=3, max_chars=60, template='{title}', compress=0,
        threads=4, skip=True, output_dir=None):
    output_dir = output_dir or tempfile.mkdtemp(prefix='jmtest-')
    engine = JmEngine(log=lambda s: None)
    engine.client = FakeClient(title, photos, per_photo)

    from jmfav.engine import AlbumStub
    results = engine.download_albums(
        [AlbumStub('123456', title)], output_dir,
        max_title_chars=max_chars,
        template=template,
        compress_level=compress,
        image_threads=threads,
        skip_existing=skip,
    )
    return results[0], output_dir


def main():
    ok = True

    def check(label, cond, extra=''):
        nonlocal ok
        print(('PASS ' if cond else 'FAIL ') + label + (f'  {extra}' if extra else ''))
        if not cond:
            ok = False

    long_title = '[無邪氣漢化組] (C99) [紺色果實] サレンの樂しい夢 (プリンセスコネクト!Re:Dive) [中國翻譯]'

    # 1. 基本：多章节打包 + 章节子目录 + 顺序
    r, out = run(long_title, photos=3, per_photo=4, max_chars=26)
    check('下载成功', r.ok, r.error)
    check('图片张数', r.images == 12, f'images={r.images}')
    check('标题被洗成作品名', r.short_title.startswith('サレンの樂しい夢'), r.short_title)
    check('文件名不含汉化组', '無邪氣' not in os.path.basename(r.path),
          os.path.basename(r.path))
    with zipfile.ZipFile(r.path) as zf:
        names = zf.namelist()
    check('zip 条目数', len(names) == 12, str(len(names)))
    check('含章节子目录', all(n.count('/') == 1 for n in names), names[:2])
    check('顺序正确', names[0].endswith('00001.webp'), names[0])
    check('无中间文件残留', not os.path.exists(os.path.join(out, '.jmtmp')),
          str(os.listdir(out)))

    # 2. 单章：不放子目录
    r2, out2 = run('短标题', photos=1, per_photo=5)
    with zipfile.ZipFile(r2.path) as zf:
        n2 = zf.namelist()
    check('单章不建子目录', all('/' not in n for n in n2), n2[:2])
    check('单章文件名', os.path.basename(r2.path) == '[测试作者] 短标题.zip',
          os.path.basename(r2.path))

    # 3. 已存在则跳过
    r3, _ = run(long_title, photos=3, per_photo=4, max_chars=26, output_dir=out)
    check('已存在跳过', r3.skipped and r3.ok, f'skipped={r3.skipped}')

    # 4. 不跳过 → 生成 (2)
    r4, _ = run(long_title, photos=3, per_photo=4, max_chars=26, output_dir=out, skip=False)
    check('不覆盖生成副本', os.path.basename(r4.path).endswith(' (2).zip'),
          os.path.basename(r4.path))

    # 5. 非法字符（提取后「a」留下，后面的全是分隔符）
    r5, _ = run('a/b:c*?"<>|', photos=1, per_photo=2, max_chars=0)
    check('非法字符不出现', not any(c in os.path.basename(r5.path) for c in '<>:"/\\|?*'),
          os.path.basename(r5.path))

    # 6. 模板 + 压缩级别（模板里写了 {author} → 不再自动加作者前缀）
    r6, _ = run('模板测试', photos=1, per_photo=3, template='{id} {title}', compress=6)
    check('模板生效', os.path.basename(r6.path) == '123456 [测试作者] 模板测试.zip',
          os.path.basename(r6.path))
    r6b, _ = run('模板测试', photos=1, per_photo=3,
                 template='{title} - {author}', compress=0)
    check('模板自写作者不重复', os.path.basename(r6b.path) == '模板测试 - 测试作者.zip',
          os.path.basename(r6b.path))
    with zipfile.ZipFile(r6.path) as zf:
        check('压缩写入正常', zf.testzip() is None and len(zf.namelist()) == 3)

    # 7. 空标题兜底（用本子 ID）
    r7, _ = run('', photos=1, per_photo=1, max_chars=0)
    check('空标题兜底', os.path.basename(r7.path) == 'JM123456.zip', os.path.basename(r7.path))

    print('\nRESULT:', 'ALL PASS' if ok else 'HAS FAILURES')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
