<!-- VERSION: 2026-09-16.v1 -->
<!-- CHANGELOG
     2026-09-16.v1 — First version. One call per reference SET (a folder of
       screenshots that is one post, usually a competitor's carousel). Reads
       the slides in order so the note is about the post's structure, not
       one slide. Marcus's own note on the folder, when present, is the
       reason it was saved and is weighted above what the model sees.
-->
Marcus (founder of Selene Dreams, premium natural-fibre bedding) saved this Instagram post in the brand's reference folder as an example of what he wants the brand's {lane} content to learn from. It is saved slide by slide. Most saved posts are from OTHER brands — treat it as a competitor's work unless the slides show it is Selene's own.

Set name (his folder name, often "brand - topic"): {set_name}
Marcus's note on why he saved it: {marcus_note}

View EVERY slide with the Read tool, IN THIS ORDER ({slide_count} slides):
{slide_list}

Then write EXACTLY one JSON object to {out_path} with the Write tool:

{{
  "shows": "one or two sentences: what the post is, as a whole — topic, format (photo carousel / text cards / mixed), tone, who it is talking to",
  "structure": "two or three sentences: how it is built — what slide 1 does to stop the scroll, how the teaching is sequenced across the middle slides, where the payoff or reveal lands, how much text sits on each slide, how it closes",
  "on_brand": "one sentence: which part of this fits a calm, natural, quietly luxurious bedding brand — and, if something does not fit, say that in half a sentence",
  "borrow": "one or two sentences: the transferable moves — the hook mechanism, the pacing, the way it makes one point per slide, the kind of proof it uses. Never the brand, layout, colours, typography or copy."
}}

Plain sentences. No adjectives stacked for effect. If Marcus left a note, let it steer what you call out in "borrow". Name the other brand in "shows" if it is visible; keep it out of "borrow". No commentary, no other files.
