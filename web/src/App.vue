<script setup lang="ts">
// web/src/App.vue — 全站外框（頂部 header + <router-view>）（開發規格 003 §2.1）
import { ref, computed, onMounted } from "vue"
import CompareBar from "@/components/CompareBar.vue"
import { useWatchlist } from "@/composables/useWatchlist"

const dark = ref(false)
const { items: watchlistItems } = useWatchlist()
const watchlistCount = computed(() => watchlistItems.value.length)

function applyTheme(v: boolean) {
  dark.value = v
  document.documentElement.dataset.theme = v ? "dark" : "light"
}

onMounted(() => {
  // 預設尊重系統偏好；手動切換後以 localStorage 記住
  const saved = localStorage.getItem("coolpc-theme")
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches
  applyTheme(saved ? saved === "dark" : prefersDark)
})

function toggleTheme() {
  applyTheme(!dark.value)
  localStorage.setItem("coolpc-theme", dark.value ? "dark" : "light")
}
</script>

<template>
  <div class="app">
    <header class="app-header">
      <div class="app-header-inner">
        <a class="app-logo" href="#/" aria-label="CoolPC Tracker 首頁">
          <span class="logo-badge" aria-hidden="true">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 3v18h18" />
              <path d="M7 14l4-4 3 3 5-6" />
            </svg>
          </span>
          CoolPC Tracker
        </a>
        <span class="app-sub">原價屋商品價格追蹤</span>
        <div class="app-header-right">
          <router-link to="/dashboard" class="nav-dashboard-link">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <rect x="3" y="3" width="7" height="7" />
              <rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
            </svg>
            <span>Dashboard</span>
          </router-link>
          <router-link to="/watchlist" class="watchlist-link">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
            <span>我的追蹤</span>
            <span v-if="watchlistCount > 0" class="watchlist-badge">{{ watchlistCount }}</span>
          </router-link>
          <button
            class="theme-btn"
            type="button"
            :aria-pressed="dark"
            @click="toggleTheme"
          >
            <svg v-if="!dark" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" />
            </svg>
            <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="5" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
            <span>{{ dark ? "切換淺色" : "切換深色" }}</span>
          </button>
        </div>
      </div>
    </header>

    <router-view />
    <CompareBar />
  </div>
</template>
