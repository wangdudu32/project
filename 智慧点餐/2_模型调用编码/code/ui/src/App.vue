<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import api, { money } from "./api";
import AuthDialog from "./components/AuthDialog.vue";
import AssistantPanel from "./components/AssistantPanel.vue";
import DeliveryPanel from "./components/DeliveryPanel.vue";
import CartPanel from "./components/CartPanel.vue";
import OrdersPanel from "./components/OrdersPanel.vue";
import AdminPanel from "./components/AdminPanel.vue";

const settings = ref({
  restaurant_name: "小满餐厅",
  restaurant_hours: "每天 09:00-22:00",
});
const user = ref(null);
const authVisible = ref(false);
const tab = ref("menu");
const menu = ref([]);
const loading = ref(true);
const menuError = ref("");
const search = ref("");
const category = ref("全部");
const highlighted = ref([]);
const cart = ref({ items: [], total_amount: "0.00", total_quantity: 0 });
const busy = ref(false);
const cartReady = ref(false);
const categories = computed(() => [
  "全部",
  ...new Set(menu.value.map((item) => item.category)),
]);
const filtered = computed(() =>
  menu.value.filter(
    (item) =>
      (category.value === "全部" || item.category === category.value) &&
      `${item.dish_name} ${item.description}`.includes(search.value.trim()),
  ),
);

