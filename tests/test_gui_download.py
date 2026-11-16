"""GUI 全链路测试：真实联网，走「开始下载」按钮的代码路径。

用一个小的真实本子，验证 UI 的进度回调、完成回调、文件落盘都正常。
注意：测试会临时改 config.json 的内容，结束时恢复原状。
用法：python tests/test_gui_download.py [album_id]
"""

import os
import sys
import tempfile
import threading
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jmfav.gui as gui_mod
from jmfav.engine import AlbumStub
from jmfav.paths import CONFIG_PATH

# 自动化测试里不能弹模态框，否则会一直卡住等人点
class _SilentBox:
    def __getattr__(self, _name):
        return lambda *a, **k: None

    def askyesno(self, *a, **k):
        return True


gui_mod.messagebox = _SilentBox()
from jmfav.gui import JmApp  # noqa: E402


def main():
    album_id = sys.argv[1] if len(sys.argv) > 1 else '1490921'
    out_dir = tempfile.mkdtemp(prefix='jmgui-')

    # 备份配置，测试结束还原（避免把临时目录写进用户配置）
    backup = None
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'rb') as fp:
            backup = fp.read()

    app = JmApp()
    app.var_output.set(out_dir)
    app.var_max_chars.set('40')
    app.var_threads.set('12')
    app.var_quality.set('90')

    # 用真实客户端，但跳过登录（下载接口本身不强制登录）
    from jmcomic import JmOption
    option = JmOption.construct({
        'client': {'impl': 'api', 'postman': {'type': 'curl_cffi_session'}},
    })
    app.engine.client = option.new_jm_client(impl='api')

    logs = []
    app._log = lambda text: logs.append(text)      # 避免依赖 Text 控件
    app._on_albums([AlbumStub(album_id, 'GUI 测试')])

    done = threading.Event()
    real_done = app._on_download_done

    def hook(results):
        real_done(results)
        done.set()

    app._on_download_done = hook
    app._start_download()

    deadline = time.time() + 180
    while not done.is_set() and time.time() < deadline:
        app.update()
        time.sleep(0.1)

    app.update()
    print('\n'.join(logs[-12:]))
    print('\n进度条:', app.var_progress.get(), '|', app.var_progress_text.get())

    files = [f for f in os.listdir(out_dir) if f.endswith('.zip')]
    ok = bool(files)
    if ok:
        path = os.path.join(out_dir, files[0])
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        print('文件:', files[0])
        print('条目:', len(names), '| 校验:', zipfile.ZipFile(path).testzip() is None)
        ok = len(names) > 0
    else:
        print('没有产出文件')

    app._busy = False
    app.destroy()

    # 还原配置
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
