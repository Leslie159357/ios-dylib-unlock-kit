/*
 * doka_unlock.c — Doka相机 (com.ydgn.dokacamera) 2.2.3 会员解锁件
 * 纯 C / 零 SDK / 弱加载；分层：
 *   ① NSUserDefaults 键值覆盖（VipManager.* 持久化层）
 *   ② VipManager 实例 ivar 直写（内存态：storedHasSubscribed / validatedEntitlementIsVip / storedExpiryDate）
 *   ③ UIViewController.viewWillAppear 节流复写（对抗服务端异步刷新回写 false）
 *   ④ 写拦截：app 把 VIP 键写成 false/0 时，改写成解锁值
 * 边界：端侧滤镜/相机/去水印可解锁；按次云端 AI（App Attest 服务端对账）不保证。
 */
#include <stddef.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdbool.h>

typedef signed char          BOOL_T;
typedef long                 NSINT;
typedef struct objc_object  *id;
typedef struct objc_selector *SEL;
typedef struct objc_class   *Class;
typedef struct objc_method  *Method;
typedef struct objc_ivar    *Ivar;

extern id      objc_getClass(const char *name);
extern SEL     sel_registerName(const char *name);
extern Class   object_getClass(id obj);
extern const char *class_getName(Class c);
extern Class   class_getSuperclass(Class cls);
extern Method  class_getInstanceMethod(Class cls, SEL name);
extern void    method_setImplementation(Method m, void *imp);
extern void   *method_getImplementation(Method m);
extern Ivar    class_getInstanceVariable(Class cls, const char *name);
extern ptrdiff_t ivar_getOffset(Ivar v);
extern int     objc_getClassList(Class *buf, int max);
extern id      objc_msgSend(id self, SEL op, ...);

extern size_t  strlen(const char *s);
extern int     strcmp(const char *a, const char *b);
extern int     strncmp(const char *a, const char *b, size_t n);
extern char   *strstr(const char *h, const char *n);
extern int     tolower(int c);
extern void   *malloc(size_t n);
extern char   *getenv(const char *name);
extern int     snprintf(char *b, size_t n, const char *f, ...);
extern int     vsnprintf(char *b, size_t n, const char *f, va_list ap);
extern void   *fopen(const char *p, const char *m);
extern size_t  fwrite(const void *p, size_t s, size_t n, void *f);
extern int     fclose(void *f);
extern int     open(const char *path, int flags, ...);
extern int     dup2(int oldfd, int newfd);
extern double  time(double *t);

#define O_WRONLY_ 1
#define O_CREAT_  0x200
#define O_APPEND_ 0x8

/* ---------------- 日志 ---------------- */
#define LOG_CAP 4000
static int g_loglines = 0;
static void hlog(const char *fmt, ...) {
    if (g_loglines > LOG_CAP) return;
    char path[512], buf[1024];
    const char *home = getenv("HOME");
    if (!home) return;
    snprintf(path, sizeof(path), "%s/Documents/DokaUnlock.log", home);
    void *f = fopen(path, "a");
    if (!f) return;
    va_list ap; va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    fwrite(buf, 1, strlen(buf), f);
    fwrite("\n", 1, 1, f);
    fclose(f);
    g_loglines++;
}

#define MSG0(o, s)    ((id (*)(id, SEL))objc_msgSend)((id)(o), sel_registerName(s))
#define MSG1(o, s, a) ((id (*)(id, SEL, id))objc_msgSend)((id)(o), sel_registerName(s), (id)(a))
static id cls(const char *n) { return (id)objc_getClass(n); }

/* ---------------- 目标键 ---------------- */
#define FAR_FUTURE 4102444800.0     /* 2100-01-01 */
#define BIG_COUNT  999999

static const char *BOOL_KEYS[] = {
    "VipManager.validatedEntitlementIsVip",
    "VipManager.isVip",
    "VipManager.isVIP",
    "VipManager.isPro",
    "VipManager.hasSyncedIndependentAIFilterCount",
};
static const char *DATE_KEYS[] = {
    "VipManager.expiryDate",
    "VipManager.vipDetail.lastPrefetchAt",
};
static const char *COUNT_KEYS[] = {
    "VipManager.freeUseCount",
    "VipManager.freeAIComposeCount",
    "VipManager.freeAIFilterCount",
    "VipManager.remainingCount",
    "VipManager.aiCount",
    "VipManager.remaining_count",
};
static const char *STR_KEYS[] = {
    NULL, /* v2: 不再伪造 originalTransactionId —— 服务端可能拿它查订单，
             假单号反而被判为异常账号，导致免费 AI 额度不发放 */
};
#define N_ARR(a) ((int)(sizeof(a)/sizeof((a)[0])))

