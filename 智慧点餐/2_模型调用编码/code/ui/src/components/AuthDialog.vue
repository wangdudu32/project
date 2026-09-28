<script setup>
import { reactive, ref } from "vue";
import api from "../api";

const emit = defineEmits(["close", "success"]);
const mode = ref("login");
const form = reactive({ username: "", password: "" });
const loading = ref(false);
const error = ref("");

async function submit() {
  if (loading.value) return;
  error.value = "";
  loading.value = true;
  try {
    const user = await api.post(`/auth/${mode.value}`, form, {
      skipAuthReset: true,
    });
    emit("success", user);
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <el-dialog
    :model-value="true"
    :title="mode === 'login' ? '欢迎回来' : '创建账号'"
    width="420px"
    class="responsive-dialog"
    :close-on-click-modal="false"
    @close="emit('close')"
  >
    <p class="muted">登录后即可保存购物车、下单和查看订单。</p>
    <div>
      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            aria-label="用户名"
            autocomplete="username"
            maxlength="32"
            placeholder="3–32 位字母、数字或下划线"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            aria-label="密码"
            type="password"
            show-password
            :autocomplete="
              mode === 'login' ? 'current-password' : 'new-password'
            "
            maxlength="128"
            placeholder="8–128 位密码"
          />
        </el-form-item>
        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          class="gap-bottom"
        />
        <el-button
          type="primary"
          native-type="submit"
          :loading="loading"
          class="full-width"
          >{{ mode === "login" ? "登录" : "注册并登录" }}</el-button
        >
      </el-form>
    </div>
    <div class="dialog-footer">
      <el-button
        text
        :disabled="loading"
        @click="
          mode = mode === 'login' ? 'register' : 'login';
          error = '';
        "
      >
        {{ mode === "login" ? "还没有账号？去注册" : "已有账号，去登录" }}
      </el-button>
    </div>
  </el-dialog>
</template>
