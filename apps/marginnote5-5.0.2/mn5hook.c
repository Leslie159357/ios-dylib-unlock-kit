// mn5hook3.c — MarginNote 5.0.2: entitlement unlock + custom AI bootstrap.
// v3: no iCloudSyncManager hooks at all (they stalled the launch spinner).
// AI injection fires on the first -[MNEntitlementResolver currentSnapshot].

typedef struct objc_class *Class;
typedef struct objc_object { Class isa; } *id;
typedef struct objc_selector *SEL;
typedef struct objc_method *Method;
typedef void (*IMP)(void);

extern id objc_getClass(const char *name);
extern SEL sel_registerName(const char *name);
extern const char *sel_getName(SEL sel);
extern Class object_getClass(id obj);
extern Method *class_copyMethodList(Class cls, unsigned int *outCount);
extern IMP method_getImplementation(Method m);
extern IMP method_setImplementation(Method m, IMP imp);
extern SEL method_getName(Method m);
extern id objc_msgSend(id self, SEL op, ...);
extern void free(void *p);
extern char *getenv(const char *name);
extern int open(const char *path, int flags, ...);
extern long write(int fd, const void *buf, unsigned long n);
extern void close(int fd);

#define O_WRONLY 1
#define O_CREAT  0x200
#define O_APPEND 0x8

#define AI_BASEURL "https://dl.1122275.xyz/probe/mn/a104be5a5973/v1"
#define AI_KEY     "cpa"
#define AI_MINI    "deepseek-v4.1-flash"
#define AI_NORMAL  "deepseek-v4.1-flash-eco"

static char logpath[512];
static unsigned long slen(const char *s) { unsigned long n = 0; while (s[n]) n++; return n; }
static int seq(const char *a, const char *b) { while (*a && *b && *a == *b) { a++; b++; } return *a == *b; }
static int swith(const char *s, const char *p) { while (*p) { if (*s != *p) return 0; s++; p++; } return 1; }

