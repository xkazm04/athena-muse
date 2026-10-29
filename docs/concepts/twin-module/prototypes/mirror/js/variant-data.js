// Mirror variant: extra invented copy, consistent with ../shared/twin-data.js (see NOTES.md).
// Tagged text: {pieceId|words} = words a piece of the twin shaped; {~|words} = stock phrasing
// (the stranger's voice); {-pieceId|words} = words this frame took out (shown struck, once).
window.TWIN_VARIANT = {
  // The one inbound message the mirror answers, from the first minute.
  inbound: {
    from: "Wren Atlas",
    address: "wren@paperlanterns.example",
    subject: "Your Friday features",
    at: "2026-10-29T15:48:00",
    text: "Hi! A friend sent me your channel and I love the visualizers. I just put 'Paper Lanterns' up on Suno. Do you ever feature tracks from smaller artists like me? What would it involve?",
  },

  // The twin's draft reply to Wren after each frame (12 versions, index = frame).
  drafts: [
    "{~|Dear Wren Atlas,}\n\n{~|Thank you for reaching out regarding} {p_mtype|a feature of your track}{~|. We have received your inquiry and will review your request in due course. Featured artists may be offered compensation for their work. Please do not hesitate to contact us with any further questions.}\n\n{~|Kind regards,}\n{p_name|The Partnerships Team}",
    "{~|Dear Wren Atlas,}\n\n{~|Thank you for reaching out regarding} {p_mtype|a feature of your track}{~|. We have received your inquiry and will review your request in due course. Featured artists may be offered compensation for their work. Please do not hesitate to contact us with any further questions.}\n\n{~|Kind regards,}\n{-p_name|The Partnerships Team} {p_sign|Alex, Low Tide Visuals}",
    "{~|Dear Wren Atlas,}\n\n{~|Thank you for reaching out regarding} {p_mtype|a feature of your track}{~|. I have received your inquiry and will review your request in due course. Featured artists may be offered compensation for their work. Please do not hesitate to contact me with any further questions.}\n\n{~|Kind regards,}\n{p_sign|Alex, Low Tide Visuals}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning; that hush before the last chorus is something else.} {p_v1|Thanks for writing!} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {~|Happy to pay you something for it, too.} {p_v3|Would you be up for it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {-p_v2|that hush before the last chorus is something else.} {p_v5|the quiet just before the last chorus is beautiful.} {-p_v1|Thanks for writing!} {p_v5|Thank you for writing.} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {~|Happy to pay you something for it, too.} {-p_v3|Would you be up for it?} {p_v3|Would you be open to me featuring it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {~|Happy to pay you something for it, too.} {p_v3|Would you be open to me featuring it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {p_k1|In return for a credit and a link, you would get a free visualizer to use anywhere.} {~|Happy to pay you something for it, too.} {p_v3|Would you be open to me featuring it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {p_k1|In return for a credit and a link, you would get a free visualizer to use anywhere.} {-p_n1|Happy to pay you something for it, too.} {p_v3|Would you be open to me featuring it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {p_k1|In return for a credit and a link, you would get a free visualizer to use anywhere.} {p_v3|Would you be open to me featuring it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {p_purpose|I make visualizers for tracks I love and feature them on my channel.} {p_k1|In return for a credit and a link, you would get a free visualizer to use anywhere.} {p_v3|Would you be open to me featuring it?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {-p_purpose|I make visualizers for tracks I love and feature them on my channel.} {p_m2|I make visualizers for tracks I love and feature one on my channel every Friday.} {p_m1|In return for a credit and a link, you would get a free visualizer to use anywhere.} {-p_v3|Would you be open to me featuring it?} {p_v3|Would you be open to me featuring it this Friday?}\n\n{p_v4|cheers, Alex}",
    "{p_v1|Hi Wren,}\n\n{p_v2|'Paper Lanterns' has been on repeat here since this morning;} {p_v5|the quiet just before the last chorus is beautiful.} {p_v5|Thank you for writing.} {p_m2|I make visualizers for tracks I love and feature one on my channel every Friday.} {p_m1|In return for a credit and a link, you would get a free visualizer to use anywhere.} {p_v3|Would you be open to me featuring it this Friday?}\n\n{p_v4|cheers, Alex}",
  ],

  // Full text of the four sent mails she keeps; tags mark the phrases a piece learned from
  // (only pieces whose evidence names that sample). The shared excerpts sit inside these.
  samplesFull: {
    s1: "{p_v1|Hi Mira,} {p_v2|'Salt Lines' has been on repeat here since Tuesday; that bridge at 2:10 is something else.} I make visualizers for tracks I love, and I'd really like to make one for this. {p_m1|You'd get the finished video free to use anywhere, and I'd credit you with a link in the description.} No rush at all, and no hard feelings if it isn't for you.\n\n{p_v4|cheers, Alex}",
    s2: "{p_v1|Hey! Glad you liked it.} I can push the colour a bit warmer and send a new cut by Thursday. {p_v3|Does that work?} The fade felt a little early to me too, so I'll hold the last frame longer. The $50 for the track goes out with it.\n\n{p_v4|cheers, Alex}",
    s3: "Hi both, {p_m2|I'd love to feature 'Low Orbit' this Friday} with a full visualizer. {p_v3|Would you be up for it?} {p_v2|The way the drums drop out halfway through} is how I found it, honestly. Credit and link in the description as always.\n\n{p_v4|cheers, Alex}",
    s4: "{p_v1|All sorted, your name and link are in the description now.} Thanks again for letting me use it. {p_v3|Want me to send you the numbers at the end of the month?}\n\n{p_v4|cheers, Alex}",
  },

  // Before the twin exists (setup: describe).
  describe: {
    line: "Tell me what this twin should handle for you, in a sentence. I'll build it here while we talk, and you'll watch its reply to Wren change as it learns you.",
    ask: { place: "who", text: "What should your twin do for you?", suggestions: [
      "Write to Suno creators and keep each conversation going until we agree",
      "Answer creators who write to me about features",
      "Follow up with creators who went quiet",
    ] },
  },

  // The latest exchange per twin, for the small mirror in an opened ledger row.
  exchanges: {
    tw_desk: { with: "Harbor Bakery", theirs: "Hi Alex, sorry this slipped. Payment for invoice 2026-031 goes out by Friday.", their_at: "2026-10-29T11:40:00", reply_from: "dr_1" },
    tw_family: { with: "Brightside Club", theirs: "We've looked again and credited two days to your September invoice.", their_at: "2026-09-24T17:40:00", reply: "Thank you, that's perfect. Have a good week. Alex", reply_at: "2026-09-24T18:02:00", reply_state: "signed" },
    tw_partners: null,
    tw_partners_live: { with: "Lumen Vale (practice)", theirs: "Sounds fair. Go for it, credit me as Lumen Vale and link the track please.", their_at: "2026-10-29T16:20:00", reply: "Brilliant, thank you! It goes out this Friday, credited to Lumen Vale with a link to 'Glass Harbor'. I'll send you the link when it's live.\n\ncheers, Alex", reply_at: "2026-10-29T16:20:00", reply_state: "alone" },
  },

  // Athena's line and the one question at each step of the rehearsal.
  rehearsal: {
    running: { line: "Mission set. I'm playing Lumen Vale on your practice page; it's writing its first message now.", ask: { text: "Read it as it lands. Is it you?", suggestions: ["That's me, sign it", "Not me", "Let me edit it"] } },
    waits: { line: "Its first message waits for your signature, as you set for Gmail first messages.", ask: { text: "Is this you?", suggestions: ["That's me, sign it", "Not me", "Let me edit it"] } },
    held: { line: "Lumen asked about exclusive rights, which is on its never list, and it was 77 sure against your bar of 80. So it waits for you.", ask: { text: "Fix it in your words, or sign it as it is?", suggestions: ["Use my edit", "That's me, send it", "Not me"] } },
    edited: { line: "Got it. Fewer exclamation marks, and say plainly what stays theirs. It writes that way from now on.", ask: { text: "Let Lumen answer?", suggestions: ["Carry on", "Show what it learned", "Edit it again"] } },
    sent: { line: "Lumen agreed. Its reply was 91 sure with an empty risk list, so it went on its own, as you allowed for replies.", ask: { text: "Was that you too?", suggestions: ["That's me", "Not me", "Let me edit it"] } },
    resolved: { line: "Mission resolved: Lumen said yes, and the outcome is filed in Notion: Partnerships. It's ready to go live.", ask: { text: "Go live?", suggestions: ["Go live", "Rehearse the money question", "Rehearse once more"] } },
    handed: { line: "Lumen asked for money. It must never promise money, so it stopped and handed the conversation back to you.", ask: { text: "How should money questions go?", suggestions: ["I'll answer Lumen myself", "Say kindly that there's no fee", "Back to the yes path"] } },
    golive: { ask: { text: "What next?", suggestions: ["Show me my twins", "Give it a real mission", "Rehearse again"] } },
  },
};
