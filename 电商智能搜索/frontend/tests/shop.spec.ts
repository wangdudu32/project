import { expect, test } from "@playwright/test";
import fs from "node:fs";

test("catalog renders Chinese text, photos and a responsive layout", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.locator(".product-card")).toHaveCount(12);
  await page.evaluate(() => document.fonts.ready);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(
    await page.evaluate(() =>
      document.fonts.check('14px "Noto Sans SC Variable"', "日常好物"),
    ),
  ).toBeTruthy();
  const imageFailures = await page
    .locator(".product-card img")
    .evaluateAll(
      (images) =>
        images.filter(
          (image) =>
            (image as HTMLImageElement).complete &&
            !(image as HTMLImageElement).naturalWidth,
        ).length,
    );
  expect(imageFailures).toBe(0);
  expect(errors).toEqual([]);
  fs.mkdirSync("../runtime/screenshots", { recursive: true });
  for (
    let y = 0;
    y < (await page.evaluate(() => document.body.scrollHeight));
    y += 650
  ) {
    await page.evaluate((position) => scrollTo(0, position), y);
    await page.waitForTimeout(80);
  }
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({
    path: `../runtime/screenshots/${info.project.name}.png`,
    fullPage: true,
  });
});

test("natural language search applies price, color and negative constraints", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".product-card")).toHaveCount(12);
  const result = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/search") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("textbox", { name: "搜索商品", exact: true })
    .fill("500元以内的白色通勤运动鞋，不要厚底");
  await page.getByRole("button", { name: "搜索好物", exact: true }).click();
  const body = await (await result).json();
  expect(body.products.length).toBeGreaterThan(0);
  for (const product of body.products) {
    expect(product.price).toBeLessThanOrEqual(500);
    expect(product.color).toBe("白色");
    expect(product.tags).not.toContain("厚底");
    expect(product.stock).toBeGreaterThan(0);
  }
  await expect(page.locator(".product-card").first()).toBeVisible();
});

test("favorites persist and product comparison shows authoritative attributes", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.locator(".product-card")).toHaveCount(12);
  await page.locator(".favorite-button").first().click();
  if (info.project.name === "mobile")
    await page.getByRole("button", { name: "打开心愿清单" }).click();
  else await page.getByRole("button", { name: /^心愿清单/ }).click();
  await expect(page.locator(".product-card")).toHaveCount(1);
  await page.reload();
  expect(
    await page.evaluate(
      () => JSON.parse(localStorage.getItem("seek.favorites") ?? "[]").length,
    ),
  ).toBe(1);
  await page.getByRole("button", { name: "SEEK 寻物首页" }).click();
  await expect(page.locator(".product-card")).toHaveCount(12);
  await page.locator(".compare-toggle").nth(0).click();
  await page.locator(".compare-toggle").nth(1).click();
  await page.getByRole("button", { name: "开始对比", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "好物放一起，选择更清晰。" }),
  ).toBeVisible();
  await expect(page.locator(".comparison-table tbody tr")).toHaveCount(7);
  await page.getByRole("button", { name: "关闭商品对比" }).click();
  await expect(page.locator(".compare-dialog")).not.toBeVisible();
});

test("shopping assistant renders tool products and retains session across turns", async ({
  page,
  request,
}) => {
  const product = await (await request.get("/api/products/p0001")).json();
  const session = "bfe41a6f-03c0-49a3-ac2a-b646de6c876b";
  let turn = 0;
  await page.route("**/api/chat", async (route) => {
    const input = route.request().postDataJSON();
    if (turn > 0) expect(input.session_id).toBe(session);
    turn += 1;
    await route.fulfill({
      json: {
        session_id: session,
        message: "这件商品符合当前预算，详情已列在下方。",
        products: [product],
        comparison: null,
        filters: {
          color: "白色",
          max_price: 500,
          exclude_tags: turn > 1 ? ["厚底"] : [],
        },
        degraded: false,
        notices: [],
      },
    });
  });
  await page.goto("/");
  await page
    .getByRole("button", { name: /AI 帮我选/ })
    .first()
    .click();
  await page
    .getByRole("textbox", { name: "输入购物需求" })
    .fill("500元以内白色运动鞋");
  await page.getByRole("button", { name: "发送购物需求" }).click();
  await expect(page.locator(".chat-product")).toHaveCount(1);
  await expect(page.locator(".chat-filter-chips")).toContainText("¥500 内");
  await page.getByRole("textbox", { name: "输入购物需求" }).fill("不要厚底的");
  await page.getByRole("button", { name: "发送购物需求" }).click();
  await expect(page.locator(".chat-product")).toHaveCount(2);
  await expect(page.locator(".chat-filter-chips")).toContainText("不要厚底");
});
