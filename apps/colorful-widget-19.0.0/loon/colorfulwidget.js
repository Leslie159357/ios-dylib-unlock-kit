/*
 * Colorful Widget 彩虹小组件 (com.sm.widget) 会员解锁
 *
 * 两条链路：
 *  A) POST /api/widget/colorful/userExtend/get —— 服务端会员态，决定 +[ServerVipUtils isServiceVip]
 *     AES-128-CBC，key = iv = "jr1WrfW8q2sV6xir"，响应零填充、base64url；
 *     明文 {"vipFlag":1}（ServerVipModel 唯一属性 vipFlag，ObjC Ivar offset 16，64 位读取后 ==1 判定）。
 *     密文已离线算好，脚本内不含加密实现。
 *  B) buy.itunes.apple.com / sandbox.itunes.apple.com verifyReceipt —— 本地收据会员态
 *     -[MCWPurchaseManager refreshUserPayState] 命中 isPermanent: 即 userPayState=3；
 *     -[MCWPurchaseManager isVipUser] = (userPayState==3) || isServiceVip。
 */

// base64url( AES-128-CBC(key=iv=jr1WrfW8q2sV6xir, zeroPad('{"vipFlag":1}')) )
var VIP_BLOB = "P_p-0PeKdUMMb06TJtycxQ";

var url = (typeof $request !== "undefined" && $request && $request.url) ? $request.url : "";

/* ---------------- A) 服务端会员态 ---------------- */
if (url.indexOf("/api/widget/colorful/userExtend/get") >= 0) {
  var env = {
    addr: "",
    code: "0",
    data: VIP_BLOB,
    msg: "成功",
    updateTime: Date.now()
  };
  var s1 = JSON.stringify(env);
  console.log("[ColorfulWidget] userExtend/get -> vipFlag=1");
  $done({
    status: "HTTP/1.1 200 OK",
    headers: {
      "Content-Type": "application/json;charset=UTF-8",
      "Content-Length": String(s1.length),
      "Server-Encrypt": "true"
    },
    body: s1
  });
} else {

  /* ---------------- B) 本地收据会员态 ---------------- */
  var APP_ITEM_ID = 1538946171;
  var BUNDLE_ID = "com.sm.widget";

  var FAR_MS = 4070908800000;
  var FAR_STR = "2099-01-01 00:00:00 Etc/GMT";
  var FAR_PST = "2098-12-31 16:00:00 America/Los_Angeles";
  var AT_MS = 1700000000000;
  var AT_STR = "2023-11-14 22:13:20 Etc/GMT";
  var AT_PST = "2023-11-14 14:13:20 America/Los_Angeles";

  var ITEMS = ["cf_forever_14.4.0", "cf__forever_0_4.7.1", "wg_life_0_2.3.0", "cf_year_0_9.4.0"];

  var inApp = ITEMS.map(function (pid, idx) {
    return {
      quantity: "1",
      product_id: pid,
      transaction_id: "2000000" + (100000 + idx),
      purchase_date_ms: String(AT_MS),
      purchase_date: AT_STR,
      purchase_date_pst: AT_PST,
      original_purchase_date_ms: String(AT_MS),
      original_purchase_date: AT_STR,
      original_purchase_date_pst: AT_PST,
      expires_date_ms: String(FAR_MS),
      expires_date: FAR_STR,
      expires_date_pst: FAR_PST,
      is_trial_period: "false",
      is_in_intro_offer_period: "false",
      in_app_ownership_type: "PURCHASED",
      web_order_line_item_id: "2000000" + (200000 + idx)
      // 故意不带 original_transaction_id：partner_tran_id 为空 -> 跳过服务端设备绑定
    };
  });

  var rcpt = {
    status: 0,
    environment: "Production",
    receipt: {
      receipt_type: "Production",
      bundle_id: BUNDLE_ID,
      app_item_id: APP_ITEM_ID,
      adam_id: APP_ITEM_ID,
      application_version: "19.0.0",
      original_application_version: "1.0",
      version_external_identifier: 855047032,
      download_id: 502246001715825900,
      receipt_creation_date_ms: String(AT_MS),
      receipt_creation_date: AT_STR,
      receipt_creation_date_pst: AT_PST,
      request_date_ms: String(Date.now()),
      request_date: FAR_STR,
      request_date_pst: FAR_PST,
      original_purchase_date_ms: String(AT_MS),
      original_purchase_date: AT_STR,
      original_purchase_date_pst: AT_PST,
      in_app: inApp
    },
    latest_receipt_info: inApp,
    pending_renewal_info: [{
      product_id: "cf_year_0_9.4.0",
      auto_renew_product_id: "cf_year_0_9.4.0",
      auto_renew_status: "1",
      is_in_billing_retry_period: "0",
      expiration_intent: "0"
    }]
  };

  var s2 = JSON.stringify(rcpt);
  console.log("[ColorfulWidget] verifyReceipt -> forged lifetime receipt, " + s2.length + " bytes");
  $done({
    status: "HTTP/1.1 200 OK",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Length": String(s2.length)
    },
    body: s2
  });
}
