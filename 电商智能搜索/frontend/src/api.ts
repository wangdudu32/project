export type Product = {
  id: string;
  name: string;
  subtitle: string;
  brand: string;
  category: string;
  color: string;
  color_label: string;
  price: number;
  original_price: number;
  stock: number;
  tags: string[];
  description: string;
  material: string;
  sizes: string[];
  weight: string;
  image: string;
  created_at: string;
  is_demo: boolean;
};

export type Filters = {
  category?: string | null;
  brand?: string | null;
  color?: string | null;
  min_price?: number | null;
  max_price?: number | null;
  in_stock?: boolean;
  exclude_tags?: string[];
};

export type SortOrder = "relevance" | "price_asc" | "price_desc" | "newest";
export type SearchResult = {
  products: Product[];
  total: number;
  page: number;
  page_size: number;
  filters: Filters;
  meta: {
    backend: string;
    semantic: boolean;
    reranked: boolean;
    elapsed_ms: number;
    notices: string[];
  };
};
export type Facets = {
  total: number;
  categories: { name: string; count: number }[];
  brands: string[];
  colors: string[];
};
export type Comparison = {
  products: Product[];
  rows: { label: string; values: (string | number | string[])[] }[];
};
export type ChatAnswer = {
  session_id: string;
  message: string;
  products: Product[];
  comparison: Comparison | null;
  filters: Filters;
  degraded: boolean;
  notices: string[];
};
export type Conversation = {
  session_id: string;
  state: { filters: Filters };
  messages: {
    role: "user" | "assistant";
    content: string;
    payload?: ChatAnswer;
  }[];
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
    signal: options.signal ?? AbortSignal.timeout(90000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "请求未完成，请检查输入或稍后重试",
    );
  }
  return response.json();
}

export function searchProducts(
  query: string,
  filters: Filters,
  sort: SortOrder,
  page: number,
  signal?: AbortSignal,
) {
  return request<SearchResult>("/search", {
    method: "POST",
    body: JSON.stringify({ query, filters, sort, page, page_size: 12 }),
    signal,
  });
}

export const getFacets = () => request<Facets>("/facets");
export const getProduct = (id: string) =>
  request<Product>("/products/" + encodeURIComponent(id));
export const compareProducts = (ids: string[]) =>
  request<Comparison>("/compare", {
    method: "POST",
    body: JSON.stringify({ product_ids: ids }),
  });
export const sendChat = (message: string, sessionId: string | null) =>
  request<ChatAnswer>("/chat", {
    method: "POST",
    body: JSON.stringify({ message, session_id: sessionId }),
  });
export const getConversation = (id: string) =>
  request<Conversation>("/chat/" + encodeURIComponent(id));
export const deleteConversation = (id: string) =>
  request("/chat/" + encodeURIComponent(id), { method: "DELETE" });
export const recordEvent = (
  kind: "click" | "favorite" | "compare",
  id: string,
) =>
  request("/events", {
    method: "POST",
    body: JSON.stringify({ kind, product_id: id }),
  }).catch(() => undefined);

export const money = (value: number) =>
  new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
