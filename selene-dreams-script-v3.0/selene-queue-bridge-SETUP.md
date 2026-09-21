# Selene Generation Queue — Bridge Setup (one time, ~5 min)

This makes prompt rows land in your sheet **even when your Mac is closed**. A cloud
Cowork session commits a small file to your `selene-ig-memory` GitHub repo; an Apps
Script living inside your spreadsheet checks that repo every 5 minutes and appends the
row on Google's side.

You only do this once. After it's set up, you never touch it again.

---

## What you need
- The `selene-ig-memory` GitHub token (the same one your weekly research and caption
  agents already use — it's stored in this project's memory; I can paste it into the
  chat when you reach Step 4 if you don't have it handy).

## Steps

**1. Open the script editor**
Open the "Selene Dreams — Content Generation Queue" sheet in your browser →
menu **Extensions → Apps Script**. A new tab opens.

**2. Paste the script**
Delete whatever's in the default `Code.gs` file, then paste the entire contents of
`selene-queue-bridge.gs`. Click the **Save** icon (or Cmd+S).

> If you already have other Apps Script code in this project (e.g. a `trigger.gs`
> from the generation flow), don't delete it — instead click the **+** next to
> "Files", add a new script file called `queueBridge`, and paste the code there.
> The function names here are unique and won't collide.

**3. Add the GitHub token**
Click the **gear icon (Project Settings)** in the left sidebar → scroll to
**Script Properties** → **Add script property**:
- Property: `GITHUB_TOKEN`
- Value: *(the selene-ig-memory token)*

Click **Save script properties**.

**4. Test the connection**
Back in the editor, choose `testConnection` from the function dropdown at the top and
click **Run**. The first run asks you to authorize — approve it (it's your own script
on your own account). Then open **Execution log** (bottom): you should see
`Token present.` and `Queue files found: []` (empty is correct — nothing queued yet).

**5. Turn on the 5-minute timer**
Choose `installTrigger` from the function dropdown → **Run**. That's it — the bridge
now checks GitHub every 5 minutes.

---

## How to confirm it works end-to-end
Next time you pick posts from a cloud session with your Mac closed, the session will
commit a file into the repo's `queue/` folder. Within ~5 minutes a new row appears in
the Generation Queue tab, Status blank, ready for you to flip to "Ready".

## To pause or remove it later
In the editor, run `removeTriggers()`. The script stays but stops firing.

## Notes
- The script only **reads** your repo and updates its own internal processed-list; it
  never pushes to GitHub.
- It enforces the 3-prompt cap (ignores anything past Prompt 3).
- It uses the same "don't overwrite a row that has any content" rule as `append_row.py`,
  so it won't clobber draft rows.
- Runs free on your Google account (well within Apps Script quotas at this volume).
