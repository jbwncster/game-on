# Game On! — Eastern Wake Campus Library

Manual availability tracker for 28 games, puzzles and LEGO items. **All checkouts are 3-hour loans.** This does **not** integrate with SirsiDynix; the official checkout and return must happen in SirsiDynix first.

## Student features
- Search titles, barcodes, categories, and call numbers
- Availability sections: ready to borrow, checked out, out of service
- Cover art and known missing-piece warnings
- Clear last staff change and connection status, refresh button and mobile responsive layout
- Keyboard navigation, skip link and status announcements
- SVG QR code at `/qr` pointing at the public catalog

## Staff features
- Password-protected login and 12-hour staff sessions
- USB/keyboard barcode scanner lookup (barcode + Enter); scanning **does not check out an item**
- Staff-confirmed SirsiDynix transaction before each 3-hour checkout/return
- Out-of-service status and private 250-character condition notes, persisted as maintenance events
- Staff usage totals, overdue lists, CSV export, and password-protected reset of reporting totals
- Maintenance changes do not clear historical circulation, and item notes never appear in public feeds

## Deployment requirements
Python 3.10+ / Flask. Install `pip install -r requirements.txt`.
Set `APP_SECRET` to a cryptographically random value at least 32 characters long and `STAFF_PASSWORD_HASH` to a PBKDF2 hash. See `.env.example` for settings. **Never commit credentials or patron information.**

For Vercel hosting, configure a **private** Vercel Blob store with `BLOB_READ_WRITE_TOKEN`. On local hosting, `DATABASE_PATH` is a SQLite database that must live on persistent storage. If a Vercel deployment lacks Blob credentials, startup intentionally fails rather than reporting inaccurate availability.

Set `PUBLIC_SITE_URL` to the confirmed canonical public HTTPS URL (e.g. `https://YOUR-SITE.example`), used for the QR code and LibGuides snippet. The fallback is the request URL, so explicitly configuring the URL is recommended.

## LibGuides
Open `/libguides-snippet` for HTML that links to the student catalog in a new tab. Paste this into a LibGuides HTML editor. The link approach is robust when third-party iframe embedding is blocked.

Download the SVG at `/qr` for a shelf flyer or LibGuides image. **Verify the QR code opens the deployed public catalog before printing it.**

## Cover images
The 28 `items.json` entries refer to `static/covers/cover_01.webp` through `cover_28.webp`. Align covers with the seven-page Adobe Express PDF. *Amazing Coral Reef* has no verified exact box cover in that document; keep its placeholder until identified. The earlier extracted ZIP is not automatically synced to GitHub.

## Testing
Run `python -m unittest discover -s tests -v`. Also manually test: staff login, real barcode scanner input, each maintenance state, 3-hour due times, CSV download/reset, connection interruption, mobile layouts, screen readers, and persistence across a fresh deployment. Confirm with Wake Tech IT before publishing or hosting product imagery.

## Privacy
Do not enter names, ID numbers, patron details, or borrowing histories in condition notes. Only staff should receive notes. The student board shows item status, not patron data.
