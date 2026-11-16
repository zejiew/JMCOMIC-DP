"""把 dist/ 打成发布用的 zip（解压即用，无需安装）。

用法：python make_release.py
产物：release/JM下载器-v1.2.0-win64.zip
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
RELEASE = os.path.join(ROOT, 'release')

VERSION = '1.3.0'
NAME = f'JM下载器-v{VERSION}-win64'


def main() -> int:
    if not os.path.isdir(DIST):
        print('还没有 dist/，先跑 python build.py', file=sys.stderr)
        return 1

    exe = os.path.join(DIST, 'JM下载器.exe')
    if not os.path.exists(exe):
        print('dist/ 里没有 JM下载器.exe', file=sys.stderr)
        return 1

    os.makedirs(RELEASE, exist_ok=True)
    zip_path = os.path.join(RELEASE, NAME + '.zip')

    # 只收发布需要的文件
    wanted = ['JM下载器.exe', 'jmfav-cli.exe', '使用说明.txt']

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for fname in wanted:
            path = os.path.join(DIST, fname)
            if not os.path.exists(path):
                continue
            zf.write(path, arcname=f'{NAME}/{fname}')
            print(f'  加入 {fname}')

    size = os.path.getsize(zip_path) / 1024 / 1024
    print(f'\n发布包：{zip_path}')
    print(f'体积  ：{size:.1f} MB')
    total_inside = sum(os.path.getsize(os.path.join(DIST, f))
                       for f in wanted if os.path.exists(os.path.join(DIST, f)))
    print(f'解压后：{total_inside / 1024 / 1024:.1f} MB')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
