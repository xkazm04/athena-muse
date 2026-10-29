// Source of the invented Twin example. build.mjs computes every derived field (pieces after each
// frame, coverage, ready, readiness, stats) from this file; never hand-edit twin-data.js.

export const invented =
  "Every name, address, track, amount and conversation here is invented for a design prototype. None of it is a real person, account or service.";

export const owner = { name: "Alex Moreno", first: "Alex", studio: "Low Tide Visuals" };

// The places a twin is made of, in the order the setup fills them.
export const places = [
  { id: "who", label: "Who it speaks as", required: 1 },
  { id: "channels", label: "Where it speaks", required: 1 },
  { id: "voice", label: "How it sounds", required: 1 },
  { id: "knowledge", label: "What it knows", required: 0.5 },
  { id: "chores", label: "What it does there", required: 0.5 },
  { id: "never", label: "What it must never do", required: 1 },
  { id: "autonomy", label: "What it may send alone", required: 1 },
  { id: "memory", label: "What it remembers about you", required: 0 },
  { id: "mission", label: "Its first mission", required: 0 },
];

export const channelKinds = {
  gmail: { label: "Gmail", by: "Google", connect: "sign_in" },
  notion: { label: "Notion", by: "Notion", connect: "key" },
};

export const autonomyLevels = [
  { id: "review", label: "Review", says: "You write. It only suggests." },
  { id: "assist", label: "Assist", says: "It drafts. You sign every send." },
  { id: "auto", label: "Auto", says: "It sends on its own when it is sure and its risk list is empty. Otherwise it waits for you." },
];

// The overview. Dates are relative to `now`.
export const now = "2026-10-29T16:20:00";
export const twins = [
  {
    id: "tw_desk",
    name: "Client desk",
    purpose: "Answers client email for the studio: quotes, scheduling and invoices.",
    state: "live",
    since: "2026-08-04",
    channels: [
      { kind: "gmail", account: "alex@lowtide-visuals.example", status: "connected", autonomy: "auto", bar: 85, health: "active", last_at: "2026-10-29T15:52:00" },
      { kind: "notion", account: "Low Tide studio", status: "connected", autonomy: "assist", bar: null, health: "quiet", last_at: "2026-10-27T10:05:00" },
    ],
    filled: { who: 1, channels: 1, voice: 1, knowledge: 1, chores: 1, never: 1, autonomy: 1, memory: 1, mission: 1 },
    week: { sent: 23, sent_alone: 14, held_by_risk: 3, median_reply_min: 38, cost_usd: 1.84 },
    missions: [
      { id: "ms_1", title: "Chase the overdue invoice from Harbor Bakery", with: "Harbor Bakery", channel: "gmail", state: "open", turns: 3, last_at: "2026-10-29T11:40:00", note: "Second reminder sent; they said 'by Friday'." },
      { id: "ms_2", title: "Book the kickoff call with Northwind Florals", with: "Northwind Florals", channel: "gmail", state: "resolved", turns: 4, last_at: "2026-10-28T09:12:00", note: "Call booked for Mon 3 Nov, 10:00. Filed to Notion." },
      { id: "ms_3", title: "Agree a new logo deadline with Pine & Co", with: "Pine & Co", channel: "gmail", state: "handed_back", turns: 2, last_at: "2026-10-29T14:03:00", note: "They asked for a discount. You never said how much it may give, so it handed this back to you." },
    ],
    waiting: [
      { id: "dr_1", mission: "ms_1", channel: "gmail", to: "accounts@harborbakery.example", subject: "Re: Invoice 2026-031", excerpt: "Thanks for the update. Friday works; I'll look out for it then. If anything changes, just let me know.", confidence: 88, risks: ["Mentions a payment date you have not confirmed"], why: "held" },
      { id: "dr_2", mission: null, channel: "gmail", to: "hello@quietfern.example", subject: "Quote for a 30 s loop", excerpt: "Happy to help. For a 30 second loop my usual rate is on the attached sheet; do you have a deadline in mind?", confidence: 72, risks: [], why: "below_bar" },
    ],
  },
  {
    id: "tw_family",
    name: "Family admin",
    purpose: "Handles school and club email: forms, pickups and the monthly invoice.",
    state: "paused",
    since: "2026-09-15",
    channels: [
      { kind: "gmail", account: "alex.moreno@home.example", status: "needs_sign_in", autonomy: "review", bar: null, health: "stale", last_at: "2026-09-26T19:30:00" },
    ],
    filled: { who: 1, channels: 0.5, voice: 1, knowledge: 0.5, chores: 1, never: 1, autonomy: 1, memory: 0, mission: 1 },
    week: { sent: 0, sent_alone: 0, held_by_risk: 0, median_reply_min: null, cost_usd: 0 },
    missions: [
      { id: "ms_4", title: "Dispute the extra club days in September", with: "Brightside Club", channel: "gmail", state: "resolved", turns: 5, last_at: "2026-09-24T18:02:00", note: "Credit of two days agreed." },
    ],
    waiting: [],
    paused_because: "Google asked you to sign in again on 26 Sep.",
  },
  {
    id: "tw_partners",
    name: "Partnerships",
    purpose: "Reaches out to Suno creators and keeps each conversation going until you agree.",
    state: "setting_up",
    since: null,
    channels: [],
    filled: { who: 0.5, channels: 0, voice: 0, knowledge: 0, chores: 0, never: 0, autonomy: 0, memory: 0, mission: 0 },
    week: { sent: null, sent_alone: null, held_by_risk: null, median_reply_min: null, cost_usd: 0.06 },
    missions: [],
    waiting: [],
  },
];

