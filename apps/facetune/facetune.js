/*
 * Facetune VIP 解锁脚本 v1.0.1
 * 目标: com.lightricks.Facetune2 (Facetune 26.36 / build 10288)
 *
 * 依据（脱壳二进制 + 官方 Web 前端交叉核对）：
 *   BZRGriffinEntitlement.JSONKeyPathsByPropertyKey:
 *     entitlementID -> entitlementId, redemptionIDs -> redemptionIds,
 *     featureTags -> featureTags, apps -> apps, platforms -> platforms,
 *     expirationDate -> expirationMs, notBeforeDate -> notBeforeMs,
 *     gracePeriodUntilDate -> gracePeriodUntilMs
 *   optionalPropertyKeys = {expirationDate, notBeforeDate, gracePeriodUntilDate}
 *   => entitlementId / redemptionIds / featureTags / apps / platforms 为必填
 *   apps 存的是 Lightricks 内部 app slug（facetune2 / photoleap / lightleap），
 *   不是 bundle id —— v1.0.0 只给 bundle id，过滤链取不到本 app 的权益。
 *   filterPremium 内含断言「entitlements 非空但 retrievalDate 为 nil」→ 该字段必须给，
 *   且 List 类未重写 JSONKeyPathsByPropertyKey，默认按属性名映射，*Date 后缀走 ISO。
 *   v1.0.2: 补 retrievalDate(ISO) + 根节点 isSandbox。
 *
 * By Leslie
 */

var NOW_MS = Date.now();
var FAR_MS = 4102444799000;            // 2099-12-31T23:59:59Z
var PAST_MS = NOW_MS - 90 * 86400000;

function premiumEntitlement() {
  return {
    entitlementId: 'facetune2.premium',
    redemptionIds: [],
    featureTags: ['premium', 'pro', 'vip', 'unlimited', 'facetune_premium', 'facetune2_premium'],
    apps: ['facetune2', 'facetune', 'com.lightricks.Facetune2', 'com.lightricks.facetune2'],
    platforms: ['i', 'ios'],
    expirationMs: FAR_MS,
    notBeforeMs: PAST_MS,
    gracePeriodUntilMs: FAR_MS
  };
}

function handleEntitlement() {
  var body = {};
  try {
    body = JSON.parse($response.body || '{}');
  } catch (e) {
    body = {};
  }
  var list = [];
  if (body && body.entitlements && body.entitlements.length) {
    list = body.entitlements;
  }
  list.push(premiumEntitlement());
  body.entitlements = list;
  body.retrievalDate = new Date(NOW_MS).toISOString();
  body.isSandbox = false;
  $done({ body: JSON.stringify(body) });
}

function handleCredits() {
  var body = {};
  try {
    body = JSON.parse($response.body || '{}');
  } catch (e) {
    body = {};
  }
  if (body && body.balances && body.balances.length) {
    for (var i = 0; i < body.balances.length; i++) {
      if (!body.balances[i]) continue;
      body.balances[i].credit = 9999;
      body.balances[i].consumedItems = [];
    }
  }
  $done({ body: JSON.stringify(body) });
}

try {
  var url = $request.url || '';
  if (url.indexOf('/shared-subscription/entitlement') !== -1) {
    handleEntitlement();
  } else if (url.indexOf('/consumables/balance') !== -1) {
    handleCredits();
  } else {
    $done({});
  }
} catch (err) {
  $done({});
}
