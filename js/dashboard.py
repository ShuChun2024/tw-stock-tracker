"use strict";

/* =====================================================
   11. 首頁卡片及展開／縮合
   ===================================================== */

/*
 * breakout_state.json 獨立資料。
 *
 * 不修改 analysisMap。
 * 不修改原有技術面評分。
 */

let breakoutStateMap = new Map();
let breakoutStateUpdateTime = "";
let breakoutStateLoadError = "";

/*
 * 狀態中文名稱。
 */

const BREAKOUT_STATUS_LABELS = {
  inactive: "未啟動",
  watching: "觀察中",
  holding: "持有中",
  stopped: "已停止"
};

/*
 * 狀態 CSS class。
 */

const BREAKOUT_STATUS_CLASSES = {
  inactive: "breakout-inactive",
  watching: "breakout-watching",
  holding: "breakout-holding",
  stopped: "breakout-stopped"
};


/* =====================================================
   11-1. 讀取 breakout_state.json
   ===================================================== */

async function loadBreakoutState() {
  try {
    const response = await fetch(
      "./breakout_state.json?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const data = await response.json();

    if (
      !data ||
      typeof data !== "object" ||
      data.schema_version !== 1 ||
      !data.stocks ||
      typeof data.stocks !== "object" ||
      Array.isArray(data.stocks)
    ) {
      throw new Error(
        "breakout_state.json 格式不正確"
      );
    }

    const nextMap = new Map();

    Object.entries(data.stocks).forEach(([key, stock]) => {
      if (
        !stock ||
        typeof stock !== "object" ||
        Array.isArray(stock)
      ) {
        return;
      }

      const code = normalizeCode(
        stock.stock_id || key
      );

      if (!code) {
        return;
      }

      nextMap.set(code, {
        ...stock,
        stock_id: code
      });
    });

    breakoutStateMap = nextMap;

    breakoutStateUpdateTime =
      data.update_time || "";

    breakoutStateLoadError = "";

    console.log(
      "突破策略資料載入完成，共 " +
      breakoutStateMap.size +
      " 檔"
    );

    return true;

  } catch (error) {
    console.error(
      "載入 breakout_state.json 失敗：",
      error
    );

    breakoutStateMap = new Map();
    breakoutStateUpdateTime = "";
    breakoutStateLoadError = error.message;

    return false;
  }
}


/* =====================================================
   11-2. 突破策略資料格式化
   ===================================================== */

/*
 * 文字格式化。
 */

function breakoutText(value) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "—";
  }

  return escapeHTML(String(value));
}


/*
 * 數值。
 * 回傳未跳脫字串，由 renderBreakoutField 統一處理。
 */

function breakoutNumber(value, decimals = 2) {
  if (!validNumber(value)) {
    return "—";
  }

  return fmt(value, decimals);
}


/*
 * 百分比。
 */

function breakoutPercent(value) {
  if (!validNumber(value)) {
    return "—";
  }

  return signedPercent(value);
}


/*
 * 一般資料欄位。
 */

function renderBreakoutField(label, value) {
  return `
    <div class="breakout-field">
      <div class="breakout-field-label">
        ${escapeHTML(label)}
      </div>

      <div class="breakout-field-value">
        ${breakoutText(value)}
      </div>
    </div>
  `;
}


/*
 * 歷史訊號類型名稱。
 *
 * 顯示英文代碼，但使用易讀格式。
 * 未知類型保留原始文字。
 */

const BREAKOUT_SIGNAL_LABELS = {
  watch: "Watch",
  watch_end: "Watch_end",
  entry: "Entry",
  exit: "Exit",
  stop: "Stop"
};


/*
 * 歷史訊號類型 CSS class。
 */

const BREAKOUT_SIGNAL_CLASSES = {
  watch: "breakout-signal-watch",
  watch_end: "breakout-signal-watch-end",
  entry: "breakout-signal-entry",
  exit: "breakout-signal-exit",
  stop: "breakout-signal-stop"
};


