//
//  TingDeVIP.m — 每日德语听力 (com.eusoft.ting-de) 会员解锁
//
//  目标 App: 每日德语听力 26.10.2 (build 463)
//  静态分析结论（IDA/objc 元数据）：
//    * AppDelegate 上存在全局属性  isVip (TB,N,V_isVip)  ivar: _isVip @ offset 9
//    * AppDelegate 上存在 vipType (Ti,N,V_vipType)
//    * 本地状态键: KEY_CURRENT_IS_VIP_STATUS / Key_User_Info / USER_DictVip
//    * VIP 类型值域（服务端字段 tingviptype）: forevervip / multiyearvip / annualfeevip
//    * 本地判定入口方法: -[? checkTingVip:]  -[? checkTingVipWithNavigationController:]
//
//  本 dylib 做三件事：
//    1. -[AppDelegate isVip] 恒 YES，-[AppDelegate setIsVip:] 丢弃 NO
//    2. -[AppDelegate vipType] 恒返回最高档；setter 忽略
//    3. NSUserDefaults / MMKV 里任何含 VIP 语义的 key 读取一律 YES
//  另外挂调试日志，方便确认命中点。
//

#import <Foundation/Foundation.h>
#import <objc/runtime.h>
#import <objc/message.h>

#define TAG @"[TINGVIP]"

static IMP orig_isVip = NULL;
static IMP orig_setIsVip = NULL;
static IMP orig_vipType = NULL;
static IMP orig_boolForKey = NULL;
static IMP orig_objectForKey = NULL;

#pragma mark - AppDelegate hooks

static BOOL rep_isVip(id self, SEL _cmd) {
    return YES;
}

static void rep_setIsVip(id self, SEL _cmd, BOOL v) {
    // 忽略任何写入，保持 YES
    if (orig_setIsVip) { /* 不转发 */ }
}

static int rep_vipType(id self, SEL _cmd) {
    return 3;   // 最高档
}

static void rep_setVipType(id self, SEL _cmd, int v) {
    // 忽略
}

#pragma mark - NSUserDefaults hooks

static BOOL keyLooksVip(NSString *key) {
    if (![key isKindOfClass:[NSString class]]) return NO;
    NSString *u = [key uppercaseString];
    return [u containsString:@"VIP"] || [u containsString:@"PREMIUM"] || [u containsString:@"MEMBER"];
}

static BOOL rep_boolForKey(id self, SEL _cmd, NSString *key) {
    if (keyLooksVip(key)) {
        NSLog(@"%@ NSUserDefaults boolForKey:%@ -> YES", TAG, key);
        return YES;
    }
    return ((BOOL(*)(id, SEL, NSString *))orig_boolForKey)(self, _cmd, key);
}

static id rep_objectForKey(id self, SEL _cmd, NSString *key) {
    if ([key isEqualToString:@"KEY_CURRENT_IS_VIP_STATUS"]) {
        NSLog(@"%@ NSUserDefaults objectForKey:%@ -> @YES", TAG, key);
        return @YES;
    }
    return ((id(*)(id, SEL, NSString *))orig_objectForKey)(self, _cmd, key);
}


#pragma mark - 通用 VIP 语义 BOOL 方法扫描（UserInfo / AppDelegate 等）

static BOOL selIsVipSemantic(SEL sel) {
    NSString *n = [NSStringFromSelector(sel) lowercaseString];
    return [n containsString:@"vip"] || [n containsString:@"premium"] ||
           [n containsString:@"member"] || [n containsString:@"subscribe"];
}

/// 在类上把所有「VIP 语义 + 返回 BOOL」的实例方法改成恒 YES
static int hookVipBoolMethods(Class cls, const char *why) {
    if (!cls) return 0;
    unsigned int count = 0;
    Method *ms = class_copyMethodList(cls, &count);
    if (!ms) return 0;
    int n = 0;
    for (unsigned int i = 0; i < count; i++) {
        SEL sel = method_getName(ms[i]);
        const char *ret = method_copyReturnType(ms[i]);
        BOOL isBool = ret && (strcmp(ret, "B") == 0 || strcmp(ret, "c") == 0);
        free((void *)ret);
        if (!isBool) continue;
        if (!selIsVipSemantic(sel)) continue;
        method_setImplementation(ms[i], (IMP)rep_isVip);
        NSLog(@"%@ hooked -[%s %@] -> YES (%s)", TAG, class_getName(cls),
              NSStringFromSelector(sel), why);
        n++;
    }
    free(ms);
    return n;
}