// The setup conversation for Partnerships. Each frame is one reply from Athena.
// `user` is what the person did to get the frame; `ops` change the twin; `confirm` inks her proposals;
// `panel` names the interactive part shown in the main area for this frame (see SCHEMA.md).
export const need =
  "I want a twin that writes to Suno creators whose tracks I'd like to feature on my channel, and keeps each conversation going until we agree.";

export const frames = [
  {
    user: { text: need },
    elapsed_s: 5.8,
    line: "A twin for creator outreach: it writes to musicians as you and keeps each conversation going until you have a yes. I'll build it here while we talk.",
    ops: [
      { op: "add", piece: { id: "p_name", place: "who", label: "Partnerships", detail: "the name I'd give it", origin: "athena" } },
      { op: "add", piece: { id: "p_purpose", place: "who", label: "Writes to Suno creators and keeps each conversation going until you agree", origin: "you" } },
      { op: "add", piece: { id: "p_mtype", place: "mission", label: "Get a creator's permission to feature their track", detail: "the kind of mission it will run", origin: "athena" } },
    ],
    confirm: [],
    panel: null,
    ask: { place: "who", text: "Who should it sign as when it writes?", suggestions: ["As me, Alex", "As Alex from Low Tide Visuals", "As my assistant, on my behalf"] },
  },
  {
    user: { text: "", choice: 1 },
    elapsed_s: 4.2,
    line: "It signs as Alex from Low Tide Visuals. To write to creators it needs your mailbox. Sign in with Google; I'll only ask to read and send mail.",
    ops: [
      { op: "add", piece: { id: "p_sign", place: "who", label: "Signs as Alex from Low Tide Visuals", origin: "you" } },
      { op: "add", piece: { id: "p_gmail", place: "channels", label: "Gmail", detail: "waiting for you to sign in", origin: "athena" } },
    ],
    confirm: ["p_name"],
    panel: { kind: "connect", channel: "gmail" },
    ask: { place: "channels", text: "Sign in with the Google account it should write from.", suggestions: ["Sign in with Google", "Use a different account", "Skip mail for now"] },
  },
  {
    user: { text: "", choice: 0 },
    elapsed_s: 6.9,
    line: "Signed in as alex@lowtide-visuals.example. To sound like you, it learns only from mail you wrote yourself. I found six replies you sent to musicians this year; I'd keep the four marked.",
    ops: [
      { op: "change", piece: { id: "p_gmail", detail: "alex@lowtide-visuals.example", origin: "you" } },
    ],
    confirm: ["p_gmail"],
    panel: { kind: "samples" },
    ask: { place: "voice", text: "Which of these sound like you?", suggestions: ["The four you marked", "All six", "I'll paste one instead"] },
  },
  {
    user: { text: "", choice: 0 },
    elapsed_s: 7.4,
    line: "From those four, this is how you write to creators. I've set its style to match; the dials show where each value came from.",
    ops: [
      { op: "add", piece: { id: "p_v1", place: "voice", label: "Warm and short, first name first", origin: "athena", evidence: ["s1", "s2", "s4"] } },
      { op: "add", piece: { id: "p_v2", place: "voice", label: "Opens with something specific about their track", origin: "athena", evidence: ["s1", "s3"] } },
      { op: "add", piece: { id: "p_v3", place: "voice", label: "Ends with one clear question", origin: "athena", evidence: ["s2", "s3", "s4"] } },
      { op: "add", piece: { id: "p_v4", place: "voice", label: "Signs off 'cheers, Alex'", origin: "athena", evidence: ["s1", "s2", "s3", "s4"] } },
    ],
    confirm: [],
    panel: { kind: "style" },
    ask: { place: "voice", text: "Is that a bit too casual for a first message to a stranger?", suggestions: ["Keep it as it is", "A little more formal at first contact", "Shorter still"] },
  },
  {
    user: { text: "", choice: 1 },
    elapsed_s: 5.1,
    line: "First messages get full sentences and no slang; replies stay as relaxed as you are. Next, what it may know. Connect Notion and pick the pages it can answer from.",
    ops: [
      { op: "add", piece: { id: "p_v5", place: "voice", label: "First message: full sentences, no slang", origin: "you" } },
      { op: "dial", dial: "formality", value: 3, source: "you" },
      { op: "add", piece: { id: "p_notion", place: "channels", label: "Notion", detail: "waiting for your key", origin: "athena" } },
    ],
    confirm: ["p_v1", "p_v2", "p_v3", "p_v4"],
    panel: { kind: "connect", channel: "notion" },
    ask: { place: "knowledge", text: "Paste the key from your Notion integration, then choose its pages.", suggestions: ["I've pasted it", "Show me where to find it", "Skip Notion for now"] },
  },
  {
    user: { text: "", choice: 0 },
    elapsed_s: 4.6,
    line: "Notion accepted the key for the Low Tide studio workspace. These are the pages it can see. I'd leave your journal out.",
    ops: [
      { op: "change", piece: { id: "p_notion", detail: "Low Tide studio", origin: "you" } },
    ],
    confirm: ["p_notion"],
    panel: { kind: "pages" },
    ask: { place: "knowledge", text: "Which pages may it answer from?", suggestions: ["Offer, stats and shortlist", "Everything it can see", "Only the offer"] },
  },
  {
    user: { text: "", choice: 0 },
    elapsed_s: 5.5,
    line: "It will answer from those three and nothing else. Notion can do more than answer questions: these are ready-made chores it can run there.",
    ops: [
      { op: "add", piece: { id: "p_k1", place: "knowledge", label: "Partnership offer", detail: "Notion page", origin: "you" } },
      { op: "add", piece: { id: "p_k2", place: "knowledge", label: "Channel stats", detail: "Notion page, read fresh each time", origin: "you" } },
      { op: "add", piece: { id: "p_k3", place: "knowledge", label: "Track shortlist", detail: "Notion database", origin: "you" } },
      { op: "add", piece: { id: "p_n0", place: "never", label: "Never quote a page you didn't share", origin: "athena" } },
    ],
    confirm: [],
    panel: { kind: "chores" },
    ask: { place: "chores", text: "Which should it run?", suggestions: ["File outcomes and the practice page", "All three", "None for now"] },
  },
  {
    user: { text: "", choice: 1 },
    elapsed_s: 4.9,
    line: "Three chores, all on Notion. Now the lines it must never cross. I'd start with these.",
    ops: [
      { op: "add", piece: { id: "p_c1", place: "chores", label: "File the outcome", detail: "adds each yes to 'Partnerships'", origin: "you" } },
      { op: "add", piece: { id: "p_c2", place: "chores", label: "Task inbox", detail: "new missions from your 'Twin inbox' page", origin: "you" } },
      { op: "add", piece: { id: "p_c3", place: "chores", label: "Practice page", detail: "rehearses on a Notion page first", origin: "you" } },
      { op: "add", piece: { id: "p_n1", place: "never", label: "Never promise money or a fee", origin: "athena" } },
      { op: "add", piece: { id: "p_n2", place: "never", label: "Never agree to exclusive rights", origin: "athena" } },
      { op: "add", piece: { id: "p_n3", place: "never", label: "Never share another creator's contact", origin: "athena" } },
    ],
    confirm: [],
    panel: null,
    ask: { place: "never", text: "Anything to add?", suggestions: ["Those are right", "Also: never send attachments", "Also: never write after 9 pm their time"] },
  },
  {
    user: { text: "", choice: 2 },
    elapsed_s: 4.4,
    line: "Four lines it will never cross. How much may it send without you? If anything is on its risk list, it always waits for you.",
    ops: [
      { op: "add", piece: { id: "p_n4", place: "never", label: "Never write after 9 pm their time", origin: "you" } },
    ],
    confirm: ["p_n0", "p_n1", "p_n2", "p_n3"],
    panel: { kind: "autonomy" },
    ask: { place: "autonomy", text: "For Gmail?", suggestions: ["Assist: I sign every send", "First message Assist, replies Auto", "Auto, with the risk check"] },
  },
  {
    user: { text: "", choice: 1 },
    elapsed_s: 5.2,
    line: "First messages wait for your signature; replies go on their own when it is at least 80 sure and nothing is on its risk list. Reading your mail, I noticed a few things about you. It only uses the ones you keep.",
    ops: [
      { op: "add", piece: { id: "p_a1", place: "autonomy", label: "Gmail, first message: Assist", detail: "you sign it", origin: "you" } },
      { op: "add", piece: { id: "p_a2", place: "autonomy", label: "Gmail, replies: Auto", detail: "at 80 or more, empty risk list", origin: "you" } },
      { op: "add", piece: { id: "p_a3", place: "autonomy", label: "Notion practice page: Auto", detail: "nothing leaves Notion", origin: "athena" } },
    ],
    confirm: [],
    panel: { kind: "memory" },
    ask: { place: "memory", text: "Keep these?", suggestions: ["Yes to the first two", "Yes to all four", "One by one"] },
  },
  {
    user: { text: "", choice: 0 },
    elapsed_s: 4.0,
    line: "It remembers two things about you and forgets the rest. It's ready to try: give it a first mission. It will rehearse on your practice page, with me playing the creator.",
    ops: [
      { op: "add", piece: { id: "p_m1", place: "memory", label: "You make a free visualizer in exchange for a credit", origin: "you", evidence: ["s1"] } },
      { op: "add", piece: { id: "p_m2", place: "memory", label: "You publish on Fridays", origin: "you", evidence: ["s3"] } },
    ],
    confirm: ["p_a3"],
    panel: null,
    ask: { place: "mission", text: "What should it get done first?", suggestions: ["Get Lumen Vale's yes to feature 'Glass Harbor'", "Ask three shortlisted creators if they're open", "Follow up with Mira Soleil"] },
  },
  {
    user: { text: "", choice: 0 },
    elapsed_s: 3.6,
    line: "Mission set. I'll play Lumen Vale on your practice page. Mark each draft 'that's me' or 'not me'; anything you change teaches it.",
    ops: [
      { op: "add", piece: { id: "p_ms", place: "mission", label: "Get Lumen Vale's yes to feature 'Glass Harbor'", detail: "rehearse first", origin: "you" } },
    ],
    confirm: ["p_mtype"],
    panel: { kind: "rehearsal" },
    ask: null,
  },
];

