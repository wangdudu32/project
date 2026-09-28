<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import api, { money } from "../api";
import OrdersPanel from "./OrdersPanel.vue";

const emit = defineEmits(["menu-changed"]);
const tab = ref("menu");
const items = ref([]);
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const dialog = ref(false);
const editingId = ref(null);
const formError = ref("");
const form = reactive({});
const defaults = {
  dish_name: "",
  price: 10,
  category: "",
  description: "",
  spice_level: 0,
  flavor: "",
  main_ingredients: "",
  cooking_method: "",
  is_vegetarian: false,
  allergens: "",
  is_available: true,
};
async function load() {
  loading.value = true;
  error.value = "";
  try {
    items.value = await api.get("/admin/menu");
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
}
function edit(item) {
  editingId.value = item?.id || null;
  for (const key of Object.keys(defaults))
    form[key] = item ? item[key] : defaults[key];
  form.price = Number(form.price);
  formError.value = "";
  dialog.value = true;
}
function menuPayload(item) {
  return Object.fromEntries(
    Object.keys(defaults).map((key) => [key, item[key]]),
  );
}
async function save() {
  if (saving.value) return;
  saving.value = true;
  formError.value = "";
  try {
    if (editingId.value)
      await api.put(`/admin/menu/${editingId.value}`, menuPayload(form));
    else await api.post("/admin/menu", menuPayload(form));
    dialog.value = false;
    ElMessage.success("菜品已保存");
    await load();
    emit("menu-changed");
  } catch (err) {
    formError.value = err.message;
  } finally {
    saving.value = false;
  }
}
async function toggle(item) {
  saving.value = true;
  try {
    await api.put(`/admin/menu/${item.id}`, {
      ...menuPayload(item),
      is_available: !item.is_available,
    });
    await load();
    emit("menu-changed");
  } catch (err) {
    ElMessage.error(err.message);
  } finally {
    saving.value = false;
  }
}
onMounted(load);
</script>

<template>
  <el-tabs v-model="tab" class="admin-tabs">
    <el-tab-pane label="菜品管理" name="menu">
      <section class="panel">
        <div class="section-heading">
          <div>
            <span class="eyebrow">商家工作台</span>
            <h2>菜品管理</h2>
          </div>
          <el-button type="primary" @click="edit(null)">新增菜品</el-button>
        </div>
        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          class="gap-bottom"
        />
        <el-skeleton v-if="loading" :rows="4" animated />
        <el-table v-else :data="items" class="full-width">
          <el-table-column prop="dish_name" label="菜名" min-width="140" />
          <el-table-column prop="category" label="分类" min-width="90" />
          <el-table-column label="价格" min-width="90"
            ><template #default="{ row }">{{
              money(row.price)
            }}</template></el-table-column
          >
          <el-table-column label="状态" min-width="90"
            ><template #default="{ row }"
              ><el-tag :type="row.is_available ? 'success' : 'info'">{{
                row.is_available ? "供应中" : "已下架"
              }}</el-tag></template
            ></el-table-column
          >
          <el-table-column label="操作" min-width="160"
            ><template #default="{ row }"
              ><el-button size="small" :disabled="saving" @click="edit(row)"
                >编辑</el-button
              ><el-button
                size="small"
                :disabled="saving"
                @click="toggle(row)"
                >{{ row.is_available ? "下架" : "上架" }}</el-button
              ></template
            ></el-table-column
          >
        </el-table>
      </section>
    </el-tab-pane>
    <el-tab-pane label="订单处理" name="orders" lazy
      ><OrdersPanel v-if="tab === 'orders'" admin
    /></el-tab-pane>
  </el-tabs>
  <el-dialog
    v-model="dialog"
    :title="editingId ? '编辑菜品' : '新增菜品'"
    width="560px"
    class="responsive-dialog"
    :close-on-click-modal="false"
  >
    <div>
      <el-form label-position="top" :disabled="saving" @submit.prevent="save">
        <el-form-item label="菜名"
          ><el-input
            v-model="form.dish_name"
            aria-label="菜名"
            maxlength="100"
            required
        /></el-form-item>
        <div class="form-columns">
          <el-form-item label="分类"
            ><el-input
              v-model="form.category"
              aria-label="菜品分类"
              maxlength="50"
              required
          /></el-form-item>
          <el-form-item label="价格（元）"
            ><el-input-number
              v-model="form.price"
              aria-label="菜品价格"
              :min="0.01"
              :max="99999"
              :precision="2"
              :step="0.01"
          /></el-form-item>
        </div>
        <el-form-item label="描述"
          ><el-input
            v-model="form.description"
            aria-label="菜品描述"
            type="textarea"
            maxlength="2000"
        /></el-form-item>
        <div class="form-columns">
          <el-form-item label="辣度"
            ><el-select v-model="form.spice_level" aria-label="菜品辣度"
              ><el-option
                v-for="(text, index) in ['不辣', '微辣', '中辣', '重辣']"
                :key="index"
                :label="text"
                :value="index" /></el-select
          ></el-form-item>
          <el-form-item label="口味"
            ><el-input
              v-model="form.flavor"
              aria-label="菜品口味"
              maxlength="100"
          /></el-form-item>
        </div>
        <el-form-item label="主要食材"
          ><el-input
            v-model="form.main_ingredients"
            aria-label="主要食材"
            maxlength="1000"
        /></el-form-item>
        <el-form-item label="过敏原"
          ><el-input
            v-model="form.allergens"
            aria-label="过敏原"
            maxlength="200"
            placeholder="如：花生、大豆；未填写表示未标注"
        /></el-form-item>
        <el-form-item label="烹饪方式"
          ><el-input
            v-model="form.cooking_method"
            aria-label="烹饪方式"
            maxlength="50"
        /></el-form-item>
        <el-checkbox v-model="form.is_vegetarian">素食</el-checkbox
        ><el-checkbox v-model="form.is_available">上架供应</el-checkbox>
        <el-alert
          v-if="formError"
          :title="formError"
          type="error"
          :closable="false"
          class="gap-top"
        />
        <div class="dialog-footer">
          <el-button @click="dialog = false">返回</el-button
          ><el-button type="primary" native-type="submit" :loading="saving"
            >保存菜品</el-button
          >
        </div>
      </el-form>
    </div>
  </el-dialog>
</template>
