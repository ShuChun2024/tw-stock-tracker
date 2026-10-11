"use strict";

// ============================================================
// 評分明細
// 基本面 40 + 法人籌碼 20 + 技術面 40 = 100
// 外資持股不納入總分
// ============================================================
function renderScoreBreakdown(s) {
  const breakdown = s?.score_breakdown || {};

  const fundamental = validNumber(
    breakdown.fundamental ?? breakdown.revenue
  );

  const chip = validNumber(
    breakdown.chip ?? breakdown.institutional ?? s?.chip_score
  );

  const technical = validNumber(
    breakdown.technical ?? s?.technical?.score
  );

  const total = validNumber(s?.score);

  function item(label, value, max) {
    const shown = value === null ? "—" : scoreText(value);

    const percentage = value === null
      ? 0
      : Math.max(0, Math.min(100, value / max * 100));

    return `
      <div class="score-row">
        <span>${escapeHTML(label)}</span>
        <div class="score-track">
          <div class="score-fill" style="width:${percentage}%"></div>
        </div>
        <span class="score-row-value">${escapeHTML(shown)} / ${max}</span>
      </div>
    `;
  }

  return `
    <section class="section">
      <div class="section-title">評分明細</div>

      <div class="detail-line">
        總分：
        <strong class="${escapeHTML(scoreColor(total))}">
          ${escapeHTML(scoreText(total))} / 100
        </strong>
      </div>

      <div class="score-breakdown">
        ${item("基本面／營收", fundamental, 40)}
        ${item("法人籌碼", chip, 20)}
        ${item("技術面", technical, 40)}
      </div>

      <div class="technical-details-note">
        外資持股為輔助觀察指標，不列入上述總分。
      </div>
    </section>
  `;
}
