"""命令行入口（无界面也能批量下载）。

三种取数来源，随便用哪个：
    （默认）收藏夹      --folder / --pages / --limit
    搜索                --search 关键词 [--search-pages N] [--sort] [--category]
    车号                --ids 123456 789012  或  --id 123456

例：
    python run.py --cli -u 用户 -p 密码 --search 秘密 --search-pages 2
    python run.py --cli -u 用户 -p 密码 --ids 123456 https://18comic.vip/album/789012/
    python run.py --cli -u 用户 -p 密码 --id 123456 --name-mode full
"""

from __future__ import annotations

import argparse
import os
import sys

from .engine import AlbumStub, JmEngine
from .ids import parse_album_ids, try_parse_album_id
from .paths import DEFAULT_OUTPUT

SORT_CHOICES = {'latest': 'mr', 'hot': 'mv', 'pictures': 'mp', 'likes': 'tf'}
CATEGORY_CHOICES = {'all': '0', 'doujin': 'doujin', 'single': 'single',
                    'short': 'short', 'hanman': 'hanman', 'meiman': 'meiman',
                    'another': 'another'}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='jmfav',
        description='把 JM 的漫画批量下载成 zip，文件名用作品名（超长自动截断）。',
    )
    p.add_argument('-u', '--username', help='JM 用户名')
    p.add_argument('-p', '--password', help='JM 密码')
    p.add_argument('--no-login', action='store_true',
                   help='不登录直接下载（收藏夹和搜索需要登录，车号通常不用）')
    p.add_argument('-o', '--output', default=DEFAULT_OUTPUT, help='输出目录')

    # ---- 来源：收藏夹 ----
    p.add_argument('-f', '--folder', default='0', help='收藏夹 ID（默认 0 = 全部）')
    p.add_argument('-l', '--limit', type=int, default=0, help='最多下载多少个（0 = 不限）')
    p.add_argument('--pages', type=int, default=0, help='最多读取多少页收藏（0 = 全部）')
    p.add_argument('--list-folders', action='store_true', help='只列出收藏夹后退出')

    # ---- 来源：搜索 ----
    p.add_argument('-s', '--search', metavar='关键词',
                   help='站内搜索这个关键词（填车号也能直达）')
    p.add_argument('--search-pages', type=int, default=1,
                   help='搜索翻多少页，默认 1')
    p.add_argument('--sort', default='latest', choices=list(SORT_CHOICES),
                   help='搜索排序：latest/hot/pictures/likes，默认 latest')
    p.add_argument('--category', default='all', choices=list(CATEGORY_CHOICES),
                   help='搜索分类，默认 all')

    # ---- 来源：车号 ----
    p.add_argument('--ids', nargs='+', metavar='ID', help='直接下载这些车号/链接')
    p.add_argument('--id', metavar='ID', help='只下载这一个车号')

    # ---- 命名 ----
    p.add_argument('--name-mode', default='smart', choices=['smart', 'full'],
                   help='smart = 自动提取作品名（默认）；full = 用完整原标题')
    p.add_argument('--max-chars', type=int, default=60,
                   help='标题最多保留多少字，超出截断（0 = 不限制）')
    p.add_argument('--template', default='{title}',
                   help='命名模板，可用 {title} {id} {author} {date}；'
                        '默认 {title} 已自动带作者前缀 [作者] 作品名')

    # ---- 下载 ----
    p.add_argument('-t', '--threads', type=int, default=8, help='每章并行下载图片数')
    p.add_argument('--compress', type=int, default=0, help='zip 压缩级别 0-9（0 = 不压缩）')
    p.add_argument('--no-skip', action='store_true', help='不跳过已存在的压缩包')
    p.add_argument('--no-split', action='store_true',
                   help='整本合成一个压缩包（默认按章节拆成小包）')
    p.add_argument('--format', default='auto',
                   choices=['auto', 'webp', 'jpeg', 'png'],
                   help='解密后重新编码的图片格式，auto = 跟随原图')
    p.add_argument('-q', '--quality', type=int, default=90,
                   help='重编码质量 50-100，默认 90（webp 下约 45dB PSNR）')
    p.add_argument('--proxy', default='', help='如 http://127.0.0.1:7890（默认走系统代理）')
    p.add_argument('--dry-run', action='store_true',
                   help='只打印将要下载什么、会用什么文件名，不真下')
    return p


