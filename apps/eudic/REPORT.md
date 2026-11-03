# 欧路软件 EuDic 系（德语助手 / 欧路词典 / 每日德语听力）授权模型

## 一、结论先行
授权判定 **100% 在本地**，无服务端校验，Loon 改写无效，只能 dylib / 二进制补丁。
实测样本：德语助手 iOS 26.10.1 (eusoft.dehelper.ip, 执行文件 EuDic_de, build 759, arm64)。

## 二、判定链（IDA 定位法）
1. 搜符号 `isProVersion` → 会有多个类（UserInfo / EUUIUtils / ReaderKitManager），伪代码都是同一段内联：
   ```c
   v2 = +[EuDictManager sharedInstance];
   -[EuDictManager myCus](v2, "myCus");        // 懒加载，构造时写全局
   return (unsigned)G < 7 & (0x64u >> G);      // G = 全局 dword
   ```
   位掩码 0x64 → 只有 G ∈ {2, 5, 6} 为真（2=主授权，5/6=增强包，0=未注册，1=过期，3=试用）。
2. 追该全局（本例 `dword_101EB8D08`）的写入点：`xrefs → 取 STR 指令`，通常 3 处：构造函数内、`-sub_1004AA9B0`(读 app_config.SerialCode_Ip)、`-[EuDictManager myCus]`(keychain 过期检查 → 写 1)。
3. 词库闸门：`-[EuDictManager myLibs]` 先调 myCus，再用同一个全局算 `USER_DictVip` 写进 NSUserDefaults（standard + app group），并把 `&全局` 传给 C++ 词库管理器（本例 `sub_100525C8` → `sub_100525DE8`），VIP 版权词典可用性由该值决定。
4. 翻译 VIP 是另一条线：`/api/v3/user/profile` 响应 `data.transvip` / `data.transvip_endtime` → `+[EUUserInfo parseAiUserProfileResponse:]` → `USER_TransVip` / `USER_TransVip_EndTime`。这一条可以用 Loon 改 JSON，也可以 dylib hook。
5. 反调试障碍为零：`+[EUVerityBundleSignature checkCodeSignWithProvisionID:]` 编译期就是 `return true`，自签/注入不触发校验。

## 三、可用 dylib 方案（零 SDK 交叉编译，已验证）
- constructor 里只做内存写：`*(int*)((char*)_dyld_get_image_header(0) + 0x1EB8D08) = 2;`（偏移 = 全局 vmaddr − 0x100000000）
- Foundation 写入（NSUserDefaults setBool）**不要放 constructor**，放进 `-[EuDictManager myCus]` / `myLibs` 的 hook 回调里，避开 LoadControl 早期初始化
- 必须 hook `myCus` 原实现返回后再次纠正全局，否则登录/序列号校验失败路径会把它刷成 1
- `+[EULicense verifyLicensePackage:showSuccessMessage:showFailMessage:]` 直接 swizzle 成返回 YES（不调原实现），阻断降级
- 类名坑：二进制里 `UserInfo` 与 `EUUserInfo` 可能同时存在，IDA 的函数名带 EU 前缀不代表类名带；`objc_getClass` 拿不准就两个都 hook（找不到会静默跳过）

## 四、二手包识别
资源站的「X_pro.ipa」常已把构造函数的 `movz w8, #0` 改成 `#2`（等价全解锁）。判断方法：看 `isProVersion` 反编译里全局初值来源，若 constructor 无条件写 2 而 `-sub_XXX` 里还有 `if (G==3||G==0)` 试用分支，就是被补过的。自研 dylib 不依赖该处补丁，替换基线包也能用。


## 本目录产物

- `EuDicUnlock.dylib`（66,592 B，arm64）
- `REPORT.md`：EuDic 系（德语助手 / 欧路词典 / 每日德语听力）授权模型

`strings` 实测作用点：`verifyLicensePackage:showSuccessMessage:showFailMessage:` 直接返回 YES、
全局授权位 `dword_101EB8D08` 写 2、`USER_DictVip` / `USER_TransVip` / `USER_TransVip_EndTime` 写 NSUserDefaults。
