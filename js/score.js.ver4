"use strict";
// ============================================================
// 評分明細
// 基本面／營收 40 分 + 法人籌碼 20 分 + 技術面 40 分
// 外資持股輔助分數不納入總分
// ============================================================
function renderScoreBreakdown(s) {
  const score = s?.score || {};
  const breakdown =
    s?.score_breakdown ||
    s?.score_details ||
    s?.scores ||
    {};
  // 相容不同欄位名稱；不在前端重新計算總分
  const fundamental = validNumber(
    breakdown.fundamental ??
    breakdown.revenue ??
    score.fundamental ??
    s?.fundamental_score
  );
  const institutional = validNumber(
    breakdown.institutional ??
    breakdown.chip ??
    score.institutional ??
    s?.institutional_score ??
    s?.chip_score
  );
  const technical = validNumber(
    breakdown.technical ??
    score.technical ??
    s?.technical_score
  );
  const total = validNumber(
    s?.total_score ??
    s?.totalScore ??
    score.total ??
    score.total_score ??
    s?.score_total ??
    (typeof s?.score === "number" ? s.score : null)
  );
  function item(label, value, max) {
    const shown = value === null ? "—" : scoreText(value);
    const percentage = value === null
      ? 0
      : Math.max(0, Math.min(100, value / max * 100));
    return `
      <div class="score-item">
        <div class="score-label">
          <span>${escapeHTML(label)}</span>
          <span>${escapeHTML(shown)} / ${max}</span>
        </div>
        <div class="score-bar">
          <div class="score-bar-fill"
               style="width:${percentage}%"></div>
        </div>
      </div>
    `;
  }
  return `
    <section class="score-breakdown">
      <div class="section-title">評分明細</div>
      <div class="score-total ${escapeHTML(scoreColor(total))}">
        <span>總分</span>
        <strong>${escapeHTML(scoreText(total))} / 100</strong>
      </div>
      ${item("基本面／營收", fundamental, 40)}
      ${item("法人籌碼", institutional, 20)}
      ${item("技術面", technical, 40)}
      <div class="footer">
        外資持股為輔助觀察指標，不列入上述總分。
      </div>
    </section>
  `;
}
