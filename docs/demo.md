# Cursor demo recording

Status: the dedicated account is `evvbmstu.kaiten.ru`; use `MCP Demo` in `Main`. The `kaiten-demo` server is configured locally in Cursor. No recording has been made yet.

## Prepare

Prepare the fixture with `scripts/prepare_demo.py --apply` as documented in [CHECKING.md](../CHECKING.md#воспроизводимый-демо-стенд). Use `MCP Demo`, starting column `To Do`, destination `In Progress`, and its standard lane. Board and seed-card links are recorded in `reports/demo-fixture.json`. The dedicated board is intended to retain demonstration cards. Only create or change cards belonging to this demonstration. Keep a record of their returned IDs for any later requested cleanup.

Connect kaiten-mcp and install the companion skill using README.en.md. Start a fresh Cursor Agent chat and verify that the skill is available. Use a disposable project and frame only the relevant chat; keep credentials, unrelated conversations and private board data out of view. Choose a board whose name and card URLs may appear publicly.

## Record in English

Select the `kaiten-demo` server for every request; the working-account server is outside this demonstration. Use actual tool responses and preserve any meaningful errors or clarifications.

1. “Use the Kaiten skill. On MCP Demo, in To Do, create a card titled ‘Kaiten demo: password visibility toggle’. Describe adding a show/hide control to the login password field. Acceptance criteria: toggling preserves the entered value, and the control works with the keyboard. Return the card link.”
2. “Move that card to In Progress and verify its location.”
3. “Review only cards whose titles start with ‘Kaiten demo:’ on this board. Summarize their current columns and suggest next steps. Leave the cards unchanged.”

Check the created card's description and final column through MCP readback. If more demo cards would improve the overview, create them only with the user's agreed demo scope. One card is sufficient for the baseline recording.

## Export and publish

Export the real capture to `docs/assets/kaiten-demo.gif`, targeting 30–45 seconds and a legible chat crop. Shorten waiting time if needed; do not replace tool results with fabricated responses. Inspect the complete GIF for legibility, looping and exposed private data.

Once the file exists, replace the pending-demo paragraphs in both READMEs with the image and a localized caption describing the create → move → review workflow. Keep this scenario linked for reproducibility. Until then, keep the pending status and omit image links so the documentation has no broken asset.
