// ScriptingGroupFix.dylib — v3 (arm64 / iOS 17+)
//
// 两个修复：
//  A. App Group 容器缺失：swizzle -[NSFileManager containerURLForSecurityApplicationGroupIdentifier:]
//     在自身沙盒 Library/Group Containers/<group>/ 下建目录并返回 URL。
//     （原实现 containerURL 返回 nil，ScriptingKit 里是强制解包 → SIGTRAP）
//  B. iCloud 授权缺失：CloudKit 的 +[CKContainer containerWithIdentifier:] 抛 NSException
//     → 主线程 SIGABRT。这里 interpose SecTaskCopyValueForEntitlement，只对 iCloud 相关
//     entitlement key 返回原始值（其余 key 一律透传）。
//
// 注：objc_msgSend 一律走精确原型的函数指针调用；可变参在 Apple arm64 ABI 下压栈传递，
//     用 C 可变参声明会读到垃圾指针（v2 的教训）。

typedef void *id_t;
typedef void *SEL_t;
typedef void *Method_t;

extern id_t objc_getClass(const char *name);
extern SEL_t sel_registerName(const char *name);
extern id_t objc_msgSend(id_t self, SEL_t op, ...);
extern Method_t class_getInstanceMethod(id_t cls, SEL_t name);
extern void *method_setImplementation(Method_t m, void *imp);
extern void *dlsym(void *handle, const char *symbol);
extern const void *SecTaskCopyValueForEntitlement(const void *task, const void *entitlement, const void **error);

#define RTLD_NEXT_HANDLE ((void *)-1)

typedef id_t (*Msg0)(id_t, SEL_t);
typedef id_t (*Msg1)(id_t, SEL_t, id_t);
typedef id_t (*Msg2)(id_t, SEL_t, id_t, id_t);
typedef id_t (*Msg4)(id_t, SEL_t, id_t, id_t, id_t, id_t);

static inline id_t MSG0(id_t o, SEL_t s) { return ((Msg0)(void *)objc_msgSend)(o, s); }
static inline id_t MSG1(id_t o, SEL_t s, id_t a) { return ((Msg1)(void *)objc_msgSend)(o, s, a); }
static inline id_t MSG2(id_t o, SEL_t s, id_t a, id_t b) { return ((Msg2)(void *)objc_msgSend)(o, s, a, b); }
static inline id_t MSG4(id_t o, SEL_t s, id_t a, id_t b, id_t c, id_t d) {
    return ((Msg4)(void *)objc_msgSend)(o, s, a, b, c, d);
}

static int streq(const char *a, const char *b) {
    if (!a || !b) return 0;
    while (*a && *a == *b) { a++; b++; }
    return *a == *b;
}

static id_t nsstr(const char *utf8) {
    id_t cls = objc_getClass("NSString");
    if (!cls) return 0;
    return MSG1(cls, sel_registerName("stringWithUTF8String:"), (id_t)utf8);
}

// ---------------------------------------------------------------- A. app group

static id_t (*orig_container)(id_t, SEL_t, id_t);

static void ensure_dir(id_t path) {
    if (!path) return;
    id_t fm = MSG0(objc_getClass("NSFileManager"), sel_registerName("defaultManager"));
    if (!fm) return;
    MSG4(fm,
         sel_registerName("createDirectoryAtPath:withIntermediateDirectories:attributes:error:"),
         path, (id_t)1, (id_t)0, (id_t)0);
}

static id_t append_component(id_t base, id_t component) {
    if (!base || !component) return 0;
    return MSG1(base, sel_registerName("stringByAppendingPathComponent:"), component);
}

