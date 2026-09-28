<script setup>
import { ref } from "vue";
import api from "../api";

const address = ref("");
const mode = ref("2");
const loading = ref(false);
const result = ref(null);
async function check() {
  if (!address.value.trim() || loading.value) return;
  loading.value = true;
  result.value = null;
  try {
    result.value = await api.post("/delivery", {
      address: address.value,
      travel_mode: mode.value,
    });
  } catch (err) {
    result.value = { success: false, message: err.message };
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <section class="panel">
    <h2>能送到我这里吗？</h2>
    <p class="muted">查询路线距离和预计配送时间。</p>
    <form @submit.prevent="check" class="delivery-form">
      <el-input
        v-model="address"
        aria-label="查询配送地址"
        placeholder="城市、街道及详细地址"
        maxlength="300"
      />
      <div class="inline-form">
        <el-select v-model="mode" aria-label="出行方式"
          ><el-option label="电动车" value="2" /><el-option
            label="步行"
            value="1" /><el-option label="驾车" value="3"
        /></el-select>
        <el-button native-type="submit" :loading="loading">查询范围</el-button>
      </div>
    </form>
    <el-alert
      v-if="result"
      :type="result.success && result.in_range ? 'success' : 'warning'"
      :title="result.message"
      :closable="false"
      class="gap-top"
    />
    <p v-if="result?.success" class="muted">
      {{ result.formatted_address }} · {{ result.distance }} 公里 · 约
      {{ Math.ceil(result.duration / 60) }} 分钟
    </p>
  </section>
</template>
