// The stage's doors (onboarding v2): "Describe a need" on Projects and on Chores, and after the first
// run's ready step. Each opens `#stage/new`.

import { toHash } from "../route";

export const DESCRIBE_A_NEED = "Describe a need";

export function DescribeDoor({ push = false }: { push?: boolean }) {
  return (
    <a href={toHash({ view: "stage", id: null })} className={push ? "btn m-push" : "btn"} data-role="describe-door">
      {DESCRIBE_A_NEED}
    </a>
  );
}