static bool in_list(const char *k, const char **arr, int n) {
    if (!k) return false;
    for (int i = 0; i < n; i++) if (arr[i] && strcmp(k, arr[i]) == 0) return true;
    return false;
}
static bool is_bkey(const char *k) { return in_list(k, BOOL_KEYS, N_ARR(BOOL_KEYS)); }
static bool is_dkey(const char *k) { return in_list(k, DATE_KEYS, N_ARR(DATE_KEYS)); }
static bool is_ckey(const char *k) { return in_list(k, COUNT_KEYS, N_ARR(COUNT_KEYS)); }
static bool is_skey(const char *k) { return in_list(k, STR_KEYS, N_ARR(STR_KEYS)); }

static const char *LOG_KEYS[] = {
    "ai_compose_remaining_count",
    "remaining_compose_count",
    "ai_compose_engine_mode",
    "ai_compose_engine_mode_v1",
};
static bool is_lkey(const char *k) { return in_list(k, LOG_KEYS, N_ARR(LOG_KEYS)); }

static const char *cstr_of(id o) {
    if (!o) return NULL;
    id nsc = cls("NSString");
    if (!nsc) return NULL;
    BOOL_T isStr = ((BOOL_T (*)(id, SEL, id))objc_msgSend)(o, sel_registerName("isKindOfClass:"), nsc);
    if (!isStr) return NULL;
    return ((const char *(*)(id, SEL))objc_msgSend)(o, sel_registerName("UTF8String"));
}
static const char *clsname(id o) { return o ? class_getName(object_getClass(o)) : "nil"; }
static id nsstr(const char *s) {
    return ((id (*)(id, SEL, const char *))objc_msgSend)(cls("NSString"),
             sel_registerName("stringWithUTF8String:"), s);
}
static id future_date(void) {
    return ((id (*)(id, SEL, double))objc_msgSend)(cls("NSDate"),
             sel_registerName("dateWithTimeIntervalSince1970:"), FAR_FUTURE);
}
static id future_num(void) {
    return ((id (*)(id, SEL, double))objc_msgSend)(cls("NSNumber"),
             sel_registerName("numberWithDouble:"), FAR_FUTURE);
}
static id count_num(void) {
    return ((id (*)(id, SEL, long))objc_msgSend)(cls("NSNumber"),
             sel_registerName("numberWithLong:"), (long)BIG_COUNT);
}
static id bool_num(void) {
    return ((id (*)(id, SEL, BOOL_T))objc_msgSend)(cls("NSNumber"),
             sel_registerName("numberWithBool:"), (BOOL_T)1);
}

/* 类型镜像：返回与原值同类别（或合理默认）的伪造值 */
static id forge_obj(const char *k, id orig) {
    if (is_bkey(k)) {
        if (orig && ((BOOL_T (*)(id, SEL, id))objc_msgSend)(orig, sel_registerName("isKindOfClass:"), cls("NSString")))
            return nsstr("1");
        return bool_num();
    }
    if (is_dkey(k)) {
        if (orig && ((BOOL_T (*)(id, SEL, id))objc_msgSend)(orig, sel_registerName("isKindOfClass:"), cls("NSNumber")))
            return future_num();
        if (orig && cstr_of(orig)) return nsstr("2100-01-01T00:00:00Z");
        return future_date();
    }
    if (is_ckey(k)) {
        if (orig && cstr_of(orig)) return nsstr("999999");
        return count_num();
    }
    if (is_skey(k)) {
        return nsstr("2000000000000001");
    }
    return orig;
}

/* ---------------- hook 组 ---------------- */
typedef struct {
    const char *name;
    id      (*obj)(id, SEL, id);
    id      (*str)(id, SEL, id);
    double  (*dbl)(id, SEL, id);
    NSINT   (*itg)(id, SEL, id);
    BOOL_T  (*bl)(id, SEL, id);
    void    (*setobj)(id, SEL, id, id);
} Ops;

