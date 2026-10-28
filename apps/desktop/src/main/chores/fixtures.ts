// Fixture chores for the preview and the tests. Invented, like the chores themselves; the figures
// below are made up for layout and are not bench results.

import type { BenchSummary, ChoreDetail, ChoreSummary } from "../../lib/contract";

export const fixtureBench = (over: Partial<BenchSummary> = {}): BenchSummary => ({
  verdict: "exceeds",
  reasons: ["Recall 0.83 against a bar of 0.75", "No false claims", "38 minutes against a bar of 45"],
  found: 10,
  eligible: 12,
  value_found_usd: 2880,
  value_total_usd: 3107,
  false_claims: 0,
  duplicates: 1,
  traps_filed: 0,
  turns: 14,
  minutes: 38.4,
  engine: "claude_code",
  model: "claude-dev",
  run_at: "2026-10-27T09:30:00Z",
  ...over,
});

export const fixtureChore = (over: Partial<ChoreSummary> = {}): ChoreSummary => ({
  id: "paper-flip-through",
  title: "A parent's mail, filmed once",
  short_title: "A parent's medical mail, filmed once and checked",
  promise:
    "A parent's pile of medical mail filmed once: every sheet found, every date and dollar read twice and tied to the crop of paper it came from.",
  category: "health",
  job: "contest",
  senses: ["paper"],
  featured: "rehearsed",
  origin: "library",
  bench: fixtureBench(),
  ...over,
});

export const FIXTURE_CHORES: ChoreSummary[] = [
  fixtureChore({
    id: "renovation-witness",
    title: "A kitchen remodel held to the record of four weekly walks",
    short_title: "Remodel changes and payments held to the walks",
    promise: "Four weekly walks of the kitchen become a record the change orders and invoices are held to.",
    category: "construction",
    senses: ["walk"],
    featured: "unproven",
    bench: undefined,
  }),
  fixtureChore(),
  fixtureChore({
    id: "prior-auth-denial-appeal",
    title: "A mother's plan denial of her rehab, appealed",
    short_title: "A parent's plan denial appealed from paper and calls",
    promise: "The letters on the kitchen table and two recorded calls become one appeal packet, every sentence cited.",
    senses: ["paper", "call"],
    featured: "failing",
    bench: fixtureBench({
      verdict: "short",
      reasons: ["Recall 0.50 against a bar of 0.75", "One false claim against a bar of 0"],
      found: 1,
      eligible: 2,
      value_found_usd: 0,
      value_total_usd: 10400,
      false_claims: 1,
      engine: "muse",
      model: "muse-spark",
      cost_usd: 0.4213,
    }),
  }),
  fixtureChore({
    id: "care-circle",
    title: "A parent home from hospital: the bottles checked, every act signed by the right person",
    short_title: "A parent's care, shared by the family",
    promise: "The bottles at home are checked against the discharge papers and each family request is done only with the right yes.",
    category: "family",
    job: "comply",
    senses: ["circle", "paper"],
    featured: "proven",
    bench: fixtureBench({ verdict: "meets", found: 9, eligible: 12, value_found_usd: 0, value_total_usd: 0 }),
  }),
];

export const fixtureDetail = (over: Partial<ChoreDetail> = {}): ChoreDetail => ({
  chore: fixtureChore(),
  brief:
    "An adult child films **a parent's pile of medical and benefits mail** once, on the phone.\n\n**Disputed, appealed or refunded - $3,107:**\n- Every sheet found and read twice\n- A field the reads disagree on is asked, not guessed",
  persona: "An adult child handling a retired parent's medical and benefits mail, a pile at a time",
  apps: [
    { app_id: "camera", name: "Phone camera" },
    { app_id: "harbor", name: "Harbor Health member portal" },
  ],
  proofs: [
    {
      sense: "paper",
      id: "sheets-found",
      question: "Does the camera find every sheet in the pile?",
      bar: 0.95,
      op: ">=",
      passed: true,
      n: 14,
      measured: 1,
    },
    {
      sense: "paper",
      id: "field-agreement",
      question: "Do the two reads agree on dates and dollars?",
      bar: 0.9,
      op: ">=",
      passed: true,
      n: 212,
      measured: 0.934,
      note: "Six fields were asked instead of read; none was guessed.",
    },
  ],
  backends: { reader: "fixture", segmenter: "fixture" },
  ...over,
});
