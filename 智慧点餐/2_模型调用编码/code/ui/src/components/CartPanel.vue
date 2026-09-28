<script setup>
import { computed, reactive, ref } from "vue";
import api, { money } from "../api";

const props = defineProps({ cart: Object, user: Object, busy: Boolean });
const emit = defineEmits(["quantity", "clear", "ordered", "login"]);
const storageKey = `aimenu:checkout:${props.user?.id}`;
let saved = null;
try {
  saved = JSON.parse(sessionStorage.getItem(storageKey));
} catch {
  /* 浏览器可能禁用存储 */
}
const pending = ref(saved);
const form = reactive(
  saved || {
    contact_name: "",
    contact_phone: "",
    delivery_address: "",
    remark: "",
  },
);
const loading = ref(false);
const error = ref("");
const unavailable = computed(() =>
  props.cart.items.some((row) => !row.dish.is_available),
);

async function checkout() {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  if (!pending.value) {
    pending.value = {
      contact_name: form.contact_name,
      contact_phone: form.contact_phone,
      delivery_address: form.delivery_address,
      remark: form.remark,
      request_id: crypto.randomUUID(),
    };
    try {
      sessionStorage.setItem(storageKey, JSON.stringify(pending.value));
    } catch {
      /* 仍可在当前页面重试 */
    }
  }
  try {
    const order = await api.post("/orders", pending.value);
    pending.value = null;
    try {
      sessionStorage.removeItem(storageKey);
    } catch {
      /* 无可清理记录 */
    }
    emit("ordered", order);
  } catch (err) {
    error.value = err.message;
    // 网络超时可能已生成订单，重试时必须继续使用同一个请求编号。
    if (err.status && err.status < 500) {
      pending.value = null;
      try {
        sessionStorage.removeItem(storageKey);
      } catch {
        /* 无可清理记录 */
      }
    }
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="panel cart-panel">
    <div class="section-heading">
      <h2>我的购物车</h2>
      <el-button
        v-if="cart.items.length"
        text
        :disabled="busy || loading || !!pending"
        @click="emit('clear')"
        >清空</el-button
      >
    </div>
    <el-empty
      v-if="!cart.items.length"
      description="先选几道喜欢的菜吧"
      :image-size="70"
    />
    <div v-for="row in cart.items" :key="row.dish.id" class="cart-row">
      <div>
        <strong>{{ row.dish.dish_name }}</strong>
        <p class="muted">
          {{ money(row.dish.price) }}
          <span v-if="!row.dish.is_available" class="error-text">已下架</span>
        </p>
      </div>
      <div class="quantity-controls">
        <el-button
          circle
          size="small"
          :aria-label="`减少${row.dish.dish_name}`"
          :disabled="busy || loading || !!pending"
          @click="emit('quantity', row.dish.id, row.quantity - 1)"
          >−</el-button
        >
        <span>{{ row.quantity }}</span>
        <el-button
          circle
          size="small"
          :aria-label="`增加${row.dish.dish_name}`"
          :disabled="
            busy ||
            loading ||
            !!pending ||
            row.quantity >= 99 ||
            !row.dish.is_available
          "
          @click="emit('quantity', row.dish.id, row.quantity + 1)"
          >+</el-button
        >
        <el-button
          text
          size="small"
          :disabled="busy || loading || !!pending"
          @click="emit('quantity', row.dish.id, 0)"
          >移除</el-button
        >
      </div>
    </div>
    <template v-if="cart.items.length || pending">
      <div class="cart-total">
        <span>共 {{ cart.total_quantity }} 份</span
        ><strong>{{ money(cart.total_amount) }}</strong>
      </div>
      <el-alert
        v-if="unavailable"
        title="请移除已下架菜品后再下单"
        type="warning"
        :closable="false"
        class="gap-bottom"
      />
      <el-form
        label-position="top"
        :disabled="loading"
        @submit.prevent="checkout"
      >
        <el-form-item label="收货人"
          ><el-input
            v-model="form.contact_name"
            :disabled="!!pending"
            aria-label="收货人"
            maxlength="50"
            required
        /></el-form-item>
        <el-form-item label="手机号"
          ><el-input
            v-model="form.contact_phone"
            :disabled="!!pending"
            aria-label="手机号"
            maxlength="11"
            inputmode="tel"
            pattern="1[3-9][0-9]{9}"
            required
        /></el-form-item>
        <el-form-item label="收货地址"
          ><el-input
            v-model="form.delivery_address"
            :disabled="!!pending"
            aria-label="收货地址"
            maxlength="300"
            minlength="5"
            required
        /></el-form-item>
        <el-form-item label="备注（选填）"
          ><el-input
            v-model="form.remark"
            :disabled="!!pending"
            aria-label="订单备注"
            maxlength="300"
            placeholder="口味、餐具等需求"
        /></el-form-item>
        <p class="muted">
          本项目使用模拟支付。配送范围请先查询或联系商家确认。
        </p>
        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          class="gap-bottom"
        />
        <p v-if="pending && !loading" class="muted">
          订单结果待确认，请使用同一笔请求重试，或到我的订单查看。
        </p>
        <el-button
          type="primary"
          native-type="submit"
          class="full-width"
          :loading="loading"
          :disabled="busy || (unavailable && !pending)"
          >{{ pending ? "重试提交" : "提交订单" }}</el-button
        >
      </el-form>
    </template>
    <el-button
      v-if="!user"
      type="primary"
      class="full-width"
      @click="emit('login')"
      >登录后点餐</el-button
    >
  </section>
</template>