async function loadMenu() {
  loading.value = true;
  menuError.value = "";
  try {
    menu.value = (await api.get("/menu/list")).menu_items;
    if (!categories.value.includes(category.value)) category.value = "全部";
  } catch (err) {
    menuError.value = err.message;
  } finally {
    loading.value = false;
  }
}
async function loadCart() {
  if (!user.value) return;
  cartReady.value = false;
  try {
    cart.value = await api.get("/cart");
    cartReady.value = true;
  } catch (err) {
    ElMessage.error(err.message);
  }
}
function resetUser() {
  user.value = null;
  cart.value = { items: [], total_amount: "0.00", total_quantity: 0 };
  cartReady.value = false;
  tab.value = "menu";
}
async function loggedIn(value) {
  user.value = value;
  authVisible.value = false;
  await loadCart();
  ElMessage.success("登录成功");
}
async function logout() {
  try {
    await api.post("/auth/logout");
    resetUser();
  } catch (err) {
    ElMessage.error(err.message);
  }
}
async function quantity(dishId, value) {
  if (!user.value) {
    authVisible.value = true;
    return;
  }
  if (busy.value || !cartReady.value) return;
  busy.value = true;
  try {
    cart.value = await api.put(`/cart/${dishId}`, { quantity: value });
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    busy.value = false;
  }
}
function add(item) {
  const row = cart.value.items.find((row) => row.dish.id === item.id);
  if (row?.quantity >= 99) {
    ElMessage.warning("每道菜最多 99 份");
    return;
  }
  quantity(item.id, (row?.quantity || 0) + 1);
}
async function clearCart() {
  busy.value = true;
  try {
    cart.value = await api.delete("/cart");
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    busy.value = false;
  }
}
async function ordered(order) {
  ElMessage.success(`订单 #${order.id} 已提交，请完成模拟支付`);
  tab.value = "orders";
  await loadCart();
}
function navigate(value) {
  if (value !== "menu" && !user.value) {
    authVisible.value = true;
    return;
  }
  tab.value = value;
}
function recommend(ids) {
  highlighted.value = ids.map(String);
  category.value = "全部";
  search.value = "";
}
async function menuChanged() {
  await Promise.all([loadMenu(), loadCart()]);
}
onMounted(async () => {
  window.addEventListener("aimenu:unauthorized", resetUser);
  await Promise.all([
    loadMenu(),
    api
      .get("/config")
      .then((value) => {
        settings.value = value;
      })
      .catch(() => {}),
    api
      .get("/auth/me", { skipAuthReset: true })
      .then(async (value) => {
        user.value = value;
        await loadCart();
      })
      .catch(() => {}),
  ]);
});
onUnmounted(() => window.removeEventListener("aimenu:unauthorized", resetUser));
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <a class="brand" href="#" @click.prevent="tab = 'menu'"
        ><span class="brand-mark">食</span
        ><span
          >{{ settings.restaurant_name
          }}<small>智慧点餐 · 好好吃饭</small></span
        ></a
      >
      <nav aria-label="主导航">
        <button :class="{ active: tab === 'menu' }" @click="navigate('menu')">
          点餐</button
        ><button
          :class="{ active: tab === 'orders' }"
          @click="navigate('orders')"
        >
          我的订单</button
        ><button
          v-if="user?.is_admin"
          :class="{ active: tab === 'admin' }"
          @click="navigate('admin')"
        >
          商家后台
        </button>
      </nav>
      <div class="account">
        <template v-if="user"
          ><span>{{ user.username }}</span
          ><el-button text @click="logout">退出</el-button></template
        ><el-button v-else type="primary" plain @click="authVisible = true"
          >登录 / 注册</el-button
        >
      </div>
    </header>
    <main>
      <template v-if="tab === 'menu'">
        <section class="hero">
          <div>
            <span class="eyebrow">一日三餐，认真对待</span>
            <h1>今天，也要好好吃饭。</h1>
            <p>从喜欢的口味开始，选一份刚刚好的美味。</p>
          </div>
          <div class="opening">
            <span class="status-dot"></span>{{ settings.restaurant_hours
            }}<small>{{ settings.restaurant_address || "欢迎光临" }}</small>
          </div>
        </section>
        <div class="shop-layout">
          <div class="menu-column">
            <AssistantPanel
              :key="user?.id || 'guest'"
              :ai-enabled="settings.ai_enabled"
              @recommend="recommend"
            />
            <section class="panel menu-panel">
              <div class="section-heading">
                <div>
                  <span class="eyebrow">新鲜出品</span>
                  <h2>
                    今日菜单 <small>{{ menu.length }} 道菜</small>
                  </h2>
                </div>
                <el-button :loading="loading" @click="loadMenu">刷新</el-button>
              </div>
              <div class="menu-filters">
                <div class="category-list">
                  <button
                    v-for="item in categories"
                    :key="item"
                    :class="{ active: category === item }"
                    @click="category = item"
                  >
                    {{ item }}
                  </button>
                </div>
                <el-input
                  v-model="search"
                  aria-label="搜索菜品"
                  placeholder="搜索菜名"
                  clearable
                  class="menu-search"
                />
              </div>
              <el-alert
                v-if="menuError"
                :title="menuError"
                type="error"
                :closable="false"
                class="gap-bottom"
              />
              <el-skeleton v-if="loading" :rows="6" animated />
              <div v-else-if="filtered.length" class="menu-grid">
                <article
                  v-for="item in filtered"
                  :key="item.id"
                  class="dish-card"
                  :class="{
                    recommended: highlighted.includes(String(item.id)),
                  }"
                >
                  <div class="dish-top">
                    <span class="dish-category">{{ item.category }}</span
                    ><el-tag
                      v-if="highlighted.includes(String(item.id))"
                      size="small"
                      type="warning"
                      >为你推荐</el-tag
                    >
                  </div>
                  <h3>{{ item.dish_name }}</h3>
                  <p class="dish-description">
                    {{ item.description || "美味现做，欢迎品尝。" }}
                  </p>
                  <div class="dish-tags">
                    <span>{{ item.spice_text }}</span
                    ><span v-if="item.is_vegetarian">素食</span
                    ><span v-if="item.flavor">{{ item.flavor }}</span>
                  </div>
                  <p class="allergens">
                    过敏原：{{ item.allergens || "未标注，请咨询商家" }}
                  </p>
                  <div class="dish-bottom">
                    <strong class="price">{{ money(item.price) }}</strong
                    ><el-button
                      type="primary"
                      plain
                      :disabled="busy || (!!user && !cartReady)"
                      :aria-label="`添加${item.dish_name}`"
                      @click="add(item)"
                      >＋ 加入</el-button
                    >
                  </div>
                </article>
              </div>
              <el-empty v-else description="没有找到符合条件的菜品" />
            </section>
          </div>
          <aside class="sidebar">
            <div v-if="user && !cartReady" class="panel">
              <p>购物车暂未加载</p>
              <el-button @click="loadCart">重新加载</el-button>
            </div>
            <CartPanel
              v-else
              :key="user?.id || 'guest'"
              :cart="cart"
              :user="user"
              :busy="busy"
              @quantity="quantity"
              @clear="clearCart"
              @ordered="ordered"
              @login="authVisible = true"
            /><DeliveryPanel />
          </aside>
        </div>
      </template>
      <OrdersPanel v-else-if="tab === 'orders' && user" :key="user.id" />
      <AdminPanel
        v-else-if="tab === 'admin' && user?.is_admin"
        @menu-changed="menuChanged"
      />
    </main>
    <footer>智慧点餐 · 本地演示项目 · 仅模拟支付，不产生真实扣款</footer>
    <AuthDialog
      v-if="authVisible"
      @close="authVisible = false"
      @success="loggedIn"
    />
  </div>
