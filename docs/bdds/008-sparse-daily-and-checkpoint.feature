# language: zh-TW
@crawler @sparse-daily @checkpoint @p0 @regression
Feature: 稀疏異動日誌 + 週全量 Checkpoint（008-sparse-daily-and-checkpoint）
  作為一個 系統維護者與每日排程系統
  我希望 data/daily/ 只存「價格/狀態真的異動的商品」（稀疏 delta）、平價日不寫入，並以每 7 天的全量快照 data/checkpoints/{YYYYMMDD}.json 作為歷史回溯錨點，version_data 以「最新 checkpoint + 回放 delta」逐日 carry forward 重建完整歷史
  以便 大幅縮減儲存與 git noise（daily 從 ~35KB/天降至 ~1-2KB/天），同時確保完整歷史可重建、且 delta 遺失時最多回放 7 天即可自癒

  Background:
    Given data/items/{g}.json 分類檔為最新狀態快照（g=1/3/4/5/6/7/8/9/12，純 items 陣列）
    And data/meta.json 記錄 crawled_at、各分類商品數與 status（ok/partial/failed）
    And store.diff 能將商品分類為 new_items / changed_items / refreshed_items / unchanged_ids / gone_ids / carryover_ids
    And 本功能保留 data/daily/ 檔名，但其語意改為「異動 delta」（docstring 註明），避免大量 refactor
    # 長度參考：舊全量 daily 檔 ~35KB/天（~1440 筆）；稀疏 delta 檔 ~1-2KB/天；每 7 天一檔全量 checkpoint 等同舊 daily 全量格式

  @smoke @happy-path @p0
  Scenario: 價格異動日僅寫入異動與新增商品（稀疏 delta）
    Given 今日解析後共 1449 筆商品
    And 其中 3 筆價格或狀態真正異動（changed_items）、2 筆為新商品（new_items）
    And 其餘商品為平價（unchanged_ids）或失敗分類 carryover
    When 爬蟲執行 diff 並呼叫 store.write_daily(今日, 異動價格清單)
    Then data/daily/{今日}.json 被寫入且只含 5 筆（3 異動 + 2 新增，且價格皆存在）
    And 每筆為 {item_id: price} 格式（compact JSON）
    And 平價商品（unchanged_ids）與 carryover 商品不被寫入當日 daily 檔

  @happy-path @p0
  Scenario: 平價日（無任何異動與新增）不產生額外 daily 寫入，避免 git noise
    Given 今日所有成功爬取商品價格與狀態皆與昨日完全相同（0 異動、0 新增）
    When 爬蟲執行完畢並呼叫 store.write_daily
    Then data/daily/{今日}.json 不存在或為空（無新 daily 檔產生）
    And git diff 不因平價日而增加整檔 noise（~35KB）
    And data/items/{g}.json 與 data/meta.json 仍正常更新（狀態快照保持最新）

  @happy-path @p0
  Scenario: 距上次 checkpoint ≥ 7 天的當日寫入全量 checkpoint 快照
    Given 最近一次 checkpoint 為 7 天前（data/checkpoints/{C}.json 存在）
    And 今日已寫入稀疏 daily 檔
    When 爬蟲判斷今日為 checkpoint 日並呼叫 store.write_checkpoint
    Then data/checkpoints/{今日}.json 被寫入當日所有商品的全量價格 {id: price}
    And checkpoint 檔格式等同舊 daily 全量檔（可作為回放自癒錨點）
    And data/items/{g}.json 與 data/meta.json 照常更新

  @happy-path @p1
  Scenario: 所有 checkpoint 錨點 + 稀疏 delta 逐日 carry forward 重建完整歷史
    Given data/checkpoints/{C}.json 為最新全量快照（C 日）
    And data/daily/ 存在 C 日之後的稀疏異動檔 {C+1} 與 {C+2}
    When scripts/version_data.py 執行 build_trends
    Then 以 C 日 checkpoint 全量價格作為重建起點
    And 依序回放 C 日之後的 daily delta，未異動商品在前一值基礎上 carry forward
    And api/trends/{id}.json 的 history 依日期升冪、每日一點完整還原
    And build_trends 為純函數、可單測且冪等（同輸入 → 同輸出）

  @regression @p0
  Scenario: 遷移完成後首次 run 的 api/trends 與遷移前完全等價（equivalence test）
    Given 遷移前 api/trends/{id}.json 已由舊全量 daily 聚合產出（基準結果）
    When 遷移腳本執行完成後首次執行 crawler 與 version_data
    And 之後執行等價回歸測試（對比遷移前後 api/trends history）
    Then api/trends/{id}.json 的 history 與遷移前完全一致
    And 所有商品的遷移後歷史長度與逐點價格皆與遷移前一致

  @edge-case @boundary
  Scenario Outline: checkpoint 日門檻（距上次 ≥ 7 天）的邊界判定
    Given 最近一次 checkpoint 為 <daysAgo> 天前
    When 今日爬蟲成功執行並判斷是否為 checkpoint 日
    Then 判定<isCheckpoint> checkpoint 日
    And <writeBehavior>

    Examples:
      | daysAgo        | isCheckpoint | writeBehavior                                              |
      | 3 天前         | 非           | 不寫入 data/checkpoints/ 全量快照（僅寫稀疏 daily delta）    |
      | 6 天前         | 非           | 不寫入 data/checkpoints/ 全量快照                           |
      | 7 天前（邊界）  | 為           | 寫入 data/checkpoints/{今日}.json 全量快照                  |
      | 12 天前        | 為           | 寫入 data/checkpoints/{今日}.json 全量快照                  |

  @error-handling @p0
  Scenario: checkpoint 日當天爬取失敗（status=failed）時不覆寫 items、不寫 checkpoint
    Given 今天是距上次 checkpoint ≥ 7 天的 checkpoint 日
    And 爬蟲偵測到商品數驟降或解析異常（status=failed）
    When 爬蟲執行完畢
    Then data/checkpoints/{今日}.json 不被寫入
    And data/items/{g}.json 不被覆寫，維持既有資料
    And data/meta.json 解析狀態記錄為 failed
    And 下次成功 run 時再重新判斷 checkpoint 日

  @error-handling @p1
  Scenario: 某天 delta 檔遺失時，以 checkpoint + 其餘 delta 回放自癒，最多補回 7 天
    Given data/checkpoints/{C}.json 為最新全量快照（C 日）
    And data/daily/ 有 {C+2} 的 delta 檔，但 {C+1} 的 daily 檔遺失
    When scripts/version_data.py 執行 build_trends
    Then 跳過遺失的 {C+1} daily 檔
    And 以 C 日 checkpoint 為錨點回放其餘有效 delta
    And api/trends/{id}.json 仍可重建完整歷史，缺失片段最多 7 天
    And 不需人工介入；下一次全量 checkpoint 後即自癒

  @error-handling @p1
  Scenario: 某天 delta 檔損壞（無法解析）時跳過並以 checkpoint + 其餘 delta 重建，不崩潰
    Given data/checkpoints/{C}.json 有效
    And data/daily/ 的 {C+1}.json 無法解析（JSON 格式錯誤）
    When scripts/version_data.py 執行 build_trends
    Then 跳過損壞的 {C+1}.json（不中斷整體重建）
    And 以其餘有效 checkpoint + delta 正常產出 api/trends/{id}.json
    And 重建過程不拋例外、其餘商品歷史不受影響

  @business-rules @p0
  Scenario: 遷移腳本 seed checkpoint + 保留所有舊 daily
    Given 既有 data/daily/ 為舊全量檔（每檔含全商品 {id: price}）
    And data/checkpoints/ 尚不存在（首次遷移）
    When 維護者手動執行遷移腳本一次
    Then 以最舊的全量 daily 檔 seed checkpoint，寫入 data/checkpoints/{最舊日}.json
    And 保留所有既有舊全量 daily 檔作為 legacy 全量回放源（不刪除任何舊檔）
    And 既有資料不被破壞、不遺失

  @business-rules @p0
  Scenario: 遷移後首次執行以 checkpoint 為錨點回放 delta，結果與遷移前等價（回歸通過）
    Given 遷移腳本已完成（已建立 checkpoint + 所有舊 daily 保留為 legacy）
    And 遷移前 api/trends 結果已存為基準
    When 遷移後首次執行 crawler 與 version_data
    Then 以 data/checkpoints/ 為錨點、回放其後 delta（缺失日由 carry forward 補齊，無缺口）重建 api/trends
    And api/trends/{id}.json 與遷移前完全等價（BDD 回歸通過）

  @edge-case @p0
  Scenario: 首次執行且無任何 checkpoint 與 daily 檔時進入純新增模式
    Given data/checkpoints/ 與 data/daily/ 皆不存在（全新部署）
    And 今日解析的皆為新商品（new_items）
    When 首次執行爬蟲
    Then data/daily/{今日}.json 寫入全部新商品（稀疏，皆為 new_items）
    And 不因缺乏 checkpoint 錨點而失敗
    And 本次不寫 checkpoint 全量快照（無全量基準可依）；之後每 7 天正常排程

  @edge-case
  Scenario: 失敗分類（carryover）商品價格未知，不寫入當日稀疏 daily
    Given 今日「顯示卡」分類抓取失敗（health check 判定為 partial）
    And 該分類既有商品今日未成功爬取，被移入 carryover_ids 原樣保留
    When 爬蟲寫入當日 sparse daily
    Then data/daily/{今日}.json 不寫入失敗分類（carryover）商品
    And 僅寫入成功分類中真正異動 + 新增且價格存在的商品

  @edge-case
  Scenario: 異動商品價格缺失（None）時不寫入當日稀疏 daily
    Given 商品 A 狀態異動但價格解析為 None（價格缺失）
    When 爬蟲寫入當日 sparse daily
    Then 商品 A 不被寫入 data/daily/{今日}.json
    And 僅寫入價格存在（非 None）的異動與新增商品

  @business-rules
  Scenario Outline: 稀疏寫入範圍僅限 changed + new 且價格存在（其餘分類一律排除）
    Given 今日 diff 結果含 <category>
    And 該類商品價格 <hasPrice>
    When store.write_daily 以異動清單寫入當日 daily
    Then <written> 被寫入 data/daily/{今日}.json

    Examples:
      | category      | hasPrice    | written                          |
      | changed_items | 價格存在     | 會（寫入 {item_id: price}）       |
      | new_items     | 價格存在     | 會（寫入 {item_id: price}）       |
      | changed_items | 價格缺失 None | 不會                            |
      | new_items     | 價格缺失 None | 不會                            |
      | refreshed_items | 價格存在   | 不會（非「真的異動」，不寫入）      |
      | unchanged_ids | 價格存在     | 不會（平價日，不寫入）             |
      | carryover_ids | 價格未知     | 不會（失敗分類，不寫入）           |
      | gone_ids      | 無           | 不會（已消失，不寫入）             |

  @edge-case
  Scenario: checkpoint 日當天即使無任何異動（純平價日）仍寫入全量 checkpoint
    Given 今天是距上次 checkpoint ≥ 7 天的 checkpoint 日
    And 今日所有商品價格皆與上次相同（0 異動、0 新增）
    When 爬蟲執行完畢
    Then data/daily/{今日}.json 不產生（平價日）
    And data/checkpoints/{今日}.json 仍被寫入當日全量快照（每 7 天一檔的錨點不缺席）
