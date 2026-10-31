// The stage's doors (onboarding v2): "Describe a need" on Projects and on Chores, and after the first
// run's ready step. Each opens `#stage/new`.

import { toHash } from "../route";

export const DESCRIBE_A_NEED = "Describe a need";

/** `primary`: the depth's one primary action (the Chores title row, ADR 0016). */
export function DescribeDoor({ push = false, primary = false }: { push?: boolean; primary?: boolean }) {
  const className = ["btn", primary && "btn-primary", push && "m-push"].filter(Boolean).join(" ");
  return (
    <a href={toHash({ view: "stage", id: null })} className={className} data-role="describe-door">
      {DESCRIBE_A_NEED}
    </a>
  );
}
