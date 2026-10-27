import * as Dialog from "@radix-ui/react-dialog";
import { ArrowUpRight, Check, Heart, Scale, Sparkles, X } from "lucide-react";
import { money, type Product } from "../api";
import { Button } from "./Button";

type Props = {
  product: Product | null;
  favorite: boolean;
  selected: boolean;
  onClose: () => void;
  onFavorite: (product: Product) => void;
  onCompare: (product: Product) => void;
  onAsk: (message: string) => void;
};

export function ProductDialog({
  product,
  favorite,
  selected,
  onClose,
  onFavorite,
  onCompare,
  onAsk,
}: Props) {
  return (
    <Dialog.Root
      open={Boolean(product)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content
          className="product-dialog"
          aria-describedby="product-description"
        >
          {product && (
            <>
              <Dialog.Close className="dialog-close" aria-label="关闭商品详情">
                <X size={20} />
              </Dialog.Close>
              <div className="detail-image">
                <img src={product.image} alt={product.name} />
                <span className="detail-image-label">
                  THE EVERYDAY EDIT / SEEK
                </span>
              </div>
              <div className="detail-content">
                <div className="detail-brand">
                  {product.brand}
                  <ArrowUpRight size={17} />
                </div>
                <Dialog.Title>{product.name}</Dialog.Title>
                <div className="detail-price">
                  <span>¥{money(product.price)}</span>
                  <del>¥{money(product.original_price)}</del>
                </div>
                <div className="detail-tags">
                  {product.tags.map((tag) => (
                    <span key={tag}>{tag}</span>
                  ))}
                </div>
                <Dialog.Description id="product-description">
                  {product.description}
                </Dialog.Description>
                <dl className="detail-specs">
                  <div>
                    <dt>颜色</dt>
                    <dd>{product.color_label}</dd>
                  </div>
                  <div>
                    <dt>材质</dt>
                    <dd>{product.material}</dd>
                  </div>
                  <div>
                    <dt>重量</dt>
                    <dd>{product.weight}</dd>
                  </div>
                  <div>
                    <dt>库存</dt>
                    <dd>
                      {product.stock > 0 ? `${product.stock} 件` : "暂无库存"}
                    </dd>
                  </div>
                </dl>
                <div className="size-heading">
                  可选尺码<span>模拟尺码范围</span>
                </div>
                <div className="size-list">
                  {product.sizes.map((size) => (
                    <span key={size}>{size}</span>
                  ))}
                </div>
                <div className="detail-actions">
                  <Button
                    variant={selected ? "blue" : "primary"}
                    onClick={() => onCompare(product)}
                  >
                    {selected ? <Check size={17} /> : <Scale size={17} />}
                    {selected ? "已加入对比" : "加入商品对比"}
                  </Button>
                  <Button
                    variant="secondary"
                    size="icon"
                    aria-label={favorite ? "取消收藏" : "收藏商品"}
                    onClick={() => onFavorite(product)}
                  >
                    <Heart
                      size={18}
                      fill={favorite ? "currentColor" : "none"}
                    />
                  </Button>
                </div>
                <Button
                  variant="ghost"
                  className="detail-ask"
                  onClick={() => {
                    onAsk(
                      `帮我介绍商品 ${product.id}（${product.name}），它适合什么场景？`,
                    );
                    onClose();
                  }}
                >
                  <Sparkles size={16} />让 AI 帮我了解这件好物
                  <ArrowUpRight size={14} />
                </Button>
                <p className="demo-note">
                  模拟商品及参数 · 图片仅作风格示意 · 不提供交易
                </p>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
