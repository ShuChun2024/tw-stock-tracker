"use strict";

/*
 * 個股突破策略卡片。
 */

function renderBreakoutPanel(stockId) {
  const state = breakoutStateMap.get(
    normalizeCode(stockId)
  );

  /*
   * 整份 JSON 載入失敗。
   */

  if (breakoutStateLoadError) {
    return `
      <div class="breakout-section">

        <div class="breakout-header">

          <div class="breakout-title">
            布林突破策略
          </div>

        </div>

        <div class="breakout-empty">
          突破策略資料載入失敗：
          ${escapeHTML(breakoutStateLoadError)}
        </div>

      </div>
    `;
  }

  /*
   * 該股票尚無策略紀錄。
   */

  if (!state) {
    return `
      <div class="breakout-section">

        <div class="breakout-header">

          <div class="breakout-title">
            布林突破策略
          </div>

          <span class="breakout-status breakout-inactive">
            尚無紀錄
          </span>

        </div>

        <div class="breakout-empty">
          breakout_state.json 尚無此股票的策略紀錄。
        </div>

      </div>
    `;
  }

  /*
   * 策略狀態。
   */

  const status = state.status || "inactive";

  const statusLabel =
    BREAKOUT_STATUS_LABELS[status] || "未知狀態";

  const statusClass =
    BREAKOUT_STATUS_CLASSES[status] ||
    "breakout-inactive";

  /*
   * 觀測清單狀態。
   *
   * 與策略 status 分開處理。
   */

  const watchlistLabel =
    state.watchlist_active === true
      ? "啟用"
      : state.watchlist_active === false
        ? "停用"
        : "未提供";

  const watchlistClass =
    state.watchlist_active === true
      ? "breakout-watchlist-active"
      : state.watchlist_active === false
        ? "breakout-watchlist-inactive"
        : "breakout-watchlist-unknown";

  /*
   * 目前持有交易。
   */

  const trade = state.active_trade;

  const hasTrade =
    trade &&
    typeof trade === "object" &&
    !Array.isArray(trade);

  /*
   * 摘要資訊。
   */

  return `
    <div class="breakout-section">

      <div class="breakout-header">

        <div class="breakout-title">
          布林突破策略
        </div>

        <span class="breakout-status ${statusClass}">
          ${escapeHTML(statusLabel)}
        </span>

      </div>

      <div class="breakout-summary">

        <div class="breakout-summary-item">

          <div class="breakout-summary-label">
            最後處理日期
          </div>

          <div class="breakout-summary-value">
            ${breakoutText(state.last_processed_date)}
          </div>

        </div>

        <div class="breakout-summary-item">

          <div class="breakout-summary-label">
            觀測清單狀態
          </div>

          <div class="breakout-summary-value">
            <span class="breakout-watchlist-badge ${watchlistClass}">
              ${escapeHTML(watchlistLabel)}
            </span>
          </div>

        </div>

        ${
          hasTrade
            ? `
              <div class="breakout-summary-item">

                <div class="breakout-summary-label">
                  進場價格
                </div>

                <div class="breakout-summary-value">
                  ${breakoutNumber(trade.entry_price)}
                </div>

              </div>

              <div class="breakout-summary-item">

                <div class="breakout-summary-label">
                  持有天數
                </div>

                <div class="breakout-summary-value">
                  ${
                    validNumber(trade.holding_days)
                      ? escapeHTML(trade.holding_days + " 天")
                      : "—"
                  }
                </div>

              </div>
            `
            : ""
        }

      </div>

      <details class="breakout-details">

        <summary class="breakout-toggle">

          <span>
            查看突破策略詳細資料
          </span>

          <span class="breakout-toggle-arrow">
            ⌄
          </span>

        </summary>

        <div class="breakout-detail-content">

          ${renderBreakoutSignal(
            "觀察訊號",
            state.watch_signal
          )}

          ${renderBreakoutSignal(
            "進場訊號",
            state.entry_signal
          )}

          ${renderBreakoutSignal(
            "出場訊號",
            state.exit_signal
          )}

          <div class="breakout-subsection">

            <div class="breakout-subtitle">
              目前持有交易
            </div>

            ${renderActiveBreakoutTrade(
              state.active_trade
            )}

          </div>

          <div class="breakout-subsection">

            <div class="breakout-subtitle">
              歷史訊號紀錄
            </div>

            ${renderBreakoutSignalHistory(
              state.signal_history
            )}

          </div>

          <div class="breakout-subsection">

            <div class="breakout-subtitle">
              歷史交易紀錄
            </div>

            ${renderBreakoutTradeHistory(
              state.trade_history
            )}

          </div>

          <div class="breakout-meta">

            <div class="breakout-meta-row">
              <span>最後處理日期</span>
              <span>${breakoutText(state.last_processed_date)}</span>
            </div>

            <div class="breakout-meta-row">
              <span>個股更新時間</span>
              <span>${breakoutText(state.updated_at)}</span>
            </div>

            <div class="breakout-meta-row">
              <span>策略資料更新時間</span>
              <span>${breakoutText(breakoutStateUpdateTime)}</span>
            </div>

          </div>

        </div>

      </details>

    </div>
  `;
}
