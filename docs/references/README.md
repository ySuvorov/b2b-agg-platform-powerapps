# UI Reference Screenshots

Source: https://www.media5.com/case/michelin/

These screenshots are from the original Michelin B2B portal project by Media5
and serve as the **visual and functional reference** for the Buyer Code App
(`/search` page). They define which fields to display and how to structure
the two-level results table.

## Files

| File | Contents |
|---|---|
| `michelin-ui-search.webp` | Search form with filters (Параметры, Сезон) + results table with expanded warehouse rows + Season/Additional filter popups |
| `michelin-ui-results.webp` | Full app layout in context + product detail modal + Popular sizes quick-pick panel |

---

## Search form — fields to implement

### Block: Параметры (tire size)

| Field | Input type | Maps to |
|---|---|---|
| Ширина (Width) | dropdown | `b2b_canonicalproduct.b2b_width` |
| Профиль (Profile) | dropdown | `b2b_canonicalproduct.b2b_profile` |
| Диаметр R (Diameter) | dropdown | `b2b_canonicalproduct.b2b_diameter` |

> **NOT implemented (demo scope cut):** second spare-tire size row.

### Block: Сезон (Season) — checkboxes

| Label | Maps to `b2b_season` value |
|---|---|
| Зимние (шип) | WinterStudded |
| Зимние (нешип) | WinterFriction |
| Летние | Summer |
| Всесезон | AllSeason |

> **NOT implemented (demo scope cut):** "Дополнительно" block
> (XL, RunFlat, FR, С, Усиленная).

### Filter bar (applied to results)

| Label | Filters on |
|---|---|
| Город | `b2b_warehouse.b2b_city` |
| Бренды | `b2b_canonicalproduct.b2b_brand` |
| Год | `b2b_supplieroffer.b2b_year` |
| Поставщики | `b2b_supplier.b2b_name` (via warehouse) |

### Quick-pick: Popular sizes matrix

Grid of common sizes grouped by diameter (R13–R21). Clicking a size pre-fills
Ширина / Профиль / Диаметр in the Параметры block. Static data, no Dataverse
query — computed from top N most-stocked canonical products in seed data.

---

## Results table — two levels

### Level 1: Canonical product row (collapsed)

| Column | Source | Notes |
|---|---|---|
| # | row counter | |
| БРЕНД | `b2b_canonicalproduct.b2b_brand` | sortable |
| МОДЕЛЬ | `b2b_canonicalproduct.b2b_model` | sortable |
| (photo) | `b2b_canonicalproduct.b2b_image` | thumbnail |
| ТИПОРАЗМЕР | calc: `width/profile R diameter` | sortable |
| ИНД. | calc: `loadindex + speedindex` e.g. "91T" | sortable |
| ОСТАТОК (шт.) | SUM of `b2b_supplieroffer.b2b_stock` across all matching warehouses | |
| ИСК. ЦЕНА (₽) | MIN of `b2b_supplieroffer.b2b_price` | |
| СВОЯ ЦЕНА (₽) | MIN of `b2b_supplieroffer.b2b_buyerprice` | nullable |
| (cart icon) | add to cart action | |

### Level 2: Warehouse offer row (on row expand)

| Column | Source | Notes |
|---|---|---|
| ПОСТАВЩИК | `b2b_supplier.b2b_name` (via warehouse) | with city sub-filter |
| СКЛАД | `b2b_warehouse.b2b_name` | |
| ГОД | `b2b_supplieroffer.b2b_year` | year of manufacture |
| СТРАНА | `b2b_supplieroffer.b2b_country` | |
| ДОСТАВКА (дн.) | `b2b_supplieroffer.b2b_leaddays` | |
| АКТУАЛЬНОСТЬ | `b2b_supplieroffer.b2b_stockdate` | date stock was confirmed |
| ОСТАТОК (шт.) | `b2b_supplieroffer.b2b_stock` | |
| ИСК. ЦЕНА (₽) | `b2b_supplieroffer.b2b_price` | |
| СВОЯ ЦЕНА (₽) | `b2b_supplieroffer.b2b_buyerprice` | |

---

## Product detail modal (click on warehouse row)

Header: `{brand} {model} {size}` + offer count

| Field | Source |
|---|---|
| ПОСТАВЩИК | `b2b_supplier.b2b_name` |
| АКТУАЛЬНОСТЬ | `b2b_supplieroffer.b2b_stockdate` |
| СКЛАД (column) | `b2b_warehouse.b2b_name` |
| ГОД | `b2b_supplieroffer.b2b_year` |
| СТРАНА | `b2b_supplieroffer.b2b_country` |
| ДОСТ. (дн.) | `b2b_supplieroffer.b2b_leaddays` |
| ИСК. ЦЕНА | `b2b_supplieroffer.b2b_price` |
| СВОЯ ЦЕНА | `b2b_supplieroffer.b2b_buyerprice` |
| ОСТАТОК (шт.) | `b2b_supplieroffer.b2b_stock` |
| ИТОГО | qty × price |

Footer: `N поставщиков | M шт. | X ₽` + **Добавить в корзину** button.