</template>

<style>
:root {
  font-family: Inter, "PingFang SC", "Microsoft YaHei", sans-serif;
  color: #292c26;
  background: #f6f5f1;
  --el-color-primary: #b34e2c;
  --el-color-primary-light-3: #c7795f;
  --el-color-primary-light-5: #d9a18e;
  --el-color-primary-light-7: #eacec3;
  --el-color-primary-light-8: #f0ded6;
  --el-color-primary-light-9: #f9f0eb;
  --el-color-primary-dark-2: #90391c;
  --el-border-radius-base: 8px;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
}
button,
input {
  font: inherit;
}
button {
  cursor: pointer;
}
h1,
h2,
h3,
p {
  margin-top: 0;
}
h1 {
  font-size: 34px;
  letter-spacing: -1px;
  margin-bottom: 14px;
}
h2 {
  font-size: 20px;
  margin-bottom: 14px;
}
h2 small {
  font-size: 12px;
  color: #85887d;
  font-weight: 400;
  margin-left: 6px;
}
h3 {
  font-size: 21px;
  margin-bottom: 10px;
}
.app-shell {
  max-width: 1360px;
  margin: auto;
  padding: 0 32px;
}
.site-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 96px;
  border-bottom: 1px solid #e6e5dd;
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  color: inherit;
  text-decoration: none;
  font-size: 21px;
  font-weight: 700;
  white-space: nowrap;
}
.brand small {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: #7f8378;
  margin-top: 5px;
  letter-spacing: 1px;
}
.brand-mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 14px;
  background: #b34e2c;
  color: white;
  font-size: 24px;
}
.site-header nav {
  display: flex;
  gap: 8px;
}
.site-header nav button {
  background: none;
  border: 0;
  padding: 12px 18px;
  color: #797d73;
  border-radius: 8px;
  white-space: nowrap;
}
.site-header nav button.active {
  background: #ebece5;
  color: #343f2e;
  font-weight: 700;
}
.account {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  max-width: 260px;
}
.account > span {
  overflow: hidden;
  text-overflow: ellipsis;
}
.hero {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 42px 0 32px;
}
.hero p {
  color: #797d73;
  margin-bottom: 0;
}
.eyebrow {
  font-size: 11px;
  letter-spacing: 2px;
  color: #969a8b;
  display: block;
  margin-bottom: 10px;
}
.opening {
  font-size: 13px;
  background: #eceee4;
  padding: 18px 22px;
  border-radius: 12px;
  line-height: 1.6;
}
.opening small {
  display: block;
  color: #797d73;
  margin-top: 4px;
}
.status-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #849265;
  margin-right: 8px;
}
.shop-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 24px;
  align-items: start;
}
.menu-column,
.sidebar {
  display: flex;
  flex-direction: column;
  gap: 24px;
  min-width: 0;
}
.panel {
  background: #fff;
  border: 1px solid #e8e7df;
  border-radius: 16px;
  padding: 24px;
  min-width: 0;
}
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.section-heading h2 {
  margin-bottom: 0;
}
.section-heading .eyebrow {
  margin-bottom: 6px;
}
.muted {
  font-size: 13px;
  color: #7d8176;
  line-height: 1.7;
}
.gap-bottom {
  margin-bottom: 16px;
}
.gap-top {
  margin-top: 16px;
}
.full-width {
  width: 100%;
}
.chat-form,
.inline-form {
  display: flex;
  gap: 10px;
}
.delivery-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.inline-form .el-select {
  min-width: 0;
  flex: 1;
}
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 20px 0;
}
.suggestions .el-button {
  margin: 0;
}
.messages {
  max-height: 360px;
  overflow: auto;
  margin: 16px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.message {
  background: #f6f7f2;
  border-radius: 12px;
  padding: 14px 16px;
  max-width: 95%;
  align-self: flex-start;
}
.message.user {
  align-self: flex-end;
  background: #fcf1e9;
}
.message small {
  font-size: 11px;
  color: #8a8d81;
}
.message p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  margin: 6px 0 0;
  font-size: 14px;
  line-height: 1.8;
}
.menu-filters {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.category-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.category-list button {
  border: 1px solid #e9e8e1;
  background: #fff;
  padding: 7px 15px;
  border-radius: 20px;
  color: #6e7467;
  font-size: 13px;
}
.category-list button.active {
  background: #354932;
  color: white;
  border-color: #354932;
}
.menu-search {
  max-width: 190px;
}
.menu-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}
.dish-card {
  border: 1px solid #e8e7df;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s;
}
.dish-card.recommended {
  border-color: #c36b40;
  background: #fffbf6;
}
.dish-top {
  display: flex;
  justify-content: space-between;
  min-height: 28px;
  gap: 8px;
  margin-bottom: 12px;
}
.dish-category {
  color: #8b927f;
  font-size: 11px;
  letter-spacing: 2px;
}
.dish-description {
  color: #7e8277;
  font-size: 13px;
  line-height: 1.8;
  min-height: 46px;
  overflow-wrap: anywhere;
}
.dish-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.dish-tags span {
  font-size: 11px;
  background: #f1f3eb;
  color: #737c64;
  padding: 4px 8px;
  border-radius: 4px;
}
.allergens {
  font-size: 11px;
  color: #929587;
  line-height: 1.6;
  margin: 12px 0 20px;
  overflow-wrap: anywhere;
}
.dish-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: auto;
}
.price {
  color: #ad4b2a;
  font-size: 22px;
}
.cart-row {
  border-bottom: 1px solid #eeeee8;
  padding: 16px 0;
}
.cart-row strong {
  font-size: 14px;
}
.cart-row p {
  margin: 4px 0 10px;
}
.quantity-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}
.quantity-controls .el-button {
  margin: 0;
}
.cart-total {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 22px 0;
  color: #737969;
  font-size: 13px;
}
.cart-total strong {
  font-size: 23px;
  color: #ad4b2a;
}
.el-form-item {
  margin-bottom: 16px;
}
.el-form-item__label {
  font-size: 13px !important;
}
.error-text {
  color: #ba4131;
}
.orders-panel,
.admin-tabs {
  margin-top: 32px;
}
.order-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.order-card {
  border: 1px solid #e8e7df;
  border-radius: 12px;
  padding: 20px;
}
.order-card p {
  font-size: 14px;
  line-height: 1.7;
  overflow-wrap: anywhere;
}
.order-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.order-actions > div {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.order-actions .el-button {
  margin: 0;
}
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  margin-top: 24px;
  font-size: 13px;
  color: #7d8176;
}
.detail-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid #eee;
  padding: 14px 0;
}
.form-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.form-columns .el-input-number {
  width: 100%;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  margin-top: 22px;
}
footer {
  padding: 36px 0;
  color: #949889;
  text-align: center;
  font-size: 12px;
}
.el-dialog__body p {
  overflow-wrap: anywhere;
}
.responsive-dialog {
  max-width: calc(100vw - 32px);
}
@media (max-width: 1000px) {
  .shop-layout {
    grid-template-columns: minmax(0, 1fr) 300px;
    gap: 16px;
  }
  .panel {
    padding: 20px;
  }
  .app-shell {
    padding: 0 20px;
  }
  .menu-grid {
    grid-template-columns: 1fr;
  }
  .site-header {
    gap: 12px;
  }
  .site-header nav button {
    padding: 10px;
  }
  .hero h1 {
    font-size: 28px;
  }
}
@media (max-width: 720px) {
  .site-header {
    flex-wrap: wrap;
    padding: 18px 0;
    gap: 16px;
  }
  .site-header nav {
    order: 3;
    width: 100%;
    justify-content: center;
  }
  .account {
    max-width: 180px;
  }
  .hero {
    padding: 28px 0;
    flex-direction: column;
    align-items: flex-start;
  }
  .hero h1 {
    font-size: 27px;
  }
  .opening {
    width: 100%;
    font-size: 12px;
    padding: 14px 18px;
  }
  .shop-layout {
    grid-template-columns: 1fr;
  }
  .menu-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .dish-card {
    padding: 14px;
  }
  .dish-card h3 {
    font-size: 18px;
  }
  .app-shell {
    padding: 0 14px;
  }
  .panel {
    padding: 18px;
  }
  .form-columns {
    grid-template-columns: 1fr;
    gap: 0;
  }
  .brand {
    font-size: 18px;
  }
  .brand small {
    font-size: 10px;
  }
  .brand-mark {
    width: 40px;
    height: 40px;
  }
  .price {
    font-size: 20px;
  }
  .dish-bottom {
    gap: 8px;
    flex-wrap: wrap;
  }
}
@media (max-width: 390px) {
  .menu-grid {
    grid-template-columns: 1fr;
  }
}
</style>
