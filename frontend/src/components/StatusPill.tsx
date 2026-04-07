import { labelFromStatus, statusTone } from "../lib/utils";

interface StatusPillProps {
  status: string;
}

export function StatusPill({ status }: StatusPillProps) {
  const tone = statusTone(status);
  return (
    <span className={`status-pill tone-${tone}`}>
      {labelFromStatus(status)}
    </span>
  );
}
