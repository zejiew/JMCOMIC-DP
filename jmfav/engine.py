"""与 jmcomic 交互的核心逻辑：登录、拉收藏夹、下载并直接打成压缩包。

这里刻意不用 jmcomic 自带的 zip 插件，原因是那个插件是「先落盘图片、再压缩、
再删原图」的三步走，既慢（每张图都要落盘一次）又占空间。我们自己在回调里把
图片字节直接写进 zip，省掉中间文件。

并发策略：同一章节内的图片用线程池并行「下载 + 解密 + 编码」，但写入 zip 时按
页码顺序串行，既快又能保证压缩包内的图片顺序不乱、内存占用也受控。

实测（单本 52 页、1359×1920 的页面、8 线程）：约 5 张/秒。瓶颈在 PIL 的重编码
（约 170ms/张），不在网络（约 0.15 秒/张）。
"""

from __future__ import annotations

import os
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

from .naming import build_archive_name, sanitize_filename


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #

@dataclass
class AlbumStub:
    """收藏夹列表里的一条记录（还没拉详情）。"""
    album_id: str
    title: str


@dataclass
class FolderInfo:
    folder_id: str
    name: str
    count: int = 0


@dataclass
class SearchResult:
    """一页搜索结果。"""
    items: List[AlbumStub]
    total: int = 0
    page: int = 1
    page_count: int = 0
    single: bool = False          # 关键词命中了「车号直达」


@dataclass
class AlbumResult:
    album_id: str
    title: str
    path: str = ''
    images: int = 0
    ok: bool = False
    skipped: bool = False
    error: str = ''
    seconds: float = 0.0
    short_title: str = ''       # 实际用于命名的「作品名」


class Cancelled(Exception):
    """用户点了取消。"""


ProgressCb = Callable[[dict], None]


def _noop(_payload: dict) -> None:
    pass


# --------------------------------------------------------------------------- #
# 引擎
# --------------------------------------------------------------------------- #

