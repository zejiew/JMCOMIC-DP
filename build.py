"""一键打包成 exe。

用法：
    python build.py             # 打包（默认单文件、无控制台）
    python build.py --onedir    # 打包成文件夹（启动更快，但文件多）
    python build.py --console   # 保留控制台窗口（排查问题时用）

产物：
    dist/JM下载器.exe        GUI
    dist/jmfav-cli.exe       命令行版
    dist/使用说明.txt
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, 'dist')
BUILD = os.path.join(ROOT, 'build')

APP_NAME = 'JM下载器'
VERSION = '1.3.0'

# 必须显式声明的模块（都是函数内延迟 import，PyInstaller 静态分析看不到）
HIDDEN = [
    'jmcomic',
    'jmcomic.api',
    'jmcomic.jm_client_impl',
    'jmcomic.jm_client_interface',
    'jmcomic.jm_downloader',
    'jmcomic.jm_entity',
    'jmcomic.jm_exception',
    'jmcomic.jm_option',
    'jmcomic.jm_plugin',
    'jmcomic.jm_toolkit',
    'jmcomic.jm_config',
    'jmcomic.jm_feature',
    'jmcomic.jm_runtime',
    'jmcomic.jm_task_context',
    'Crypto',
    'Crypto.Cipher',
    'Crypto.Cipher.AES',
    'curl_cffi',
    'curl_cffi.requests',
    'curl_cffi.requests.session',
    'PIL',
    'PIL.Image',
    'PIL.ImageFile',
    'PIL.ImageDraw',
    'PIL.ImageChops',
    'PIL.ImageTk',
    'PIL.ImageFont',
    'yaml',
    'requests',
    'charset_normalizer',
    'certifi',
    'jmfav',
    'jmfav.codec',
    'jmfav.engine',
    'jmfav.naming',
    'jmfav.title',
    'jmfav.ids',
    'jmfav.gui',
    'jmfav.cli',
    'jmfav.paths',
    'jmfav.theme',
]

# 明确不打的（体积大且用不到）
EXCLUDE = [
    'matplotlib', 'scipy', 'pandas', 'notebook', 'IPython', 'jupyter',
    'pytest', 'sphinx', 'numpy', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
    'test', 'unittest', 'pydoc', 'doctest',
]


def _run(cmd: list) -> int:
    print('$', ' '.join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


def build_one(script: str, name: str, console: bool, onedir: bool,
              icon: str = '', splash: str = '', version_file: str = '') -> bool:
    args = [
        sys.executable, '-m', 'PyInstaller',
        '--noconfirm',
        '--clean',
        '--name', name,
        '--distpath', DIST,
        '--workpath', os.path.join(BUILD, name),
        '--specpath', BUILD,
        '--onedir' if onedir else '--onefile',
        '--console' if console else '--windowed',
    ]
    for mod in HIDDEN:
        args += ['--hidden-import', mod]
    for mod in EXCLUDE:
        args += ['--exclude-module', mod]
    if icon and os.path.exists(icon):
        args += ['--icon', icon]
        args += ['--add-data', f'{icon}{os.pathsep}.']
    # 界面上要用的素材（头像 / logo）一起打进去，运行时从 _MEIPASS/assets 读
    assets = os.path.join(ROOT, 'assets')
    if os.path.isdir(assets):
        args += ['--add-data', f'{assets}{os.pathsep}assets']
    if version_file and os.path.exists(version_file):
        args += ['--version-file', version_file]
    if splash and os.path.exists(splash) and not console and not onedir:
        # bootloader 级启动画面：在 Python 解释器起来之前就显示，
        # 正好盖住单文件 exe 解压自身的那两三秒
        args += ['--splash', splash]
    args.append(script)

    code = _run(args)
    if code != 0:
        print(f'\n[失败] {name} 打包返回码 {code}')
        return False
    return True


def write_readme() -> None:
    text = f"""JM 下载器 v{VERSION} —— 使用说明
=====================================

双击「{APP_NAME}.exe」即可运行，不需要安装 Python。

第一次打开时请：
  1. 填用户名和密码，点「登录」
  2. 在「收藏夹 / 搜索 / 车号」任选一页，勾选要下的条目
  3. 点右侧「开始下载勾选项」

三个标签页
----------
  收藏夹   选收藏夹 →「载入收藏」→ 勾选 → 下载
  搜索     输入关键词 →「搜索」→ 边看边勾（可翻页，翻页是追加）
           排序可选 最新/最热/最多图/最多喜欢，分类可限定
  车号     粘贴 ID 或链接 →「添加」→ 下载
           支持 123456 / JM123456 / 网址；多个用逗号或空格隔开
           也可以填一个后点「直接下载这个 ID」立刻下

