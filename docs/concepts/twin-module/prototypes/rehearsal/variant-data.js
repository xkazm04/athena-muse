// Rehearsal variant - extra invented copy, consistent with ../shared/twin-data.js.
// The script's beats, the twin's pencil lines per frame, the overview's mission scripts and
// Athena's lines during the rehearsal. Nothing here is real; see NOTES.md, "Variant data".
window.REHEARSAL = {
  // Before the first frame: the person has not said what the twin is for.
  describe: {
    line: "Tell me what this twin should handle for you. I'll write its first conversation as a script while we talk, and each answer fills a line.",
    ask: {
      place: "who",
      text: "What should your twin do for you?",
      suggestions: [
        "Write to Suno creators about featuring their tracks",
        "Answer client email for the studio",
        "Handle school and club email",
      ],
    },
  },

  // Frame 11 has no question in the shared data (the rehearsal starts); the panel still asks one.
  f11ask: { place: "mission", text: "Start the rehearsal on your practice page?", suggestions: ["Start it", "Change the mission first", "Not yet"] },

  // Names that fill the blanks once the mission is set (frame 11).
  names: { creator: "Lumen", artist: "Lumen Vale", track: "Glass Harbor", date: "Fri 31 Oct", terms: "Credit and link, no fee, not exclusive" },

  // The script: the conversation its first mission will need, in beat order.
  // `needs[]`: what the twin needs to play the beat. A need is met in pencil when one of its pieces
  // is her proposal, in ink when one of them is confirmed. `got` is how the need reads once met.
  beats: [
    {
      id: "b1", side: "twin", turn: "t1", title: "Its first message",
      needs: [
        { place: "who", ids: ["p_sign"], need: "needs a name to sign", got: "signs as Alex" },
        { place: "channels", ids: ["p_gmail"], need: "needs your mailbox", got: "your Gmail" },
        { place: "voice", ids: ["p_v1", "p_v2", "p_v3", "p_v4", "p_v5"], need: "needs your voice", got: "in your voice" },
        { place: "mission", ids: ["p_ms", "p_mtype"], need: "needs a creator and a track", got: "a creator, a track", gotInk: "Lumen Vale" },
        { place: "autonomy", ids: ["p_a1"], need: "may it send this alone?", got: "waits for your signature" },
      ],
    },
    {
      id: "b2", side: "creator", turn: "t2", title: "They reply",
      cue: "They ask what they'd get, and whether it's exclusive.",
    },
    {
      id: "b3", side: "twin", turn: "t3", title: "Its answer",
      needs: [
        { place: "voice", ids: ["p_v1", "p_v2", "p_v3", "p_v4", "p_v5"], need: "needs your voice", got: "in your voice" },
        { place: "knowledge", ids: ["p_k1"], need: "needs to know your offer", got: "knows your offer" },
        { place: "never", ids: ["p_n2"], need: "must not agree to exclusivity", got: "never agrees to exclusive" },
        { place: "autonomy", ids: ["p_a2"], need: "may it send this alone?", got: "alone if sure and safe" },
      ],
    },
    {
      id: "b4", side: "creator", turn: "t4", title: "They say yes",
      cue: "They say yes, and how to credit them.",
    },
    {
      id: "b5", side: "twin", turn: "t5", title: "Its thanks",
      needs: [
        { place: "voice", ids: ["p_v1", "p_v2", "p_v3", "p_v4", "p_v5"], need: "needs your voice", got: "in your voice" },
        { place: "memory", ids: ["p_m2"], need: "needs to know when you publish", got: "you publish on Fridays" },
        { place: "autonomy", ids: ["p_a2"], need: "may it send this one alone?", got: "may go alone at 80" },
      ],
    },
    {
      id: "b6", side: "chore", turn: "outcome", title: "File the outcome",
      needs: [
        { place: "chores", ids: ["p_c1"], need: "needs a chore to file it", got: "File the outcome" },
        { place: "channels", ids: ["p_notion"], need: "needs your Notion", got: "your Notion" },
      ],
    },
  ],

  // The twin's pencil line for each beat, by the first frame it applies to. [[x]] is a blank in the
  // script until the mission names it (creator, artist, track) or a later answer fills it.
  lines: {
    b1: [
      { from: 3, text: "Hey [[creator]]! '[[track]]' has been on repeat here all week, that synth bit after the second chorus is something else. I make visualizers for tracks I love and feature them on my channel. Up for it?\n\ncheers, Alex" },
      { from: 4, text: "Hi [[creator]], I've had '[[track]]' on repeat all week; the way the synths open up after the second chorus is lovely. I'm Alex from Low Tide Visuals: I make music visualizers and feature tracks I love on my channel. Would you be open to me featuring '[[track]]' with a full visualizer?\n\ncheers, Alex" },
      { from: 10, text: "Hi [[creator]], I've had '[[track]]' on repeat all week; the way the synths open up after the second chorus is lovely. I'm Alex from Low Tide Visuals: I make music visualizers and feature tracks I love on my channel every Friday. Would you be open to me featuring '[[track]]' with a full visualizer and a credit to you?\n\ncheers, Alex" },
    ],
    b3: [
      { from: 3, text: "Great question! You'd get [[what you offer]]. And [[on exclusivity]]\n\ncheers, Alex" },
      { from: 6, text: "Great question! You'd get a free visualizer you can use anywhere, plus a credit and link in the description. And [[on exclusivity]]\n\ncheers, Alex" },
      { from: 7, text: "Great question! You'd get a free visualizer you can use anywhere, plus a credit and link in the description. And no, totally not exclusive, it's yours to share wherever you like!\n\ncheers, Alex" },
    ],
    b5: [
      { from: 3, text: "Brilliant, thank you! It goes out [[when]], credited to [[artist]] with a link to '[[track]]'. I'll send you the link when it's live.\n\ncheers, Alex" },
      { from: 10, text: "Brilliant, thank you! It goes out this Friday, credited to [[artist]] with a link to '[[track]]'. I'll send you the link when it's live.\n\ncheers, Alex" },
    ],
  },

  // The Notion row the last beat will file, cell by cell, with the frame each cell becomes known.
  outcomeCells: [
    { key: "Track", from: 11, blank: "track" },
    { key: "Artist", from: 11, blank: "artist" },
    { key: "Terms", from: 7, blank: "terms" },
    { key: "Date", from: 10, blank: "date" },
  ],

  // The card the stage shows on frames whose shared `panel` is null.
  cast: [
    { who: "Partnerships", role: "your twin", does: "writes as you and keeps the conversation going" },
    { who: "The creator", role: "played by Athena", does: "in the rehearsal, before anyone real" },
    { who: "You", role: "the signature", does: "sign what it may not send alone" },
  ],
  missionChoices: [
    { title: "Get Lumen Vale's yes to feature 'Glass Harbor'", why: "On your Track shortlist; never written to before" },
    { title: "Ask three shortlisted creators if they're open", why: "Three conversations at once; better after a rehearsal" },
    { title: "Follow up with Mira Soleil", why: "You wrote to her on 3 Mar; no answer since" },
  ],

  // Style presets: the dial values a preset sets (formality, warmth, humour, energy, length,
  // directness, expressiveness, detail). Dials you set yourself keep your value.
  presetValues: {
    "Friendly pro": { formality: 3, warmth: 4, humor: 2, energy: 3, length: 3, directness: 3, expressiveness: 3, detail: 3 },
    "Brief and direct": { formality: 3, warmth: 2, humor: 1, energy: 2, length: 1, directness: 5, expressiveness: 2, detail: 2 },
    "Warm storyteller": { formality: 2, warmth: 5, humor: 3, energy: 4, length: 4, directness: 2, expressiveness: 5, detail: 4 },
  },

  // Athena's panel during the rehearsal, one entry per step.
  rehearsal: {
    running: { line: "I'm Lumen Vale now. Your twin is writing its first message on the practice page.", ask: { text: "Want me to play Lumen any differently?", suggestions: ["Just play it", "Ask for money instead", "Be hard to convince"] } },
    waits: { line: "Its first message waits for your signature, as first messages always will.", ask: { text: "Is this you?", suggestions: ["That's me", "Not me", "Let me edit it"] } },
    held: { line: "Lumen asked about exclusivity, so its answer is held: 77 is under your bar of 80, and one risk is on its list.", ask: { text: "Send it as it is, or put it in your words?", suggestions: ["Let me edit it", "That's me, send it", "Not me"] } },
    editing: { line: "Change anything you like. Whatever you change, it learns from.", ask: { text: "Done editing?", suggestions: ["Save my edit", "Use her suggested edit", "Cancel"] } },
    edited: { line: "Got it. It learned to use fewer exclamation marks and to say plainly what stays theirs.", ask: { text: "Carry on with the rehearsal?", suggestions: ["Carry on", "What did it learn?", "Try them asking for money"] } },
    sent: { line: "That reply went on its own: 91 is above your bar of 80 and nothing was on its risk list.", ask: { text: "Was that you?", suggestions: ["That's me", "Not me", "Make the bar stricter"] } },
    resolved: { line: "Lumen said yes. The mission is resolved and the outcome is filed to Notion: Partnerships.", ask: { text: "Ready to let it work for real?", suggestions: ["Go live", "Rehearse once more", "Try them asking for money"] } },
    handed: { line: "Lumen asked for $200. It must never promise money, so it stopped and handed the conversation back to you.", ask: { text: "What now?", suggestions: ["Back to the yes path", "I'll answer this one myself", "Go live anyway"] } },
  },

  // The overview: each mission as a script of beats. `at` is the beat it is on (1-based);
  // `waiting` names what it waits for.
  missionScripts: {
    ms_1: { beats: ["First reminder", "Second reminder", "They said 'by Friday'", "Thank them, confirm Friday", "Payment lands"], at: 4, waiting: "your signature on its reply", draft: "dr_1" },
    ms_2: { beats: ["Offer three times", "They picked Monday", "Confirm the call", "They confirmed", "File it to Notion"], at: 6, waiting: null },
    ms_3: { beats: ["Ask for a new date", "They asked for a discount", "Answer the discount", "Agree the date", "File it"], at: 3, waiting: "you: it handed this back" },
    ms_4: { beats: ["Point out the extra days", "They checked", "Ask for a credit", "They agreed", "Note the credit"], at: 6, waiting: null },
    ms_5: { beats: ["First message", "They reply", "Its answer", "They say yes", "Its thanks", "File the outcome"], at: 7, waiting: null },
  },
};
