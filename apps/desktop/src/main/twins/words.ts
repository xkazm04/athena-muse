// The twins page's plain words (Passport). Never "token", "connector", "OAuth", "API", "prompt", "node"
// or "slot" on screen. Pink is the person, violet her pencil; green, amber and red mean status only.

import type { Autonomy, ChannelKind, MissionState, Place, TwinState, WaitReason } from "../../lib/contract";

/** Each place's plain label, in setup order (SCHEMA.md `places`). */
export const PLACE_LABEL: Record<Place, string> = {
  who: "Who it speaks as",
  channels: "Where it speaks",
  voice: "How it sounds",
  knowledge: "What it knows",
  chores: "What it does there",
  never: "What it must never do",
  autonomy: "What it may send alone",
  memory: "What it remembers about you",
  mission: "Its first mission",
};

/** The document's name for each place; the plain label always sits beside it. */
export const SECTION: Record<Place, string> = {
  who: "Identity",
  channels: "Visas",
  voice: "Voice",
  knowledge: "Reads from",
  chores: "Permits",
  never: "Restrictions",
  autonomy: "Clearance",
  memory: "Endorsements",
  mission: "First entry",
};

/** What an empty section still promises. */
export const SECTION_EMPTY: Record<Place, string> = {
  who: "Name, signature and purpose",
  channels: "Gmail and Notion, once you sign in",
  voice: "Learned only from mail you sent",
  knowledge: "Notion pages you choose",
  chores: "Ready-made chores you pick",
  never: "Lines it must not cross",
  autonomy: "Review, Assist or Auto, per channel",
  memory: "Facts about you that you keep",
  mission: "A goal on one conversation",
};

export const CHANNEL_LABEL: Record<ChannelKind, string> = { gmail: "Gmail", notion: "Notion" };

export const LEVEL: Record<Autonomy, { label: string; says: string }> = {
  review: { label: "Review", says: "You write. It only suggests." },
  assist: { label: "Assist", says: "It drafts. You sign every send." },
  auto: {
    label: "Auto",
    says: "It sends on its own when it is sure and its risk list is empty. Otherwise it waits for you.",
  },
};

export const STATE_BADGE: Record<TwinState, { label: string; tone: string }> = {
  live: { label: "Live", tone: "success" },
  paused: { label: "Paused", tone: "warning" },
  setting_up: { label: "Being issued", tone: "info" },
};

export const MISSION_BADGE: Record<MissionState | "taken", { label: string; tone?: string }> = {
  open: { label: "Open", tone: "info" },
  resolved: { label: "Resolved", tone: "success" },
  handed_back: { label: "Handed back to you", tone: "human" },
  taken: { label: "With you now" },
};

/** Why a draft waits, as its stamp and its one line. */
export const WAIT: Record<WaitReason, string> = {
  review: "On Review: you write, it only suggests",
  assist: "On Assist: you sign every send",
  first_message: "First messages wait for your signature",
  below_bar: "Not sure enough",
  risk: "Held by its risk list",
  paused: "Paused: it sends nothing",
};

export const RULE =
  "It sends alone only when the channel is on Auto, it is at least as sure as the bar, and its risk list is empty. Anything else waits for you. A paused channel never sends.";

export const TWINS_WORDS = {
  invented: "Invented example",
  inventedTitle: "Every name, address, track, amount and conversation here is invented.",
  title: "Twins",
  lead: "They write as you where you connect them, and hand back what they are not sure of.",
  newTwin: "New twin",
  herWindow: "Her window",
  backToTwins: "Back to your twins",
  twins: "Your twins",
  loadProblem: "Your twins could not be loaded",
  loadProblemLine: "Something went wrong reaching them. This is not an empty list, and nothing was changed.",
  retry: "Try again",
  showExample: "Show the invented example",
  firstRunTitle: "No twins yet",
  firstRunLine:
    "A twin writes as you in your Gmail and Notion. It learns your voice from mail you sent, sends on its own only when it is sure and its risk list is empty, and hands back to you what it is not sure of.",
  firstRunGo: "Set up a first twin with Athena",
  firstRunHint: "You talk; she fills in its document. Nothing is sent while you set it up.",
  waitingForYou: "Waiting for you",
  also: "Also",
  nothingWaits: "Nothing waits for you.",
  ledger: "Twins ledger",
  notLoaded: "Not loaded. This is not an empty list.",
  noTwins: "No twins yet. Your first one shows here once Athena has helped you set it up.",
  // the setup page
  describeLine: "Tell me what this twin is for, in your words. I'll fill in its document while we talk.",
  describeAsk: "What should this twin do for you?",
  describeSuggestions: [
    "Write to Suno creators I'd like to feature, until they agree",
    "Answer client email for the studio",
    "Handle school and club email",
  ],
  ownWords: "Or in your own words",
  send: "Send",
  stillNeeds: "She still needs",
  allFilled: "Everything it needs is filled in. Memory and a first mission are up to you.",
  enough: "That's enough, rehearse it",
  leftOpen: "Left open",
  inkAll: (n: number) => `Ink all her pencil (${n})`,
  filled: (n: number) => `${n}% filled`,
  thinking: "Athena is thinking",
  slow: "Still thinking. Slower than usual; nothing is lost.",
  failed: "Nothing usable came back. Nothing was changed on the document.",
  sayDifferently: "Say it differently",
  landsHere: "Your answer lands here",
  writingHere: "She is writing here",
  staged: "This example follows one path, so she answers as in the example.",
  typed: "Noted in your words. This example follows one path, so she answers as in the example.",
  tookMission: (goal: string) =>
    `She took the first mission she suggested: ${goal}. You can change it before going live.`,
  goLive: "Go live",
  goLiveWhen: "Go live opens when the rehearsal ends: resolved, or handed back to you.",
  goLiveNow: "The rehearsal is done. Go live when you are happy.",
  issuedNothingMore: "Issued. Nothing more is needed.",
  liveFlash: (name: string) => `${name} is live. Its document is issued and in your wallet.`,
  // the nested pages
  soundsLike: "Sounds like",
  soundsLikeNone: "not written yet: its first draft shows once it rehearses",
} as const;

