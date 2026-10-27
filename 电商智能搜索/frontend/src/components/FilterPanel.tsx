import { Check, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useEffect, useId, useState } from "react";
import type { Facets, Filters } from "../api";
import { Button } from "./Button";

export const colorValues: Record<string, string> = {
  白色: "#f7f5ee",
  黑色: "#292a2d",
  灰色: "#a1a3a6",
  蓝色: "#5270ad",
  绿色: "#7c896c",
  棕色: "#b89a7b",
};

type Props = {
  filters: Filters;
  facets: Facets | null;
  onChange: (filters: Filters) => void;
  onReset: () => void;
};

export function FilterPanel({ filters, facets, onChange, onReset }: Props) {
  const brandGroup = useId();
  const [minimum, setMinimum] = useState("");
  const [maximum, setMaximum] = useState("");
  const [priceError, setPriceError] = useState("");
  useEffect(() => {
    setMinimum(filters.min_price?.toString() ?? "");
    setMaximum(filters.max_price?.toString() ?? "");
  }, [filters.min_price, filters.max_price]);

  function applyPrice() {
    const low = minimum === "" ? null : Number(minimum);
    const high = maximum === "" ? null : Number(maximum);
    if (
      (low !== null && (!Number.isFinite(low) || low < 0)) ||
      (high !== null && (!Number.isFinite(high) || high < 0)) ||
      (low !== null && high !== null && low > high)
    ) {
      setPriceError("请输入有效的价格范围");
      return;
    }
    setPriceError("");
    onChange({ ...filters, min_price: low, max_price: high });
  }

  return (
    <aside className="filter-panel" aria-label="商品筛选">
      <div className="filter-heading">
        <span>
          <SlidersHorizontal size={16} /> 筛选好物
        </span>
        <button onClick={onReset} aria-label="重置全部筛选">
          <RotateCcw size={14} /> 重置
        </button>
      </div>
      <section className="filter-section">
        <h3>
          你的预算 <span>PRICE RANGE</span>
        </h3>
        <div className="price-inputs">
          <label>
            <span>¥</span>
            <input
              aria-label="最低价格"
              type="number"
              min="0"
              max="100000"
              placeholder="最低"
              value={minimum}
              onChange={(event) => setMinimum(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") applyPrice();
              }}
            />
          </label>
          <span>—</span>
          <label>
            <span>¥</span>
            <input
              aria-label="最高价格"
              type="number"
              min="0"
              max="100000"
              placeholder="最高"
              value={maximum}
              onChange={(event) => setMaximum(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") applyPrice();
              }}
            />
          </label>
        </div>
        {priceError && (
          <p className="field-error" role="alert">
            {priceError}
          </p>
        )}
        <Button
          variant="secondary"
          size="small"
          className="price-apply"
          onClick={applyPrice}
        >
          应用价格范围
        </Button>
        <div className="budget-presets">
          {[300, 500, 800].map((price) => (
            <button
              key={price}
              className={filters.max_price === price ? "active" : ""}
              onClick={() =>
                onChange({ ...filters, min_price: null, max_price: price })
              }
            >
              ¥{price} 内
            </button>
          ))}
        </div>
      </section>
      <section className="filter-section">
        <h3>
          喜欢的品牌 <span>BRANDS</span>
        </h3>
        <div className="brand-list">
          <label>
            <input
              type="radio"
              name={brandGroup}
              checked={!filters.brand}
              onChange={() => onChange({ ...filters, brand: null })}
            />
            <span>全部品牌</span>
          </label>
          {facets?.brands.map((brand) => (
            <label key={brand}>
              <input
                type="radio"
                name={brandGroup}
                checked={filters.brand === brand}
                onChange={() => onChange({ ...filters, brand })}
              />
              <span>{brand}</span>
            </label>
          ))}
        </div>
      </section>
      <section className="filter-section">
        <h3>
          心动的颜色 <span>COLORS</span>
        </h3>
        <div className="color-list">
          {Object.entries(colorValues).map(([name, color]) => (
            <button
              key={name}
              className={`color-choice ${filters.color === name ? "active" : ""}`}
              aria-label={`筛选${name}`}
              aria-pressed={filters.color === name}
              onClick={() =>
                onChange({
                  ...filters,
                  color: filters.color === name ? null : name,
                })
              }
            >
              <span className="color-swatch" style={{ background: color }}>
                {filters.color === name && (
                  <Check
                    size={13}
                    color={
                      name === "黑色" || name === "蓝色" ? "white" : "#292a2d"
                    }
                  />
                )}
              </span>
              <span>{name}</span>
            </button>
          ))}
        </div>
      </section>
      <section className="filter-section">
        <h3>
          再贴心一点 <span>PREFERENCES</span>
        </h3>
        <div className="preference-list">
          <label>
            <input
              type="checkbox"
              checked={filters.in_stock !== false}
              onChange={(event) =>
                onChange({ ...filters, in_stock: event.target.checked })
              }
            />
            <span>只看有库存</span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={filters.exclude_tags?.includes("厚底") ?? false}
              onChange={(event) =>
                onChange({
                  ...filters,
                  exclude_tags: event.target.checked
                    ? [...(filters.exclude_tags ?? []), "厚底"]
                    : filters.exclude_tags?.filter((tag) => tag !== "厚底"),
                })
              }
            />
            <span>不看厚底款</span>
          </label>
        </div>
      </section>
      <div className="filter-note">
        <span className="tiny-plus">✳</span>
        <p>
          选择不必将就。
          <br />
          让每件好物，都适合你。
        </p>
      </div>
    </aside>
  );
}
