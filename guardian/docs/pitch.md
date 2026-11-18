# Pitch: OpenHands (2 minutes, ~300 words)

**Line to remember:** *The cheapest line of code is the one you never write.*

---

**[0:00 to 0:20] The graveyard**

> Every bank has a graveyard. It isn't full of failed products. It's full of pull requests.
> Thousands of them, closed with a reviewer's note: "we already have this", "never log a customer ID", "this triples the bill".
> That graveyard is the best training manual we own, and nobody ever visits it.

**[0:20 to 0:35] Ask the room**

> Quick show of hands: who has written a helper, then found out at review that it already existed?
> *(pause)* That's the problem. The knowledge exists. It just arrives too late.

**[0:35 to 1:05] What we built**

> OpenHands turns that graveyard into a colleague who shows up twice, with the same memory both times.
> **Before you code**, you paste a ticket and get one screen back: the helper to call, with a real place it's already used; the past PR that tried this, and why the reviewer rejected it; and the person to ask.
> **When you open the PR**, you get one comment covering reuse, history, security and cost, sorted by severity.

*(Demo: run `/blueprint` on the ticket. It names the planted helper in seconds.)*

**[1:05 to 1:40] Why it's different**

> 1. **It's allowed to say nothing.** If a finding has no file, PR number or rule ID behind it, it's deleted before you see it. Most AI reviewers try to say more. We try to be trusted.
> 2. **It reads the "no"s.** Rejected PRs hold more knowledge than merged ones, so we quote the reviewer's actual reason.
> 3. **It points you to a person, not just code.** It names the owner from git history and the reviewer who rejected the last attempt.
> 4. **There's no new platform.** The playbooks are plain files. A compliance officer can change a rule without raising an engineering ticket.

**[1:40 to 2:00] The metric and the close**

> We'd like banks to track a new number: **lines of code not written.**
> Every time the blueprint points to an existing helper, that's code nobody has to review, test, patch or audit for the next ten years.
> Next step: run it silently on one team for a month and compare it with human reviewers.
> **The best pull request is the one you never had to open.**

---

**Delivery tips**
- Pause after the graveyard line. It's the hook.
- During the demo, read the reviewer's rejection reason aloud. That's when the audience gets it.
- Don't quote numbers we haven't measured. "Evidence or silence" applies to the pitch too.
