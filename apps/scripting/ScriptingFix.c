// ScriptingFix.dylib — v5 (arm64 / iOS 17+)
//
// 策略：直接切断 iCloud，而不是伪造授权。
//   A. App Group 容器缺失 → swizzle -[NSFileManager containerURLForSecurityApplicationGroupIdentifier:]
//      在沙盒 Library/Group Containers/<group>/ 下建目录并返回 URL。
//   B. CloudKit 切断 → swizzle +[CKContainer containerWithIdentifier:] 直接返回 nil，
//      不再进入 CloudKit 的授权校验（原实现里缺授权就抛 NSException → SIGABRT）。
//      另有 +[CKContainer defaultContainer] 同样返回 nil，任何路径都构造不出 CKContainer。
//
// objc_msgSend 一律走精确原型函数指针（Apple arm64 ABI：可变实参压栈，C 可变参声明会读到垃圾）。

typedef void *id_t;
typedef void *SEL_t;
typedef void *Method_t;

extern id_t objc_getClass(const char *name);
extern void *object_getClass(id_t obj);
extern SEL_t sel_registerName(const char *name);
extern id_t objc_msgSend(id_t self, SEL_t op, ...);
extern Method_t class_getInstanceMethod(id_t cls, SEL_t name);
extern Method_t class_getClassMethod(id_t cls, SEL_t name);
extern void *method_setImplementation(Method_t m, void *imp);

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

static id_t nsstr(const char *utf8) {
    id_t cls = objc_getClass("NSString");
    if (!cls) return 0;
    return MSG1(cls, sel_registerName("stringWithUTF8String:"), (id_t)utf8);
}

// ---------------------------------------------------------- A. App Group 兜底

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

// ------------------------------------------------------------ B. 切断 CloudKit

static id_t ck_nil(id_t self, SEL_t cmd, id_t arg) {
    (void)self; (void)cmd; (void)arg;
    return 0;   // 不构造 CKContainer，CloudKit 的授权校验永远不会被触发
}

static void disable_cloudkit(void) {
    id_t cls = objc_getClass("CKContainer");
    if (!cls) return;
    Method_t m = class_getClassMethod(cls, sel_registerName("containerWithIdentifier:"));
    if (m) method_setImplementation(m, (void *)ck_nil);
    m = class_getClassMethod(cls, sel_registerName("defaultContainer"));
    if (m) method_setImplementation(m, (void *)ck_nil);
}

// ---------------------------------------------------------------- 安装

__attribute__((constructor)) static void install_hooks(void) {
    id_t fmcls = objc_getClass("NSFileManager");
    if (fmcls) {
        SEL_t sel = sel_registerName("containerURLForSecurityApplicationGroupIdentifier:");
        Method_t m = class_getInstanceMethod(fmcls, sel);
        if (m) {
            void *prev = method_setImplementation(m, (void *)group_container);
            orig_container = (id_t (*)(id_t, SEL_t, id_t))prev;
        }
    }
    disable_cloudkit();
}