/*
 * 歷史訊號名詞解釋。
 *
 * 固定顯示在歷史訊號清單最下方。
 */

const BREAKOUT_SIGNAL_EXPLANATIONS = [
  {
    type: "watch",
    label: "Watch",
    description: "符合布林收斂及股價盤整條件，列入突破觀察。"
  },
  {
    type: "watch_end",
    label: "Watch_end",
    description: "原本的盤整觀察條件已解除，結束觀察。"
  },
  {
    type: "entry",
    label: "Entry",
    description: "出現符合策略設定的突破進場訊號。"
  },
  {
    type: "exit",
    label: "Exit",
    description: "持有期間出現策略設定的出場訊號。"
  },
  {
    type: "stop",
    label: "Stop",
    description: "交易停止或停損紀錄。"
  }
];


/*
 * 歷史訊號名詞解釋區塊。
 */

function renderBreakoutSignalGlossary() {
  return `
    <div class="breakout-signal-glossary">

      <div class="breakout-glossary-title">
        名詞解釋
      </div>

      <div class="breakout-glossary-list">

        ${BREAKOUT_SIGNAL_EXPLANATIONS.map(item => `
          <div class="breakout-glossary-item">

            <div class="breakout-glossary-term">
              ${escapeHTML(item.label)}
            </div>

            <div class="breakout-glossary-description">
              ${escapeHTML(item.description)}
            </div>

          </div>
        `).join("")}

      </div>

    </div>
  `;
}


/*
 * 訊號詳細內容。
 *
 * 支援：
 * watch_signal
 * entry_signal
 * exit_signal
 */

function renderBreakoutSignal(title, signal) {
  if (
    !signal ||
    typeof signal !== "object" ||
    Array.isArray(signal)
  ) {
    return `
      <div class="breakout-subsection">
        <div class="breakout-subtitle">
          ${escapeHTML(title)}
        </div>

        <div class="breakout-empty">
          尚無紀錄
        </div>
      </div>
    `;
  }

  return `
    <div class="breakout-subsection">

      <div class="breakout-subtitle">
        ${escapeHTML(title)}
      </div>

      <div class="breakout-fields">

        ${renderBreakoutField(
          "訊號日期",
          signal.date
        )}

        ${renderBreakoutField(
          "訊號原因",
          signal.reason
        )}

        ${
          signal.execution_date !== undefined
            ? renderBreakoutField(
                "預計執行日期",
                signal.execution_date
              )
            : ""
        }

        ${
          signal.exit_price !== undefined
            ? renderBreakoutField(
                "出場價格",
                breakoutNumber(signal.exit_price)
              )
            : ""
        }

      </div>

    </div>
  `;
}


/* =====================================================
   11-3. 目前持有交易
   ===================================================== */

function renderActiveBreakoutTrade(trade) {
  if (
    !trade ||
    typeof trade !== "object" ||
    Array.isArray(trade)
  ) {
    return `
      <div class="breakout-empty">
        目前沒有未完成交易。
      </div>
    `;
  }

  return `
    <div class="breakout-fields">

      ${renderBreakoutField(
        "進場訊號日期",
        trade.entry_signal_date
      )}

      ${renderBreakoutField(
        "實際進場日期",
        trade.entry_date
      )}

      ${renderBreakoutField(
        "進場價格",
        breakoutNumber(trade.entry_price)
      )}

      ${renderBreakoutField(
        "持有天數",
        validNumber(trade.holding_days)
          ? trade.holding_days + " 天"
          : "—"
      )}

      ${renderBreakoutField(
        "持有期間最高價",
        breakoutNumber(trade.highest_price)
      )}

      ${renderBreakoutField(
        "持有期間最低價",
        breakoutNumber(trade.lowest_price)
      )}

      ${renderBreakoutField(
        "最大有利變動 MFE",
        breakoutPercent(trade.mfe_pct)
      )}

      ${renderBreakoutField(
        "最大不利變動 MAE",
        breakoutPercent(trade.mae_pct)
      )}

      ${renderBreakoutField(
        "待執行出場日期",
        trade.pending_exit_date
      )}

      ${renderBreakoutField(
        "待執行出場原因",
        trade.pending_exit_reason
      )}

    </div>
  `;
}


