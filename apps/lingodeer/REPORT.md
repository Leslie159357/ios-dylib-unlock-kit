# LingoDeer v3 全站 RSA+AES 双信封 —— Loon 无解实证（2026-10-15）

## 一句话

LingoDeer iOS 3.1.16 的 `/v3/*` 全量 API 走 **RSA-1024 + AES/CBC 双信封**，AES 会话密钥
由客户端**每请求随机生成**（`UUID.randomUUID().toString().substring(0,16)`），只以 RSA 密文
出现在网络上；**响应体又用同一把会话密钥加密**。因此 MITM 既读不到响应也造不出响应。

## 判定配方（拿到同类 App 5 分钟定性）

1. 抓一个包，看响应：`content-type: application/json` 但 body 是纯 base64 串（不是 `{`）。
2. 看请求体：只有一个字段 `token`，其值是 base64，解开是
   `{"enKey": "...", "enIV": "...", "enContent": "...", "caller": "..."}`。
3. 量长度：`enKey` / `enIV` 的 base64 长度 172 → 128 字节 → **RSA-1024 密文块**（PKCS1
   padding 下明文 16 字节，正好是一把 AES-128 密钥 / 一个 IV）。
4. `caller` 长度 44 → 32 字节 → AES-CBC 加密接口名（如 `purchase_memberstatus`）后的块数。

三条同时命中 → 直接判定 Loon 死路，别浪费时间写脚本。

## 证据链

### 1. 真机抓包（iOS 3.1.16，com.lingodeer）

真实 API 域名是 **`v3api.lingodeer.com`**（不是 azure / lambda / www —— 那些是 Android 与 Web 用的）。

请求头特征：

    :authority: v3api.lingodeer.com
    :path: /v3/purchase_memberstatus
    user-agent: LingoDeer/3.1.16 (iOS; iPhone; iOS 18.6.2; zh-Hans-CN)
    content-type: application/json

抓到的端点（全部同构）：

    /v3/purchase_memberstatus          ← 会员状态（解锁目标）
    /v3/apple_purchase_restore
    /v3/me_data_get
    /v3/me_data_bookmark_get
    /v3/me_data_progress_update
    /v3/me_data_streak_get_all_collection
    /v3/me_data_subcourse_progress_get
    /v3/me_data_task_unitlesson_get
    /v3/me_data_xp_and_learntime_get_all_collection
    /v3/fluent_progress_sync
    /v3/review_srs_record_get
    /v3/user_bigfans_check
    /v3/user_firebase_openid_check
    /v3/user_firebase_openid_law
    /v3/user_items_review_data_sync

全部请求体形如 `{"token":"<base64>"}`；全部响应体是 base64 密文（如
`/v3/purchase_memberstatus` 响应 366 字节，`"2+W9+hN+JF..."`）。

### 2. 反编译实证（Android 包 com.lingodeer，同一后端、同一套信封）

R8 混淆后关键类仍在。`Lhv/a;`（加密助手）：

    // 生成会话密钥：每请求随机！
    public static SecretKeySpec c() {
        String u = UUID.randomUUID().toString();
        return new SecretKeySpec(u.substring(0, 16).getBytes("UTF-8"), "AES");
    }

    // 加密（请求侧）：AES/CBC/PKCS7 + base64
    public static String a(String p5, String p6, String p7) { ... Cipher.getInstance("AES/CBC/PKCS7Padding") ... }

    // 解密（响应侧）：用的就是同一个会话密钥/IV
    public static String b(String responseBody, SecretKey key, SecretKey iv) {
        Cipher c = Cipher.getInstance("AES/CBC/PKCS7Padding");
        c.init(2, new SecretKeySpec(new String(key.getEncoded(), CHARSET).getBytes(CHARSET), "AES"),
                  new IvParameterSpec(...));
        return new String(c.doFinal(Base64.decode(responseBody, 0)));
    }

    // 服务端公钥（硬编码，RSA-1024，指数 AQAB=65537）
    public static PublicKey d() { ... RSAPublicKeySpec(new BigInteger(1, b64("3PZM7KmHBq53tBqrf...")), new BigInteger(1, b64("AQAB"))) ... }

信封组装（`Lnv/p;->y`）：`setEnKey(RSA(key))`、`setEnIV(RSA(iv))`、
`setEnContent(AES(content, key, iv))`、`setCaller(AES(callerName, key, iv))`，
再把整包 base64 塞进 `{"token": ...}`。

响应侧调用点：`Lhv/a;->b(String, SecretKey, SecretKey)` 的调用者
（`Ldv/u0;->v/a`）**没有明文兜底**——解密抛异常直接进 `ApiResponse$Error`。
即：网络层塞明文 JSON 不会降级解析，只会报错。

### 3. 为什么"伪造自己的信封"也不行

Loon 确实可以自己生成 key/iv、用抓出来的服务端公钥 RSA 加密，从而让服务器用**我们**的密钥加密响应。
但：① 客户端仍用它**自己**的密钥解密 → 拿到垃圾；② 业务鉴权（Firebase idToken）在**密文内部**，
请求头里没有 Authorization，我们无法构造带有效鉴权的伪造请求。
所以两条路都断。

### 4. 明文面残留（无权益价值）

- `firebaseremoteconfig.googleapis.com` 是**明文**，请求头带 `x-ios-bundle-identifier: com.lingodeer`
  （可精准守门，不会污染别家 App）。149 条配置全是**折扣/文案/开关**类
  （`billing_page_*`、`annual_discount`、`is_lock_free_level`、`daily_free_tell_me_why_count`），
  **不含任何权益位**，改不了会员。
- `d27hu3tsvatwlt.cloudfront.net/newsfeed/newsfeed.json`、`webjson.lingodeer.com` 静态图 →
  内容，与鉴权无关。

## 结论与出路

- Loon/QX 层面：**无解，且不是"难"而是密码学不可达**。
- 唯一出路：`ipa-unlocker` 走脱壳 IPA + dylib 弱加载注入。Hook 目标（二选一）：
  1. 解密函数（Android 对应 `hv.a.b`；iOS Swift 侧同名逻辑），让响应解密后返回我们构造的 JSON；
  2. 直接 Hook 会员模型（`UserPurchaseStatusResponse` / `CurrentPurchaseStatus` / `PremiumStatus`，
     字段 `expired_date_ms` / `expired_date_str` / `membershipType` / `isSubscribed`）。
- 由于 iOS 18.6.2 未越狱，需要**已脱壳的 IPA** 才能定符号/偏移。

## 撤回记录

曾于 v1.0.0 误判为"自建后端明文字段可改"并上线插件（拦了 azure/lambda/www 三个错域名，
且真域名其实是加密的），**已撤回并回滚 README**，库内不留无效插件。
教训：面向 iOS 的判定必须先拿真机抓包确认域名，再决定是否写插件；Android 域名 ≠ iOS 域名。


## 本目录产物

- `LingoDeer_unlock_dylib.dylib`（50,352 B，arm64）
- `REPORT.md`：`/v3/*` RSA-1024 + AES 双信封协议判定（这条决定了 Loon 无解，只能端上动手）

`strings` 实测 hook 目标：`isSubscribeUserAndPremiumEnable`、`userHadPurchased`、`needPurchase`、
`needPurchaseFor:`、`showLifetimePurchase`、`canFreeUseWithoutPurchaseForLangType:`、`membershipPurchaseType`，
即把会员判定统一短路为「已购买」，不走协议层。
