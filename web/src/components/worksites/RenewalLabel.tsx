import React from "react";
import { Info } from "lucide-react";

/** The worksite's renewal reference (R1, R2…) is a label only (BR-JB-08). */
export const RENEWAL_LABEL = "Contract renewal no. (label only)";
export const RENEWAL_HINT =
  "A label only. It does not select the salary revision; that is the Salary revision field (BR-JB-08).";

/** "Contract renewal no. (label only)" with an info icon whose tooltip explains BR-JB-08. */
export const RenewalLabel: React.FC<{ htmlFor?: string; className?: string }> = ({
  htmlFor,
  className,
}) => {
  const content = (
    <>
      {RENEWAL_LABEL}
      <span title={RENEWAL_HINT} aria-label={RENEWAL_HINT} className="inline-flex align-middle ml-1 cursor-help">
        <Info className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
      </span>
    </>
  );
  return htmlFor ? (
    <label htmlFor={htmlFor} className={className} title={RENEWAL_HINT}>
      {content}
    </label>
  ) : (
    <span className={className} title={RENEWAL_HINT}>
      {content}
    </span>
  );
};
