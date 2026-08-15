// web/src/router/index.ts — 路由（開發規格 003 §2.12）
// GitHub Pages SPA：createWebHashHistory()（重新整理不 404，deep link 相容）
import { createRouter, createWebHashHistory } from "vue-router"
import ListingView from "@/views/ListingView.vue"
import ProductDetailView from "@/views/ProductDetailView.vue"

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", name: "listing", component: ListingView },
    // 004：商品詳情頁（/product/:id；id 為 hex，仍以 encodeURIComponent 防呆）
    { path: "/product/:id", name: "product-detail", component: ProductDetailView },
  ],
})
