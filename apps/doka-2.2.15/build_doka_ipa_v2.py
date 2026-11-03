#!/usr/bin/env python3
"""build_doka_ipa.py v2 — 保留原包逐条目压缩方式，只替换主二进制/Info.plist 并新增 dylib

用法: python3 build_doka_ipa.py <base.ipa> <dylib> <out.ipa> [main_bin_name]
相比 v1（全量重新压缩）体积更接近原包，且不动资源条目的字节。
"""
import os, sys, shutil, zipfile, subprocess, plistlib, tempfile

base, dylib, out = sys.argv[1], sys.argv[2], sys.argv[3]
DYNAME = 'DokaCore.dylib'

src = zipfile.ZipFile(base)
apps = [n for n in src.namelist() if n.startswith('Payload/') and n.endswith('.app/')]
assert len(apps) == 1, apps
appdir = apps[0]
pl_path = appdir + 'Info.plist'
pl = plistlib.loads(src.read(pl_path))
binname = pl['CFBundleExecutable']
main_rel = appdir + binname
dylib_rel = appdir + 'Frameworks/' + DYNAME

# 1) 解出主二进制与 Info.plist 到临时目录做修改
tmp = tempfile.mkdtemp()
main_path = os.path.join(tmp, binname)
open(main_path, 'wb').write(src.read(main_rel))
subprocess.check_call(['python3', '/opt/data/skills/ipa-unlocker/scripts/inject_weak.py',
                       main_path, '@executable_path/Frameworks/' + DYNAME])
pl['UIFileSharingEnabled'] = True
pl['LSSupportsOpeningDocumentsInPlace'] = True
pl_bytes = plistlib.dumps(pl)
main_bytes = open(main_path, 'rb').read()
dy_bytes = open(dylib, 'rb').read()

# 2) 按原条目顺序重打包：未改动条目沿用原压缩方式与字节
if os.path.exists(out):
    os.remove(out)
written = set()
with zipfile.ZipFile(out, 'w') as z:
    for info in src.infolist():
        name = info.filename
        if name in (main_rel, dylib_rel):
            continue
        data = src.read(name)
        if name == pl_path:
            data = pl_bytes
        zi = zipfile.ZipInfo(name, date_time=info.date_time)
        zi.external_attr = info.external_attr
        zi.compress_type = info.compress_type
        z.writestr(zi, data, compress_type=info.compress_type)
        written.add(name)
    # 主二进制：必须 ZIP_STORED + 0755
    zi = zipfile.ZipInfo(main_rel, date_time=(2026, 10, 27, 9, 0, 0))
    zi.external_attr = 0o100755 << 16
    zi.compress_type = zipfile.ZIP_STORED
    z.writestr(zi, main_bytes)
    # dylib：同样 STORED + 0755
    zi = zipfile.ZipInfo(dylib_rel, date_time=(2026, 10, 27, 9, 0, 0))
    zi.external_attr = 0o100755 << 16
    zi.compress_type = zipfile.ZIP_STORED
    z.writestr(zi, dy_bytes)
src.close()
shutil.rmtree(tmp, ignore_errors=True)
print('OK', out, os.path.getsize(out))