class JmEngine:
    """封装登录态与客户端，供 GUI/CLI 共用。

    :param postman: 传输实现。``curl_cffi_session`` 复用连接，实测比默认的
        ``curl_cffi``（每个请求新建连接）快一倍，所以默认用它。
    :param proxy: 形如 ``http://127.0.0.1:7890`` 的代理；为空则走系统代理。
    :param image_format: 解密后重新编码的格式，``auto`` = 跟随原图。
    :param image_quality: 重编码质量（1-100），默认 90（PSNR 约 45dB，肉眼无差）。
    """

    def __init__(self, log: Callable[[str], None] = print,
                 postman: str = 'curl_cffi_session',
                 proxy: str = '',
                 image_format: str = 'auto',
                 image_quality: int = 90):
        self._log = log
        self.postman = postman or 'curl_cffi_session'
        self.proxy = (proxy or '').strip()
        self.image_format = (image_format or 'auto').lower()
        self.image_quality = int(image_quality or 90)
        self.option = None
        self.client = None
        self.username: Optional[str] = None
        self._lock = threading.RLock()

    def _client_conf(self) -> dict:
        """组装 client 配置（含传输实现与可选代理）。"""
        conf: dict = {'impl': 'api', 'postman': {'type': self.postman}}
        if self.proxy:
            conf['postman']['meta_data'] = {'proxies': self.proxy}
        return conf

    def connect_anonymous(self) -> None:
        """建一个不带登录态的客户端（部分条目无需登录即可下载）。"""
        from jmcomic import JmOption

        with self._lock:
            option = JmOption.construct({'client': self._client_conf()},
                                        cover_default=True)
            self.option = option
            self.client = option.new_jm_client(impl='api')
            self.username = None

    # ---------------- 登录 ----------------

    def login(self, username: str, password: str) -> dict:
        """账号密码登录（走移动端 API），返回包含用户名/uid 的信息。"""
        from jmcomic import JmOption
        from jmcomic.jm_client_impl import JmApiClient

        username = (username or '').strip()
        password = password or ''
        if not username or not password:
            raise ValueError('账号和密码都要填')

        with self._lock:
            self._log('正在创建客户端并登录…')
            option = JmOption.construct({
                'client': self._client_conf(),
                'download': {'threading': {'image': 1, 'photo': 1}},
            }, cover_default=True)
            # 注意：option.auth 是 AdvancedDict，它的 __getattr__ 会拦截 update
            # 这类方法名，所以只能逐键赋值，不能调 .update()。
            option.auth.username = username
            option.auth.password = password

            client = option.new_jm_client(impl='api')
            assert isinstance(client, JmApiClient)
            client.login(username, password)

            self.option = option
            self.client = client
            self.username = username

            info = {
                'username': username,
                'user_id': client._user_id,
                'cookies': dict(client['cookies'] or {}),
            }
            self._log(f'登录成功：{username}（uid={client._user_id}）')
            return info

    def login_with_cookies(self, cookies: dict, username: str = '') -> dict:
        """用已有的 cookies 恢复登录态（无需密码）。"""
        from jmcomic import JmOption

        if not cookies:
            raise ValueError('cookies 不能为空')

        with self._lock:
            option = JmOption.construct({
                'auth': {'cookies': dict(cookies), 'username': username or None},
                'client': self._client_conf(),
                'download': {'threading': {'image': 1, 'photo': 1}},
            }, cover_default=True)
            client = option.new_jm_client(impl='api')
            self.option = option
            self.client = client
            self.username = username or None
            return {'username': self.username, 'cookies': dict(cookies)}

    @property
    def logged_in(self) -> bool:
        return self.client is not None

    def _require_client(self):
        if self.client is None:
            raise RuntimeError('还没登录，请先登录')
        return self.client

    # ---------------- 收藏夹 ----------------

    def list_folders(self) -> List[FolderInfo]:
        """拉一次收藏夹首页，取文件夹列表与总数。"""
        page = self._require_client().favorite_folder(page=1)
        folders = [FolderInfo('0', '全部收藏', int(page.total))]
        seen = {'0'}
        for folder_id, name in page.iter_folder_id_name():
            folder_id = str(folder_id)
            if folder_id in seen:
                continue
            seen.add(folder_id)
            folders.append(FolderInfo(folder_id, str(name)))
        return folders

    def iter_favorite(self, folder_id: str = '0', pages: Optional[int] = None,
                      should_stop: Callable[[], bool] = lambda: False
                      ) -> Iterable[List[AlbumStub]]:
        """逐页产出收藏夹（每页 20 条）。"""
        client = self._require_client()
        folder_id = str(folder_id or '0')

        page_no = 1
        while True:
            if should_stop():
                raise Cancelled()
            page = client.favorite_folder(page=page_no, folder_id=folder_id)
            items = [AlbumStub(str(aid), str(title))
                     for aid, title in page.iter_id_title()]
            if not items:
                break
            yield items

            if page_no >= int(page.page_count):
                break
            if pages is not None and page_no >= pages:
                break
            page_no += 1

    def fetch_all_favorites(self, folder_id: str = '0',
                            limit: Optional[int] = None,
                            pages: Optional[int] = None,
                            progress: ProgressCb = _noop,
                            should_stop: Callable[[], bool] = lambda: False
                            ) -> List[AlbumStub]:
        """把收藏夹全部翻完，返回条目列表（已去重）。"""
        out: List[AlbumStub] = []
        seen = set()
        for page_items in self.iter_favorite(folder_id, pages, should_stop):
            for item in page_items:
                if item.album_id in seen:
                    continue
                seen.add(item.album_id)
                out.append(item)
                progress({'type': 'fetch', 'count': len(out), 'latest': item.title})
                if limit and len(out) >= limit:
                    return out
        return out

    # ---------------- 搜索 ----------------

    def search(self, keyword: str, page: int = 1,
               order_by: str = 'mr', time: str = 'a',
               category: str = '0', sub_category: Optional[str] = None
               ) -> 'SearchResult':
        """站内搜索。

        关键词是纯数字时会命中「车号直达」，返回单本；否则返回一页结果。
        """
        client = self._require_client()
        keyword = (keyword or '').strip()
        if not keyword:
            raise ValueError('搜索关键词不能为空')

        raw = client.search_site(keyword, page=page, order_by=order_by,
                                 time=time, category=category,
                                 sub_category=sub_category)

        items = [AlbumStub(str(aid), str(title))
                 for aid, title in raw.iter_id_title()]
        return SearchResult(
            items=items,
            total=int(raw.total or 0),
            page=page,
            page_count=int(raw.page_count or 0),
            single=getattr(raw, 'is_single_album', False),
        )

    def search_all(self, keyword: str, pages: int = 1,
                   order_by: str = 'mr', time: str = 'a',
                   category: str = '0',
                   progress: ProgressCb = _noop,
                   should_stop: Callable[[], bool] = lambda: False
                   ) -> List[AlbumStub]:
        """连续翻若干页搜索结果（默认只翻 1 页，避免一次拉太多）。"""
        out: List[AlbumStub] = []
        seen = set()
        for page_no in range(1, max(1, pages) + 1):
            if should_stop():
                raise Cancelled()
            result = self.search(keyword, page=page_no, order_by=order_by,
                                 time=time, category=category)
            for item in result.items:
                if item.album_id in seen:
                    continue
                seen.add(item.album_id)
                out.append(item)
                progress({'type': 'search', 'count': len(out),
                          'latest': item.title})
            if result.single or page_no >= max(1, result.page_count):
                break
        return out

    def resolve_album_id(self, text: str) -> str:
        """从用户输入里解析出本子 ID（支持链接、JM123456、纯数字）。"""
        from .ids import parse_album_id
        return parse_album_id(text)

    def download_albums(self,
                        albums: Sequence[AlbumStub],
                        output_dir: str,
                        max_title_chars: int = 60,
                        template: str = '{title}',
                        compress_level: int = 0,
                        image_threads: int = 8,
                        skip_existing: bool = True,
                        order_by_name: bool = False,
                        image_format: Optional[str] = None,
                        image_quality: Optional[int] = None,
                        name_mode: str = 'smart',
                        progress: ProgressCb = _noop,
                        should_stop: Callable[[], bool] = lambda: False,
                        ) -> List[AlbumResult]:
        """逐个本子下载并打包成 zip，名称取自标题（超长自动截断）。"""
        os.makedirs(output_dir, exist_ok=True)

        fmt = (image_format or self.image_format or 'auto').lower()
        quality = int(image_quality if image_quality is not None else self.image_quality)
        results: List[AlbumResult] = []
        total = len(albums)

        for index, stub in enumerate(albums, start=1):
            if should_stop():
                break

            started = time.time()
            result = AlbumResult(stub.album_id, stub.title)
            progress({
                'type': 'album_start', 'index': index, 'total': total,
                'album_id': stub.album_id, 'title': stub.title,
            })

            try:
                self._download_one(
                    stub, output_dir, max_title_chars, template, int(compress_level),
                    max(1, int(image_threads)), skip_existing, order_by_name,
                    result, progress, should_stop, fmt, quality, name_mode,
                )
            except Cancelled:
                result.error = '已取消'
                results.append(result)
                progress({'type': 'album_done', 'result': result,
                          'index': index, 'total': total})
                break
            except Exception as exc:  # 单本失败不影响后续
                result.ok = False
                result.error = friendly_error(exc)
                self._log(f'[失败] {stub.title} → {result.error}')
            finally:
                result.seconds = round(time.time() - started, 1)

            results.append(result)
            progress({'type': 'album_done', 'result': result,
                      'index': index, 'total': total})

        return results

    def _download_one(self,
                      stub: AlbumStub,
                      output_dir: str,
                      max_title_chars: int,
                      template: str,
                      compress_level: int,
                      image_threads: int,
                      skip_existing: bool,
                      order_by_name: bool,
                      result: AlbumResult,
                      progress: ProgressCb,
                      should_stop: Callable[[], bool],
                      image_format: str = 'auto',
                      image_quality: int = 90,
                      name_mode: str = 'smart',
                      ) -> None:
        client = self._require_client()

        # 1. 拉详情（拿到真实标题、作者、章节列表）
        album = client.get_album_detail(stub.album_id)
        title = album.title or stub.title
        result.title = title

        # 智能命名：从「[漢化組][作者] 作品名 (出處) [語言]」里剥出作品名
        from .title import clean_title
        short_title = clean_title(title) if name_mode != 'full' else title
        result.short_title = short_title

        archive = build_archive_name(
            title=short_title,
            max_chars=max_title_chars,
            template=template,
            album_id=album.album_id,
            author=album.author,
            date=album.update_date,
            output_dir=output_dir,
            ext='.zip',
            name_mode='smart',
            raw_title=title,
        )
        zip_path = os.path.join(output_dir, archive + '.zip')
        zip_path = _unique_path(zip_path, allow_existing=skip_existing)
        result.path = zip_path

        if short_title != title:
            self._log(f'命名：{short_title}')

        # 2. 已存在且是合法 zip 就跳过
        if skip_existing and os.path.exists(zip_path) and zipfile.is_zipfile(zip_path):
            result.ok = True
            result.skipped = True
            result.images = _count_zip_entries(zip_path)
            self._log(f'[跳过] 已存在：{os.path.basename(zip_path)}')
            return

        photos = list(album)
        if order_by_name:
            photos.sort(key=lambda p: _natural_key(str(p.name)))
        if not photos:
            raise RuntimeError('这个本子没有章节')

        progress({'type': 'album_meta', 'album_id': album.album_id,
                  'title': title, 'photos': len(photos), 'path': zip_path})

        tmp_path = zip_path + '.part'
        written = 0
        used_dirs = set()

        try:
            with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_STORED) as zf, \
                    ThreadPoolExecutor(max_workers=image_threads) as pool:
                for p_index, photo in enumerate(photos, start=1):
                    if should_stop():
                        raise Cancelled()

                    client.check_photo(photo)
                    if len(photos) > 1:
                        arc_dir = _unique_dir_name(used_dirs, sanitize_filename(
                            f'{photo.index:03d} {photo.name}'.strip()
                        ) or f'{photo.index:03d}')
                    else:
                        arc_dir = ''

                    image_list = list(photo)
                    progress({
                        'type': 'photo_start', 'album_id': album.album_id,
                        'title': title, 'photo_index': p_index,
                        'photo_total': len(photos), 'photo_name': photo.name,
                        'images': len(image_list), 'images_done': written,
                    })

                    # 分批并行拉取，按顺序写盘，兼顾速度与顺序、内存可控
                    batch = max(4, image_threads * 2)
                    for start in range(0, len(image_list), batch):
                        if should_stop():
                            raise Cancelled()
                        chunk = image_list[start:start + batch]
                        fetched = pool.map(
                            lambda img: self._fetch_image(client, img, arc_dir,
                                                          image_format, image_quality),
                            chunk,
                        )
                        for arc_name, data in fetched:
                            _zip_write(zf, arc_name, data, compress_level)
                            written += 1
                            progress({
                                'type': 'image_done', 'album_id': album.album_id,
                                'images_done': written, 'images_total': album.page_count,
                                'photo_index': p_index, 'photo_total': len(photos),
                            })

            os.replace(tmp_path, zip_path)
            result.ok = True
            result.images = written
            self._log(f'[完成] {os.path.basename(zip_path)}（{written} 张）')

        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _fetch_image(self, client, img, arc_dir: str = '',
                     image_format: str = 'auto',
                     image_quality: int = 90) -> Tuple[str, bytes]:
        """下载一张图 → 内存解密 → 编码，返回 (zip 内路径, 字节)。

        全程不落临时文件，比 jmcomic 默认的「下载到磁盘再读回来」少两次磁盘 IO。
        """
        from jmcomic import JmImageTool

        from .codec import decode_scramble, encode_image

        resp = client.get_jm_image(img.download_url)
        resp.require_success()
        raw = resp.content

        # GIF 不重新编码（会丢掉动画帧），直接原样入包
        if img.is_gif:
            return self._arc_name(arc_dir, img), raw

        num = JmImageTool.get_num_by_detail(img)

        requested = (image_format or 'auto').lower()
        target = requested
        if target == 'auto':
            origin = img.img_file_suffix.lower()
            if origin == '.png':
                target = 'png'
            elif origin in ('.webp', ''):
                target = 'webp'
            else:
                target = 'jpeg'

        # 无需解扰的图（老本子）在 auto 模式下直接存原始字节，完全不用重编码；
        # 用户显式指定了格式才按要求的格式转（不然选了 jpeg 却拿到 webp 会很困惑）
        if num == 0 and requested == 'auto':
            return self._arc_name(arc_dir, img), raw

        pic = decode_scramble(raw, num)
        data, suffix = encode_image(pic, target, quality=image_quality)
        return self._arc_name(arc_dir, img, override_name=f'{img.img_file_name}{suffix}'), data

    @staticmethod
    def _arc_name(arc_dir: str, img, override_name: str = '') -> str:
        name = override_name or f'{img.img_file_name}{img.img_file_suffix}'
        return f'{arc_dir}/{name}' if arc_dir else name

    def download_single(self, album_id: str, output_dir: str, **kwargs) -> AlbumResult:
        """下载单个本子（给「粘贴车号」用）。"""
        return self.download_albums([AlbumStub(str(album_id), str(album_id))],
                                    output_dir, **kwargs)[0]


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #

