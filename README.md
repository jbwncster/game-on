# Game On! — Eastern Wake Reserve Tracker

## Definitive inventory and artwork

**Source of truth:** the seven-page PDF `Eastern_Wake_Games_On_Reserve_Adobe_Express_Editable(1).pdf` supplied by Eastern Wake staff. Its 28 cards and the names, descriptions, piece counts, player counts, loan labels, warnings, and SirsiDynix barcode values printed on them supersede any conflicting website or marketplace listing. The aligned `items.json` includes `source_page` (four cards per page) for easy auditing. Amazon, eBay, BoardGameGeek, and the public LibGuide are secondary sources for artwork only, and should not change the catalog data. The supplied PDF itself is not committed to this repository.



A staff-managed availability board for the Eastern Wake Campus Library's **28 games, puzzles, and LEGO items**. This repository contains the Flask application. It is not yet a live website.

## Features
- Public **Ready to Borrow** and **Checked Out** views
- Staff-only checkout and check-in controls
- Automatic timestamps and three-hour due windows, displayed in Eastern Time
- Overdue countdown and recent activity log
- Manual updates; **not connected to SirsiDynix**
- One card per unique item; no patron information collected

## Run locally
1. Install Python 3.10+ and `pip install -r requirements.txt`.
2. Copy `.env.example` to `.env`.
3. Generate a random 32+ character `APP_SECRET` and a password hash. Do not commit either value.
4. Run `python app.py` and open http://localhost:5000.

Generate a staff password hash with:
```bash
python -c "import hashlib,secrets,getpass; p=getpass.getpass('Staff password: '); s=secrets.token_bytes(16); n=390000; print('pbkdf2_sha256$'+str(n)+'$'+s.hex()+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),s,n).hex())"
```

## Hosting / LibGuides
Host on a secure HTTPS server with a **persistent** disk. Set `DATABASE_PATH` to the persistent disk path; otherwise all statuses may disappear during redeployments. Configure `APP_SECRET` and `STAFF_PASSWORD_HASH` as private host environment variables. Do **not** use static GitHub Pages for this Flask app.

When deployed, embed the secure URL in a LibGuides HTML box:
```html
<iframe src="https://YOUR-DEPLOYED-SITE" title="Game On! Eastern Wake Reserve Tracker" width="100%" height="950" style="border:0" loading="lazy"></iframe>
```

**Security:** Use a stronger, unique staff password before production deployment, and ask Wake Tech IT to review hosting, authentication, access controls, backups, and permission to use game cover artwork. Avoid patron names or borrowing histories in this tracker.

## Cover image assets (still to upload)

The PDF includes card art for 27 items and one placeholder for Amazing Coral Reef. The earlier source package includes 28 optimized cover-image assets (which may not all match the PDF). The source package includes optimized cover images under `static/covers/cover_01.webp` through `cover_28.webp`. Those **binary images have not yet been uploaded to this repository**. Until then, the web page displays a dice placeholder instead of the cover. Extract the [GitHub-ready ZIP](https://chatgpt.com/) supplied in the project conversation, then use GitHub's **Add file → Upload files** to upload `static/covers/` (preserving the paths). Do not upload `.env`.

## Testing status

Python and JavaScript source syntax has been checked locally. End-to-end Flask tests and physical barcode scanner tests have **not** been completed. The repo is not yet deployed and is not ready to embed in LibGuides until hosting, persistent storage, and staff sign-in are verified.
