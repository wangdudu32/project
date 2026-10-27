import * as Dialog from "@radix-ui/react-dialog";
import {
  ArrowDown,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronLeft,
  ChevronRight,
  Heart,
  LoaderCircle,
  RotateCcw,
  Scale,
  Search,
  SearchX,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  compareProducts,
  getFacets,
  getProduct,
  recordEvent,
  searchProducts,
  type Comparison,
  type Facets,
  type Filters,
  type Product,
  type SearchResult,
  type SortOrder,
} from "./api";
import { Button } from "./components/Button";
import { ChatPanel } from "./components/ChatPanel";
import { CompareDialog } from "./components/CompareDialog";
import { FilterPanel } from "./components/FilterPanel";
import { ProductCard } from "./components/ProductCard";
import { ProductDialog } from "./components/ProductDialog";

const categories = [
  { name: "全部好物", value: null },
  { name: "运动鞋履", value: "运动鞋" },
  { name: "山野户外", value: "户外鞋" },
  { name: "日常服饰", value: "服饰" },
  { name: "随身包袋", value: "包袋" },
  { name: "生活配饰", value: "配饰" },
];
const defaultFilters: Filters = { in_stock: true, exclude_tags: [] };

function readFavorites(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem("seek.favorites") ?? "[]");
    return Array.isArray(value)
      ? value
          .filter((item): item is string => typeof item === "string")
          .slice(0, 50)
      : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [view, setView] = useState<"discover" | "newest" | "favorites">(
    "discover",
  );
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [sort, setSort] = useState<SortOrder>("relevance");
  const [page, setPage] = useState(1);
  const [revision, setRevision] = useState(0);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [favorites, setFavorites] = useState<string[]>(readFavorites);
  const [selected, setSelected] = useState<Product[]>([]);
  const [detail, setDetail] = useState<Product | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatPrompt, setChatPrompt] = useState<{
    id: number;
    text: string;
  } | null>(null);
  const [mobileFilters, setMobileFilters] = useState(false);
  const [toast, setToast] = useState("");
  const catalog = useRef<HTMLElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const filtersKey = JSON.stringify(filters);
  const favoriteKey = view === "favorites" ? favorites.join(",") : "";

  useEffect(() => {
    getFacets()
      .then(setFacets)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    localStorage.setItem("seek.favorites", JSON.stringify(favorites));
  }, [favorites]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 3800);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    async function load() {
      try {
        let response: SearchResult;
        if (view === "favorites") {
          const loaded = await Promise.allSettled(favorites.map(getProduct));
          const products = loaded.flatMap((item) =>
            item.status === "fulfilled" ? [item.value] : [],
          );
          if (sort === "price_asc") products.sort((a, b) => a.price - b.price);
          if (sort === "price_desc") products.sort((a, b) => b.price - a.price);
          if (sort === "newest")
            products.sort((a, b) => b.created_at.localeCompare(a.created_at));
          response = {
            products: products.slice((page - 1) * 12, page * 12),
            total: products.length,
            page,
            page_size: 12,
            filters: {},
            meta: {
              backend: "catalog",
              semantic: false,
              reranked: false,
              elapsed_ms: 0,
              notices: [],
            },
          };
        } else {
          response = await searchProducts(
            query,
            JSON.parse(filtersKey),
            sort,
            page,
            controller.signal,
          );
        }
        if (!controller.signal.aborted) setResult(response);
      } catch (failure) {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error
              ? failure.message
              : "暂时没有连接上服务，请稍后再试",
          );
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [query, filtersKey, sort, page, revision, view, favoriteKey]);

  function changeFilters(next: Filters) {
    setFilters(next);
    setPage(1);
  }
  function reset() {
    setFilters(defaultFilters);
    setQuery("");
    setInput("");
    setPage(1);
  }
  function navigate(next: typeof view) {
    setView(next);
    reset();
    setSort(next === "newest" ? "newest" : "relevance");
  }
  function runSearch(text = input) {
    setView("discover");
    setQuery(text.trim());
    setInput(text);
    setPage(1);
    setRevision((value) => value + 1);
  }
  function askAssistant(text?: string) {
    setChatOpen(true);
    if (text) setChatPrompt({ id: Date.now(), text });
  }
  function openProduct(product: Product) {
    setDetail(product);
    void recordEvent("click", product.id);
  }
  function toggleFavorite(product: Product) {
    if (favorites.includes(product.id)) {
      setFavorites((previous) => previous.filter((id) => id !== product.id));
      setToast("已移出心愿清单");
    } else if (favorites.length >= 50) setToast("心愿清单最多保存 50 件好物");
    else {
      setFavorites((previous) => [...previous, product.id]);
      setToast("已收藏，喜欢的好物慢慢挑");
      void recordEvent("favorite", product.id);
    }
  }
  function toggleCompare(product: Product) {
    if (selected.some((item) => item.id === product.id))
      setSelected((previous) =>
        previous.filter((item) => item.id !== product.id),
      );
    else if (selected.length >= 3) setToast("一次可以比较最多三件商品");
    else setSelected((previous) => [...previous, product]);
  }
  async function showComparison() {
    setCompareLoading(true);
    try {
      setComparison(
        await compareProducts(selected.map((product) => product.id)),
      );
      selected.forEach((product) => void recordEvent("compare", product.id));
    } catch (failure) {
      setToast(failure instanceof Error ? failure.message : "商品对比暂不可用");
    } finally {
      setCompareLoading(false);
    }
  }

  const activeCount = [
    filters.brand,
    filters.color,
    filters.min_price,
    filters.max_price,
    ...(filters.exclude_tags ?? []),
  ].filter((value) => value != null && value !== "").length;
  const pageCount = Math.ceil((result?.total ?? 0) / 12);

  return (
    <>
      <div className="announcement">
        <div>
          <span>
            <i />
            把喜欢的，带进日常。
          </span>
          <span className="announcement-right">
            THE EVERYDAY EDIT<span>电商智能搜索演示</span>
          </span>
        </div>
      </div>
      <header className="site-header">
        <div className="header-inner">
          <button
            className="wordmark"
            onClick={() => navigate("discover")}
            aria-label="SEEK 寻物首页"
          >
            <span>
              SEEK<span className="wordmark-star">✳</span>
            </span>
            <i />
            寻物
          </button>
          <nav aria-label="主导航">
            <button
              className={view === "discover" ? "active" : ""}
              onClick={() => navigate("discover")}
            >
              发现好物
            </button>
            <button
              className={view === "newest" ? "active" : ""}
              onClick={() => navigate("newest")}
            >
              新品上架
              <span className="nav-dot" />
            </button>
            <button
              className={view === "favorites" ? "active" : ""}
              onClick={() => navigate("favorites")}
            >
              心愿清单
              {favorites.length > 0 && <small>{favorites.length}</small>}
            </button>
          </nav>
          <div className="header-actions">
            <button
              className="header-search"
              aria-label="聚焦商品搜索"
              onClick={() => {
                searchInput.current?.focus();
                catalog.current?.scrollIntoView({ behavior: "smooth" });
              }}
            >
              <Search size={20} strokeWidth={1.6} />
            </button>
            <Button
              variant="secondary"
              size="small"
              onClick={() => askAssistant()}
            >
              <Sparkles size={15} />
              <span>AI 帮我选</span>
              <ArrowUpRight size={14} />
            </Button>
            <button
              className="mobile-favorite"
              aria-label="打开心愿清单"
              onClick={() => navigate("favorites")}
            >
              <Heart size={19} />
            </button>
          </div>
        </div>
      </header>
      <main className="main-container">
        {view !== "favorites" && (
          <section className="hero" aria-label="日常好物精选">
            <img
              className="hero-image"
              src="/images/hero.png"
              alt="雾白与蓝色拼接的运动跑鞋，置于暖色石台之上"
            />
            <div className="hero-gradient" />
            <div className="hero-copy">
              <div className="hero-eyebrow">
                <span /> CURATED FOR YOUR EVERYDAY
              </div>
              <h1>
                找到刚刚好的
                <br />
                <em>日常好物。</em>
              </h1>
              <p>
                从城市通勤，到周末山野。
                <br />
                让每一次寻找，都更懂你的生活。
              </p>
              <div className="hero-actions">
                <Button
                  onClick={() => {
                    reset();
                    setView("discover");
                    catalog.current?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  探索日常灵感 <ArrowUpRight size={17} />
                </Button>
                <button className="hero-ai" onClick={() => askAssistant()}>
                  <Sparkles size={15} />让 AI 帮我找
                </button>
              </div>
            </div>
            <div className="hero-image-caption">
              <span>THE NEW EVERYDAY</span>
              <strong>AIR FORM / 01</strong>
              <span>
                轻一点，走得更自在。
                <ArrowUpRight size={14} />
              </span>
            </div>
            <span className="hero-index">01 — 03</span>
          </section>
        )}
        {view !== "favorites" && (
          <div className="benefits">
            <span>
              <Search size={15} />
              说出需求，发现更多可能
            </span>
            <i />
            <span>
              <Scale size={16} />
              好物对比，选择更从容
            </span>
            <i />
            <span>
              <Sparkles size={15} />
              AI 陪你，找到心动那件
            </span>
          </div>
        )}
        <section className="catalog" ref={catalog}>
          <div className="catalog-intro">
            <div>
              <span className="eyebrow">
                {view === "favorites"
                  ? "SAVED FOR LATER"
                  : view === "newest"
                    ? "JUST LANDED"
                    : "FIND SOMETHING YOU LOVE"}
              </span>
              <h2>
                {view === "favorites"
                  ? "把喜欢的，留在这里。"
                  : view === "newest"
                    ? "新鲜上架，日常上新。"
                    : "为日常，多一点喜欢。"}
              </h2>
            </div>
            <span className="catalog-intro-note">
              {view === "favorites"
                ? `${favorites.length} 件心动好物`
                : `${facets?.total ?? "—"} 件好物，等你发现`}
              <ArrowDown size={15} />
            </span>
          </div>
          {view !== "favorites" && (
            <>
              <form
                className="search-bar"
                onSubmit={(event) => {
                  event.preventDefault();
                  runSearch();
                }}
              >
                <Search size={21} strokeWidth={1.7} />
                <input
                  ref={searchInput}
                  aria-label="搜索商品"
                  maxLength={200}
                  value={input}
                  placeholder="搜索好物，或直接说出你的需求：500 元以内的白色通勤鞋"
                  onChange={(event) => setInput(event.target.value)}
                />
                {input && (
                  <button
                    type="button"
                    className="clear-search"
                    aria-label="清空搜索内容"
                    onClick={() => {
                      setInput("");
                      if (query) {
                        setQuery("");
                        setPage(1);
                      }
                    }}
                  >
                    <X size={16} />
                  </button>
                )}
                <Button type="submit" variant="blue">
                  搜索好物
                  <ArrowRight size={17} />
                </Button>
              </form>
              <div className="search-suggestions">
                <span>灵感搜索</span>
                {["白色通勤鞋", "轻量徒步鞋", "500 元以内", "通勤双肩包"].map(
                  (suggestion) => (
                    <button
                      key={suggestion}
                      onClick={() => {
                        setFilters(defaultFilters);
                        runSearch(suggestion);
                      }}
                    >
                      {suggestion}
                      <ArrowUpRight size={12} />
                    </button>
                  ),
                )}
                <button
                  className="search-ai-link"
                  onClick={() => askAssistant()}
                >
                  <Sparkles size={13} />
                  需求有点复杂？问问 AI
                </button>
              </div>
              <div
                className="category-tabs"
                role="tablist"
                aria-label="商品分类"
              >
                {categories.map((category) => (
                  <button
                    role="tab"
                    aria-selected={
                      (filters.category ?? null) === category.value
                    }
                    className={
                      (filters.category ?? null) === category.value
                        ? "active"
                        : ""
                    }
                    key={category.name}
                    onClick={() =>
                      changeFilters({ ...filters, category: category.value })
                    }
                  >
                    {category.name}
                    {category.value === null && (
                      <span>{facets?.total ?? ""}</span>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
          <div
            className={`catalog-layout ${view === "favorites" ? "favorites-layout" : ""}`}
          >
            {view !== "favorites" && (
              <div className="desktop-filters">
                <FilterPanel
                  filters={filters}
                  facets={facets}
                  onChange={changeFilters}
                  onReset={reset}
                />
              </div>
            )}
            <div className="catalog-results">
              <div className="results-toolbar">
                <div>
                  <span>
                    {query
                      ? `“${query}”`
                      : view === "favorites"
                        ? "我的心愿清单"
                        : "精选好物"}
                  </span>
                  <small>
                    {loading ? "正在寻找…" : `共 ${result?.total ?? 0} 件`}
                  </small>
                </div>
                <div className="results-actions">
                  {view !== "favorites" && (
                    <button
                      className="mobile-filter-button"
                      onClick={() => setMobileFilters(true)}
                    >
                      <SlidersHorizontal size={15} />
                      筛选{activeCount > 0 && <span>{activeCount}</span>}
                    </button>
                  )}
                  <label className="sort-label">
                    <span className="sr-only">商品排序</span>
                    <select
                      aria-label="商品排序"
                      value={sort}
                      onChange={(event) => {
                        setSort(event.target.value as SortOrder);
                        setPage(1);
                      }}
                    >
                      <option value="relevance">综合推荐</option>
                      <option value="newest">最新上架</option>
                      <option value="price_asc">价格从低到高</option>
                      <option value="price_desc">价格从高到低</option>
                    </select>
                  </label>
                </div>
              </div>
              {activeCount > 0 && view !== "favorites" && (
                <div className="active-filters">
                  {filters.brand && (
                    <button
                      onClick={() => changeFilters({ ...filters, brand: null })}
                    >
                      {filters.brand}
                      <X size={12} />
                    </button>
                  )}
                  {filters.color && (
                    <button
                      onClick={() => changeFilters({ ...filters, color: null })}
                    >
                      {filters.color}
                      <X size={12} />
                    </button>
                  )}
                  {filters.max_price != null && (
                    <button
                      onClick={() =>
                        changeFilters({
                          ...filters,
                          max_price: null,
                          min_price: null,
                        })
                      }
                    >
                      预算 ¥{filters.max_price} 内<X size={12} />
                    </button>
                  )}
                  {filters.exclude_tags?.map((tag) => (
                    <button
                      key={tag}
                      onClick={() =>
                        changeFilters({
                          ...filters,
                          exclude_tags: filters.exclude_tags?.filter(
                            (value) => value !== tag,
                          ),
                        })
                      }
                    >
                      不要{tag}
                      <X size={12} />
                    </button>
                  ))}
                </div>
              )}
              {error ? (
                <div className="empty-state" role="alert">
                  <SearchX size={36} />
                  <h3>好物暂时走丢了</h3>
                  <p>{error}</p>
                  <Button
                    variant="secondary"
                    onClick={() => setRevision((value) => value + 1)}
                  >
                    <RotateCcw size={15} />
                    重新加载
                  </Button>
                </div>
              ) : loading ? (
                <div
                  className="product-grid"
                  aria-label="正在加载商品"
                  aria-busy="true"
                >
                  {Array.from({ length: 9 }, (_, index) => (
                    <div className="skeleton-card" key={index}>
                      <div />
                      <span />
                      <span />
                      <small />
                    </div>
                  ))}
                </div>
              ) : result?.products.length ? (
                <>
                  <div className="product-grid">
                    {result.products.map((product) => (
                      <ProductCard
                        key={product.id}
                        product={product}
                        favorite={favorites.includes(product.id)}
                        selected={selected.some(
                          (item) => item.id === product.id,
                        )}
                        onOpen={openProduct}
                        onFavorite={toggleFavorite}
                        onCompare={toggleCompare}
                      />
                    ))}
                  </div>
                  {result.meta.notices.length > 0 && (
                    <p className="search-service-note">
                      部分智能搜索能力暂不可用，已显示按当前条件检索的商品。
                    </p>
                  )}
                  {pageCount > 1 && (
                    <div className="pagination">
                      <span>
                        第 {page} 页 / 共 {pageCount} 页
                      </span>
                      <div>
                        <button
                          aria-label="上一页"
                          disabled={page === 1}
                          onClick={() => setPage((value) => value - 1)}
                        >
                          <ChevronLeft size={17} />
                        </button>
                        {Array.from(
                          { length: Math.min(5, pageCount) },
                          (_, index) =>
                            Math.max(1, Math.min(page - 2, pageCount - 4)) +
                            index,
                        ).map((value) => (
                          <button
                            key={value}
                            className={page === value ? "active" : ""}
                            aria-label={`第 ${value} 页`}
                            aria-current={page === value ? "page" : undefined}
                            onClick={() => setPage(value)}
                          >
                            {value}
                          </button>
                        ))}
                        {pageCount > 5 && page < pageCount - 2 && (
                          <span>…</span>
                        )}
                        <button
                          aria-label="下一页"
                          disabled={page === pageCount}
                          onClick={() => setPage((value) => value + 1)}
                        >
                          <ChevronRight size={17} />
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="empty-state">
                  {view === "favorites" ? (
                    <Heart size={38} />
                  ) : (
                    <SearchX size={38} />
                  )}
                  <h3>
                    {view === "favorites"
                      ? "喜欢的好物，值得留个位置。"
                      : "还没找到刚刚好的那件"}
                  </h3>
                  <p>
                    {view === "favorites"
                      ? "点一下商品上的爱心，把心动慢慢收集起来。"
                      : "试试减少筛选条件，或让 AI 陪你换个角度找找。"}
                  </p>
                  <Button
                    variant="secondary"
                    onClick={() => {
                      if (view === "favorites") navigate("discover");
                      else reset();
                    }}
                  >
                    {view === "favorites" ? "去发现好物" : "清空筛选条件"}
                    <ArrowRight size={15} />
                  </Button>
                </div>
              )}
            </div>
          </div>
        </section>
        <section className="assistant-banner">
          <div className="banner-sparkle">
            <Sparkles size={28} strokeWidth={1.3} />
          </div>
          <div>
            <span className="eyebrow">A LITTLE HELP, A BETTER FIND</span>
            <h2>还没有灵感？把想法交给寻物。</h2>
            <p>预算、风格、使用场景，说说你的想法，一起找到答案。</p>
          </div>
          <Button variant="secondary" onClick={() => askAssistant()}>
            开启我的选购对话
            <ArrowUpRight size={17} />
          </Button>
        </section>
      </main>
      <footer className="site-footer">
        <div>
          <span className="footer-wordmark">
            SEEK<span>寻物</span>
          </span>
          <p>愿每一次寻找，都恰好心动。</p>
        </div>
        <div>
          <span>为日常而选，为喜欢而寻。</span>
          <small>演示空间 · 商品与规格均为模拟信息 · 不提供交易</small>
        </div>
      </footer>
      {!chatOpen && (
        <button className="chat-launcher" onClick={() => askAssistant()}>
          <span>
            <Sparkles size={21} />
          </span>
          <span>
            选购有疑问？<strong>问问寻物 AI</strong>
          </span>
          <ArrowUpRight size={17} />
        </button>
      )}
      {selected.length > 0 && (
        <div className="compare-bar">
          <span className="compare-bar-icon">
            <Scale size={20} />
          </span>
          <div className="compare-thumbnails">
            {selected.map((product) => (
              <button
                key={product.id}
                onClick={() => toggleCompare(product)}
                aria-label={`移出对比 ${product.name}`}
              >
                <img src={product.image} alt={product.name} />
                <span>
                  <X size={10} />
                </span>
              </button>
            ))}
          </div>
          <span className="compare-count">已选 {selected.length} / 3 件</span>
          <Button
            size="small"
            disabled={selected.length < 2 || compareLoading}
            onClick={() => void showComparison()}
          >
            {compareLoading ? (
              <LoaderCircle className="spin" size={15} />
            ) : (
              <Scale size={15} />
            )}
            开始对比
          </Button>
          <button
            className="compare-clear"
            aria-label="清空对比列表"
            onClick={() => setSelected([])}
          >
            <X size={18} />
          </button>
        </div>
      )}
      {toast && (
        <div className="toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
      <ProductDialog
        product={detail}
        favorite={Boolean(detail && favorites.includes(detail.id))}
        selected={Boolean(
          detail && selected.some((product) => product.id === detail.id),
        )}
        onClose={() => setDetail(null)}
        onFavorite={toggleFavorite}
        onCompare={toggleCompare}
        onAsk={askAssistant}
      />
      <CompareDialog
        comparison={comparison}
        onClose={() => setComparison(null)}
      />
      <ChatPanel
        open={chatOpen}
        prompt={chatPrompt}
        onClose={() => setChatOpen(false)}
        onProduct={openProduct}
        onComparison={setComparison}
      />
      <Dialog.Root open={mobileFilters} onOpenChange={setMobileFilters}>
        <Dialog.Portal>
          <Dialog.Overlay className="dialog-overlay" />
          <Dialog.Content
            className="mobile-filter-dialog"
            aria-describedby="filter-dialog-description"
          >
            <Dialog.Title>找到适合你的好物</Dialog.Title>
            <Dialog.Description
              id="filter-dialog-description"
              className="sr-only"
            >
              按预算、品牌、颜色和偏好筛选商品
            </Dialog.Description>
            <Dialog.Close className="dialog-close" aria-label="关闭筛选">
              <X size={20} />
            </Dialog.Close>
            <FilterPanel
              filters={filters}
              facets={facets}
              onChange={changeFilters}
              onReset={reset}
            />
            <Button
              className="mobile-filter-done"
              onClick={() => setMobileFilters(false)}
            >
              查看筛选结果
              <ArrowRight size={16} />
            </Button>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </>
  );
}
