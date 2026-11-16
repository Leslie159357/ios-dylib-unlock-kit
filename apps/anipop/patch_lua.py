#!/usr/bin/env python3
"""
开心消消乐 Lua 补丁打包器（Cocos2d-x + HelloLua 通用骨架）

用法:
    python3 patch_lua.py <解密后的.ipa> <输出_unsigned.ipa> [--key <32hex>]

做什么:
    1. 从 Assets/static_config.<hex>.xml 读权威清单；
    2. 未给 --key 时，从 HelloLua 的 __TEXT,__const 暴力扫 AES-128 key
       （判据：用文件前 16B 当 IV，解出首块是 zlib 头 0x78 0x01/5e/9c/da）；
    3. 对 PATCHES 里每个 (value, anchor, new) 做解密 → 字节级替换；
    4. 重新加密（zlib 9 + PKCS#7 + 随机 IV）、按新密文 md5 重命名；
    5. 同步 static_config 的 md5/size（文件名不动）；
    6. 重打包，剥离 _CodeSignature / SC_Info。

依赖: pycryptodome
"""
import zipfile, zlib, re, os, sys, hashlib, struct
from Crypto.Cipher import AES

# ---------------------------------------------------------------- 补丁定义
# 每条: (清单里的 value, 原文 anchor(bytes), 替换后的 bytes)
# anchor 必须唯一命中 1 次，否则脚本报错退出，不会静默改错。
MOD = b'-- [MOD]'

