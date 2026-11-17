#!/usr/bin/env python3
"""Waterllama 1.94.30 (build 1379) — Premium 解锁 + iCloud 断链补丁。

输入：脱壳后的主二进制 Payload/Water.app/Water
输出：打过补丁的二进制（替换回 .app 后重打包 IPA）

三组补丁：
  A. 会员位      —— purchaseState 的 7 处读取 + 1 处写入，全部恒真
  B. CloudKit    —— +[CKContainer defaultContainer] 5 处调用点返回 nil
                    （重签后无 iCloud entitlement，原调用会抛 CKException 崩溃）
  C. 等待点      —— dispatch_group_wait 7 处直返 0
                    （容器为 nil 时 completion 不会回来，原等待会把主线程挂死被看门狗杀）

所有补丁都以「原指令 == 预期值」做前置校验，版本不符直接报错退出。

用法：
    python3 patch_waterllama.py <input_binary> <output_binary>
"""
import hashlib
import struct
import sys

BASE = 0x100000000  # __TEXT vmaddr；该 App 的 __TEXT fileoff = 0

# 脱壳（cryptid=0）后的原始主二进制
KNOWN_SHA256 = "fd326619bb5c6c84c96914af82b87c71d28f9f44b3afdc24214c1982aa23fee4"

MOV_W0_1 = 0x52800020   # mov w0, #1
MOV_W0_0 = 0x52800000   # mov w0, #0
MOV_W20_1 = 0x52800034  # mov w20, #1

# (vmaddr, 原指令, 新指令, 说明)
PATCHES = [
    # ---- A. 会员位：7 处 boolForKey:"purchaseState" ----
    (0x1003515DC, 0x9422D6A9, MOV_W0_1, "读取 purchaseState #1 -> 恒真"),
    (0x100352AC4, 0x9422D16F, MOV_W0_1, "读取 purchaseState #2 -> 恒真"),
    (0x1004BDA70, 0x941D2584, MOV_W0_1, "读取 purchaseState #3 -> 恒真"),
    (0x1004BEA58, 0x941D218A, MOV_W0_1, "读取 purchaseState #4 -> 恒真"),
    (0x1004BFE78, 0x941D1C82, MOV_W0_1, "读取 purchaseState #5 -> 恒真"),
    (0x1004C059C, 0x941D1AB9, MOV_W0_1, "读取 purchaseState #6 -> 恒真"),
    (0x1004C1A18, 0x941D159A, MOV_W0_1, "读取 purchaseState #7（Free/Premium 文案分支）-> 恒真"),
    (0x1003534F0, 0x39408354, MOV_W20_1, "写入口 ldrb w20,[x26,#0x20] -> mov w20,#1（saveSubscriptionStatus 永远写 true）"),

    # ---- B. CloudKit：+[CKContainer defaultContainer] ----
    (0x1005715D8, 0x941A6672, MOV_W0_0, "defaultContainer #1 -> nil"),
    (0x100573520, 0x941A5EA0, MOV_W0_0, "defaultContainer #2 -> nil"),
    (0x1005769E8, 0x941A516E, MOV_W0_0, "defaultContainer #3 -> nil"),
    (0x100576A94, 0x941A5143, MOV_W0_0, "defaultContainer #4 -> nil（首轮崩溃点）"),
    (0x100576E14, 0x941A5063, MOV_W0_0, "defaultContainer #5 -> nil"),

    # ---- C. 等待点：dispatch_group_wait ----
    (0x10057666C, 0x941A25EE, MOV_W0_0, "dispatch_group_wait #1 -> 直返 0"),
    (0x100576B34, 0x941A24BC, MOV_W0_0, "dispatch_group_wait #2 -> 直返 0（二轮看门狗点）"),
    (0x100576E48, 0x941A23F7, MOV_W0_0, "dispatch_group_wait #3 -> 直返 0"),
    (0x1006460F4, 0x9416E74C, MOV_W0_0, "dispatch_group_wait #4 -> 直返 0"),
    (0x100649958, 0x9416D933, MOV_W0_0, "dispatch_group_wait #5 -> 直返 0"),
    (0x10064A894, 0x9416D564, MOV_W0_0, "dispatch_group_wait #6 -> 直返 0"),
    (0x10064BA00, 0x9416D109, MOV_W0_0, "dispatch_group_wait #7 -> 直返 0"),
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
        print("!! 版本不匹配（非 1.94.30 / 1379 的脱壳二进制），补丁地址可能失效。")
        print("!! 继续会对 20 个地址逐一做原指令校验，校验不过即中止。")

    ok = 0
    for addr, old, new, desc in PATCHES:
        off = addr - BASE
        if off < 0 or off + 4 > len(data):
            print(f"!! {addr:#x} 超出文件范围")
            return 1
        cur = struct.unpack("<I", data[off:off + 4])[0]
        if cur != old:
            print(f"!! {addr:#x} 原指令不符：期望 {old:#010x}，实际 {cur:#010x} —— {desc}")
            return 1
        data[off:off + 4] = struct.pack("<I", new)
        ok += 1
        print(f"   {addr:#010x}  {old:#010x} -> {new:#010x}   {desc}")

    with open(dst, "wb") as f:
        f.write(data)
    print(f"\n{ok}/{len(PATCHES)} 条补丁已应用 -> {dst}")
    print(f"输出 sha256: {hashlib.sha256(data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