static id_t group_container(id_t self, SEL_t cmd, id_t group) {
    if (!group) {
        return orig_container ? orig_container(self, cmd, group) : 0;
    }
    const char *gname = (const char *)MSG0(group, sel_registerName("UTF8String"));
    if (!gname) {
        return orig_container ? orig_container(self, cmd, group) : 0;
    }

    id_t env = MSG0(MSG0(objc_getClass("NSProcessInfo"), sel_registerName("processInfo")),
                    sel_registerName("environment"));
    id_t home = env ? MSG1(env, sel_registerName("objectForKey:"), nsstr("HOME")) : 0;
    if (!home) {
        return orig_container ? orig_container(self, cmd, group) : 0;
    }

    id_t path = append_component(home, nsstr("Library"));
    path = append_component(path, nsstr("Group Containers"));
    path = append_component(path, nsstr(gname));
    if (!path) {
        return orig_container ? orig_container(self, cmd, group) : 0;
    }

    ensure_dir(path);
    ensure_dir(append_component(path, nsstr("Documents")));
    id_t lib = append_component(path, nsstr("Library"));
    ensure_dir(lib);
    ensure_dir(append_component(lib, nsstr("Caches")));

    id_t url = MSG2(objc_getClass("NSURL"),
                    sel_registerName("fileURLWithPath:isDirectory:"),
                    path, (id_t)1);
    if (url) {
        return url;
    }
    return orig_container ? orig_container(self, cmd, group) : 0;
}

// ------------------------------------------------- B. iCloud entitlement 兜底

static const void *(*real_stcvfe)(const void *, const void *, const void **);

static const void *cf_owned(id_t obj) {
    if (!obj) return 0;
    return (const void *)MSG0(obj, sel_registerName("retain"));
}

static const void *spoof(const char *key) {
    if (streq(key, "com.apple.developer.icloud-container-identifiers") ||
        streq(key, "com.apple.developer.ubiquity-container-identifiers")) {
        id_t arr = objc_getClass("NSArray");
        return cf_owned(MSG1(arr, sel_registerName("arrayWithObject:"),
                             nsstr("iCloud.com.thomfang.Scripting")));
    }
    if (streq(key, "com.apple.developer.icloud-services")) {
        id_t arr = MSG1(objc_getClass("NSArray"), sel_registerName("arrayWithObject:"),
                        nsstr("CloudKit"));
        return cf_owned(MSG1(arr, sel_registerName("arrayByAddingObject:"),
                             nsstr("CloudDocuments")));
    }
    if (streq(key, "com.apple.developer.icloud-container-environment")) {
        return cf_owned(nsstr("Production"));
    }
    if (streq(key, "com.apple.developer.team-identifier")) {
        return cf_owned(nsstr("58P5F4LJ36"));
    }
    if (streq(key, "application-identifier")) {
        return cf_owned(nsstr("58P5F4LJ36.com.scripting.ios"));
    }
    if (streq(key, "com.apple.developer.ubiquity-kvstore-identifier")) {
        return cf_owned(nsstr("58P5F4LJ36.com.scripting.ios"));
    }
    return 0;
}

static const void *my_stcvfe(const void *task, const void *entitlement, const void **error) {
    if (!real_stcvfe) {
        real_stcvfe = (const void *(*)(const void *, const void *, const void **))
                          dlsym(RTLD_NEXT_HANDLE, "SecTaskCopyValueForEntitlement");
    }
    const char *key = entitlement
                          ? (const char *)MSG0((id_t)entitlement, sel_registerName("UTF8String"))
                          : 0;
    const void *fake = key ? spoof(key) : 0;
    if (fake) {
        return fake;
    }
    return real_stcvfe ? real_stcvfe(task, entitlement, error) : 0;
}

__attribute__((used)) static const struct {
    const void *replacement;
    const void *replacee;
} interpose_entries[] __attribute__((section("__DATA,__interpose"))) = {
    {(const void *)&my_stcvfe, (const void *)&SecTaskCopyValueForEntitlement},
};

// ---------------------------------------------------------------- 安装

__attribute__((constructor)) static void install_hooks(void) {
    id_t cls = objc_getClass("NSFileManager");
    if (cls) {
        SEL_t sel = sel_registerName("containerURLForSecurityApplicationGroupIdentifier:");
        Method_t m = class_getInstanceMethod(cls, sel);
        if (m) {
            void *prev = method_setImplementation(m, (void *)group_container);
            orig_container = (id_t (*)(id_t, SEL_t, id_t))prev;
        }
    }
}