// Interactive parts the frames name in `panel`.
export const connect = {
  gmail: {
    asks_for: ["Read your mail", "Send mail as you"],
    never_asks_for: ["Delete mail", "Your contacts", "Your calendar"],
    states: {
      idle: "Sign in with Google",
      waiting: "Waiting for you in the browser. Google's sign-in page opened there.",
      connected: "Signed in as alex@lowtide-visuals.example",
      failed: "Google's sign-in did not finish. Nothing was saved.",
    },
    waiting_s: 18,
    timeout_s: 600,
  },
  notion: {
    where_to_find: ["In Notion, open Settings, then Connections", "Make a new integration called 'Athena twin'", "Copy its key and paste it here", "Share the pages it may read with that integration"],
    states: {
      idle: "Paste your Notion key",
      checking: "Checking the key with Notion",
      connected: "Notion accepted the key: Low Tide studio",
      rejected: "Notion did not accept that key. Check you copied all of it.",
    },
    checking_s: 2,
  },
};

export const samples = [
  { id: "s1", to: "Mira Soleil", subject: "Your track 'Salt Lines'", date: "2026-03-03", words: 92, mark: true, excerpt: "Hi Mira, 'Salt Lines' has been on repeat here since Tuesday; that bridge at 2:10 is something else. I make visualizers for tracks I love..." },
  { id: "s2", to: "Odd Weather", subject: "Re: visualizer draft", date: "2026-05-19", words: 61, mark: true, excerpt: "Hey! Glad you liked it. I can push the colour a bit warmer and send a new cut by Thursday. Does that work?..." },
  { id: "s3", to: "Kite & Copper", subject: "Feature on Friday?", date: "2026-07-02", words: 74, mark: true, excerpt: "Hi both, I'd love to feature 'Low Orbit' this Friday with a full visualizer. Would you be up for it?..." },
  { id: "s4", to: "Juno Park", subject: "Re: credits", date: "2026-08-21", words: 48, mark: true, excerpt: "All sorted, your name and link are in the description now. Thanks again for letting me use it. cheers, Alex" },
  { id: "s5", to: "Marlow", subject: "Fwd: invoice", date: "2026-06-11", words: 12, mark: false, excerpt: "See below. Can you check this?", why_not: "A forward, not your own writing" },
  { id: "s6", to: "Team Low Tide", subject: "Weekly notes", date: "2026-09-30", words: 310, mark: false, excerpt: "Notes for the week: render queue, the Friday slot, invoices...", why_not: "Written to your team, not to a creator" },
];