命名
----
程序会自动从长标题里提取「作品名」，去掉汉化组、作者、语言标注：

  [無邪氣漢化組] (C99) [紺色果實] サレンの樂しい夢 (プリコネ) [中國翻譯] [無修正]
    → サレンの樂しい夢 (プリコネ)

列表第二列「命名预览」就是最终文件名，右键可复制。
想用完整原标题：右栏「命名方式」改成「完整原标题」。
标题超过「标题最多字数」（默认 60）会自动截断。

文件位置
--------
  下载的 zip：程序旁边会建一个 downloads 文件夹
              （若程序放在无写入权限的目录，则存到系统「下载」文件夹）
  配置文件：  程序旁边的 config.json
              里面有你填的用户名和登录 cookies，别随便发给别人
  未完成的包：xxx.zip.part，下次重跑会自动跳过已完成的

命令行版
--------
  同目录的 jmfav-cli.exe 是命令行版本：

  jmfav-cli.exe -u 用户名 -p 密码
  jmfav-cli.exe -u 用户名 -p 密码 --search 秘密 --search-pages 2
  jmfav-cli.exe -u 用户名 -p 密码 --ids 123456 789012
  jmfav-cli.exe -h                         查看全部参数

常见问题
--------
  登录失败        先在浏览器确认账号能登。登录成功后 cookies 会保存，
                  下次自动复用。
  下载很慢        瓶颈在图片解码后的重编码。把「图片格式」改成 jpeg
                  （快约 10 倍，体积大些），或把「图片线程」调到 12-16。
  提示登录失效    点一次「登录」刷新 cookies。
  车号页名字是
  JM123456        后台正在补全标题，稍等就变成真名。

仅供个人备份自己已收藏、有权访问的内容使用。
请遵守当地法律与站点条款。

-------------------------------------
构建 BY 星汐（zejiew）
-------------------------------------
"""
    path = os.path.join(DIST, '使用说明.txt')
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(text)
    print('已写入', path)


def main() -> int:
    onedir = '--onedir' in sys.argv
    console = '--console' in sys.argv

    # 图标与启动图没有就先生成
    icon = os.path.join(ROOT, 'icon.ico')
    if not os.path.exists(icon):
        print('生成图标…')
        subprocess.call([sys.executable, os.path.join(ROOT, 'make_icon.py')], cwd=ROOT)

    splash = os.path.join(ROOT, 'splash.png')
    if not os.path.exists(splash):
        print('生成启动图…')
        subprocess.call([sys.executable, os.path.join(ROOT, 'make_splash.py')], cwd=ROOT)

    # 版本信息资源（exe 属性里能看到名字与版本）
    ver_gui = os.path.join(ROOT, 'version_gui.txt')
    ver_cli = os.path.join(ROOT, 'version_cli.txt')
    if not (os.path.exists(ver_gui) and os.path.exists(ver_cli)):
        print('生成版本信息…')
        subprocess.call([sys.executable, os.path.join(ROOT, 'make_version.py')], cwd=ROOT)

    if os.path.isdir(DIST):
        shutil.rmtree(DIST, ignore_errors=True)

    print('=' * 60)
    print(f'打包 JM 下载器 v{VERSION}')
    print(f'模式：{"文件夹" if onedir else "单文件"} / '
          f'{"控制台" if console else "无控制台"}')
    print('=' * 60)

    ok_gui = build_one('pack_entry.py', APP_NAME, console, onedir,
                       icon=icon, splash=splash, version_file=ver_gui)
    ok_cli = build_one('pack_cli.py', 'jmfav-cli', True, onedir,
                       icon=icon, version_file=ver_cli)

    if os.path.isdir(DIST):
        write_readme()

    print('\n' + '=' * 60)
    if ok_gui:
        print(f'GUI   : {os.path.join(DIST, APP_NAME + (".exe" if sys.platform == "win32" else ""))}')
    else:
        print('GUI   : 打包失败')
    if ok_cli:
        print(f'CLI   : {os.path.join(DIST, "jmfav-cli.exe")}')
    else:
        print('CLI   : 打包失败')
    total = 0
    for root, _dirs, files in os.walk(DIST):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    print(f'总体积: {total / 1024 / 1024:.1f} MB')
    print('=' * 60)
    return 0 if (ok_gui and ok_cli) else 1


if __name__ == '__main__':
    raise SystemExit(main())
