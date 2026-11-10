"use strict";

/*
 * 策略狀態中文名稱。
 */

const BREAKOUT_STATUS_LABELS = {
  inactive: "未啟動",
  watching: "觀察中",
  holding: "持有中",
  stopped: "已停止"
};

/*
 * 策略狀態 CSS class。
 */

const BREAKOUT_STATUS_CLASSES = {
  inactive: "breakout-inactive",
  watching: "breakout-watching",
  holding: "breakout-holding",
  stopped: "breakout-stopped"
};

/*
 * 歷史訊號類型名稱。
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
 * 數值格式化。
 */

function breakoutNumber(value, decimals = 2) {
  if (!validNumber(value)) {
    return "—";
  }

  return fmt(value, decimals);
}

/*
 * 百分比格式化。
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
