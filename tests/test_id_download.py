"""联网测试：车号下载（真实下一个小本子），并校验命名。"""

import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jmfav.gui as gui_mod
from jmfav.engine import AlbumStub
from jmfav.paths import CONFIG_PATH


class _SilentBox:
    def __getattr__(self, _name):
        return lambda *a, **k: None

    def askyesno(self, *a, **k):
        return True


gui_mod.messagebox = _SilentBox()
from jmfav.gui import JmApp  # noqa: E402


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    out_dir = tempfile.mkdtemp(prefix='jmid-')

    backup = None
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'rb') as fp:
            backup = fp.read()

    app = JmApp()
    app.var_output.set(out_dir)
    app.var_threads.set('12')

    from jmcomic import JmOption
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    app.engine.client = option.new_jm_client(impl='api')

    # 走「车号页」这条路径
    app.var_id_input.set(f'JM{album_id}')
    app._add_ids()
    app.update()

    print('车号页条目:', [(a.album_id, a.title[:40]) for a in app.tab_id.albums])
    app.notebook.select(2)
    app.update()

    # 等标题补全（后台线程）
    import time
    deadline = time.time() + 30
    while time.time() < deadline and app.tab_id.albums[0].title.startswith('JM'):
        app.update()
        time.sleep(0.1)
    print('补全后标题:', app.tab_id.albums[0].title[:60])

    app.refresh_list()
    app.update()
    rows = app.tab_id.tree.get_children()
    vals = app.tab_id.tree.item(rows[0])['values'] if rows else ()
    print('行内容:', vals)
    preview = vals[1] if vals else ''
    print('命名预览:', preview)

    ok = True
    if not preview or preview.startswith('JM'):
        print('FAIL 命名预览没有提取出作品名')
        ok = False

    # 真下载
    app._launch_download([AlbumStub(album_id, app.tab_id.albums[0].title)], out_dir)
    done = False
    import threading
    ev = threading.Event()
    real = app._on_download_done

    def hook(results):
        real(results)
        ev.set()

    app._on_download_done = hook
    deadline = time.time() + 180
    while not ev.is_set() and time.time() < deadline:
        app.update()
        time.sleep(0.1)

    files = [f for f in os.listdir(out_dir) if f.endswith('.zip')]
    if not files:
        print('FAIL 没有产出文件')
        ok = False
    else:
        path = os.path.join(out_dir, files[0])
        with zipfile.ZipFile(path) as zf:
            n = len(zf.namelist())
        print('文件:', files[0])
        print('条目:', n)
        if files[0].startswith('JM') and files[0][2:9].isdigit():
            print('FAIL 文件名还是车号，没提取到作品名')
            ok = False

    app._busy = False
    app.destroy()
    try:
        if backup is None:
            if os.path.exists(CONFIG_PATH):
                os.remove(CONFIG_PATH)
        else:
            with open(CONFIG_PATH, 'wb') as fp:
                fp.write(backup)
    except OSError:
        pass

    print('RESULT:', 'OK' if ok else 'FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
