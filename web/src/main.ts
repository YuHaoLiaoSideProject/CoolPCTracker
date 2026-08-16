// web/src/main.ts — 003 起：createApp + router 掛載（取代 002 最小消費實作）
/// <reference types="vite/client" />

import { createApp } from "vue"
import { router } from "@/router"
import App from "@/App.vue"
import "@/styles/tokens.css"

const app = createApp(App)
app.use(router)
app.mount("#app")
