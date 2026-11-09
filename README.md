# Game On! — Eastern Wake Reserve Tracker

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
