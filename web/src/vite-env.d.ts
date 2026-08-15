/// <reference types="vite/client" />

/** 002 §1.7 合約：build 期注入的資料版本號（vite.config.ts `define.__DATA_VERSION__`，
 *  由 ../data/meta.json 的 version 驅動；本地無資料檔時為 0）。
 *  useItems 以此組出版本化資料檔路徑 data/items.v{n}.json。 */
declare const __DATA_VERSION__: string