// Eight style dials, 1-5. `source`: learned (from samples), preset, you.
export const style = {
  presets: ["Friendly pro", "Brief and direct", "Warm storyteller"],
  dials: [
    { id: "formality", label: "Formality", low: "casual", high: "formal", value: 2, source: "learned" },
    { id: "warmth", label: "Warmth", low: "cool", high: "warm", value: 4, source: "learned" },
    { id: "humor", label: "Humour", low: "none", high: "playful", value: 2, source: "learned" },
    { id: "energy", label: "Energy", low: "calm", high: "lively", value: 3, source: "learned" },
    { id: "length", label: "Length", low: "short", high: "long", value: 2, source: "learned" },
    { id: "directness", label: "Directness", low: "gentle", high: "direct", value: 4, source: "learned" },
    { id: "expressiveness", label: "Expressiveness", low: "plain", high: "vivid", value: 3, source: "learned" },
    { id: "detail", label: "Detail", low: "light", high: "thorough", value: 2, source: "preset" },
  ],
};

export const pages = [
  { id: "pg1", title: "Partnership offer", kind: "page", suggest: true },
  { id: "pg2", title: "Channel stats", kind: "page", suggest: true },
  { id: "pg3", title: "Track shortlist", kind: "database", suggest: true },
  { id: "pg4", title: "Rates and terms", kind: "page", suggest: false, why_not: "For clients, not creators" },
  { id: "pg5", title: "Journal", kind: "page", suggest: false, why_not: "Personal" },
];

