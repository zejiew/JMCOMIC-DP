"""批量下载 JM 的漫画，自动打成以作品名命名的 zip。

模块划分：

    title.py    从「[漢化組][作者] 作品名 (出處) [語言]」里提取作品名
    ids.py      车号 / 链接解析（支持 JM123456、album 链接、批量粘贴）
    naming.py   截断、Windows 非法字符处理、整条路径限长
    codec.py    图片解扰还原与重新编码（纯内存，不落临时文件）
    engine.py   登录、收藏夹、站内搜索、逐本下载并写 zip
    gui.py      图形界面（收藏夹 / 搜索 / 车号 三个标签页）
    cli.py      命令行界面
    paths.py    配置与默认目录

典型用法：

    from jmfav import JmEngine

    engine = JmEngine()
    engine.login('用户名', '密码')

    # 收藏夹
    albums = engine.fetch_all_favorites(folder_id='0')
    # 搜索
    albums = engine.search_all('秘密', pages=2)
    # 车号
    albums = [AlbumStub('123456', 'x')]

    engine.download_albums(albums, 'D:/漫画', max_title_chars=60)
"""

from .ids import looks_like_id, parse_album_id, parse_album_ids
from .naming import build_archive_name, sanitize_filename, truncate_title
from .paths import CONFIG_PATH, DEFAULT_OUTPUT, app_dir
from .title import clean_title

__version__ = '1.3.0'

__all__ = [
    'JmEngine',
    'AlbumStub',
    'AlbumResult',
    'FolderInfo',
    'SearchResult',
    'clean_title',
    'parse_album_id',
    'parse_album_ids',
    'looks_like_id',
    'build_archive_name',
    'sanitize_filename',
    'truncate_title',
    'DEFAULT_OUTPUT',
    'CONFIG_PATH',
    'app_dir',
]


def __getattr__(name):
    """延迟导入 engine，让 `import jmfav` 不必依赖 jmcomic 已安装。"""
    if name in ('JmEngine', 'AlbumStub', 'AlbumResult', 'FolderInfo',
                'SearchResult', 'Cancelled'):
        from . import engine
        return getattr(engine, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