def _zip_write(zf: zipfile.ZipFile, arc_name: str, data: bytes, compress_level: int) -> None:
    """图片本身已是压缩格式，默认 STORED（最快）；用户指定级别才走 deflate。"""
    info = zipfile.ZipInfo(arc_name)
    info.external_attr = 0o600 << 16
    if compress_level and compress_level > 0:
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, data, compresslevel=min(int(compress_level), 9))
    else:
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, data)


def _unique_path(path: str, allow_existing: bool = True) -> str:
    """同名压缩包：跳过模式下直接复用；否则自动加 (2)(3)…不覆盖。"""
    if not os.path.exists(path):
        return path
    if allow_existing:
        return path

    root, ext = os.path.splitext(path)
    n = 2
    while os.path.exists(f'{root} ({n}){ext}'):
        n += 1
    return f'{root} ({n}){ext}'


def _count_zip_entries(path: str) -> int:
    try:
        with zipfile.ZipFile(path) as zf:
            return len([n for n in zf.namelist() if not n.endswith('/')])
    except Exception:
        return 0


_DIGITS_RE = re.compile(r'(\d+)')


def _natural_key(text: str):
    """自然排序：让「第2话」排在「第10话」前面。"""
    parts = _DIGITS_RE.split(text or '')
    return [int(p) if p.isdigit() else p.lower() for p in parts]


def _unique_dir_name(used: set, name: str, limit: int = 90) -> str:
    """zip 内的章节目录名去重 + 限长（同名章节在 zip 里会互相覆盖）。"""
    name = name[:limit].rstrip(' .') or '未命名'
    candidate = name
    n = 2
    while candidate.lower() in used:
        candidate = f'{name} ({n})'
        n += 1
    used.add(candidate.lower())
    return candidate


def friendly_error(exc: BaseException) -> str:
    """把底层异常翻译成人话，避免界面上弹一堆 JSON。"""
    text = str(exc) or exc.__class__.__name__
    low = text.lower()

    if '請先登入' in text or '请先登录' in text or '"code":401' in text:
        return '未登录或登录已失效，请重新登录'
    if 'timeout' in low or 'timed out' in low:
        return '连接超时，检查网络或代理设置'
    if 'proxy' in low or 'connection refused' in low or 'failed to connect' in low:
        return '连不上服务器，检查网络或代理设置'
    if 'not found' in low or '404' in low:
        return '内容不存在（可能已被删除）'
    if len(text) > 300:
        text = text[:300] + '…'
    return text