static Ops UD;

#define MKHOOKS(TAG, OPS)                                                        \
static id TAG##_obj(id self, SEL _c, id key) {                                   \
    const char *k = cstr_of(key);                                                \
    id orig = OPS.obj ? OPS.obj(self,_c,key) : NULL;                             \
    if (!k) return orig;                                                         \
    if (is_lkey(k)) { hlog("[doka] OBSERVE %s = <%s>", k, clsname(orig)); return orig; } \
    if (is_bkey(k) || is_dkey(k) || is_ckey(k) || is_skey(k)) {                  \
        id r = forge_obj(k, orig);                                               \
        hlog("[doka] %s obj %s: %s -> %s", OPS.name, k, clsname(orig), clsname(r)); \
        return r;                                                                \
    }                                                                            \
    return orig;                                                                 \
}                                                                                \
static id TAG##_str(id self, SEL _c, id key) {                                   \
    const char *k = cstr_of(key);                                                \
    id orig = OPS.str ? OPS.str(self,_c,key) : NULL;                             \
    if (!k) return orig;                                                         \
    if (is_dkey(k)) { hlog("[doka] %s str %s -> ISO", OPS.name, k); return nsstr("2100-01-01T00:00:00Z"); } \
    if (is_skey(k)) { hlog("[doka] %s str %s -> txn", OPS.name, k); return nsstr("2000000000000001"); }     \
    if (is_bkey(k)) { return nsstr("1"); }                                        \
    if (is_ckey(k)) { return nsstr("999999"); }                                   \
    return orig;                                                                 \
}                                                                                \
static double TAG##_dbl(id self, SEL _c, id key) {                               \
    const char *k = cstr_of(key);                                                \
    double orig = OPS.dbl ? OPS.dbl(self,_c,key) : 0.0;                          \
    if (!k) return orig;                                                         \
    if (is_dkey(k)) { hlog("[doka] %s dbl %s -> far", OPS.name, k); return FAR_FUTURE; } \
    if (is_ckey(k)) return (double)BIG_COUNT;                                    \
    if (is_bkey(k)) return 1.0;                                                  \
    return orig;                                                                 \
}                                                                                \
static NSINT TAG##_int(id self, SEL _c, id key) {                                \
    const char *k = cstr_of(key);                                                \
    NSINT orig = OPS.itg ? OPS.itg(self,_c,key) : 0;                             \
    if (!k) return orig;                                                         \
    if (is_ckey(k)) { hlog("[doka] %s int %s -> 999999", OPS.name, k); return (NSINT)BIG_COUNT; } \
    if (is_bkey(k)) return 1;                                                    \
    if (is_dkey(k)) return (NSINT)FAR_FUTURE;                                    \
    return orig;                                                                 \
}                                                                                \
static BOOL_T TAG##_bool(id self, SEL _c, id key) {                              \
    const char *k = cstr_of(key);                                                \
    BOOL_T orig = OPS.bl ? OPS.bl(self,_c,key) : (BOOL_T)0;                      \
    if (!k) return orig;                                                         \
    if (is_bkey(k)) { if (!orig) hlog("[doka] %s bool %s 0->1", OPS.name, k); return (BOOL_T)1; } \
    if (is_ckey(k)) return (BOOL_T)1;                                            \
    return orig;                                                                 \
}                                                                                \
static void TAG##_set(id self, SEL _c, id v, id key) {                           \
    const char *k = cstr_of(key);                                                \
    if (k) {                                                                     \
        if (is_bkey(k) || is_dkey(k) || is_ckey(k) || is_skey(k)) {               \
            id fv = forge_obj(k, v);                                             \
            hlog("[doka] %s WRITE %s (%s) -> forced (%s)", OPS.name, k, clsname(v), clsname(fv)); \
            if (OPS.setobj) OPS.setobj(self, _c, fv, key);                        \
            return;                                                              \
        }                                                                        \
    }                                                                            \
    if (OPS.setobj) OPS.setobj(self, _c, v, key);                                 \
}

MKHOOKS(ud, UD)

