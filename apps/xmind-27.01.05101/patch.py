#!/usr/bin/env python3
"""Xmind iOS 27.01.05101 静态补丁器

用法：python3 patch.py <已解密的主二进制 Yogurt> <输出路径>

前提：IPA 已脱壳（主二进制 cryptid=0）。补丁按虚拟地址换算
（__TEXT 基址 0x100000000，文件偏移 = VA - 0x100000000），
对 arm64 slice 直接改指令，打完用 ldid -S 重签。

六处补丁全部是"函数开头 8 字节改成 mov/ret"，语义见 README.md。
"""
import sys

BASE = 0x100000000

PATCHES = [
    # (VA, 新字节, 原字节前缀, 说明)
    (0x10042E2A4, "60008052c0035fd6", "ffc306d1", "PersonalLicenseType -> 3 (Premium)"),
    (0x1004281F0, "60008052c0035fd6", "ff8306d1", "个人会员总闸 -> 3（同时解除建图数量上限）"),
    (0x10042E81C, "20008052c0035fd6", "ff8301d1", "团队/公共空间授权 -> true（原 3 张建图限制的来源）"),
    (0x10042A5B0, "20008052c0035fd6", "f44fbea9", "isPremium -> true"),
    (0x10042A5FC, "20008052c0035fd6", "fc6fbaa9", "isProPlus -> true"),
    (0x100425864, "20008052c0035fd6", "fc6fbaa9", "设备 license / Pro -> true"),
]


def main(src, dst):
    data = bytearray(open(src, "rb").read())
    for va, new_hex, expect, note in PATCHES:
        off = va - BASE
        blob = bytes.fromhex(new_hex)
        cur = data[off:off + len(blob)].hex()
        if not cur.startswith(expect):
            raise SystemExit(f"[!] {hex(va)} 期望 {expect}，实际 {cur} —— 版本不匹配，停止")
        data[off:off + len(blob)] = blob
        print(f"[+] {hex(va)} {note}  {cur} -> {new_hex}")
    open(dst, "wb").write(data)
    print(f"[=] 写出 {dst} ({len(data)} B)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
