<script setup>
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api, { money } from "../api";

const props = defineProps({ admin: Boolean });
const orders = ref([]);
const loading = ref(false);
const busy = ref(null);
const error = ref("");
const selected = ref(null);
const page = ref(0);
const hasNext = ref(false);
const nextStatus = {
  paid: "preparing",
  preparing: "delivering",
  delivering: "completed",
};
const nextText = {
  paid: "开始制作",
  preparing: "开始配送",
  delivering: "完成订单",
};

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const data = await api.get(props.admin ? "/admin/orders" : "/orders", {
      params: { offset: page.value * 10, limit: 11 },
    });
    hasNext.value = data.length > 10;
    orders.value = data.slice(0, 10);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}
async function action(order, operation) {
  if (busy.value) return;
  try {
    await ElMessageBox.confirm(
      operation === "pay"
        ? `确认模拟支付 ${money(order.total_amount)}？不会扣除真实费用。`
        : operation === "cancel"
          ? "确认取消这笔待付款订单？"
          : `确认${nextText[order.status]}？`,
      "订单操作",
      { confirmButtonText: "确认", cancelButtonText: "返回", type: "warning" },
    );
  } catch {
    return;
  }
  busy.value = order.id;
  try {
    if (operation === "status")
      await api.patch(`/admin/orders/${order.id}/status`, {
        status: nextStatus[order.status],
      });
    else await api.post(`/orders/${order.id}/${operation}`);
    ElMessage.success("操作成功");
    await load();
    if (selected.value?.id === order.id)
      selected.value = orders.value.find((item) => item.id === order.id);
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    busy.value = null;
  }
}
async function detail(order) {
  try {
    selected.value = props.admin ? order : await api.get(`/orders/${order.id}`);
  } catch (err) {
    ElMessage.error(err.message);
  }
}
function changePage(step) {
  page.value += step;
  load();
}
const dateText = (value) =>
  new Date(value).toLocaleString("zh-CN", { hour12: false });
onMounted(load);
</script>

<template>
  <section class="panel orders-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">{{
          admin ? "商家工作台" : "每一餐都有记录"
        }}</span>
        <h2>{{ admin ? "订单处理" : "我的订单" }}</h2>
      </div>
      <el-button :loading="loading" @click="load">刷新订单</el-button>
    </div>
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      class="gap-bottom"
    />
    <el-skeleton v-if="loading" :rows="4" animated />
    <el-empty v-else-if="!orders.length" description="还没有订单" />
    <div v-else class="order-list">
      <article v-for="order in orders" :key="order.id" class="order-card">
        <div class="section-heading">
          <strong>订单 #{{ order.id }}</strong
          ><el-tag
            :type="
              order.status === 'cancelled'
                ? 'info'
                : order.status === 'completed'
                  ? 'success'
                  : 'warning'
            "
            >{{ order.status_text }}</el-tag
          >
        </div>
        <p>
          {{
            order.items
              .map((item) => `${item.dish_name} × ${item.quantity}`)
              .join("、")
          }}
        </p>
        <p class="muted">
          {{ dateText(order.created_at) }} · {{ order.contact_name }}
        </p>
        <p v-if="admin" class="muted">
          {{ order.contact_phone }} · {{ order.delivery_address }}
        </p>
        <div class="order-actions">
          <strong class="price">{{ money(order.total_amount) }}</strong>
          <div>
            <el-button @click="detail(order)">查看详情</el-button>
            <template v-if="!admin && order.status === 'pending'">
              <el-button :disabled="!!busy" @click="action(order, 'cancel')"
                >取消订单</el-button
              >
              <el-button
                type="primary"
                :loading="busy === order.id"
                :disabled="!!busy"
                @click="action(order, 'pay')"
                >模拟支付</el-button
              >
            </template>
            <el-button
              v-if="admin && nextStatus[order.status]"
              type="primary"
              :loading="busy === order.id"
              :disabled="!!busy"
              @click="action(order, 'status')"
              >{{ nextText[order.status] }}</el-button
            >
          </div>
        </div>
      </article>
    </div>
    <div class="pagination">
      <el-button :disabled="page === 0 || loading" @click="changePage(-1)"
        >上一页</el-button
      ><span>第 {{ page + 1 }} 页</span
      ><el-button :disabled="!hasNext || loading" @click="changePage(1)"
        >下一页</el-button
      >
    </div>
    <el-dialog
      :model-value="!!selected"
      title="订单详情"
      width="560px"
      class="responsive-dialog"
      @close="selected = null"
    >
      <template v-if="selected">
        <p class="muted">编号：{{ selected.order_no }}</p>
        <p>状态：{{ selected.status_text }}</p>
        <p>
          收货人：{{ selected.contact_name }} · {{ selected.contact_phone }}
        </p>
        <p>地址：{{ selected.delivery_address }}</p>
        <p>备注：{{ selected.remark || "无" }}</p>
        <div
          v-for="item in selected.items"
          :key="item.dish_id"
          class="detail-row"
        >
          <span
            >{{ item.dish_name }} × {{ item.quantity
            }}<small class="muted"
              >（单价 {{ money(item.unit_price) }}）</small
            ></span
          ><strong>{{ money(item.subtotal) }}</strong>
        </div>
        <div class="cart-total">
          <span>共 {{ selected.total_quantity }} 份</span
          ><strong>{{ money(selected.total_amount) }}</strong>
        </div>
        <p class="muted">
          支付方式：模拟支付，无真实扣款。仅待付款订单可自行取消。
        </p>
      </template>
    </el-dialog>
  </section>
</template>
