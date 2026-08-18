// web/src/router/index.ts — 路由（開發規格 003 §2.12）
// GitHub Pages SPA：createWebHashHistory()（重新整理不 404，deep link 相容）
import { createRouter, createWebHashHistory } from "vue-router"
import ListingView from "@/views/ListingView.vue"

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", name: "listing", component: ListingView },
    // 017：Dashboard 頁面（懶載入，<10KB gzipped）
    { path: "/dashboard", name: "dashboard", component: () => import("@/views/DashboardView.vue") },
    // 004：商品詳情頁（/product/:id；id 為 hex，仍以 encodeURIComponent 防呆）
    // 懶載入：詳情頁帶 lightweight-charts，動態 import 拆成獨立 chunk，列表頁首屏不背圖表庫
    { path: "/product/:id", name: "product-detail", component: () => import("@/views/ProductDetailView.vue") },
    { path: "/watchlist", name: "watchlist", component: () => import("@/views/WatchlistView.vue") },
    { path: "/compare", name: "compare", component: () => import("@/views/CompareView.vue") },
  ],
})
