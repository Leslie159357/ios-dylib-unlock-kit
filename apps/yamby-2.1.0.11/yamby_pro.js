/*
 * ============================================================================
 *  Yamby Pro 解锁脚本 (Frida)  —— 只改内存, 不动 APK
 *  目标: com.hush.yamby v2.1.0.11   加固: 娜迦 NMMP (libnmmp.so / libnmmvm.so)
 * ============================================================================
 *
 *  【为什么只能走运行时】
 *    · 权益回调被娜迦虚拟化成 native（dex 无字节码）：305 个类 / 1165 个方法在 VMP 里,
 *      其中包含 uc.C5947.m11100(BillingResult, List) 与整套设置层 rc.*。
 *      静态 patch 无字节码可改；重打包还会触发娜迦完整性校验。
 *    · 但"授权校验链"是明文 dex, 钩住即可 —— APK 一个字节不改, 不触发反篡改。
 *
 *  【明文事实（全部来自 dex 反编译, 非猜测）】
 *    MainCmpActivity.onResume():
 *        String s = rc.<授权类>.<getter>();                       // 本地授权串, MMKV id = "acbz"
 *        if (非空 && s.length()>=5) {
 *            if (ub.<校验类>.<verify>(HMAC生成器("LeidACoAd!@", 31天), s)) return;
 *            if (ub.<校验类>.<verify>(HMAC生成器("LeidAC0Ad!@",120天), s)) return;
 *        }
 *        if ("gpBundle".contains("gp")) {  ... queryPurchasesAsync("inapp") ...  }  // 否则才回 Play 校验
 *    校验实现:  str.equals(generator.code(System.currentTimeMillis()))
 *    => 授权串 = "时间步长 TOTP 码", 密钥与步长(31天/120天)硬编码在包里。
 *
 *  【用法】  frida -U -f com.hush.yamby -l yamby_pro.js --no-pause
 *    先只观察(不改行为): 把 FORCE_VERIFY 与 FAKE_LICENSE 都改成 false,
 *    看 [VERIFY] / [MMKV] 日志是否命中, 再开启。
 * ============================================================================
 */

'use strict';

var FORCE_VERIFY = true;                     // 核心: 授权校验恒真
var FAKE_LICENSE = true;                     // 伪装/写入授权串
var FAKE_VALUE   = 'YAMBYPRO-RUNTIME';
var LOG_MMKV     = true;                     // 打印 MMKV 读取轨迹

// ---- 混淆后的真实名字（由 smali 自动提取, 勿手改）----
var CLS_VERIFIER   = '\u0075\u0062\u002e\u06e5\u06da\u06e5\u06d8\u06e7\u06e0\u06e8';   // ub.C5938
var M_VERIFIER     = '\u06e5\u06dc\u06db\u06eb\u06e6\u06e6';
var CLS_LICENSE    = '\u0072\u0063\u002e\u06e5\u06d6\u06d7\u06ec\u06e0\u06e4\u06dc';   // rc.C5343
var F_LICENSE_SING = '\u06e5\u06d6\u06d9\u06df\u06d9';
var M_LICENSE_GETS = ['\u06e5\u06e0\u06e1\u06d8\u06eb\u06da\u06e8', '\u06e5\u06e0\u06e2\u06e7\u06d9\u06db'];
var M_LICENSE_SETS = ['\u06e5\u06e0\u06e5\u06ec\u06dc\u06e4', '\u06e5\u06e0\u06e8\u06e7\u06df', '\u06e5\u06e1\u06e1\u06e0\u06db\u06d9'];

function log(t, m) { console.log('[' + t + '] ' + m); }

Java.perform(function () {

    // ---------- 1) 授权校验恒真 ----------
    if (FORCE_VERIFY) {
        try {
            var V = Java.use(CLS_VERIFIER);
            V[M_VERIFIER].implementation = function (gen, s) {
                log('VERIFY', '校验命中, 本地授权串=' + s + '  => 强制 true');
                return true;
            };
            log('OK', '授权校验钩子: ' + CLS_VERIFIER + '.' + M_VERIFIER);
        } catch (e) { log('FAIL', '校验钩子: ' + e); }
    }

    // ---------- 2) 伪造授权串 ----------
    if (FAKE_LICENSE) {
        M_LICENSE_GETS.forEach(function (m) {
            try {
                Java.use(CLS_LICENSE)[m].implementation = function () { return FAKE_VALUE; };
                log('OK', '授权 getter 伪装: ' + m);
            } catch (e) { log('FAIL', 'getter ' + m + ': ' + e); }
        });
        try {
            var L2 = Java.use(CLS_LICENSE);
            var inst = L2[F_LICENSE_SING].value;
            M_LICENSE_SETS.forEach(function (m) {
                try { inst[m](FAKE_VALUE); log('OK', 'setter 写入: ' + m); }
                catch (e) { log('FAIL', 'setter ' + m + ': ' + e); }
            });
        } catch (e) { log('FAIL', '单例取用失败: ' + e); }
    }

    // ---------- 3) MMKV 读取轨迹（定位其它 Pro 标记）----------
    if (LOG_MMKV) {
        ['decodeBool', 'getBoolean', 'decodeInt', 'decodeLong', 'getString', 'decodeString'].forEach(function (n) {
            try {
                var M = Java.use('com.tencent.mmkv.MMKV');
                if (!M[n] || !M[n].overloads) return;
                M[n].overloads.forEach(function (ov) {
                    if (ov.argumentTypes.length !== 2) return;
                    ov.implementation = function () {
                        var r = ov.apply(this, arguments);
                        log('MMKV', n + '(' + arguments[0] + ') = ' + r);
                        return r;
                    };
                });
                log('OK', 'MMKV 轨迹: ' + n);
            } catch (e) { log('FAIL', 'MMKV ' + n + ': ' + e); }
        });
    }

    log('DONE', '装载完成。若 Pro 未解锁，把 [MMKV] 日志发回，可定位其它门禁。');
});
