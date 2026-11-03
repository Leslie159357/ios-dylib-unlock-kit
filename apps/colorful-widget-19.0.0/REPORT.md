# Colorful Widget 彩虹小组件 19.0.0 — 会员解锁（Loon）

- **Bundle**：`com.sm.widget`
- **版本**：19.0.0（App Store id `1538946171`，开发方 Guangzhou ZHIFENG）
- **结论**：真机确认会员显示（2026-11-04）。纯 Loon 实现，无 dylib、无重打包。
- **插件**：https://loon.1122275.xyz/plugins/ColorfulWidget/ColorfulWidget.plugin?v=1.1.0

## 1. 三套加密通道

抓包里 4 个域各用一套 AES-128-CBC（key == iv，base64url，响应零填充 / 请求 PKCS7）：

| 通道 | key / iv | 用途 |
| --- | --- | --- |
| `api.unbing.cn` | `jr1WrfW8q2sV6xir` | 业务 API（会员态、AI 提示词、壁纸额度） |
| `cdn.resource.unbing.cn`（远端配置） | `OfLSbK6DD8oVmky6` | appmanage 模块配置（明文 envelope + 加密 `data`） |
| `cgi.unbing.cn` / `*.cgi.sharpmobi.com` | `PaOyRlQAFkAncjXh` / `7EGzwpSS5y1Ds7nE` | 上报、组件配置 CGI |

前两组 key 是 **base64 字面量**（`T2ZMU2JLNkREOG9WbWt5Ng==`、`OUhaUWxKZUc3UEFxI3hwdlBvYlk=`），
第三组是 ObjC `CFSTR`，`api.unbing.cn` 那组是 `__cstring` 里的裸 16 字节常量（`0x10528e9e0`）。

## 2. 会员判定链（IDA 9.5）

```
+[ServerVipUtils isServiceVip]          读 NSUserDefaults "piv_server_status"
  ← sub_1001ACA58(Bool)                 同时写 piv_server_status / piv_server_status_date
  ← sub_1001AC360(model,...)            比较 ServerVipModel.vipFlag == 1
                                        （Ivar offset 16，ldr x64，故 JSON 用整数 1 不是 true）
  ← sub_1001ACCC4 ← userExtend/get 响应
```

`-[MCWPurchaseManager isVipUser] = (userPayState == 3) || isServiceVip`，UI 分支走这里。

本地收据支线：

```
-[MCWPurchaseManager refreshUserPayState]
    productIdSet ∩ {cf_forever_14.4.0, cf__forever_0_4.7.1, wg_life_0_2.3.0} ≠ ∅  → userPayState = 3
    否则 product_id 非空 且 expires_date_ms > now                                → userPayState = 3
-[MCWPurchaseManager saveReceiptWithDeviceBindingCheck:...]
    partner_tran_id(original_transaction_id) 为空 → 不调服务端绑定，直接落本地 Documents
```

`+[MCWCheckReceiptFromAppStore checkAppStoreReceiptWithURL:receiptPassword:success:fail:]`
在 restore 时打 `sandbox.itunes.apple.com/verifyReceipt`，返回 `21008` 再打 `buy.itunes.apple.com/verifyReceipt`。

## 3. 插件实现

`colorfulwidget.js` 两条分支：

1. **A｜服务端会员态**：接管 `POST /api/widget/colorful/userExtend/get`，整包替换为
   `{"addr":"","code":"0","data":"P_p-0PeKdUMMb06TJtycxQ","msg":"成功","updateTime":<now>}`。
   `P_p-0PeKdUMMb06TJtycxQ` 是 `{"vipFlag":1}` 零填充后 AES-CBC 的 base64url 结果，
   离线预算好，脚本里不含加密实现。
2. **B｜本地收据会员态**：`verifyReceipt` 两个域返回 2099 年终身收据，覆盖三支买断 SKU，
   并**故意不带 `original_transaction_id`**，让 `partner_tran_id` 为空跳过服务端设备绑定。

## 4. 关键方法教训

- 全链路 key 搜索用「1 字节滑窗 + JSON 前缀 oracle」：对每个 key 候选只解 1~2 个块，
  判据是解密结果首个字节为 `{` / `[` 且能 UTF-8 解码，再用第二个端点密文交叉确认。
  `__cstring` 里 75MB 代码段级扫描在本机约 15 分钟，命中 1 个。
- 先前的 `PKCS7 填充校验` 与 `全 printable` 两个 oracle 在这套协议上都会漏判：
  响应是**零填充**、正文含中文，两个判据都会把正确 key 判成失败。
- 只扫 `__const`/`__data` 段会漏掉 key；`api.unbing.cn` 那组就躺在 `__cstring`。
- 抓包工具会把 `token` 头截断成 `eyJ0eX...GdoA`，别指望用它反推密钥派生。

## 5. 证据

- 抓包 `1656`（破解前）：`userExtend/get` 返回空 `data`，响应可解出 `{"endRow":0,...}` 等明文。
- 抓包 `1658`（v1.1.0 发布前）：`data` 仍为空，`verifyReceipt` 未出现，`/bs/apple/ad/service/verify/v1` 三次 404。
- 真机确认：会员标识显示（2026-11-04）。