def _collect(engine: JmEngine, args) -> list:
    """按参数决定从哪取条目。"""
    # 1) 车号优先
    raw_ids = []
    if args.id:
        raw_ids.append(args.id)
    if args.ids:
        raw_ids.extend(args.ids)
    if raw_ids:
        ids = parse_album_ids(' '.join(raw_ids))
        if not ids:
            print('没识别出任何车号', file=sys.stderr)
            return []
        return [AlbumStub(aid, f'JM{aid}') for aid in ids]

    # 2) 搜索
    if args.search:
        keyword = args.search
        order = SORT_CHOICES[args.sort]
        category = CATEGORY_CHOICES[args.category]
        print(f'搜索「{keyword}」（{args.sort} / {args.category}）…')
        albums = engine.search_all(keyword, pages=args.search_pages,
                                  order_by=order, category=category,
                                  progress=lambda p: print(
                                      f'  已收集 {p["count"]} 个', end='\r', flush=True))
        print()
        if args.limit:
            albums = albums[:args.limit]
        return albums

    # 3) 收藏夹
    albums = engine.fetch_all_favorites(
        folder_id=args.folder,
        limit=args.limit or None,
        pages=args.pages or None,
        progress=lambda p: print(f'已读取 {p["count"]} 个本子', end='\r', flush=True),
    )
    print()
    return albums


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    has_id = bool(args.ids or args.id)
    need_login = not args.no_login

    if need_login:
        if not args.username or not args.password:
            print('需要 -u 用户名 -p 密码（或用 --no-login 只下车号）',
                  file=sys.stderr)
            return 2
    else:
        # 收藏夹和搜索都要登录，只有纯车号下载能免登录
        if args.search:
            print('搜索需要登录，请提供 -u/-p', file=sys.stderr)
            return 2
        if not has_id:
            print('免登录模式只能用 --ids / --id 指定车号', file=sys.stderr)
            return 2

    quality = max(50, min(100, args.quality))
    engine = JmEngine(log=lambda s: print(s, flush=True),
                      proxy=args.proxy, image_format=args.format,
                      image_quality=quality)

    if need_login:
        try:
            engine.login(args.username, args.password)
        except Exception as exc:
            print(f'登录失败：{exc}', file=sys.stderr)
            return 1
    else:
        # 免登录：建一个不带登录态的客户端
        engine.connect_anonymous()
        print('免登录模式（只能下载无需登录的条目）')

    if args.list_folders:
        for f in engine.list_folders():
            print(f'{f.folder_id}\t{f.name}\t{f.count}')
        return 0

    albums = _collect(engine, args)
    if not albums:
        print('没有需要下载的本子')
        return 0

    if args.dry_run:
        from .title import clean_title
        from .naming import build_archive_name
        from .engine import chapter_archive_base

        split = not args.no_split
        print(f'\n将要下载 {len(albums)} 个：')
        for stub in albums:
            episodes = []
            try:
                album = engine.client.get_album_detail(stub.album_id)
                raw = album.title
                author = album.author
                episodes = list(album.episode_list or [])
            except Exception:
                raw = stub.title
                author = getattr(stub, 'author', '')
            name = raw if args.name_mode == 'full' else clean_title(raw)
            final = build_archive_name(name, max_chars=args.max_chars,
                                       template=args.template,
                                       album_id=stub.album_id,
                                       author=author,
                                       output_dir=args.output,
                                       name_mode=args.name_mode,
                                       raw_title=raw)
            print(f'  {stub.album_id}  →  {final}.zip')
            if name != raw:
                print(f'        原标题：{raw}')

            # 分章模式下把每章的包名列出来，最多 3 条，其余折成一行统计
            if not split:
                continue
            if len(episodes) <= 1:
                print('        单章本子，仍是整本一个包')
                continue

            heads = []
            for order, (pid, pindex, pname) in enumerate(episodes, start=1):
                try:
                    no = int(pindex)
                except (TypeError, ValueError):
                    no = order
                heads.append(chapter_archive_base(no, str(pname or ''),
                                                  args.output, final))
            for head in heads[:3]:
                print(f'        {head}.zip')
            if len(heads) > 3:
                print(f'        …… 共 {len(heads)} 个章节包')
        return 0

    print(f'\n开始下载 {len(albums)} 个本子 → {args.output}')
    os.makedirs(args.output, exist_ok=True)
    results = engine.download_albums(
        albums,
        args.output,
        max_title_chars=args.max_chars,
        template=args.template,
        compress_level=args.compress,
        image_threads=args.threads,
        skip_existing=not args.no_skip,
        image_format=args.format,
        image_quality=quality,
        name_mode=args.name_mode,
        split_chapters=not args.no_split,
    )

    ok = sum(1 for r in results if r.ok and not r.skipped)
    skipped = sum(1 for r in results if r.skipped)
    failed = [r for r in results if not r.ok]
    print(f'\n完成 {ok}，跳过 {skipped}，失败 {len(failed)}')
    for r in failed:
        print(f'  失败 {r.title}: {r.error}')
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
