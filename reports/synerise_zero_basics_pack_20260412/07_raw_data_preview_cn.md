# 第 7 课：原始数据长什么样

## 先说结论

这套原始数据不是“漂亮的业务表”，而是经过匿名化或编码处理的事件日志。

所以你看到的很多字段：

- 不是自然语言
- 不是可读 URL
- 也不是商品中文名

它们更像内部 ID 或编码字符串。

## 原始数据一共有哪些表

- `product_buy.parquet`
- `add_to_cart.parquet`
- `remove_from_cart.parquet`
- `page_visit.parquet`
- `search_query.parquet`
- `product_properties.parquet`

## 每张表的主要字段

### `product_buy.parquet`

- `client_id`
- `timestamp`
- `sku`

表示某个用户在某个时间买了某个商品。

### `add_to_cart.parquet`

- `client_id`
- `timestamp`
- `sku`

表示某个用户在某个时间把某个商品加入购物车。

### `remove_from_cart.parquet`

- `client_id`
- `timestamp`
- `sku`

表示某个用户在某个时间把某个商品移出购物车。

### `page_visit.parquet`

- `client_id`
- `timestamp`
- `url`

注意这里的 `url` 不是完整网页地址，而是数值型 ID。

### `search_query.parquet`

- `client_id`
- `timestamp`
- `query`

这个字段看起来像字符串，但里面的内容通常是类似 `[240 170 240 ...]` 这样的编码形式，不是直接可读的自然语言查询词。

### `product_properties.parquet`

- `sku`
- `category`
- `price`
- `name`

其中 `name` 也不是普通商品名，而是编码形式字符串。

## 为什么原始数据看起来不太“像电商数据”

因为比赛/公开数据集通常会做匿名化处理，避免直接暴露真实商品名、真实搜索词和真实页面地址。

这不会影响建模，因为：

- `sku` 还能做购买和加购统计
- `category` 还能做类目偏好
- `price` 还能做价格统计
- `query` 和 `name` 仍然可以做长度、词数或编码长度类特征

## 我给你准备了什么

为了方便你直接看，我在 `raw_data_preview_samples/` 目录里导出了每张表前 `100` 行的 `csv` 样例。

你可以直接用：

- Excel
- WPS 表格
- PyCharm

打开这些文件。

## 推荐你先看哪几个

建议先看：

1. `raw_data_preview_samples/product_buy_head100.csv`
2. `raw_data_preview_samples/add_to_cart_head100.csv`
3. `raw_data_preview_samples/page_visit_head100.csv`
4. `raw_data_preview_samples/product_properties_head100.csv`

这样最容易快速建立感觉。

## 这一课你应该记住什么

- 原始数据是事件日志，不是用户画像表
- 很多字段做了匿名化/编码处理
- 这不影响做 churn prediction
- 真正要做的是把这些事件日志聚合成用户级特征表
