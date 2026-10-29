// Passport variant: extra invented copy, consistent with ../shared/twin-data.js.
// The shared file has no words for the describe step, the rehearsal's questions, the style presets'
// dial values or the issued seal, so they live here. Everything is invented (see NOTES.md).
window.TWIN_VARIANT = {
  // passport names for each place; the plain label from the shared data always sits beside it
  sections: {
    who: "Identity",
    channels: "Visas",
    voice: "Voice",
    knowledge: "Reads from",
    chores: "Permits",
    never: "Restrictions",
    autonomy: "Clearance",
    memory: "Endorsements",
    mission: "First entry",
  },

  describe: {
    line: "Tell me what this twin is for, in your words. I'll fill in its document while we talk.",
    ask: "What should this twin do for you?",
    suggestions: [
      "Write to Suno creators I'd like to feature, until they agree",
      "Answer client email for the studio",
      "Handle school and club email",
    ],
  },

  // dial values per style preset; a swap marks every dial "preset"
  presetValues: {
    "Friendly pro": { formality: 3, warmth: 4, humor: 2, energy: 3, length: 3, directness: 3, expressiveness: 3, detail: 3 },
    "Brief and direct": { formality: 3, warmth: 2, humor: 1, energy: 2, length: 1, directness: 5, expressiveness: 2, detail: 1 },
    "Warm storyteller": { formality: 2, warmth: 5, humor: 3, energy: 3, length: 4, directness: 3, expressiveness: 4, detail: 4 },
  },

  // the specimen shown on the voice page: the opening of the first kept sample
  specimen: { sample: "s1", text: "Hi Mira, 'Salt Lines' has been on repeat here since Tuesday; that bridge at 2:10 is something else." },

  // what the bottom panel says during the dress rehearsal (frame 11 has no question of its own)
  rehearsal: {
    intro: { line: null, ask: "Start the rehearsal?", suggestions: ["Start it", "Show me the practice page first", "Change the mission"] },
    running: { line: "The practice page is open. It is writing its first message to Lumen Vale.", ask: "Wait for its first draft?", suggestions: ["Wait for it", "Show me what it reads", "Stop the rehearsal"] },
    waits: { line: "First messages wait for your signature. This one is 84 sure and its risk list is empty.", ask: "Is this you?", suggestions: ["That's me", "Not me", "I'll change a word"] },
    held: { line: "Lumen asked about exclusive rights. Its reply is 77 sure, below your bar of 80, and one thing is on its risk list, so it waits for you.", ask: "Fix it, or let it go as it is?", suggestions: ["I'll edit it", "Send it as it is", "Not me"] },
    editing: { line: "Change anything you like. Whatever you change, it learns from.", ask: "Done editing?", suggestions: ["Save my version", "Keep its version", "Start over"] },
    edited: { line: "Got it: fewer exclamation marks, and say plainly what stays theirs. It writes that way from now on.", ask: "Send your version?", suggestions: ["Send it", "Edit again", "Undo my edit"] },
    sent: { line: "Lumen agreed. Its reply was 91 sure with nothing on its risk list, so it went on its own.", ask: "Was that you?", suggestions: ["That's me", "Not me", "Why did it send?"] },
    resolved: { line: "Mission resolved: Lumen said yes. It filed the row to Notion: Partnerships, as the chore says.", ask: "Ready to go live?", suggestions: ["Go live", "Try it another way", "Not yet"] },
    handed: { line: "This time I played Lumen asking for $200. It must never promise money, so it stopped and handed the conversation back to you.", ask: "What now?", suggestions: ["Good, go live", "Replay the usual path", "Not yet"] },
    golive: { line: null, ask: "Anything else for now?", suggestions: ["Back to my twins", "Give it another mission", "Show me its document"] },
  },

  issued: { date: "29 Oct 2026", by: "Low Tide Visuals" },

  notes: {
    staged: "This example follows one path, so she answers as in the example.",
    typed: "Noted in your words. This example follows one path, so she answers as in the example.",
  },
};