// Ready-made chores (playbook presets), grouped by the tool they use. More tools arrive later.
export const chorePresets = [
  { id: "file-outcome", tool: "notion", name: "File the outcome", does: "When a conversation ends in a yes, it adds a row to your 'Partnerships' database: track, link, terms and date.", kind: "outcome", suggest: true },
  { id: "task-inbox", tool: "notion", name: "Task inbox", does: "Picks up new missions you write on your 'Twin inbox' page.", kind: "inbox", suggest: false },
  { id: "practice-page", tool: "notion", name: "Practice page", does: "Rehearses a conversation on a Notion page before it ever writes to a real person.", kind: "test", suggest: true },
  { id: "answer-comments", tool: "notion", name: "Answer comments", does: "Replies to comments on pages you share, as you.", kind: "channel", suggest: false, later: true },
  { id: "calendar-hold", tool: "calendar", name: "Hold a time", does: "Pencils a call into your calendar when someone agrees to talk.", kind: "outcome", coming: true },
  { id: "slack-thread", tool: "slack", name: "Answer in Slack", does: "Replies in a Slack thread as you.", kind: "channel", coming: true },
];

export const autonomy = {
  bar_default: 80,
  rule: "It sends alone only when the channel is on Auto, it is at least as sure as the bar, and its risk list is empty. Anything else waits for you. A paused channel never sends.",
  channels: [
    { kind: "gmail", proposed: "assist", options: ["review", "assist", "auto"], split: { first_message: "assist", replies: "auto" }, bar: 80 },
    { kind: "notion", proposed: "auto", options: ["review", "assist", "auto"], scope: "practice page only", bar: 60 },
  ],
};

