// Pigment (com.pixite.pigment) 3.16 premium unlock — v2
// v1 崩溃定位：worker 里第一次 objc_msgSend/NSString 调用就 PAC 认证失败
//   (EXC_BAD_ACCESS in +[NSString stringWithUTF8String:] <- PigmentUnlock.dylib worker)
// 本版铁律：dylib 内零 objc_msgSend、零 Foundation 调用；
//   写偏好只用 CoreFoundation；返回日期用 toll-free bridged CFDate。
//
// 判定链：
//   -[SubscriptionManager latestPremiumExpirationDate] > now  => checkIsPremium 走 premium 分支
//   RevenueCatSubscriptionHelper.isPremiumAccess 是 UI/内容侧的统一读取口
typedef unsigned long pthread_t;
extern int pthread_create(pthread_t *t, const void *attr, void *(*fn)(void *), void *arg);
extern int pthread_detach(pthread_t t);
extern int usleep(unsigned int us);

typedef struct objc_object *id;
typedef struct objc_selector *SEL;
typedef struct objc_class *Class;
typedef struct objc_method *Method;
typedef void *IMP;

extern Class objc_getClass(const char *name);
extern int objc_getClassList(Class *buffer, int count);
extern const char *class_getName(Class cls);
extern SEL sel_registerName(const char *str);
extern Method class_getInstanceMethod(Class cls, SEL name);
extern IMP method_setImplementation(Method m, IMP imp);

typedef const struct __CFString *CFStringRef;
typedef const struct __CFDate *CFDateRef;
typedef const void *CFTypeRef;
typedef void *CFAllocatorRef;

extern void *CFBundleGetMainBundle(void);
extern CFStringRef CFBundleGetIdentifier(void *bundle);
extern CFDateRef CFDateCreate(CFAllocatorRef alloc, double at);
extern double CFAbsoluteTimeGetCurrent(void);
extern void CFPreferencesSetAppValue(CFStringRef key, CFTypeRef value, CFStringRef appID);
extern int CFPreferencesAppSynchronize(CFStringRef appID);

#define CFSTR(s) ((CFStringRef)__builtin___CFStringMakeConstantString(s))

static char ret_yes(id self, SEL _cmd) { (void)self; (void)_cmd; return 1; }

// +10 年；CFDate 与 NSDate toll-free bridged，调用方当成 NSDate 用没问题
static double far_abs_time(void) { return CFAbsoluteTimeGetCurrent() + 315360000.0; }
static id ret_far_date(id self, SEL _cmd) {
  (void)self; (void)_cmd;
  return (id)CFDateCreate(0, far_abs_time());
}

static void hook_method(Class cls, const char *sel_name, IMP imp) {
  if (!cls) return;
  Method m = class_getInstanceMethod(cls, sel_registerName(sel_name));
  if (m) method_setImplementation(m, imp);
}

static int name_has(const char *hay, const char *needle) {
  if (!hay || !needle) return 0;
  for (const char *p = hay; *p; p++) {
    const char *a = p, *b = needle;
    while (*a && *b && *a == *b) { a++; b++; }
    if (!*b) return 1;
  }
  return 0;
}

// 订阅态类才敢改 isPremium；Book/Page/ASMPalette 上的 isPremium 是“此内容需付费”，
// 置真会把免费内容锁上。
static const char *STATE_SELECTORS[] = {
  "isPremium", "isPremiumAccess", "isPremiumUser", "hasPremiumAccess",
  "isPremiumMember", "hasActiveSubscription", "isSubscribed", 0
};
// 这两个语义唯一（当前用户是否订阅），对任何类都安全
static const char *SAFE_SELECTORS[] = { "isPremiumAccess", "hasPremiumAccess", 0 };
static const char *STATE_CLASS_HINTS[] = {
  "Subscription", "Subscribe", "Purchase", "UserManager",
  "UserImpl", "Profile", "Account", "Session", "StoreKit", "PremiumChecker", 0
};

static void apply_hooks(void) {
  Class sm = objc_getClass("SubscriptionManager");
  if (sm) {
    // 让 checkIsPremium 自己算出 premium：它读 latestPremiumExpirationDate 比当前时间
    hook_method(sm, "latestPremiumExpirationDate", (IMP)ret_far_date);
    hook_method(sm, "isPremium", (IMP)ret_yes);
    hook_method(sm, "isGrandfatheredPremiumStatus", (IMP)ret_yes);
  }

  int count = objc_getClassList(0, 0);
  if (count <= 0) return;
  Class *classes = (Class *)__builtin_alloca(sizeof(Class) * (unsigned long)count);
  count = objc_getClassList(classes, count);
  for (int i = 0; i < count; i++) {
    Class c = classes[i];
    const char *cn = class_getName(c);
    int interesting = 0;
    for (int k = 0; STATE_CLASS_HINTS[k]; k++) {
      if (name_has(cn, STATE_CLASS_HINTS[k])) { interesting = 1; break; }
    }
    if (interesting) {
      hook_method(c, "latestPremiumExpirationDate", (IMP)ret_far_date);
      for (int k = 0; STATE_SELECTORS[k]; k++) {
        Method m = class_getInstanceMethod(c, sel_registerName(STATE_SELECTORS[k]));
        if (m) method_setImplementation(m, (IMP)ret_yes);
      }
    }
    for (int k = 0; SAFE_SELECTORS[k]; k++) {
      Method m = class_getInstanceMethod(c, sel_registerName(SAFE_SELECTORS[k]));
      if (m) method_setImplementation(m, (IMP)ret_yes);
    }
  }
}

// 纯 CF 写偏好：constructor 之后由独立线程延迟执行，等 cfprefsd 通道就绪
static void seed_premium_dates(void) {
  CFStringRef appid = CFBundleGetIdentifier(CFBundleGetMainBundle());
  if (!appid) return;
  CFDateRef far = CFDateCreate(0, far_abs_time());
  if (!far) return;
  CFPreferencesSetAppValue(CFSTR("premium_expiration_date"), (CFTypeRef)far, appid);
  CFPreferencesSetAppValue(CFSTR("pig_premium_expiration_date"), (CFTypeRef)far, appid);
  CFPreferencesAppSynchronize(appid);
}

static void *worker(void *arg) {
  (void)arg;
  usleep(2000000);
  seed_premium_dates();
  return 0;
}

__attribute__((constructor)) static void pigment_unlock_init(void) {
  apply_hooks();
  pthread_t t;
  if (pthread_create(&t, 0, worker, 0) == 0) pthread_detach(t);
}
