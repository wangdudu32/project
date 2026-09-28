import { createApp } from "vue";
import {
  ElAlert,
  ElButton,
  ElCheckbox,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElSelect,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
} from "element-plus";
import "element-plus/dist/index.css";
import App from "./App.vue";

const app = createApp(App);
// 只注册页面使用的组件，减少打包体积。
for (const component of [
  ElAlert,
  ElButton,
  ElCheckbox,
  ElDialog,
  ElEmpty,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElOption,
  ElSelect,
  ElSkeleton,
  ElTable,
  ElTableColumn,
  ElTabPane,
  ElTabs,
  ElTag,
]) {
  app.component(component.name, component);
}
app.mount("#app");