static bool is_subclass(Class c, Class base) {
    for (int i = 0; c && i < 64; i++) { if (c == base) return true; c = class_getSuperclass(c); }
    return false;
}
static void swizzle_tree(const char *baseName, const char **sels, void *const *hooks, int n) {
    Class base = objc_getClass(baseName);
    if (!base) { hlog("[doka] !!! 未找到类 %s", baseName); return; }
    int cnt = objc_getClassList(NULL, 0);
    if (cnt <= 0) cnt = 8000;
    Class *buf = (Class *)malloc((size_t)cnt * sizeof(Class));
    if (!buf) return;
    int got = objc_getClassList(buf, cnt), hits = 0;
    for (int i = 0; i < got; i++) {
        Class c = buf[i];
        if (!c || !is_subclass(c, base)) continue;
        for (int j = 0; j < n; j++) {
            if (!hooks[j]) continue;
            Method m = class_getInstanceMethod(c, sel_registerName(sels[j]));
            if (!m || method_getImplementation(m) == hooks[j]) continue;
            method_setImplementation(m, hooks[j]);
            hits++;
        }
    }
    hlog("[doka] swizzled %s : %d", baseName, hits);
}
static void *grab(Class base, const char *sel) {
    if (!base) return NULL;
    Method m = class_getInstanceMethod(base, sel_registerName(sel));
    return m ? method_getImplementation(m) : NULL;
}

/* ---------------- VipManager 实例 ivar 直写 ---------------- */
static id  g_vip_inst = NULL;
static void force_vip_ivars(id inst) {
    if (!inst) return;
    Class c = object_getClass(inst);
    if (!c) return;
    Ivar iv;
    iv = class_getInstanceVariable(c, "storedHasSubscribed");
    if (iv) { *((BOOL_T *)((char *)inst + ivar_getOffset(iv))) = 1; }
    iv = class_getInstanceVariable(c, "validatedEntitlementIsVip");
    if (iv) { *((BOOL_T *)((char *)inst + ivar_getOffset(iv))) = 1; }
    iv = class_getInstanceVariable(c, "storedExpiryDate");
    if (iv) { *((double *)((char *)inst + ivar_getOffset(iv))) = FAR_FUTURE; }
    iv = class_getInstanceVariable(c, "entitlementRevision");
    if (iv) { *((long *)((char *)inst + ivar_getOffset(iv))) = 999; }
}

static id (*o_vipinit)(id, SEL);
static id hk_vipinit(id self, SEL _c) {
    id r = o_vipinit ? o_vipinit(self, _c) : self;
    g_vip_inst = self;
    force_vip_ivars(self);
    hlog("[doka] VipManager init hooked -> forced ivars");
    return r;
}

/* ---------------- 节流复写（视图出现时） ---------------- */
static double g_last = 0.0;
static void (*o_vwa)(id, SEL, BOOL_T);
static void hk_vwa(id self, SEL _c, BOOL_T anim) {
    if (o_vwa) o_vwa(self, _c, anim);
    double now = time(NULL);
    if (now - g_last < 3.0) return;
    g_last = now;
    force_vip_ivars(g_vip_inst);
    /* 同步把持久层写回解锁值 */
    id sud = MSG0(cls("NSUserDefaults"), "standardUserDefaults");
    if (sud && UD.setobj) {
        Ops *o = &UD;
        o->setobj(sud, sel_registerName("setObject:forKey:"), bool_num(),   nsstr("VipManager.validatedEntitlementIsVip"));
        o->setobj(sud, sel_registerName("setObject:forKey:"), future_date(), nsstr("VipManager.expiryDate"));
    }
}