/** The bottom panel during the rehearsal: her line and her one question, per step. */
export interface RehearsalAsk {
  line: string;
  ask: string;
  suggestions: [string, string, string];
}

export const REHEARSAL_ASK = {
  running: (name: string): RehearsalAsk => ({
    line: `The practice page is open. It is writing its first message to ${name}.`,
    ask: "Wait for its first draft?",
    suggestions: ["Wait for it", "Show me what it reads", "Stop the rehearsal"],
  }),
  waits: (sure: number, risks: number): RehearsalAsk => ({
    line: `First messages wait for your signature. This one is ${sure} sure and ${risks ? `${risks} thing is on its risk list` : "its risk list is empty"}.`,
    ask: "Is this you?",
    suggestions: ["That's me", "Not me", "I'll change a word"],
  }),
  held: (sure: number, bar: number | undefined, risks: readonly string[]): RehearsalAsk => ({
    line: `${risks[0] ? `${firstClause(risks[0])}. ` : ""}Its reply is ${sure} sure${bar !== undefined && sure < bar ? `, below your bar of ${bar}` : ""}${risks.length ? `, and ${risks.length === 1 ? "one thing is" : `${risks.length} things are`} on its risk list` : ""}, so it waits for you.`,
    ask: "Fix it, or let it go as it is?",
    suggestions: ["I'll edit it", "Send it as it is", "Not me"],
  }),
  editing: (): RehearsalAsk => ({
    line: "Change anything you like. Whatever you change, it learns from.",
    ask: "Done editing?",
    suggestions: ["Save my version", "Keep its version", "Start over"],
  }),
  edited: (learned: string): RehearsalAsk => ({
    line: `Got it: ${lowerFirst(learned)}. It writes that way from now on.`,
    ask: "Send your version?",
    suggestions: ["Send it", "Edit again", "Undo my edit"],
  }),
  sent: (sure: number, bar: number | undefined): RehearsalAsk => ({
    line: `Its reply was ${sure} sure${bar !== undefined ? ` against your bar of ${bar}` : ""} with nothing on its risk list, so it went on its own.`,
    ask: "Was that you?",
    suggestions: ["That's me", "Not me", "Why did it send?"],
  }),
  resolved: (where: string): RehearsalAsk => ({
    line: `Mission resolved. It filed the row to ${where}, as the chore says.`,
    ask: "Ready to go live?",
    suggestions: ["Go live", "Try it another way", "Not yet"],
  }),
  handed: (why: string): RehearsalAsk => ({
    line: why,
    ask: "What now?",
    suggestions: ["Good, go live", "Replay the usual path", "Not yet"],
  }),
  golive: (line: string): RehearsalAsk => ({
    line,
    ask: "Anything else for now?",
    suggestions: ["Back to my twins", "Give it another mission", "Show me its document"],
  }),
};

function firstClause(s: string): string {
  return s.split(":")[0]!.trim();
}

function lowerFirst(s: string): string {
  return s ? s[0]!.toLowerCase() + s.slice(1) : s;
}

/** Connecting Gmail and Notion, in plain words (ADR 0008). */
export const CONNECT_WORDS = {
  gmail: {
    title: "Gmail visa",
    sub: "Sign in with the Google account it should write from.",
    asksFor: ["Read your mail", "Send mail as you"],
    neverAsksFor: ["Delete mail", "Your contacts", "Your calendar"],
    client: "Your own Google client",
    clientHint:
      "Google signs you in through a client you make yourself, so no one else holds the keys to your mail. You paste its ID and secret once; they stay sealed on this computer.",
    clientSteps: [
      "In Google Cloud, make a project and turn on Gmail for it",
      "Under Credentials, create a client of the kind 'Desktop app'",
      "Copy its ID and secret and paste them here",
    ],
    clientId: "Client ID",
    clientSecret: "Client secret",
    signIn: "Sign in with Google",
    waiting: "Waiting for you in the browser. Google's sign-in page opened there.",
    waitingFor: "It stops waiting after 10 minutes.",
    connected: (account: string) => `Signed in as ${account}`,
    failed: "Google's sign-in did not finish. Nothing was saved.",
    failedHint: "Try again, or use a different account.",
    cancel: "Cancel",
    stamped: "The visa is on the document.",
  },
  notion: {
    title: "Notion visa",
    sub: "It reads only the pages you share with it.",
    key: "Your Notion key",
    keyPlaceholder: "Paste it here",
    check: "Check",
    checking: "Checking the key with Notion",
    connected: (account: string) => `Notion accepted the key: ${account}`,
    rejected: "Notion did not accept that key. Check you copied all of it.",
    rejectedHint: "The key is long; it is easy to miss the end.",
    whereToFind: "Where to find it",
    steps: [
      "In Notion, open Settings, then Connections",
      "Make a new integration called 'Athena twin'",
      "Copy its key and paste it here",
      "Share the pages it may read with that integration",
    ],
  },
};
