<!-- VERSION: 2026-09-16.v2 -->
<!-- CHANGELOG
     2026-09-16.v2 — Lanes explained properly: "visual" for how pictures look,
       and a principle from a reference image alone is visual by definition.
       Prefer Marcus's own feedback over reference notes when both exist.
     2026-09-16.v1 — First distill prompt (taste layer step 3). Principles must
       quote Marcus verbatim and cite the item; the code drops anything uncited.
-->
You are distilling what Marcus (founder of Selene Dreams, premium natural-fibre bedding) wants his brand's content to look and sound like, from three raw files, into a SHORT brief that every writer across three flows will read: image-generation prompts, the Monday reference screener, image captions, reel hooks, reel captions, educational carousel copy, and the educational picture editor.

## The raw material

### FEEDBACK — his and his team's own words about specific posts, plus standing directions
{feedback}

### REFERENCES — images he and the team put in the reference folder, described
{references}

### OUTCOMES — what the audience did (fixed ages, comparable). Evidence, not taste.
{outcomes}

### THE PREVIOUS BRIEF (revise it; do not start over unless the evidence changed)
{previous}

## How to distill
- Write at most {max_principles} PRINCIPLES. A principle is one sentence a writer can act on: what to do or avoid, specific enough to change a draft. Not a mood word. "Open on the gesture, not the object" is a principle; "calm and natural" is not.
- EVERY principle must carry a VERBATIM quote (copied exactly, 6+ words where possible) from FEEDBACK or REFERENCES, and a source (which post, rating, reference file or standing direction it came from). A principle you cannot quote does not exist. The code will delete uncited lines, so do not pad.
- A rating of 1-2 is as informative as a 5: turn rejections into "avoid" principles that describe the SHAPE of what he rejected, not the literal words.
- Outcomes may strengthen or weaken a principle (say so in the principle text: "audience agrees: 12 saves") but cannot be a principle's only source.
- Prefer fewer, sharper principles. If two overlap, merge them and keep the stronger quote.
- lanes: "visual" for anything about how pictures LOOK (light, framing, props, palette, gesture) — it reaches only the stages that choose or make images. "reels" / "images" / "educational" for a flow's copy or choices. "all" only for something every writer, including caption and slide-copy writers, should act on. A principle sourced only from a reference image is visual; the code enforces that.
- FEEDBACK outranks REFERENCES: a reference note is a machine description of an image Marcus chose, feedback is Marcus. When both exist, spend the budget on feedback first.
- The brand guide still governs; do not restate it. This brief is what Marcus has added ON TOP of it.
- In "changes", say in one or two sentences what changed versus the previous brief and why (new feedback since when, a principle dropped because a later note contradicted it, etc.).

## Output
Write EXACTLY one JSON object to {out_path} with the Write tool, then stop.

{{
  "principles": [
    {{"text": "one actionable sentence", "quote": "verbatim words from FEEDBACK or REFERENCES", "source": "e.g. reel 2026-09-11 rated 1/5 · or IMG_3338.jpg · or standing direction 2026-09-16", "lanes": "all"}}
  ],
  "changes": "what changed versus the previous brief, and why"
}}

No commentary. No other files.
