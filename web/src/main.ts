// web/src/main.ts — 003 起：createApp + router 掛載（取代 002 最小消費實作）
// 002 的資料版本顯示移入 App.vue header（__DATA_VERSION__ build 期注入）
/// <reference types="vite/client" />

import { createApp } from "vue"
import { router } from "@/router"
import App from "@/App.vue"
import "@/styles/tokens.css"

const app = createApp(App)
app.use(router)
app.mount("#app")

// 供 header/除錯顯示（build 期注入的資料版本號）
;(window as unknown as { __DATA_VERSION__?: string }).__DATA_VERSION__ = __DATA_VERSION__
