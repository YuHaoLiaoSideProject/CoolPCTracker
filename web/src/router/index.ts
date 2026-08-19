// web/src/router/index.ts — 路由（開發規格 003 §2.12）
// GitHub Pages SPA：createWebHashHistory()（重新整理不 404，deep link 相容）
import { createRouter, createWebHashHistory } from "vue-router"
export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", name: "home", component: () => import("@/views/HomeView.vue") },
    // 024：/dashboard 重導向至首頁（已合併為統一頁面）
    { path: "/dashboard", redirect: "/" },
    // 004：商品詳情頁（/product/:id；id 為 hex，仍以 encodeURIComponent 防呆）
    // 懶載入：詳情頁帶 lightweight-charts，動態 import 拆成獨立 chunk，列表頁首屏不背圖表庫
    { path: "/product/:id", name: "product-detail", component: () => import("@/views/ProductDetailView.vue") },
    { path: "/watchlist", name: "watchlist", component: () => import("@/views/WatchlistView.vue") },
    { path: "/compare", name: "compare", component: () => import("@/views/CompareView.vue") },
  ],
})
