#!/usr/bin/env python3
"""Repack extracted Payload tree into an unsigned IPA, preserving exec bits."""
import os, sys, zipfile

SRC = sys.argv[1]           # dir containing Payload/
OUT = sys.argv[2]
EXEC_SUFFIX = ('', '.dylib')  # Mach-O w/o extension + dylibs

def is_exec(rel):
    if 'Frameworks' in rel and rel.endswith('.dylib'):
        return True
    if rel.count('/') == 2 and rel.startswith('Payload/'):  # main binary
        return True
    if '.appex/' in rel or rel.endswith('.app/') :
        return False
    base = os.path.basename(rel)
    if rel.count('/') >= 2 and '.' not in base and '/Payload/' in rel:
        # main executables inside .appex
        parent = os.path.dirname(rel)
        if parent.endswith('.appex') or parent.endswith('.app'):
            return True
    return False

n = 0
with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
    for root, dirs, files in os.walk(SRC):
        dirs.sort(); files.sort()
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, SRC)
            if not rel.startswith('Payload/'):
                continue
            zi = zipfile.ZipInfo(rel, date_time=(2026, 11, 13, 3, 0, 0))
            mode = 0o755 if is_exec(rel) else 0o644
            zi.external_attr = (0o100000 | mode) << 16
            zi.compress_type = zipfile.ZIP_DEFLATED
            with open(full, 'rb') as fh:
                z.writestr(zi, fh.read())
            n += 1
print('files', n, 'out', OUT, os.path.getsize(OUT) // 1048576, 'MB')