__attribute__((constructor))
static void doka_init(void) {
    const char *home = getenv("HOME");
    if (home) {
        char ap[512];
        snprintf(ap, sizeof(ap), "%s/Documents/DokaApp.log", home);
        int fd = open(ap, O_WRONLY_|O_CREAT_|O_APPEND_, 0644);
        if (fd >= 0) { dup2(fd, 1); dup2(fd, 2); }
    }
    hlog("======== Doka unlock loaded (v1) ========");

    Class cud = objc_getClass("NSUserDefaults");
    UD.name = "NSUserDefaults";
    UD.obj = (id (*)(id,SEL,id))grab(cud,"objectForKey:");
    UD.str = (id (*)(id,SEL,id))grab(cud,"stringForKey:");
    UD.dbl = (double (*)(id,SEL,id))grab(cud,"doubleForKey:");
    UD.itg = (NSINT (*)(id,SEL,id))grab(cud,"integerForKey:");
    UD.bl  = (BOOL_T (*)(id,SEL,id))grab(cud,"boolForKey:");
    UD.setobj = (void (*)(id,SEL,id,id))grab(cud,"setObject:forKey:");
    if (UD.setobj == NULL) UD.setobj = (void (*)(id,SEL,id,id))grab(cud,"setObject:forKeyedSubscript:");
    hlog("[doka] origs UD obj=%d str=%d bool=%d set=%d", UD.obj!=NULL, UD.str!=NULL, UD.bl!=NULL, UD.setobj!=NULL);

    /* 启动即把持久层写为解锁态（先写，再装读 hook） */
    id sud = MSG0(cls("NSUserDefaults"), "standardUserDefaults");
    if (sud && UD.obj) {
        const char *probe[] = {"VipManager.validatedEntitlementIsVip","VipManager.expiryDate",
                               "VipManager.freeUseCount","VipManager.freeAIComposeCount",
                               "VipManager.freeAIFilterCount","VipManager.originalTransactionId",
                               "VipManager.vipDetailCache"};
        for (int i = 0; i < N_ARR(probe); i++) {
            id v = UD.obj(sud, sel_registerName("objectForKey:"), nsstr(probe[i]));
            hlog("[doka] SNAPSHOT %s = <%s>", probe[i], clsname(v));
        }
    }
    if (sud && UD.setobj) {
        UD.setobj(sud, sel_registerName("setObject:forKey:"), bool_num(), nsstr("VipManager.validatedEntitlementIsVip"));
        UD.setobj(sud, sel_registerName("setObject:forKey:"), future_date(), nsstr("VipManager.expiryDate"));
        UD.setobj(sud, sel_registerName("setObject:forKey:"), count_num(), nsstr("VipManager.freeUseCount"));
        UD.setobj(sud, sel_registerName("setObject:forKey:"), count_num(), nsstr("VipManager.freeAIComposeCount"));
        UD.setobj(sud, sel_registerName("setObject:forKey:"), count_num(), nsstr("VipManager.freeAIFilterCount"));
        hlog("[doka] primed defaults");
    }

    const char *sels[] = {"objectForKey:","stringForKey:","doubleForKey:","integerForKey:","boolForKey:",
                          "setObject:forKey:","objectForKeyedSubscript:","setObject:forKeyedSubscript:"};
    void *h_ud[] = {(void*)ud_obj,(void*)ud_str,(void*)ud_dbl,(void*)ud_int,(void*)ud_bool,
                    (void*)ud_set,(void*)ud_obj,(void*)ud_set};
    swizzle_tree("NSUserDefaults", sels, h_ud, 8);

    /* VipManager init 接管 */
    Class vc = objc_getClass("Follow.VipManager");
    if (!vc) vc = objc_getClass("_TtC6Follow10VipManager");
    if (vc) {
        Method m = class_getInstanceMethod(vc, sel_registerName("init"));
        if (m) {
            o_vipinit = (id (*)(id, SEL))method_getImplementation(m);
            method_setImplementation(m, (void*)hk_vipinit);
            hlog("[doka] VipManager init swizzled");
        } else hlog("[doka] VipManager init not found");
        /* 已有实例兜底：仅记录 ivar 布局 */
        hlog("[doka] ivar storedHasSubscribed=%d validated=%d expiry=%d",
             class_getInstanceVariable(vc,"storedHasSubscribed")!=NULL,
             class_getInstanceVariable(vc,"validatedEntitlementIsVip")!=NULL,
             class_getInstanceVariable(vc,"storedExpiryDate")!=NULL);
    } else hlog("[doka] !!! VipManager class not found");

    /* 视图出现节流复写 */
    Class uvc = objc_getClass("UIViewController");
    if (uvc) {
        Method m = class_getInstanceMethod(uvc, sel_registerName("viewWillAppear:"));
        if (m) {
            o_vwa = (void (*)(id, SEL, BOOL_T))method_getImplementation(m);
            method_setImplementation(m, (void*)hk_vwa);
            hlog("[doka] viewWillAppear guard on");
        }
    }
    hlog("======== Doka unlock ready ========");
}
