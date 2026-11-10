"use strict";

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


/*
 * 目前持有交易。
 */

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


/*
 * 歷史交易。
 */

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


/*
 * 歷史訊號。
 */

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
