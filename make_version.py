"""生成 Windows 版本信息资源（让 exe 属性里显示名字和版本）。"""

import os

VERSION = '1.3.0'
COMPANY = '个人工具'
PRODUCT = 'JM 下载器'
DESC = 'JM 漫画批量下载器'
COPYRIGHT = '仅供个人备份自己已收藏、有权访问的内容使用'


def make_version_file(path: str, internal_name: str, original: str,
                      desc: str = DESC) -> None:
    # 四段式版本号，最后一段 0
    v = VERSION.split('.')
    while len(v) < 4:
        v.append('0')
    tuple_v = tuple(int(x) for x in v[:4])
    dotted = ', '.join(str(x) for x in tuple_v)

    text = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({dotted}),
    prodvers=({dotted}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '080404b0',
        [StringStruct('CompanyName', '{COMPANY}'),
         StringStruct('FileDescription', '{desc}'),
         StringStruct('FileVersion', '{VERSION}'),
         StringStruct('InternalName', '{internal_name}'),
         StringStruct('LegalCopyright', '{COPYRIGHT}'),
         StringStruct('OriginalFilename', '{original}'),
         StringStruct('ProductName', '{PRODUCT}'),
         StringStruct('ProductVersion', '{VERSION}')])
    ]),
    VarFileInfo([VarStruct('Translation', [2052, 1200])])
  ]
)
"""
    with open(path, 'w', encoding='utf-8') as fp:
        fp.write(text)
    print('已生成', path)


if __name__ == '__main__':
    root = os.path.dirname(os.path.abspath(__file__))
    make_version_file(os.path.join(root, 'version_gui.txt'),
                      'JM下载器', 'JM下载器.exe')
    make_version_file(os.path.join(root, 'version_cli.txt'),
                      'jmfav-cli', 'jmfav-cli.exe', desc='JM 漫画下载器（命令行）')
