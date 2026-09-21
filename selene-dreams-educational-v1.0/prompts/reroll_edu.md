<!-- VERSION: 2026-09-09.v1 -->
<!-- CHANGELOG
     2026-09-09.v1 — First release. Marcus's call: generate first, show him the prompt that
       was actually used, let him say what he does and does not like, then regenerate that
       one slide from the ORIGINAL prompt plus his comment. The revised prompt is written
       back into the sheet so the next reroll builds on it and the history is auditable.
-->
You are revising ONE image-generation prompt for a Selene Dreams educational carousel slide, based on what Marcus said about the picture it produced.

# The prompt that produced the current image
{original_prompt}

# What Marcus said about the result
{comment}

# What the slide is
Slide {slide_no} of a {topic_type} carousel ({series}). The words typeset on top of it are:
{slide_text}

# How to revise
- **Change only what his comment asks for.** Everything he did not mention was working. This is a revision, not a fresh idea.
- **Keep the brand skeleton intact**: an editorial photograph for a premium natural-bedding brand, natural light, soft and ethereal mood, serene, subtle film grain, muted natural palette of moss green, ecru and winter white, no text, no logos, no visible faces. If his comment contradicts a part of this, his comment wins for that part only.
- **Translate feelings into things a camera can see.** "Too busy" becomes fewer objects and a plainer background, not the word "simpler". "Too cold" becomes warmer light and warmer tones. "Boring" becomes a specific change of angle, subject or light.
- **If white text sits on this slide** (the slide text above is not empty), the frame needs a calm, mid-to-dark region where that text goes. Say so in the prompt. Never let a revision make the frame paler overall — white type disappears on a washed-out photograph, and nothing corrects for that automatically.
- One paragraph, no line breaks, no lists.

# Output
Write a single JSON object to {out_path}:
{{
  "prompt": "the full revised generation prompt, ready to send as is",
  "changed": "one short line naming what you changed and why, for the sheet remark"
}}
Nothing else.
