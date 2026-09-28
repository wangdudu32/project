import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 60000,
  headers: { "Content-Type": "application/json", "X-Requested-With": "aimenu" },
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const status = error.response?.status;
    if (status === 401 && !error.config?.skipAuthReset) {
      window.dispatchEvent(new Event("aimenu:unauthorized"));
    }
    const detail = error.response?.data?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : error.code === "ECONNABORTED"
          ? "请求超时，请稍后重试"
          : "服务暂时不可用，请检查后端是否已启动";
    return Promise.reject(Object.assign(new Error(message), { status }));
  },
);

export const money = (value) => `¥${Number(value || 0).toFixed(2)}`;
export default api;