static void init_logpath(void) {
    char *home = getenv("HOME");
    if (!home) return;
    unsigned long i = 0;
    while (home[i] && i < 400) { logpath[i] = home[i]; i++; }
    const char *tail = "/Documents/mn5hook.log";
    unsigned long j = 0;
    while (tail[j]) { logpath[i++] = tail[j++]; }
    logpath[i] = 0;
}
static void logline(const char *s) {
    if (!logpath[0]) init_logpath();
    if (!logpath[0]) return;
    int fd = open(logpath, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return;
    write(fd, s, slen(s)); write(fd, "\n", 1); close(fd);
}

// ---- hooks ----
static long long h_tier(id self, SEL _cmd) { (void)self; (void)_cmd; return 2; }
static char h_true(id self, SEL _cmd) { (void)self; (void)_cmd; return 1; }
static long long h_zero(id self, SEL _cmd) { (void)self; (void)_cmd; return 0; }
static long long h_big(id self, SEL _cmd) { (void)self; (void)_cmd; return 999999; }
static void h_void(id self, SEL _cmd) { (void)self; (void)_cmd; }
static id h_nil(id self, SEL _cmd) { (void)self; (void)_cmd; return (id)0; }

static id mkstr(const char *s) {
    id ns = objc_getClass("NSString");
    if (!ns) return (id)0;
    SEL sel = sel_registerName("stringWithUTF8String:");
    id (*f)(id, SEL, const char *) = (id (*)(id, SEL, const char *))objc_msgSend;
    return f(ns, sel, s);
}
static id h_far_date(id self, SEL _cmd) {
    (void)self; (void)_cmd;
    id cls = objc_getClass("NSDate");
    if (!cls) return (id)0;
    SEL s = sel_registerName("dateWithTimeIntervalSince1970:");
    id (*f)(id, SEL, double) = (id (*)(id, SEL, double))objc_msgSend;
    return f(cls, s, 4102444800.0);
}
typedef struct { void *isa; int flags; int reserved; void *invoke; } BLK;
static void h_testpending(id self, SEL _cmd, BLK *blk) {
    (void)self; (void)_cmd;
    if (blk && blk->invoke) ((void (*)(BLK *, int, id))blk->invoke)(blk, 1, (id)0);
}
static id h_key(id self, SEL _cmd) { (void)self; (void)_cmd; return mkstr(AI_KEY); }

// ---- lookup ----
static int hook_count, miss_count;
static Method find_method(Class cls, const char *name, int prefix_ok) {
    unsigned int n = 0, i;
    Method *list = class_copyMethodList(cls, &n);
    Method exact = 0, pref = 0;
    if (!list) return 0;
    for (i = 0; i < n; i++) {
        const char *sn = sel_getName(method_getName(list[i]));
        if (!sn) continue;
        if (seq(sn, name)) { exact = list[i]; break; }
        if (prefix_ok && swith(sn, name)) {
            if (!pref || slen(sn) < slen(sel_getName(method_getName(pref)))) pref = list[i];
        }
    }
    free(list);
    return exact ? exact : pref;
}
static void log_hook(const char *kind, const char *cls, const char *sel, int ok) {
    char buf[256]; int i = 0;
    buf[i++] = '['; buf[i++] = ok ? 'o' : 'x'; buf[i++] = ']'; buf[i++] = ' ';
    for (int j = 0; kind[j] && i < 250; j++) buf[i++] = kind[j];
    for (int j = 0; cls[j] && i < 250; j++) buf[i++] = cls[j];
    buf[i++] = ' '; buf[i++] = '-'; buf[i++] = '[';
    for (int j = 0; sel[j] && i < 250; j++) buf[i++] = sel[j];
    buf[i++] = ']'; buf[i] = 0;
    logline(buf);
}
static IMP hook_any(const char *clsname, const char *selname, int prefix_ok, int is_class, IMP imp) {
    id cls = objc_getClass(clsname);
    id holder;
    if (!cls) { log_hook("!! class missing ", clsname, selname, 0); miss_count++; return 0; }
    holder = is_class ? (id)object_getClass(cls) : cls;
    Method m = find_method((Class)holder, selname, prefix_ok);
    if (!m) { log_hook("!! method missing ", clsname, selname, 0); miss_count++; return 0; }
    IMP old = method_getImplementation(m);
    method_setImplementation(m, imp);
    log_hook("hook ", clsname, selname, 1);
    hook_count++;
    return old;
}
#define IH(c, s, imp) hook_any(c, s, 0, 0, (IMP)imp)
#define IP(c, s, imp) hook_any(c, s, 1, 0, (IMP)imp)
#define CH(c, s, imp) hook_any(c, s, 0, 1, (IMP)imp)
#define CP(c, s, imp) hook_any(c, s, 1, 1, (IMP)imp)

// ---- AI bootstrap ----
static void inject_ai(void) {
    static int done = 0;
    if (done) return;
    done = 1;
    id aisp = objc_getClass("AIServiceProvider");
    if (!aisp) { logline("!! AIServiceProvider missing"); return; }
    Class mc = object_getClass(aisp);
    Method msave = find_method(mc, "savePendingCustomAIBaseURL", 1);
    Method mbind = find_method(mc, "bindPendingCustomAIProfileAfterSuccessfulTest", 1);
    if (!msave || !mbind) { logline("!! AI save/bind missing"); return; }
    id u = mkstr(AI_BASEURL), k = mkstr(AI_KEY), m1 = mkstr(AI_MINI), m2 = mkstr(AI_NORMAL);
    IMP fsave = method_getImplementation(msave);
    ((void (*)(id, SEL, id, id, id, id))fsave)(aisp, method_getName(msave), u, k, m1, m2);
    logline("ai savePending done");
    IMP fbind = method_getImplementation(mbind);
    char ok = ((char (*)(id, SEL))fbind)(aisp, method_getName(mbind));
    logline(ok ? "ai bind ok" : "ai bind returned 0");
}

static void inject_ai(void);
static char h_prod(id self, SEL _cmd) { (void)self; (void)_cmd; inject_ai(); return 1; }

static IMP orig_snapshot = 0;
static id h_snapshot(id self, SEL _cmd) {
    inject_ai();
    if (!orig_snapshot) return (id)0;
    return ((id (*)(id, SEL))orig_snapshot)(self, _cmd);
}

__attribute__((constructor)) static void mn5_init(void) {
    init_logpath();
    logline("=== mn5hook v7 5.0.2 load ===");

    IH("MNEntitlementSnapshot", "tier", h_tier);
    IH("MNEntitlementSnapshot", "receiptValid", h_true);
    IH("MNEntitlementSnapshot", "hasProLifetime", h_true);
    IH("MNEntitlementSnapshot", "hasMaxLifetime", h_true);
    IH("MNEntitlementSnapshot", "hasActiveFullMaxSubscription", h_true);
    IH("MNEntitlementSnapshot", "hasActiveLegacyMaxUpgradeSubscription", h_true);
    IH("MNEntitlementSnapshot", "hasLegacyMaxUpgradeLifetime", h_true);
    IH("MNEntitlementSnapshot", "hasSharedPremiumMax", h_true);
    IH("MNEntitlementSnapshot", "hasAnyActiveMax", h_true);
    IH("MNEntitlementSnapshot", "maxExpirationDate", h_far_date);
    IH("MNEntitlementSnapshot", "sharedMaxExpirationDate", h_far_date);

    IH("AppDelegate_iPad", "isValidOCRPro", h_true);
    IH("AppDelegate_iPad", "isValidOCRProInternal:", h_true);
    IP("AppDelegate_iPad", "isValidOCRProInternal:excludeTrial", h_true);
    IH("AppDelegate_iPad", "isValidProduct", h_prod);
    IH("AppDelegate_iPad", "isValidPremiumConnect", h_true);

    IP("RMStoreUserDefaultsPersistence", "isPurchasedProductOfIdentifier", h_true);
    IP("RMStoreKeychainPersistence", "isPurchasedProductOfIdentifier", h_true);

    IH("MBCreditManager", "currentCredit0", h_zero);
    IH("MBCreditManager", "currentCredit1", h_zero);
    IH("MBCreditManager", "maxCredit0", h_big);
    IH("MBCreditManager", "maxCredit1", h_big);
    IH("MBCreditManager", "remainingCredit0", h_big);
    IH("MBCreditManager", "remainingCredit1", h_big);
    IP("MBCreditManager", "hasEnoughCredit0", h_true);
    IP("MBCreditManager", "hasEnoughCredit1", h_true);

    CH("AIServiceProvider", "hasCustomAIMaxEntitlement", h_true);
    CP("AIServiceProvider", "customAIActiveAPIKeyMatchesBoundProfile", h_true);
    CP("AIServiceProvider", "customAIInternalKeyValidationResultForAPIKey", h_zero);
    CP("AIServiceProvider", "setCustomAIKeychainPassword", h_true);
    CP("AIServiceProvider", "customAIKeychainPasswordForAccount", h_key);
    CP("AIServiceProvider", "testPendingCustomAIProfileWithCompletion", h_testpending);

    IH("AppDelegate_iPad", "refreshAIModelRoutingFromCloudKitIfNeeded", h_void);
    // CloudKit-backed config fetches (5.0.2 新增): 启动后定时触发，内部直接建 CKContainer 会抛 CKException
    IP("iCloudSyncManager", "fetchServiceKeys", h_void);
    IP("iCloudSyncManager", "fetchServiceKeysInternal", h_void);
    IP("iCloudSyncManager", "fetchModelRoutingConfig", h_void);
    IP("iCloudSyncManager", "forceFetchModelRoutingConfig", h_void);
    IP("iCloudSyncManager", "fetchModelRoutingConfigInternal", h_void);
    // addon certification 也是 CloudKit 拉取（5.0.2 新增），按同一方式掐掉
    IP("iCloudSyncManager", "fetchAddonCertifications", h_void);
    IP("iCloudSyncManager", "forceFetchAddonCertifications", h_void);
    IP("iCloudSyncManager", "mn_fetchAddonCertificationPage", h_void);
    // 根上掐断：实例级 CloudKit 全部走 iCloudSyncManager 实例，
    // init 返回 nil 后所有 [sharedInstance ...] 都是空消息（5.0.0 已验证该做法可正常启动）
    IH("iCloudSyncManager", "init", h_nil);
    orig_snapshot = hook_any("MNEntitlementResolver", "currentSnapshot", 0, 1, (IMP)h_snapshot);

    logline(miss_count ? "=== loaded, some hooks missing ===" : "=== loaded, all hooks ok ===");
}