/* =====================================================
   11-4. 歷史交易
   ===================================================== */

function renderBreakoutTradeHistory(trades) {
  if (
    !Array.isArray(trades) ||
    !trades.length
  ) {
    return `
      <div class="breakout-empty">
        尚無歷史交易紀錄。
      </div>
    `;
  }

  return `
    <div class="breakout-history-list">

      ${trades.map((trade, index) => {
        if (
          !trade ||
          typeof trade !== "object" ||
          Array.isArray(trade)
        ) {
          return "";
        }

        return `
          <div class="breakout-history-item">

            <div class="breakout-history-title">
              歷史交易 ${index + 1}
            </div>

            <div class="breakout-fields">

              ${renderBreakoutField(
                "進場訊號日期",
                trade.entry_signal_date
              )}

              ${renderBreakoutField(
                "進場日期",
                trade.entry_date
              )}

              ${renderBreakoutField(
                "進場價格",
                breakoutNumber(trade.entry_price)
              )}

              ${renderBreakoutField(
                "持有天數",
                validNumber(trade.holding_days)
                  ? trade.holding_days + " 天"
                  : "—"
              )}

              ${renderBreakoutField(
                "最高價",
                breakoutNumber(trade.highest_price)
              )}

              ${renderBreakoutField(
                "最低價",
                breakoutNumber(trade.lowest_price)
              )}

              ${renderBreakoutField(
                "MFE",
                breakoutPercent(trade.mfe_pct)
              )}

              ${renderBreakoutField(
                "MAE",
                breakoutPercent(trade.mae_pct)
              )}

              ${renderBreakoutField(
                "出場日期",
                trade.exit_date
              )}

              ${renderBreakoutField(
                "出場價格",
                breakoutNumber(trade.exit_price)
              )}

              ${renderBreakoutField(
                "交易報酬率",
                breakoutPercent(trade.return_pct)
              )}

              ${renderBreakoutField(
                "出場原因",
                trade.exit_reason
              )}

            </div>

          </div>
        `;
      }).join("")}

    </div>
  `;
}


/* =====================================================
   11-5. 歷史訊號
   ===================================================== */

function renderBreakoutSignalHistory(signals) {
  const hasSignals =
    Array.isArray(signals) &&
    signals.length > 0;

  const historyContent = hasSignals
    ? `
      <div class="breakout-history-list">

        ${signals.map((signal, index) => {
          if (
            !signal ||
            typeof signal !== "object" ||
            Array.isArray(signal)
          ) {
            return "";
          }

          const type = String(signal.type || "")
            .trim()
            .toLowerCase();

          const label =
            BREAKOUT_SIGNAL_LABELS[type] ||
            String(signal.type || "未知訊號");

          const signalClass =
            BREAKOUT_SIGNAL_CLASSES[type] ||
            "breakout-signal-other";

          return `
            <div class="breakout-history-item">

              <div class="breakout-history-title">
                訊號 ${index + 1}
              </div>

              <div class="breakout-history-date-row">

                <span class="breakout-history-date">
                  ${breakoutText(signal.date)}
                </span>

                <span class="breakout-signal-type ${signalClass}">
                  ${escapeHTML(label)}
                </span>

              </div>

              <div class="breakout-history-reason">
                ${breakoutText(signal.reason)}
              </div>

            </div>
          `;
        }).join("")}

      </div>
    `
    : `
      <div class="breakout-empty">
        尚無歷史訊號紀錄。
      </div>
    `;

  return `
    <div class="breakout-signal-history">

      ${historyContent}

      ${renderBreakoutSignalGlossary()}

    </div>
  `;
}


/* =====================================================
   11-6. 個股突破策略卡片
   ===================================================== */

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
   *
   * 不論有沒有持有交易，
   * 都顯示最後處理日期及觀測清單狀態。
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


/* =====================================================
   11-7. 原有展開／縮合功能
   ===================================================== */

