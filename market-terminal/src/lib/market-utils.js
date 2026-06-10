export const fmtPct = (v) => (v > 0 ? '+' : '') + v.toFixed(2) + '%';
export const fmtFlow = (v) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(1);
export const cls = (v) => (v > 0.001 ? 'up' : v < -0.001 ? 'down' : 'flat');
export const cssVar = (v) => (v > 0.001 ? 'var(--up)' : v < -0.001 ? 'var(--down)' : 'var(--flat)');
