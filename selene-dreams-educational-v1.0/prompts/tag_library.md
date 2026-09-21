<!-- VERSION: 2026-09-10.v2 -->
<!-- CHANGELOG
     2026-09-10.v2 — LIBRARY v2. Marcus's matching design: a slide's hidden visual brief is
       matched against a sentence-length DESCRIPTION of each image plus structured fields
       (setting, action, people, light), not keyword tags alone. Also a non-brand flag for
       product types Selene does not sell. Ours / Product are NOT asked here - a vision
       model cannot know whose bedding it is; they come from the Sources tab.
     2026-09-09.v1 — First release. The Image Library's "subject" column held the Drive
       PATH, not tags, so keyword matching was matching filenames: "bed" hit 0 of 50
       images and "Row" hit 45 of 50. This pass looks at each image and writes what is
       actually in it.
-->
You are describing photographs for Selene Dreams, a natural bedding brand, so that a slide
planner can match each slide of an educational carousel to the right picture without a
human looking. The planner reads your DESCRIPTION against a short brief of what the slide
should show, so write the description the way a picture editor would brief a search.

Look at every image in this folder: {img_dir}
The files are named `IMG-XXXX.jpg` after the library id they belong to.

For EACH image, write these fields.

# description — one sentence, 18 to 35 words
What is literally in the frame, in the order a viewer notices it: the main subject, where
it is, what else is in shot, the light. Concrete and searchable. No adjectives doing sales
work, no guessing at brand or fabric you cannot see.
  Good: "A made bed with rumpled oatmeal linen sheets under a window at dusk, one warm
  bedside lamp lit, a closed book on the nightstand, curtains half drawn."
  Bad: "A beautiful serene bedroom perfect for winding down."

# subject — what is literally in the frame
Lowercase, comma separated, 4 to 8 terms. Concrete nouns and materials. Use these words
wherever they genuinely apply: bed, bedding, sheet, duvet, quilt, pillow, throw, linen,
percale, sateen, silk, cotton, texture, weave, folded, rumpled, lived in, styled, layered,
bedroom, window, lamp, nightstand, book, phone, mug, plant, hands, person, face.

# setting — where
Lowercase, 2 to 5 terms: bedroom, hotel room, tent, meadow, studio, macro, laundry, window seat...

# action — what is happening, if anything
Lowercase, 1 to 4 terms, or `none`: making the bed, turning down the bed, reading, folding
sheets, drinking from a mug, hand smoothing fabric, sleeping, phone face down...

# people — who is visible
One of: `none`, `hands only`, `person, no face`, `person, face visible`.

# light — the light
Lowercase, 2 to 4 terms including the time of day if readable (dawn, morning, midday,
dusk, night), the source (window light, lamp, overcast), and warm/cool.

# mood — how the frame feels and reads
Lowercase, comma separated, 3 to 6 terms, and the OVERALL LUMINANCE as exactly one of
`dark frame`, `mid frame`, `pale frame`. Judge it by how much of the picture is light: a
photograph that is mostly white or very light overall is `pale frame`. If in doubt between
mid and pale, say pale.

# coverEligible — can this carry a cover?
`Yes` only if the image would hold a big headline: it has a calm, uncluttered region for
text and reads well small. `No` if it is busy edge to edge, or the subject sits where a
title would go.

# nonBrand — does this show a product type Selene does not sell?
Selene sells plain natural bedding: linen, percale, Tencel and silk in solid muted colours.
`Yes` if the visible bedding is quilted, a comforter, striped, patterned, plaid, velvet,
knitted, fleece or flannel, or the main subject is furniture other than a bed (sofa,
armchair). `No` otherwise.

# Output
Write a single JSON object to {out_path}:
{{
  "images": [
    {{"id": "IMG-0001", "description": "...", "subject": "...", "setting": "...",
      "action": "...", "people": "none", "light": "...", "mood": "...",
      "coverEligible": "Yes", "nonBrand": "No"}}
  ]
}}
One entry per image, ids exactly as in the filenames, {n_images} entries. Nothing else.