function bindToggleButtons(
  grid,
  selector,
  panelClass,
  openText,
  closeText
) {
  grid.querySelectorAll(selector).forEach(button => {
    button.addEventListener("click", () => {
      const panel = button.nextElementSibling;

      if (
        !panel ||
        !panel.classList.contains(panelClass)
      ) {
        return;
      }

      const opened = panel.classList.toggle("open");

      button.setAttribute(
        "aria-expanded",
        String(opened)
      );

      const label = button.querySelector("span:first-child");
      const arrow = button.querySelector(".toggle-arrow");

      if (label) {
        label.textContent = opened ? closeText : openText;
      }

      if (arrow) {
        arrow.textContent = opened ? "⌃" : "⌄";
      }
    });
  });
}


/* =====================================================
   11-8. 消息面資料
   ===================================================== */

let eventData = [];

function renderEventPanels() {
  if (
    !Array.isArray(eventData) ||
    !window.StockEvents ||
    typeof window.StockEvents.renderEvents !== "function"
  ) {
    return;
  }

  eventData.forEach(event => {
    const stockId = normalizeCode(event?.stock_id);

    if (!stockId) {
      return;
    }

    const container = document.getElementById(
      `event-panel-${stockId}`
    );

    if (!container) {
      return;
    }

    StockEvents.renderEvents(stockId, eventData);
  });
}


/* =====================================================
   12. 首頁股票卡片
   ===================================================== */