static int hookVipBoolClassMethods(Class cls, const char *why) {
    if (!cls) return 0;
    Class meta = object_getClass(cls);
    unsigned int count = 0;
    Method *ms = class_copyMethodList(meta, &count);
    if (!ms) return 0;
    int n = 0;
    for (unsigned int i = 0; i < count; i++) {
        SEL sel = method_getName(ms[i]);
        const char *ret = method_copyReturnType(ms[i]);
        BOOL isBool = ret && (strcmp(ret, "B") == 0 || strcmp(ret, "c") == 0);
        free((void *)ret);
        if (!isBool) continue;
        if (!selIsVipSemantic(sel)) continue;
        method_setImplementation(ms[i], (IMP)rep_isVip);
        NSLog(@"%@ hooked +[%s %@] -> YES (%s)", TAG, class_getName(cls),
              NSStringFromSelector(sel), why);
        n++;
    }
    free(ms);
    return n;
}

#pragma mark - 安装

static void installHooks(void) {
    Class appDel = objc_getClass("AppDelegate");
    if (!appDel) {
        NSLog(@"%@ AppDelegate not found", TAG);
        return;
    }

    // isVip getter
    SEL sIsVip = sel_registerName("isVip");
    Method m = class_getInstanceMethod(appDel, sIsVip);
    if (m) {
        orig_isVip = method_setImplementation(m, (IMP)rep_isVip);
        NSLog(@"%@ hooked -[AppDelegate isVip] -> YES", TAG);
    } else {
        // 属性存在但 getter 未 find -> 补一个
        class_addMethod(appDel, sIsVip, (IMP)rep_isVip, "B@:");
        NSLog(@"%@ added -[AppDelegate isVip] -> YES", TAG);
    }

    SEL sSetIsVip = sel_registerName("setIsVip:");
    Method ms = class_getInstanceMethod(appDel, sSetIsVip);
    if (ms) {
        orig_setIsVip = method_setImplementation(ms, (IMP)rep_setIsVip);
        NSLog(@"%@ hooked -[AppDelegate setIsVip:] (no-op)", TAG);
    }

    SEL sVipType = sel_registerName("vipType");
    Method mt = class_getInstanceMethod(appDel, sVipType);
    if (mt) {
        orig_vipType = method_setImplementation(mt, (IMP)rep_vipType);
        NSLog(@"%@ hooked -[AppDelegate vipType] -> 3", TAG);
    }

    SEL sSetVipType = sel_registerName("setVipType:");
    Method mst = class_getInstanceMethod(appDel, sSetVipType);
    if (mst) {
        method_setImplementation(mst, (IMP)rep_setVipType);
    }

    // NSUserDefaults
    Class ud = objc_getClass("NSUserDefaults");
    if (ud) {
        Method bf = class_getInstanceMethod(ud, sel_registerName("boolForKey:"));
        if (bf) {
            orig_boolForKey = method_setImplementation(bf, (IMP)rep_boolForKey);
            NSLog(@"%@ hooked -[NSUserDefaults boolForKey:]", TAG);
        }
        Method of = class_getInstanceMethod(ud, sel_registerName("objectForKey:"));
        if (of) {
            orig_objectForKey = method_setImplementation(of, (IMP)rep_objectForKey);
            NSLog(@"%@ hooked -[NSUserDefaults objectForKey:]", TAG);
        }
    }

    // UserInfo 单例（IDA 证据：+[UserInfo sharedUserInfo]）—— 可能是 VIP 数值的真正来源
    Class ui = objc_getClass("UserInfo");
    if (ui) {
        int a = hookVipBoolMethods(ui, "UserInfo");
        int b = hookVipBoolClassMethods(ui, "UserInfo");
        NSLog(@"%@ UserInfo scanned: inst=%d cls=%d", TAG, a, b);
    } else {
        NSLog(@"%@ UserInfo class not found", TAG);
    }

    // AppDelegate 自身也扫一遍（除已 hook 的 isVip / vipType）
    int c = hookVipBoolMethods(appDel, "AppDelegate");

    NSLog(@"%@ hooks installed on %@ (appDelegate=%d)", TAG,
          [[NSBundle mainBundle] bundleIdentifier] ?: @"?", c);
}

__attribute__((constructor))
static void TingDeVIPInit(void) {
    @autoreleasepool {
        NSString *bid = [[NSBundle mainBundle] bundleIdentifier] ?: @"";
        if (![bid isEqualToString:@"com.eusoft.ting-de"]) {
            return;
        }
        NSLog(@"%@ loaded into %@", TAG, bid);
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.5 * NSEC_PER_SEC)),
                       dispatch_get_main_queue(), ^{
            installHooks();
        });
    }
}
