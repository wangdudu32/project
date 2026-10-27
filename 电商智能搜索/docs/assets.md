# 图片与字体

商品、价格、品牌与规格为模拟数据；商品图片仅作风格示意，不表示图片中的真实产品具有模拟规格，也不表示与图片品牌存在合作。

## 商品图片

来自 Unsplash，下载后保存在 `frontend/public/images/`，各文件原始地址记录在 `data/image_sources.json`。数据生成脚本不会在图片已经存在时重复下载。来源许可说明见 <https://unsplash.com/license>。

## 首页主视觉

- 文件：`frontend/public/images/hero.png`
- 尺寸：1536 × 1024
- 使用内置 imagegen 工具生成，未通过项目 `.env` 中的密钥调用图片 API。
- 用途：首页编辑式商品主视觉，不对应真实在售 SKU。

生成提示词：

```text
Use case: product-mockup. Asset type: hero photograph for a polished Chinese sneaker and outdoor shopping application. Create a photoreal premium studio product photograph in a wide landscape composition. Main subject: one unbranded modern ivory running sneaker, cobalt-blue textile panels and subtle lime-green detail, detailed mesh and sculpted cream sole, side view with toe pointing left and slightly floating above a small warm-grey stone pedestal. A second slightly blurred sneaker in the far right background. Warm off-white seamless studio background, soft daylight shadows, tasteful editorial art direction, actual believable materials, no people. Position the featured shoe in the right two thirds, some clean space left. Palette ivory, warm light grey, vivid blue accents. No letters, no text, no logos, no watermark, no UI. Output landscape approximately 1536x1024.
```

## 字体与图标

- 中文字体：`@fontsource-variable/noto-sans-sc`，通过 npm 安装并随 Vite 构建分片打包，不依赖系统中文字库。
- 字体遵循 SIL Open Font License，副本见 `font-license.txt`。
- 界面图标：`lucide-react`。
- 网站小图标由项目原生 SVG 编写。
