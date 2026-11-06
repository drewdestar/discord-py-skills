## Bot reply copy: the patterns that mark a reply as AI-written

Upstream antislop-copywriting names ~30 patterns; these are the ones that
show up in bot replies. All three marked v3.2.26 are new in that release.

**Empty AI vocabulary (R-16).** "unlock", "elevate", "empower", "delve",
"showcase", "testament", "journey", "robust", "game-changer", "next-level",
"seamless", "cutting-edge", "revolutionary". Cut the word; if the sentence
has nothing left, cut the sentence.

**Significance inflation (R-36).** "the future of X", "marking a pivotal
moment", "a testament to", "revolutionizing", "a new era of". Prove it with
a fact or cut it.

**Chatbot closers (R-36).** "I hope this helps!", "Let me know if you have
any questions", "Would you like me to expand on this?", "You're welcome!".
A bot that just answered does not need to announce its availability.

**Fake-candid openers (R-36).** "Honestly?", "Let's be honest", "Here's the
thing", "Real talk". Delete the promise, keep the content.

**Signposting announcements (R-36).** "Let's dive in", "Here's what you
need to know", "In this article we'll explore", "Without further ado",
"The key insight is" (Anaconda). Delete the signpost; the content follows
anyway.

**Filler phrases (R-36).** "In order to" for "to", "Due to the fact that"
for "because", "At this point in time" for "now", "It is important to note
that" for nothing. Cut the filler; use the short word.

**Temporal runway cliches, v3.2.26 (R-16, R-36).** Openings that set a broad
scene before saying an ordinary thing: "In today's fast-paced world", "In an
era of rapid technological disruption", "In today's ever-evolving digital
landscape". Cut the runway; start with the subject.

**Theatrical takeaways, v3.2.26 (R-36).** "Read that again.", "Let that sink
in.", "The message is clear:", "That distinction matters.", "The takeaway is
simple:", "Here is the bottom line:". Stage direction pretending to be copy.
Let the claim stand on its evidence.

**Title case in list elements, v3.2.26 (R-36).** Capitalizing every word in
a bullet: "- Comprehensive Security Audits Across All Repositories". Use
sentence case. Proper nouns, acronyms, and genuine titles keep capitals.

**All-caps emphasis (R-36).** A whole clause in ALL CAPS to shout emphasis.
Write the emphasis into the sentence or cut it.

**Rule of three overuse (R-36).** "innovation, inspiration, and insights".
AI defaults to threes. Count the items that are true and keep only those.

**Negative parallelism (R-36).** "It's not just a tool, it's a workflow."
It needs a wrong answer to push against, so the model invents one. State
the second half, or join both halves if both are real: "faster and
cheaper".

**Staccato drama (R-36).** Short sentences chopped into beats to sound
decisive. Join them with the connective they were hiding ("since", "so",
"but").

**False ranges (R-36).** "from first click to final invoice, and everything
in between" where the endpoints are not on a meaningful scale. No range
without a source (R-17).