function render() {
  const keyword = document
    .getElementById("searchInput")
    .value
    .trim()
    .toLowerCase();

  const sort = document.getElementById("sortSelect").value;

  const watchlistNames = getWatchlistNames();

  let stocks = Array.from(analysisMap.values()).map(result => ({
    ...getStockDisplayInfo(result, watchlistNames),
    analysis: result
  }));

  /* 搜尋 */

  stocks = stocks.filter(item => {
    const s = item.analysis || {};

    const text = [
      item.stock_id,
      item.short_name,
      item.company_name,
      s.stock_id,
      s.stock_name,
      s.status
    ]
      .join(" ")
      .toLowerCase();

    return text.includes(keyword);
  });

  /* 排序 */

  stocks.sort((a, b) => {
    if (sort === "name") {
      return String(a.short_name || a.stock_id).localeCompare(
        String(b.short_name || b.stock_id),
        "zh-Hant"
      );
    }

    if (
      sort === "scoreDesc" ||
      sort === "scoreAsc"
    ) {
      const av = validNumber(a.analysis?.score)
        ? Number(a.analysis.score)
        : null;

      const bv = validNumber(b.analysis?.score)
        ? Number(b.analysis.score)
        : null;

      if (av === null && bv !== null) return 1;
      if (av !== null && bv === null) return -1;

      if (av === null && bv === null) {
        return a.stock_id.localeCompare(b.stock_id);
      }

      return sort === "scoreDesc"
        ? bv - av
        : av - bv;
    }

    return a.stock_id.localeCompare(b.stock_id);
  });

  const grid = document.getElementById("stockGrid");

  /* 無資料 */

  if (!stocks.length) {
    grid.innerHTML =
      '<div class="empty">目前沒有符合搜尋條件的分析結果。</div>';
    return;
  }

  /* 股票卡片 */

  grid.innerHTML = stocks.map(item => {
    const s = item.analysis || {};
    const revenue = s.revenue || {};
    const foreign = s.foreign_holding || {};
    const quality = s.data_quality || {};

    const missing = normalizeMissingItems(
      quality.missing_items
    );

    const revenueValue = validNumber(revenue.latest_yoy)
      ? signedPercent(revenue.latest_yoy)
      : "資料不足";

    const foreignValue = validNumber(foreign.latest_percent)
      ? fmt(foreign.latest_percent) + "%"
      : "資料不足";

    const qualityText =
      quality.complete === false ||
      missing.length
        ? "資料品質提醒：" + (
            missing.length
              ? "缺少 " + missing.join("、")
              : "部分資料不完整"
          )
        : "";

    return `
      <article class="stock-card">

        <div class="stock-header">
          <div>
            <div class="stock-id">
              ${escapeHTML(item.stock_id)}
            </div>
            <div class="company-short">
              ${escapeHTML(item.short_name || "名稱待確認")}
            </div>
            <div class="company-full">
              ${escapeHTML(item.company_name || "公司全名待確認")}
            </div>
          </div>

          <span class="status">
            ${escapeHTML(scoreStatus(s))}
          </span>
        </div>

        <div class="score-area">
          <div class="score ${scoreColor(s.score)}">
            ${escapeHTML(scoreText(s.score))}
          </div>
          <div>
            <div class="score-label">
              綜合評分 / 100
            </div>
            <div class="score-label">
              ${escapeHTML(s.status || scoreStatus(s))}
            </div>
          </div>
        </div>

        <div class="metrics">
          <div class="metric">
            <div class="metric-title">
              最新營收年增率
            </div>
            <div class="metric-value ${trendClass(revenue.trend)}">
              ${escapeHTML(revenueValue)}
            </div>
            <div class="metric-sub">
              ${escapeHTML(revenue.latest_revenue_month || "")}
            </div>
          </div>

          <div class="metric">
            <div class="metric-title">
              外資持股比例
            </div>
            <div class="metric-value ${trendClass(foreign.trend)}">
              ${escapeHTML(foreignValue)}
            </div>
            <div class="metric-sub">
              ${escapeHTML(foreign.latest_date || "")}
            </div>
          </div>
        </div>

        ${renderStockPrice(s)}

        ${renderValuation(s)}

        ${renderScoreBreakdown(s)}
        ${renderInstitutional(s)}
        ${renderTechnical(s)}

        <!-- 布林突破策略 -->
        ${renderBreakoutPanel(item.stock_id)}

        <!-- 消息面 -->
        <div
          class="event-panel"
          id="event-panel-${escapeHTML(item.stock_id)}"
          data-event-stock="${escapeHTML(item.stock_id)}"
        ></div>

        ${
          qualityText
            ? `<div class="quality">${escapeHTML(qualityText)}</div>`
            : ""
        }

        <button
          class="detail-button"
          type="button"
          aria-expanded="false"
        >
          <span>查看詳細資料</span>
          <span
            class="toggle-arrow"
            aria-hidden="true"
          >⌄</span>
        </button>

        ${renderDetails(s)}

      </article>
    `;
  }).join("");

  /* 近 5 個交易日行情 */

  bindToggleButtons(
    grid,
    ".stock-price-toggle",
    "stock-price-details",
    "近 5 個交易日",
    "近 5 個交易日"
  );

  /* 三大法人 */

  bindToggleButtons(
    grid,
    ".institutional-toggle",
    "institutional-details",
    "展開三大法人詳細資料",
    "收合三大法人詳細資料"
  );

  /* 技術分析 */

  bindToggleButtons(
    grid,
    ".technical-toggle",
    "technical-details",
    "展開技術分析詳細資料",
    "收合技術分析詳細資料"
  );

  /* 完整股票明細 */

  bindToggleButtons(
    grid,
    ".detail-button",
    "details",
    "查看詳細資料",
    "收合詳細資料"
  );

  /* 消息面 */

  renderEventPanels();
}


/* =====================================================
   13. 讀取 analysis.json
   ===================================================== */

