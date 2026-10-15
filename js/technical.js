"use strict";
// ============================================================
// 技術分析
// 實際資料：technical.ma / rsi / macd / kd / volume / breakout
// ============================================================
function renderTechnical(s) {
  const t = s?.technical || {};
  const ma = t.ma || {};
  const rsi = t.rsi || {};
  const macd = t.macd || {};
  const kd = t.kd || {};
  const volume = t.volume || {};
  const breakout = t.breakout || {};
  const scoreLabel = validNumber(t.score)
    ? `${fmt(t.score, 1)} / 40`
    : "—";
  if (t.data_available !== true) {
    return `
      <div class="section">
        <div class="section-title">技術面分析</div>
        <div class="quality">
          ${escapeHTML(t.message || "尚無技術分析資料")}
        </div>
      </div>`;
  }
  return `
    <div class="section">
      <div class="section-title">
        技術面分析
        <span class="neutral">
          ｜技術分數：${escapeHTML(scoreLabel)}
        </span>
      </div>
      <!-- =====================================================
           技術面摘要
           ===================================================== -->
      <div class="technical-summary">
        <div class="technical-summary-item">
          <div class="technical-summary-label">收盤價</div>
          <div class="technical-summary-value">
            ${escapeHTML(fmt(t.latest_close))}
          </div>
        </div>
        <div class="technical-summary-item">
          <div class="technical-summary-label">成交量</div>
          <div class="technical-summary-value">
            ${escapeHTML(fmtVolume(volume.today))}
          </div>
        </div>
        <div class="technical-summary-item">
          <div class="technical-summary-label">成交量比率</div>
          <div class="technical-summary-value ${trendClass(volume.signal)}">
            ${escapeHTML(
              validNumber(volume.ratio)
                ? `${fmt(volume.ratio)} 倍`
                : "—"
            )}
          </div>
          <div class="technical-summary-sub">
            ${escapeHTML(volume.signal || "—")}
          </div>
        </div>
        <div class="technical-summary-item">
          <div class="technical-summary-label">技術趨勢</div>
          <div class="technical-summary-value ${trendClass(ma.trend)}">
            ${escapeHTML(ma.trend || "—")}
          </div>
        </div>
      </div>
      <div class="technical-meta">
        資料日期：${escapeHTML(t.latest_date || "—")}
      </div>
      <!-- =====================================================
           技術分析詳細資料開關
           ===================================================== -->
      <button
        class="technical-toggle"
        type="button"
        aria-expanded="false"
      >
        <span>展開技術分析明細</span>
        <span class="toggle-arrow" aria-hidden="true">⌄</span>
      </button>
      <!-- =====================================================
           技術分析詳細資料
           ===================================================== -->
      <div class="technical-details">
        <div class="indicator-grid">
          ${metricBox(
            "MA5",
            fmt(ma.ma5),
            "5日移動平均"
          )}
          ${metricBox(
            "MA10",
            fmt(ma.ma10),
            "10日移動平均"
          )}
          ${metricBox(
            "MA20",
            fmt(ma.ma20),
            "20日移動平均"
          )}
          ${metricBox(
            "MA60",
            fmt(ma.ma60),
            "60日移動平均"
          )}
          ${metricBox(
            "RSI(14)",
            fmt(rsi.value),
            rsi.signal || "—",
            trendClass(rsi.signal)
          )}
          ${metricBox(
            "MACD DIF",
            fmt(macd.dif, 4),
            "DIF"
          )}
          ${metricBox(
            "MACD DEA",
            fmt(macd.dea, 4),
            "DEA"
          )}
          ${metricBox(
            "MACD 柱狀值",
            fmt(macd.histogram, 4),
            "Histogram"
          )}
          ${metricBox(
            "MACD 訊號",
            macd.signal || "—",
            "MACD",
            trendClass(macd.signal)
          )}
          ${metricBox(
            "KD－K",
            fmt(kd.k),
            "K值"
          )}
          ${metricBox(
            "KD－D",
            fmt(kd.d),
            "D值"
          )}
          ${metricBox(
            "KD 訊號",
            kd.signal || "—",
            "KD",
            trendClass(kd.signal)
          )}
          ${metricBox(
            "今日成交量",
            fmtVolume(volume.today),
            "當日成交量"
          )}
          ${metricBox(
            "5 日均量",
            fmtVolume(volume.avg5),
            "5日平均成交量"
          )}
          ${metricBox(
            "成交量比率",
            validNumber(volume.ratio)
              ? `${fmt(volume.ratio)} 倍`
              : "—",
            volume.signal || "—",
            trendClass(volume.signal)
          )}
          ${metricBox(
            "20 日最高價",
            fmt(breakout.high20),
            "20日最高價"
          )}
          ${metricBox(
            "20 日最低價",
            fmt(breakout.low20),
            "20日最低價"
          )}
          ${metricBox(
            "距 20 日高點",
            signedPercent(breakout.distance_to_high20_percent),
            "距離20日最高價"
          )}
          ${metricBox(
            "距 20 日低點",
            signedPercent(breakout.distance_to_low20_percent),
            "距離20日最低價"
          )}
        </div>
        <div class="technical-details-note">
          技術訊號：
          <span class="${trendClass(breakout.signal)}">
            ${escapeHTML(breakout.signal || "—")}
          </span>
          <br>
          技術分析日期：${escapeHTML(t.latest_date || "—")}
          <br>
          技術指標是依歷史行情計算的參考資訊，不保證未來走勢。
        </div>
      </div>
    </div>`;
}
