#!/usr/bin/env python3
"""按 (member_path -> 本地文件) 替换/新增条目，其余条目字节级复制"""
import zipfile, sys, json, hashlib

src_ipa, out_ipa, manifest = sys.argv[1], sys.argv[2], sys.argv[3]
mapping = json.load(open(manifest))          # {member: localfile}
seen = set()
zin = zipfile.ZipFile(src_ipa)
with zipfile.ZipFile(out_ipa, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zout:
    for it in zin.infolist():
        data = None
        if it.filename in mapping:
            data = open(mapping[it.filename], 'rb').read()
            seen.add(it.filename)
        else:
            data = zin.read(it.filename)
        zi = zipfile.ZipInfo(it.filename, it.date_time)
        zi.compress_type = it.compress_type
        zi.external_attr = it.external_attr
        zi.internal_attr = it.internal_attr
        zi.create_system = it.create_system
        zout.writestr(zi, data)
    for member, local in mapping.items():
        if member in seen:
            continue
        data = open(local, 'rb').read()
        zi = zipfile.ZipInfo(member, (2026, 11, 2, 17, 30, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = (0o100755 << 16)
        zi.create_system = 3
        zout.writestr(zi, data)
        print("ADDED", member)
    for member in mapping:
        if member in seen:
            print("REPLACED", member)
print("out", out_ipa, hashlib.sha256(open(out_ipa, 'rb').read()).hexdigest())
