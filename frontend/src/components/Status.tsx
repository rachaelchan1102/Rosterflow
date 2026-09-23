import type { Status } from "../types";

const STATUS_LABEL: Record<Status, string> = {
  red: "Not fully staffed",
  amber: "Thin on backups",
  green: "On track",
};

const STATUS_ICON: Record<Status, string> = { red: "✕", amber: "!", green: "✓" };

/** Always icon + label (or icon + tooltip when compact) — status is never carried by color alone. */
export function StatusBadge({ status, compact = false }: { status: Status; compact?: boolean }) {
  return (
    <span className={`status-badge ${status}`} title={STATUS_LABEL[status]}>
      <span className="status-icon" aria-hidden>{STATUS_ICON[status]}</span>
      {compact ? <span className="sr-only">{STATUS_LABEL[status]}</span> : STATUS_LABEL[status]}
    </span>
  );
}

/** The caller decides the color from the same rules as everywhere else — a bar never invents its own threshold. */
export function CoverageBar({ value, target, label, status }: { value: number; target: number; label: string; status: Status }) {
  const ratio = target > 0 ? Math.min(value / target, 1) : 0;
  return (
    <div className="coverage">
      <div className="coverage-label">
        <span>{label}</span>
        <strong>{value} / {target}</strong>
      </div>
      <div className="coverage-track">
        <div className={`coverage-fill ${status}`} style={{ width: `${ratio * 100}%` }} />
      </div>
    </div>
  );
}
