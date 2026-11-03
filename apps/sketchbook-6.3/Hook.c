// Sketchbook (com.autodesk.ios.SketchBookPro3) premium unlock
// 唯一真相源：-[AppStoreConnection isPremiumBundlePurchased]
//   = (+[iPUtilities isBuildUnlockedVersion] | byte_100D554F8)
// 所有 Swift 侧缓存(bool 属性，如 BrushLibraryTableViewController.isPremiumBundlePurchased)
// 都在 init 时从这个方法取值，因此只改这里即可全量生效。
#include <stdint.h>

#define NULL ((void *)0)

typedef struct objc_object *id;
typedef struct objc_selector *SEL;
typedef struct objc_class *Class;
typedef struct objc_method *Method;
typedef void *IMP;

extern Class objc_getClass(const char *name);
extern SEL sel_registerName(const char *str);
extern Method class_getInstanceMethod(Class cls, SEL name);
extern IMP method_setImplementation(Method m, IMP imp);

static char ret_1(id self, SEL _cmd) { (void)self; (void)_cmd; return 1; }
static char ret_1_arg(id self, SEL _cmd, id a1) { (void)self; (void)_cmd; (void)a1; return 1; }

static void hook_inst(const char *cls_name, const char *sel_name, IMP imp) {
  Class c = objc_getClass(cls_name);
  if (!c) return;
  Method m = class_getInstanceMethod(c, sel_registerName(sel_name));
  if (m) method_setImplementation(m, imp);
}

__attribute__((constructor)) static void skb_unlock_init(void) {
  hook_inst("AppStoreConnection", "isPremiumBundlePurchased", (IMP)ret_1);
  hook_inst("AppStoreConnection", "getInAppPurchasesValueForKey:", (IMP)ret_1_arg);
}
