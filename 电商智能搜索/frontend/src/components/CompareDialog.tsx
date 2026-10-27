import * as Dialog from "@radix-ui/react-dialog";
import { Scale, X } from "lucide-react";
import { money, type Comparison } from "../api";

type Props = { comparison: Comparison | null; onClose: () => void };

export function CompareDialog({ comparison, onClose }: Props) {
  return (
    <Dialog.Root
      open={Boolean(comparison)}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content
          className="compare-dialog"
          aria-describedby="compare-description"
        >
          <Dialog.Close className="dialog-close" aria-label="关闭商品对比">
            <X size={20} />
          </Dialog.Close>
          <div className="dialog-eyebrow">
            <Scale size={17} /> FIND YOUR BETTER FIT
          </div>
          <Dialog.Title>好物放一起，选择更清晰。</Dialog.Title>
          <Dialog.Description id="compare-description">
            比较实际记录的商品属性，找到更适合你的那一件。
          </Dialog.Description>
          {comparison && (
            <div className="comparison-scroll">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>商品</th>
                    {comparison.products.map((product) => (
                      <th key={product.id}>
                        <img src={product.image} alt={product.name} />
                        <span>{product.brand}</span>
                        <strong>{product.name}</strong>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {comparison.rows.map((row) => (
                    <tr key={row.label}>
                      <th scope="row">{row.label}</th>
                      {row.values.map((value, index) => (
                        <td key={index}>
                          {Array.isArray(value)
                            ? value.join(" / ")
                            : row.label === "价格"
                              ? `¥${money(Number(value))}`
                              : value}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="demo-note">
            商品与规格均为模拟数据，图片仅作风格示意。
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
