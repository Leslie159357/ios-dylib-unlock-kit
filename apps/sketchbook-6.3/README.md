# Sketchbook® 6.3 (com.autodesk.ios.SketchBookPro3) 解锁存档

成品：`/opt/data/downloads/Sketchbook_6.3.0_Unlocked.ipa`（注入本目录 dylib，需自签）
迭代：只发本目录 `SketchbookUnlock.dylib`，重新注入签名即可

## 判定链（IDA 9.4 实证，2026-10-27）

    -[AppStoreConnection isPremiumBundlePurchased]
        = (+[iPUtilities isBuildUnlockedVersion] | 全局 byte_100D554F8)
    byte_100D554F8 只在一处写 1：
    -[AppStoreConnection getInAppPurchasesValueForKey:]
        NSUserDefaults["In_App_Purchases"]["Premium_Bundle_Product"]
        → +[EncryptDecrypt decryptIdentifier:error:] 解密
        → 与 identifierForVendor UUID 首段比对，相等才置位

Swift 侧缓存属性（BrushLibraryTableViewController / BrushSettingsViewController /
ColorWheelController / ColorSetEntry …）都在 init 里从上面那个方法取值，
所以在 AppStoreConnection 这一层 hook 就全量生效，不需要逐个类打补丁。

- 商品 ID：`com.autodesk.ios.SketchBookPro3.PremiumBundle`
- `+[iPUtilities isBuildUnlockedVersion]` 只影响两处 UI（隐藏升级入口），不影响功能
- 图层上限由画布尺寸决定（`+[DocumentLimit MaxLayerCount]`=64），非付费项；
  `+[DocumentLimit isGodModeOn]` 是调试开关（6000 层 / 640000 画布），未启用
- 二进制内 `appStoreReceipt` 引用 0 次、无订阅接口域名、无越狱检测 → **Loon 无拦截面**

## 为什么 Loon 不行

购买态是本地加密标记 + StoreKit 一次性内购，全流程无网络判定，
MITM 没有可篡改的响应体。

## 复现步骤

1. `ipatool purchase -b com.autodesk.ios.SketchBookPro3`（免费，先占 license）
2. `ipatool download -b ...` → 加密 IPA
3. `python3 /opt/data/tools/fairplay-decrypt-v2/decrypt.py <enc.ipa> <dec.ipa> --credential .../cred/credential.bin`
4. `docker cp Hook.c ios-dev:/tmp/ && clang --target=arm64-apple-ios15.0 -ffreestanding -nostdinc ... ;
   /usr/bin/ld64.lld-19 -dylib -no_fixup_chains -platform_version ios 15.0.0 15.0.0 -undefined dynamic_lookup`
5. `python3 build_ipa_py.py <dec.ipa> SketchbookUnlock.dylib <out.ipa>`（无 zip/unzip 环境版）

## 坑

- 本机容器没有 `zip`/`unzip`，`build_ipa.sh` 会 rc=127 静默退出 → 用 `build_ipa_py.py`
- ios-dev 里 ld64 只有 `/usr/bin/ld64.lld-19`，必须绝对路径 + `-no_fixup_chains`
- 校验构造器落段时 LC_SEGMENT_64 是 0x19（不是 0x1），写错会假阴性
