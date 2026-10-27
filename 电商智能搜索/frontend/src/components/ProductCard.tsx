import { ArrowUpRight, Check, Heart, Scale } from "lucide-react";
import { money, type Product } from "../api";

type Props = {
  product: Product;
  favorite: boolean;
  selected: boolean;
  onOpen: (product: Product) => void;
  onFavorite: (product: Product) => void;
  onCompare: (product: Product) => void;
};

export function ProductCard({
  product,
  favorite,
  selected,
  onOpen,
  onFavorite,
  onCompare,
}: Props) {
  return (
    <article className="product-card">
      <div className="product-image-wrap">
        <button
          className="product-image-button"
          onClick={() => onOpen(product)}
          aria-label={`查看 ${product.name}`}
        >
          <img
            src={product.image}
            alt={product.name}
            loading="lazy"
            onError={(event) => {
              event.currentTarget.src = "/images/hero.png";
            }}
          />
        </button>
        <span className="product-label">
          {product.tags.includes("轻量")
            ? "轻量之选"
            : product.tags.includes("复古")
              ? "复古日常"
              : "日常灵感"}
        </span>
        <button
          className={`favorite-button ${favorite ? "is-favorite" : ""}`}
          aria-label={`${favorite ? "取消收藏" : "收藏"} ${product.name}`}
          aria-pressed={favorite}
          onClick={() => onFavorite(product)}
        >
          <Heart
            size={17}
            fill={favorite ? "currentColor" : "none"}
            strokeWidth={1.6}
          />
        </button>
        <button className="quick-view" onClick={() => onOpen(product)}>
          探索这件好物 <ArrowUpRight size={15} />
        </button>
      </div>
      <div className="product-info">
        <span className="product-brand">{product.brand}</span>
        <button className="product-title" onClick={() => onOpen(product)}>
          {product.name}
        </button>
        <div className="product-subtitle">
          {product.color_label}
          <span>·</span>
          {product.tags.slice(0, 2).join(" / ")}
        </div>
        <div className="product-bottom">
          <div className="price">
            <span>¥</span>
            {money(product.price)}
            <del>¥{money(product.original_price)}</del>
          </div>
          <button
            className={`compare-toggle ${selected ? "is-selected" : ""}`}
            aria-label={`${selected ? "移出对比" : "加入对比"} ${product.name}`}
            aria-pressed={selected}
            onClick={() => onCompare(product)}
          >
            {selected ? <Check size={15} /> : <Scale size={16} />}
            <span>对比</span>
          </button>
        </div>
      </div>
    </article>
  );
}
