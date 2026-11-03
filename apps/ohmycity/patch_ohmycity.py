#!/usr/bin/env python3
"""OhMyCity 1.1.3 (build 27) — Pro 解锁静态补丁。

输入：脱壳后的主二进制 Payload/ohmycity.app/ohmycity
输出：打过补丁的二进制（原地替换后重打包 IPA 即可）

所有补丁都以「原指令 == 预期值」做前置校验，版本不符会直接报错退出，
避免把补丁按错位置。

用法：
    python3 patch_ohmycity.py <input_binary> <output_binary>
"""
import hashlib
import struct
import sys

BASE = 0x100000000  # __TEXT vmaddr

# 已知版本：OhMyCity 1.1.3 (CFBundleVersion 27)
KNOWN_SHA256 = "28195d87c4ee77e04e7d097c0d98b418a4a5850310b34c2df1b0fb3bacaa2233"

# (vmaddr, 原4字节, 新4字节, 说明)
PATCHES = [
    # ---- 关键：状态写入路径（真正生效的两条）----
    (0x1000E3EFC, 0x52802008, 0x52802028,
     "PurchaseEntitlements 默认值 mov w8,#0x100 -> #0x101（byte0=isPro 置 1，byte1=isLoaded 保持 1）"),
    (0x1000E928C, 0x39400334, 0x52800034,
     "PurchaseStore.apply(_:) 读取结构体 byte0 -> mov w20,#1（强制 isPro 为真）"),

    # ---- 兜底：getter / setter（视图若走非内联路径也有救）----
    (0x1000D91FC, 0x39404260, 0x320003E0,
     "isPro getter: ldrb w0,[x19,#0x10] -> mov w0,#1"),
    (0x1000DDE00, 0x39408660, 0x320003E0,
     "activePlan getter: ldrb w0,[x19,#0x21] -> mov w0,#1（Optional<ProPlan>: 1 == some(.lifetime)）"),
    (0x1000E4C20, 0x12000016, 0x320003F6,
     "isPro setter: and w22,w0,#1 -> mov w22,#1"),
    (0x1000E52D8, 0x12001C16, 0x320003F6,
     "activePlan setter: and w22,w0,#0xff -> mov w22,#1"),
]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    data = bytearray(open(src, "rb").read())

    sha = hashlib.sha256(data).hexdigest()
    print(f"input  : {src}")
    print(f"sha256 : {sha}")
    if sha != KNOWN_SHA256:
        print("!! 版本不匹配（非 1.1.3 / 27 的脱壳二进制），补丁地址可能失效。")
        print("!! 继续会对 6 个地址逐一做原指令校验，校验不过即中止。")

    ok = 0
    for addr, old, new, desc in PATCHES:
        off = addr - BASE
        cur = struct.unpack("<I", data[off:off + 4])[0]
        if cur != old:
            print(f"FAIL {addr:#x}: 期望 {old:#010x}，实际 {cur:#010x} —— {desc}")
            return 1
        data[off:off + 4] = struct.pack("<I", new)
        ok += 1
        print(f"ok   {addr:#x}: {old:#010x} -> {new:#010x}  {desc}")

    open(dst, "wb").write(data)
    print(f"\n{ok}/{len(PATCHES)} 条补丁写入 {dst}")
    print("提示：主二进制 chmod 755，剔除 _CodeSignature / SC_Info 后重打包。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
