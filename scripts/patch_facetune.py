#!/usr/bin/env python3
"""Facetune 26.36 (com.lightricks.Facetune2) 静态补丁器。

用法:
    python3 patch_facetune.py <Payload/Facetune.app/Facetune> [--dry-run]

行为:
  1. 逐条校验原始字节（校验失败即中止，不会改坏已是别的版本的二进制）；
  2. 写入补丁（布尔判定统一 mov w0,#1; ret）；
  3. 把 group.com.lightricks 等长改写为 groop.com.lightricks（含所有出现处）。

补丁语义见 apps/facetune/REPORT.md。此脚本只改文件，不重打包、不签名。
"""
import sys

MOV_W0_1_RET = bytes.fromhex("20008052c0035fd6")  # mov w0,#1 ; ret
NOP = bytes.fromhex("1f2003d5")                    # nop

# (文件偏移, 原字节, 补丁字节, 说明)
PATCHES = [
    (0x1071DD8, bytes.fromhex("f44fbea9fd7b01a9"), MOV_W0_1_RET,
     "-[LegacyUserSubscriptionStateProvider hasVIPAccess]"),
    (0x383D600, bytes.fromhex("f44fbea9fd7b01a9"), MOV_W0_1_RET,
     "-[BZRSubscriptionState isUserSubscriber]"),
    (0x10744C, bytes.fromhex("e8cb039008f58db9"), MOV_W0_1_RET,
     "-[FTFeatureState hasVIPAccess]"),
    (0x12CF60, bytes.fromhex("002c4039c0035fd6"), MOV_W0_1_RET,
     "-[FTFeatureViewModel hasVIPAccess]"),
    (0x12E76C, bytes.fromhex("a8ca03b0083d8eb9"), MOV_W0_1_RET,
     "-[FTLegacyState hasVIPAccess]"),
    (0x3E691A4, bytes.fromhex("ffc301d1f65704a9"), MOV_W0_1_RET,
     "+[LTKeychainStorage verifyEntitlementExistsForAccessGroupID:] -> YES"),
    (0x3B8B7AC, bytes.fromhex("530200b4"), NOP,
     "INTStorage: UserDefaults(suiteName:) == nil 的 fatal 分支"),
]

STR_OLD = b"group.com.lightricks"
STR_NEW = b"groop.com.lightricks"


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1:
        print(__doc__)
        return 2
    path = args[0]

    with open(path, "rb") as f:
        data = bytearray(f.read())

    # 先全部校验，再统一写入，避免改到一半失败
    for off, old, _new, desc in PATCHES:
        cur = bytes(data[off:off + len(old)])
        if cur != old:
            print(f"[ABORT] {desc}: 偏移 0x{off:x} 期望 {old.hex()} 实际 {cur.hex()}")
            return 1
        print(f"[ok] 0x{off:x} {desc}")

    n_str = data.count(STR_OLD)
    print(f"[ok] {STR_OLD.decode()} x{n_str} -> {STR_NEW.decode()}")

    if dry:
        print("[dry-run] 未写入")
        return 0

    for off, _old, new, _desc in PATCHES:
        data[off:off + len(new)] = new

    i = 0
    while True:
        i = data.find(STR_OLD, i)
        if i < 0:
            break
        data[i:i + len(STR_NEW)] = STR_NEW
        i += len(STR_NEW)

    with open(path, "wb") as f:
        f.write(data)
    print(f"[done] 已写入 {path}（{len(data)} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