PATCHES = [
    # 1) 进关走无限精力分支
    (
        'ubf/UBFGamePlayScene/logics/processFlow/module/UBFProcessEnergyManager.lua',
        b'function UBFProcessEnergyManager:getEnergyState()\n'
        b'\tif self.runtime:isEditorMode() then return 0 end\n'
        b'\tlocal userEnergyManager = _G.amfBean("UserEnergyManager")\n'
        b'\treturn userEnergyManager:getEnergyState()\n'
        b'end',
        b'function UBFProcessEnergyManager:getEnergyState()\n'
        b'\tif self.runtime:isEditorMode() then return 0 end\n'
        + MOD + b' \xe5\xbc\xba\xe5\x88\xb6\xe6\x97\xa0\xe9\x99\x90\xe7\xb2\xbe\xe5\x8a\x9b\n'
        b'\treturn UserEnergyState.INFINITE\n'
        b'end',
    ),
    # 2) UI 体力恒为无限（结束时间顶到 2100 年）
    (
        'amf/feature/mainscene/module/assetsbar/energy/AMFUserEnergyManager.lua',
        b'function AMFUserEnergyManager:getInfiniteEnergyEndTime()\n'
        b'    if PlatformConfig:isPlayDemo() or _G.isADPackage then\n'
        b'        local oneMoreDay = math.floor(TimeKit:time()) + 5 * 60 * 1000\n'
        b'        return oneMoreDay\n'
        b'    end\n'
        b'    return self:getEnergyValue("infiniteEnergyEndTime")\n'
        b'end',
        b'function AMFUserEnergyManager:getInfiniteEnergyEndTime()\n'
        + MOD + b' \xe6\x97\xa0\xe9\x99\x90\xe7\xb2\xbe\xe5\x8a\x9b\xe5\x88\xb0 2100 \xe5\xb9\xb4\n'
        b'    return 4102416000000\n'
        b'end',
    ),
    # 3) 道具数量显示 999
    (
        'amf/middleware/prop/userprop/AMFUserPropsManager.lua',
        b'function AMFUserPropsManager:getUserPropNumber(itemId)\n'
        b'    if self:getPropManager():isTimeLimitProp(itemId) then\n'
        b'        return self:getUserTimePropNumber(itemId)\n'
        b'    end\n'
        b'\n'
        b'    return self:_getUserPropNum(itemId)\n'
        b'end',
        b'function AMFUserPropsManager:getUserPropNumber(itemId)\n'
        + MOD + b' \xe6\x89\x80\xe6\x9c\x89\xe9\x81\x93\xe5\x85\xb7\xe6\x98\xbe\xe7\xa4\xba 999\n'
        b'    return 999\n'
        b'end',
    ),
    (
        'amf/middleware/prop/userprop/AMFUserPropsManager.lua',
        b'function AMFUserPropsManager:getUserTimePropNumber(itemId)\n'
        b'    if not privateNS.propsModel then return 0 end\n'
        b'    return privateNS.propsModel:getUserTimePropNumber(itemId)\n'
        b'end',
        b'function AMFUserPropsManager:getUserTimePropNumber(itemId)\n'
        + MOD + b'\n'
        b'    return 999\n'
        b'end',
    ),
    # 4) 点击道具时兜底（构建阶段不动，避免占位栈进列表导致闪退）
    (
        'ubf/UBFGamePlayScene/logics/sceneModules/prop/UBFPropBarModule.lua',
        b'\tlocal useStack = unit:getFirstUseStack()\n\n'
        b'\tif not useStack or useStack:getCount() == 0 then return nil ,  tostring(propUnitType) .. "\xe9\x81\x93\xe5\x85\xb7\xe6\x95\xb0\xe9\x87\x8f\xe4\xb8\x8d\xe8\xb6\xb3" end',
        b'\tlocal useStack = unit:getFirstUseStack()\n\n'
        + MOD + b' \xe6\x95\xb0\xe9\x87\x8f 0 \xe6\x97\xb6\xe5\xb0\xb1\xe5\x9c\xb0\xe8\xa1\xa5\xe6\x88\x90 999\n'
        b'\tif useStack and useStack:getCount() == 0 then useStack:setCount(999) end\n'
        b'\tif not useStack then return nil ,  tostring(propUnitType) .. "\xe9\x81\x93\xe5\x85\xb7\xe6\x95\xb0\xe9\x87\x8f\xe4\xb8\x8d\xe8\xb6\xb3" end',
    ),
    # 5) 跳过动态资源更新（否则服务端 Lua 覆盖包内补丁）
    (
        'amf/feature/login/stage/hotfix/HotfixProcessor.lua',
        b'function HotfixProcessor:isHotFixEnabled()\n'
        b'    if EnvUtil:isWindows() then return self:isWindowsHotfix() end\n'
        b'    if self:shouldSkipHotFix() then return false end\n'
        b'    \n'
        b'    return true\n'
        b'end',
        b'function HotfixProcessor:isHotFixEnabled()\n'
        + MOD + b' \xe8\xb7\xb3\xe8\xbf\x87\xe5\x8a\xa8\xe6\x80\x81\xe8\xb5\x84\xe6\xba\x90\xe6\x9b\xb4\xe6\x96\xb0\n'
        b'    return false\n'
        b'end',
    ),
    # 6) 强制用包内 static_config，忽略缓存清单
    (
        'zoo/wc/static_config_utils.lua',
        b'function static_config_utils:current_md5(...)\n'
        b'    local md5\n'
        b'    pcall(function(...)\n'
        b"        local path_utils = require 'zoo.wc.filesystem.path_utils'\n"
        b'        local static_link_file = path_utils:join(\n'
        b'                                     HeResPathUtils:getResCachePath(),\n'
        b"                                     'static_config.md5')\n"
        b'        md5 = read_file(static_link_file)\n'
        b'    end)\n'
        b'    if not md5 then md5 = ResourceLoader.getCurVersion() end\n'
        b'    return md5\n'
        b'end',
        b'function static_config_utils:current_md5(...)\n'
        + MOD + b' \xe5\xbf\xbd\xe7\x95\xa5\xe7\xbc\x93\xe5\xad\x98\xe6\xb8\x85\xe5\x8d\x95\n'
        b'    return ResourceLoader.getCurVersion()\n'
        b'end',
    ),
]

# ---------------------------------------------------------------- 加解密

def dec(blob, key):
    pt = AES.new(key, AES.MODE_CBC, blob[:16]).decrypt(blob[16:])
    pad = pt[-1]
    if 1 <= pad <= 16:
        pt = pt[:-pad]
    elif pt[-1] == 0:
        pt = pt.rstrip(b'\x00')
    return zlib.decompress(pt)


def enc(raw, key):
    c = zlib.compress(raw, 9)
    pad = (-len(c)) % 16
    if pad:
        c += bytes([pad]) * pad
    iv = os.urandom(16)
    return iv + AES.new(key, AES.MODE_CBC, iv).encrypt(c)


# ---------------------------------------------------------------- key 搜索

