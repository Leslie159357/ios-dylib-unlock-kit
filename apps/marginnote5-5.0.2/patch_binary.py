#!/usr/bin/env python3
"""MarginNote 5.0.2 主二进制静态补丁（幂等，带前置校验）。

两类补丁，全部围绕「自签包缺 iCloud 授权」与「侧载包上自定义 AI 绑定」：

A. 自定义 AI 绑定的三道内联硬门（纯 runtime hook 过不去，只能改字节）
   +[AIServiceProvider bindPendingCustomAIProfileAfterSuccessfulTest]
     0x1018f4580  tbz w0,#0,...        -> NOP      收据里的 receipt 必须是 NSString
     0x1018f460c  tbz w20,#0,...       -> NOP      六项测试标志/策略版本/收据哈希
     0x1018f49bc  mov x28,x0           -> movz x28,#1   Keychain 结果强写成功

B. CloudKit 容器创建（自签包没有 iCloud entitlement，建容器必抛 CKException→abort）
   把 `BL objc_msgSend$containerWithIdentifier:` 换成 `mov x0,#0`（返回 nil，
   后续 [nil publicCloudDatabase] 直接短路，App 走「未登录 iCloud」分支）：
     -[iCloudSyncManager init]   0x101eb7c24 / 0x101eb7c50 / 0x101eb7c94 / 0x101eb8eb4
     +[iCloudSyncManager checkActivationLive] 0x101f3c150
     +[iCloudSyncManager activateDB:]         0x101f3c5dc
   其余 29 处 containerWithIdentifier 调用点（Swift 同步引擎深处）**故意不动**，
   Swift 侧对非可选值解包，塞 nil 会换成另一种崩溃。

用法: python3 patch_binary.py <脱壳后的原型/Payload/MarginNote 5.app/MarginNote 5>
"""
import sys

BASE = 0x100000000
NOP = "1f2003d5"
MOVZ_X28_1 = "3c0080d2"
MOV_X0_0 = "000080d2"

TBZ_SITES = [
    (0x1018f4580, "bind: receipt-is-NSString gate"),
    (0x1018f460c, "bind: test-flags/receipt-hash gate"),
]

CK_SITES = [
    (0x101eb7c24, "iCloudSyncManager init #1"),
    (0x101eb7c50, "iCloudSyncManager init #2"),
    (0x101eb7c94, "iCloudSyncManager init #3"),
    (0x101eb8eb4, "iCloudSyncManager init #4"),
    (0x101f3c150, "checkActivationLive"),
    (0x101f3c5dc, "activateDB:"),
]


def main(path):
    data = bytearray(open(path, "rb").read())
    changed = 0

    for va, label in TBZ_SITES:
        off = va - BASE
        cur = bytes(data[off:off + 4])
        if cur.hex() == NOP:
            print("[skip ] %-42s %s already NOP" % (label, hex(va)))
            continue
        if (int.from_bytes(cur, "little") & 0x7F000000) != 0x36000000:
            raise SystemExit("[abort] %s %s 不是 TBZ：%s" % (label, hex(va), cur.hex()))
        data[off:off + 4] = bytes.fromhex(NOP)
        print("[patch] %-42s %s %s -> NOP" % (label, hex(va), cur.hex()))
        changed += 1

    off = 0x1018f49bc - BASE
    cur = bytes(data[off:off + 4])
    if cur.hex() == MOVZ_X28_1:
        print("[skip ] %-42s %s already movz x28,#1" % ("bind: keychain result -> true", hex(0x1018f49bc)))
    else:
        if cur.hex() != "fc0300aa":
            raise SystemExit("[abort] keychain mov unexpected: %s" % cur.hex())
        data[off:off + 4] = bytes.fromhex(MOVZ_X28_1)
        print("[patch] %-42s %s fc0300aa -> movz x28,#1" % ("bind: keychain result -> true", hex(0x1018f49bc)))
        changed += 1

    for va, label in CK_SITES:
        off = va - BASE
        cur = bytes(data[off:off + 4])
        if cur.hex() == MOV_X0_0:
            print("[skip ] %-42s %s already mov x0,#0" % (label, hex(va)))
            continue
        if (int.from_bytes(cur, "little") & 0xFC000000) != 0x94000000:
            raise SystemExit("[abort] %s %s 不是 BL：%s" % (label, hex(va), cur.hex()))
        data[off:off + 4] = bytes.fromhex(MOV_X0_0)
        print("[patch] %-42s %s %s -> mov x0,#0" % (label, hex(va), cur.hex()))
        changed += 1

    open(path, "wb").write(data)
    print("done, changed=%d" % changed)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    main(sys.argv[1])
