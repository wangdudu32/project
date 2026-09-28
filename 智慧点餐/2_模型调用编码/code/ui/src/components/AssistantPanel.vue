<script setup>
import { nextTick, ref } from "vue";
import api from "../api";

defineProps({ aiEnabled: Boolean });
const emit = defineEmits(["recommend"]);
const query = ref("");
const history = ref([]);
const loading = ref(false);
const error = ref("");
const messages = ref(null);

async function send(text = query.value) {
  if (loading.value || !text.trim()) return;
  const question = text.trim();
  const previous = history.value
    .slice(-10)
    .map(({ role, content }) => ({ role, content: content.slice(0, 4000) }));
  history.value.push({ role: "user", content: question });
  query.value = "";
  error.value = "";
  loading.value = true;
  emit("recommend", []);
  try {
    const result = await api.post("/chat", {
      query: question,
      history: previous,
    });
    history.value.push({
      role: "assistant",
      content: result.recommendation || result.response,
      mode: result.mode,
      notice: result.notice,
    });
    emit("recommend", result.menu_ids || []);
  } catch (err) {
    error.value = err.message;
    history.value.pop();
    query.value = question;
  } finally {
    loading.value = false;
    await nextTick();
    if (messages.value) messages.value.scrollTop = messages.value.scrollHeight;
  }
}
</script>

<template>
  <section class="panel assistant-panel">
    <div class="section-heading">
      <div>
        <span class="eyebrow">吃点什么</span>
        <h2>点餐小助手</h2>
      </div>
      <el-tag type="info">{{ aiEnabled ? "AI 已开启" : "本地推荐" }}</el-tag>
    </div>
    <p class="muted">告诉我口味和预算，一起挑选今天的菜单。</p>
    <div v-if="!history.length" class="suggestions">
      <el-button round size="small" @click="send('推荐不辣的素菜')"
        >不辣的素菜</el-button
      >
      <el-button round size="small" @click="send('推荐 30 元以内的川菜')"
        >30 元以内的川菜</el-button
      >
    </div>
    <div
      v-if="history.length"
      ref="messages"
      class="messages"
      aria-live="polite"
    >
      <div
        v-for="(message, index) in history"
        :key="index"
        class="message"
        :class="message.role"
      >
        <small>{{
          message.role === "user"
            ? "我"
            : message.mode === "ai"
              ? "AI 助手"
              : message.mode === "map"
                ? "配送查询"
                : "本地助手"
        }}</small>
        <p>{{ message.content }}</p>
        <small v-if="message.notice" class="muted">{{ message.notice }}</small>
      </div>
    </div>
    <p v-if="loading" class="muted" role="status">正在为你查询…</p>
    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      class="gap-bottom"
    />
    <form class="chat-form" @submit.prevent="send()">
      <el-input
        v-model="query"
        aria-label="点餐需求"
        placeholder="例如：想吃清淡一点的菜"
        maxlength="1000"
        :disabled="loading"
      />
      <el-button native-type="submit" type="primary" :loading="loading"
        >发送</el-button
      >
    </form>
    <el-button
      v-if="history.length"
      text
      size="small"
      :disabled="loading"
      @click="
        history = [];
        emit('recommend', []);
      "
      >清空对话</el-button
    >
  </section>
</template>