export const memory = [
  { id: "f1", fact: "You make a free visualizer in exchange for a credit", from: "Your reply to Mira Soleil, 3 Mar", suggest: "keep" },
  { id: "f2", fact: "You publish on Fridays", from: "Your mail to Kite & Copper, 2 Jul", suggest: "keep" },
  { id: "f3", fact: "Your channel has about 12,000 subscribers", from: "Channel stats page", suggest: "drop", reason: "It changes; it reads the page fresh instead" },
  { id: "f4", fact: "You once offered $50 for a track", from: "Your reply to Odd Weather, 19 May", suggest: "drop", reason: "A promise of money; it must never make one" },
];

// The dress rehearsal on the practice page. `at_s` is seconds since it started.
export const rehearsal = {
  where: "Notion practice page: 'Practice: Lumen Vale'",
  played_by: "Athena plays Lumen Vale",
  turns: [
    { id: "t1", at_s: 0, side: "twin", kind: "first_message", elapsed_s: 6.2, confidence: 84, risks: [], decision: "waits", decision_why: "First messages wait for your signature",
      text: "Hi Lumen, I've had 'Glass Harbor' on repeat all week; the way the synths open up after the second chorus is lovely. I'm Alex from Low Tide Visuals: I make music visualizers and feature tracks I love on my channel every Friday. Would you be open to me featuring 'Glass Harbor' with a full visualizer and a credit to you?\n\ncheers, Alex",
      mark: "me" },
    { id: "t2", at_s: 14, side: "creator", text: "Hey Alex! That sounds great honestly. What would I get out of it? And would it need to be exclusive to your channel?" },
    { id: "t3", at_s: 21, side: "twin", kind: "reply", elapsed_s: 7.8, confidence: 77, risks: ["They asked about exclusivity: it must never agree to exclusive rights"], decision: "waits", decision_why: "Below your bar of 80, and one risk on its list",
      text: "Great question! You'd get a free visualizer you can use anywhere, plus a credit and link in the description. And no, totally not exclusive, it's yours to share wherever you like!\n\ncheers, Alex",
      mark: "edited",
      edited_text: "You'd get a free visualizer you can use anywhere, plus a credit and a link in the description. It isn't exclusive: the track and the visualizer stay yours to share anywhere.\n\ncheers, Alex",
      learned: "Fewer exclamation marks; say plainly what stays theirs" },
    { id: "t4", at_s: 52, side: "creator", text: "Sounds fair. Go for it, credit me as Lumen Vale and link the track please." },
    { id: "t5", at_s: 58, side: "twin", kind: "reply", elapsed_s: 4.9, confidence: 91, risks: [], decision: "sent_alone", decision_why: "Auto: 91 is above your bar of 80 and its risk list is empty",
      text: "Brilliant, thank you! It goes out this Friday, credited to Lumen Vale with a link to 'Glass Harbor'. I'll send you the link when it's live.\n\ncheers, Alex",
      mark: "me" },
  ],
  outcome: {
    state: "resolved",
    filed: { chore: "file-outcome", where: "Notion: Partnerships", row: { Track: "Glass Harbor", Artist: "Lumen Vale", Terms: "Credit and link, no fee, not exclusive", Date: "Fri 31 Oct" } },
  },
  stuck_alternative: {
    state: "handed_back",
    at_turn: "t2",
    creator_text: "Hey Alex, I'd want $200 for it, is that OK?",
    why: "They asked for money. It must never promise money, so it handed the conversation back to you.",
  },
  slow_after_s: 12,
};

export const golive = {
  line: "Partnerships is live. First messages wait for you; replies may go on their own. You'll find it on your twins page.",
  stays: ["Gmail first messages: Assist", "Gmail replies: Auto at 80", "Notion practice page: Auto"],
};