def find_key(bin_, sample, old_key=None):
    """在 __TEXT,__const / __DATA_CONST,__const 里 16 字节对齐扫 key。"""
    iv, ct = sample[:16], sample[16:64]
    ncmds = struct.unpack('<I', bin_[16:20])[0]
    off, regions = 32, []
    for _ in range(ncmds):
        cmd, cs = struct.unpack('<II', bin_[off:off + 8])
        if cmd == 0x19:  # LC_SEGMENT_64
            nsects = struct.unpack('<I', bin_[off + 64:off + 68])[0]
            so = off + 72
            for _ in range(nsects):
                sname = bin_[so:so + 16].rstrip(b'\x00').decode()
                ssize, soff = struct.unpack('<QI', bin_[so + 40:so + 52])
                if sname == '__const':
                    regions.append((soff, ssize))
                so += 80
        off += cs

    hits = []
    for start, size in regions:
        buf = bin_[start:start + size]
        for i in range(0, len(buf) - 16, 16):
            k = buf[i:i + 16]
            if old_key and k != old_key:
                continue
            pt = AES.new(k, AES.MODE_CBC, iv).decrypt(ct[:32])
            if pt[0] == 0x78 and pt[1] in (0x01, 0x5e, 0x9c, 0xda):
                hits.append(k)
    for k in hits:
        try:
            dec(sample, k)
            return k
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- 主流程

def disk_path(value, md5):
    d, _, b = value.rpartition('/')
    pre = f'Payload/HelloLua.app/Assets/src/{d}/' if d else 'Payload/HelloLua.app/Assets/src/'
    return pre + f'{b[:-4]}.{md5}.lua'


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    src, out = sys.argv[1], sys.argv[2]
    key = bytes.fromhex(sys.argv[sys.argv.index('--key') + 1]) if '--key' in sys.argv else None

    z = zipfile.ZipFile(src)
    sc_name = [n for n in z.namelist() if re.search(r'Assets/static_config\.[0-9a-f]{32}\.xml', n)][0]
    manifest = z.read(sc_name).decode('utf-8', 'replace')
    ents = re.findall(r'<file md5="([0-9a-f]{32})" size="(\d+)" value="([^"]+)"', manifest)
    by_value = {v: (m, int(s)) for m, s, v in ents}

    if key is None:
        sample_value = next(v for v in by_value if v.endswith('ClassBridge.lua'))
        m, _ = by_value[sample_value]
        sample = z.read(disk_path(sample_value, m))
        print('[*] 未指定 key，开始暴力扫 __const ...')
        key = find_key(z.read('Payload/HelloLua.app/HelloLua'), sample)
        if not key:
            sys.exit('[-] 没扫到 AES key，请用 --key 手工指定')
        print(f'[+] key = {key.hex()}')

    grouped = {}
    for value, anchor, new in PATCHES:
        grouped.setdefault(value, []).append((anchor, new))

    replaced, new_entries, meta = {}, {}, {}
    for value, subs in grouped.items():
        if value not in by_value:
            print(f'[skip] {value} 不在本版本清单里')
            continue
        md5, _ = by_value[value]
        old_path = disk_path(value, md5)
        cur = dec(z.read(old_path), key)
        for anchor, new in subs:
            c = cur.count(anchor)
            if c != 1:
                sys.exit(f'[-] {value}: anchor 命中 {c} 次（应为 1），版本可能已变')
            cur = cur.replace(anchor, new)
        blob = enc(cur, key)
        nmd5 = hashlib.md5(blob).hexdigest()
        d, _, b = value.rpartition('/')
        pre = f'Payload/HelloLua.app/Assets/src/{d}/' if d else 'Payload/HelloLua.app/Assets/src/'
        new_path = pre + f'{b[:-4]}.{nmd5}.lua'
        replaced[old_path] = new_path
        new_entries[new_path] = blob
        meta[value] = (md5, nmd5, len(blob))
        assert dec(blob, key) == cur
        print(f'[ok] {value}\n     {md5[:8]} -> {nmd5[:8]} {len(blob)}B')

    for value, (omd5, nmd5, size) in meta.items():
        old_size = by_value[value][1]
        pat = f'<file md5="{omd5}" size="{old_size}" value="{value}"'
        rep = f'<file md5="{nmd5}" size="{size}" value="{value}"'
        if manifest.count(pat) != 1:
            sys.exit(f'[-] 清单 anchor 异常: {value}')
        manifest = manifest.replace(pat, rep)

    n = 0
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as o:
        for name in z.namelist():
            if name in replaced:
                continue
            if '_CodeSignature/' in name or '/_CodeSignature' in name or '/SC_Info/' in name:
                continue
            o.writestr(name, manifest.encode('utf-8') if name == sc_name else z.read(name))
            n += 1
        for p, blob in new_entries.items():
            o.writestr(p, blob)
            n += 1
    print(f'[done] entries={n} size={os.path.getsize(out)} -> {out}')


if __name__ == '__main__':
    main()
