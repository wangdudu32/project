import { test, expect } from "@playwright/test";

test("顾客下单、商家处理及手机页面", async ({ page }) => {
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const username = `buyer_${Date.now()}`;
  await page.goto("http://127.0.0.1:3001");
  await expect(
    page.getByRole("heading", { name: "今天，也要好好吃饭。" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "宫保鸡丁", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "不辣的素菜", exact: true }).click();
  await expect(page.locator(".dish-card.recommended")).toHaveCount(2);
  await page.getByLabel("查询配送地址").fill("北京市中关村一号");
  await page.getByRole("button", { name: "查询范围", exact: true }).click();
  await expect(
    page.getByText("配送查询暂未启用，请联系商家确认配送范围。"),
  ).toBeVisible();
  await page.getByRole("button", { name: "登录 / 注册", exact: true }).click();
  await page.getByRole("button", { name: "还没有账号？去注册" }).click();
  await page.getByLabel("用户名", { exact: true }).fill(username);
  await page.getByLabel("密码", { exact: true }).fill("browser-buyer-test");
  await page.getByRole("button", { name: "注册并登录", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "退出", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "添加宫保鸡丁", exact: true }).click();
  await expect(page.locator(".cart-row")).toHaveCount(1);
  await page.getByRole("button", { name: "添加清炒时蔬", exact: true }).click();
  await expect(page.locator(".cart-row")).toHaveCount(2);
  await expect(page.locator(".cart-total strong")).toHaveText("¥43.00");
  await page.getByLabel("收货人", { exact: true }).fill("浏览器测试");
  await page.getByLabel("手机号", { exact: true }).fill("13800138000");
  await page
    .getByLabel("收货地址", { exact: true })
    .fill("北京市海淀区中关村一号");
  await page.getByRole("button", { name: "提交订单", exact: true }).click();
  await expect(page.getByText("待付款", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "模拟支付", exact: true }).click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page.getByText("已付款", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "查看详情", exact: true }).click();
  await expect(
    page.getByText("收货人：浏览器测试 · 13800138000"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close this dialog" }).click();
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await page.getByRole("button", { name: "登录 / 注册", exact: true }).click();
  await page.getByLabel("用户名", { exact: true }).fill("browser_admin");
  await page.getByLabel("密码", { exact: true }).fill("browser-admin-test");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByRole("button", { name: "商家后台", exact: true }).click();
  await page.getByRole("button", { name: "新增菜品", exact: true }).click();
  await page.getByLabel("菜名", { exact: true }).fill("番茄炒蛋测试菜");
  await page.getByLabel("菜品分类", { exact: true }).fill("家常菜");
  await page.getByLabel("菜品价格", { exact: true }).fill("16.50");
  await page.getByRole("button", { name: "保存菜品", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "番茄炒蛋测试菜", exact: true }),
  ).toBeVisible();
  const row = page
    .getByRole("row")
    .filter({ hasText: "番茄炒蛋测试菜" })
    .last();
  await row.getByRole("button", { name: "下架", exact: true }).click();
  await expect(row.getByText("已下架", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "订单处理", exact: true }).click();
  const order = page
    .locator(".order-card")
    .filter({ hasText: "浏览器测试" })
    .first();
  for (const [button, status] of [
    ["开始制作", "制作中"],
    ["开始配送", "配送中"],
    ["完成订单", "已完成"],
  ]) {
    await order.getByRole("button", { name: button, exact: true }).click();
    await page.getByRole("button", { name: "确认", exact: true }).click();
    await expect(order.getByText(status, { exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "退出", exact: true }).click();
  await page.getByRole("button", { name: "登录 / 注册", exact: true }).click();
  await page.getByLabel("用户名", { exact: true }).fill(username);
  await page.getByLabel("密码", { exact: true }).fill("browser-buyer-test");
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByRole("button", { name: "我的订单", exact: true }).click();
  await expect(page.getByText("已完成", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "点餐", exact: true }).click();
  await page.getByRole("button", { name: "添加宫保鸡丁", exact: true }).click();
  await page.getByLabel("收货人", { exact: true }).fill("浏览器取消测试");
  await page.getByLabel("手机号", { exact: true }).fill("13800138000");
  await page
    .getByLabel("收货地址", { exact: true })
    .fill("北京市海淀区中关村一号");
  await page.getByRole("button", { name: "提交订单", exact: true }).click();
  await page.getByRole("button", { name: "取消订单", exact: true }).click();
  await page.getByRole("button", { name: "确认", exact: true }).click();
  await expect(page.getByText("已取消", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "点餐", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "今天，也要好好吃饭。" }),
  ).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
  expect(errors).toEqual([]);
  console.log(
    "PASS: registration, recommendation, delivery fallback, checkout, payment, admin menu, fulfillment, buyer completion, cancellation, mobile layout; no browser errors",
  );
});