async function refreshAnalysis() {
  if (loading) {
    return;
  }

  loading = true;

  const button = document.getElementById("refreshBtn");
  const message = document.getElementById("message");

  button.disabled = true;
  button.textContent = "讀取中…";
  message.textContent = "正在讀取最新分析資料…";
  message.style.display = "";

  try {
    const response = await fetch(
      "./analysis.json?t=" + Date.now(),
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error("HTTP " + response.status);
    }

    const data = await response.json();

    const stocks = Array.isArray(data)
      ? data
      : data.stocks;

    if (!Array.isArray(stocks)) {
      throw new Error(
        "analysis.json 格式不正確，找不到股票分析陣列。"
      );
    }

    const nextMap = new Map();

    stocks.forEach(stock => {
      if (
        !stock ||
        typeof stock !== "object"
      ) {
        return;
      }

      const code = normalizeCode(stock.stock_id);

      if (!code) {
        return;
      }

      nextMap.set(code, {
        ...stock,
        stock_id: code
      });
    });

    analysisMap = nextMap;

    analysisUpdateTime = (
      !Array.isArray(data) &&
      (
        data.update_time ||
        data.analysis_date
      )
    ) || "";

    document.getElementById("updateTime").textContent =
      "分析資料更新時間：" +
      (analysisUpdateTime || "資料未提供");

    message.textContent = "";
    message.style.display = "none";

    /*
     * 讀取行情資料。
     */

    try {
      await loadStockPrices();
    } catch (priceError) {
      console.error(
        "stock_prices.json 載入失敗：",
        priceError
      );

      stockPriceMap = new Map();
      stockPriceUpdateTime = "";
    }

    /*
     * 讀取布林突破策略資料。
     *
     * 失敗不影響 analysis.json。
     */

    await loadBreakoutState();

    /*
     * 股票分析、行情、突破策略資料準備完成。
     */

    render();

    /*
     * 讀取大盤資料。
     */

    try {
      await loadMarketIndex();
    } catch (marketError) {
      console.error(
        "market_index.json 載入失敗：",
        marketError
      );

      marketData = null;

      const marketContainer = ensureMarketIndexContainer();

      if (marketContainer) {
        marketContainer.innerHTML = `
          <div class="market-index-panel">
            <div class="market-index-title">
              台股大盤
            </div>
            <div class="market-index-error">
              大盤資料載入失敗：
              ${escapeHTML(marketError.message)}
            </div>
          </div>
        `;
      }
    }

    /*
     * 讀取消息資料。
     */

    if (
      window.StockEvents &&
      typeof window.StockEvents.loadEventData === "function"
    ) {
      try {
        const eventResult =
          await window.StockEvents.loadEventData();

        eventData = Array.isArray(eventResult?.events)
          ? eventResult.events
          : [];

        renderEventPanels();

      } catch (eventError) {
        console.error(
          "events.json 載入失敗：",
          eventError
        );

        eventData = [];

        document
          .querySelectorAll("[data-event-stock]")
          .forEach(container => {
            container.innerHTML =
              `<div class="event-error">消息資料載入失敗：${escapeHTML(eventError.message)}</div>`;
          });
      }
    }

  } catch (error) {
    message.style.display = "";

    message.textContent =
      "讀取分析資料失敗：" +
      error.message +
      "\n請確認 analysis.json 已成功發布，且 JSON 格式正確。";

    console.error("analysis.json 載入失敗：", error);

  } finally {
    loading = false;
    button.disabled = false;
    button.textContent = "↻ 重新整理";
  }
}


/* =====================================================
   14. 事件與初始化
   ===================================================== */

document
  .getElementById("refreshBtn")
  .addEventListener("click", async () => {
    await loadStockDatabase();
    await refreshAnalysis();
  });

const searchInput = document.getElementById("searchInput");

searchInput.addEventListener("input", () => {
  try {
    console.log("[搜尋] 關鍵字：", searchInput.value);
    console.log("[搜尋] 分析資料筆數：", analysisMap.size);

    render();

  } catch (error) {
    console.error("[搜尋] 渲染失敗：", error);

    document.getElementById("message").textContent =
      "搜尋時發生錯誤：" +
      error.message +
      "\n請查看瀏覽器主控台的詳細錯誤。";
  }
});

document
  .getElementById("sortSelect")
  .addEventListener("change", render);

window.addEventListener("storage", event => {
  if (
    !event.key ||
    event.key === WATCHLIST_KEY ||
    event.key === OLD_WATCHLIST_KEY
  ) {
    render();
  }
});

async function init() {
  await loadStockDatabase();
  await refreshAnalysis();
}

init();
