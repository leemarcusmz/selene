---
name: selene-video-script-writer
description: "Co-write a Selene Dreams video script + shot list with Marcus (Phase A — collaborative, not one-shot) for a Reels/TikTok video, sourcing shots from real footage first, then AI generation. Use when Marcus wants to plan a Selene Dreams video, brings a video idea or content-pillar topic, or asks for a script/shot list/voiceover for a Reel or TikTok. metadata: type: workflow"
---

# Selene Dreams Video Script Writer

Co-writes a video script and shot list for Selene Dreams with Marcus, then hands
off to `seedance-director` for any shots that need AI-generated visuals. Produces
three outputs per video: a **shot list**, a **timed voiceover script**, and a
**hook line**.

## Current phase: A — co-creation (not autonomous)

This skill currently operates in **Phase A**: everything is written together
with Marcus turn by turn, not drafted in one pass. Do not draft a complete
script and present it as a finished artifact — propose, ask, revise, shot by
shot. Phase B (single-draft-and-approve) and Phase C (fast-path autonomous)
are designed but NOT active — do not switch phases without Marcus explicitly
saying so ("gut check," his words — no automatic trigger). If in doubt, stay
in Phase A.

## Step 1: Where's the idea coming from?

Ask Marcus (or infer from what he already said):
- A specific idea he's bringing, OR
- A content pillar: fabric myth-busting, sleep/material science, how-to-choose,
  care & longevity, origin/craft story, or an objections-driven topic (check
  `objections.md` in the selene-ig-memory repo if reachable — a topic that's
  recurring there outranks the static five pillars once it has real signal)

If Marcus has no preference, the proposed starting order (his call to override,
not a rule) is: 1) fabric myth-busting, 2) how-to-choose, 3) sleep/material
science, 4) origin/craft story, 5) care & longevity, 6) objections-driven.

## Step 2: Shot sourcing — three-tier waterfall, real footage first

For each beat the idea implies, source it in this priority order:

1. **Real footage** — check the Asset Library (`asset_library.py` /
   `_state/asset-library.json` in the video pipeline folder) for a matching
   real shoot photo/clip (by fabric, product, variant, setting). If found, use
   it. Zero AI risk, zero generation cost.
2. **Animate an approved still** — a Generation Queue row already `Done`
   (passed the 12-point brand rubric + generation QA). Lower AI risk than a
   fresh generation.
3. **Generate from text** — only when neither of the above covers the shot.
   Usually the aspirational/atmospheric beats (dreamlike environments, quick
   seasonal variants).

Most videos will mix tiers. Tag every shot in the shot list with which tier
sourced it — this tag flows through to outcome tracking later, so don't skip
it even in a rough draft.

If the Asset Library is empty or not yet set up, say so plainly and fall back
to tiers ②③ — don't silently skip tier ① checking.

## Step 3: Shot list

Propose shots one at a time or in a small batch, each with: what it shows,
its source tier, and a rough duration (single clips cap at 15s per
`seedance-director`'s rules — most finished videos need 2-4 clips). Get
Marcus's reaction before locking each one in. Note any shot destined for tier
②/③ generation with which Higgsfield model fits best: `wan-2.6` for
fabric-heavy close shots (built for fluid dynamics/gravity — the thing AI
video usually gets wrong with bedding), `seedance-2.0` as the general default,
`veo-3.1` as a candidate for atmospheric/establishing shots. This is a
suggestion for the human running generation later, not something this skill
executes — this skill does not call any generation API.

## Step 4: Voiceover script

Write to Selene's brand voice rules (`brand-identity.md` / project memory
`[[selene-brand-identity]]`):
- Alternate one plain/direct sentence with one atmospheric/ethereal one —
  not all-poetic, not all-practical.
- "Soft" words — avoid harsh, industrial, mechanical, coarse language, per
  the WE ARE / WE ARE NOT lists.
- Time the script to the shot list — roughly how many words fit each shot's
  duration (conversational pace, ~2.5 words/second is a reasonable start).

## Step 5: The hook (first 1-2 seconds)

Write 2-3 hook options for the opening line — spoken, on-screen text, or
both. Most retention is won or lost here; don't treat it as an afterthought
tacked onto the rest of the script. Check `hooks-library.md` (same repo as
the image pipeline) for patterns that have worked before, filtered through
Selene's calm voice — most of that library was built for captions, so adapt
rather than copy verbatim.

## Step 6: Present, revise

Show the shot list + voiceover script + hook options together. Ask Marcus:
approve / revise a specific part / try a different angle entirely. This is
Phase A — expect and welcome back-and-forth, don't rush to a final draft.

## Step 7: Handoff

Once Marcus is happy:
- Tier ②/③ shots go to `seedance-director` for the actual EN/ZH generation
  prompts (pass the shot description + tier + suggested model).
- The approved voiceover script and hook are ready for `artlist_client.py`
  once Marcus explicitly approves spending credits on it — this skill never
  calls that itself.
- If a Video Queue sheet row exists for this video, note what would go in
  each column (see `video_queue_schema.md`) — do not write to any sheet
  without Marcus's explicit approval, same rule as the image pipeline.

## Self-improvement (not active yet — no data exists)

Once `video-script-playbook.md` exists with real outcome data (see the
performance-review-agent design in project memory), read it before writing:
which hooks, pacing, and pillars have actually performed. Until then, say
so plainly ("no outcome data yet — best judgment") rather than inventing
confidence.

## Hard rules

- Stay in Phase A (collaborative) unless Marcus explicitly says otherwise.
- Never call any generation API — this skill only writes text/plans.
- Never write to a sheet without explicit approval.
- Tag every shot with its source tier — untagged shots break the outcome
  tracking loop downstream.
- If the Asset Library, `objections.md`, or `video-script-playbook.md` are
  unreachable, say so and proceed on best judgment rather than blocking.
