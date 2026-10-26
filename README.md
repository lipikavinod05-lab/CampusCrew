# CampusCrew

A Flask + MySQL college club and event volunteer coordinator.

## Included clubs
Trendles, Wildbeats, GDG, Coders Club, BetaLabs, Cybersecurity Club, Enigma, Elix.

## Features
- Dashboard statistics from MySQL
- Club list and club-specific event filtering
- Create an event for a selected club
- Each event automatically gets three sections:
  - Tech Volunteer
  - Art Volunteer
  - PR and Management Volunteer
- Configure volunteer requirements per section
- Volunteer registration and directory search
- Assign volunteers with capacity and overlapping-event checks
- Attendance and hours tracking
- Event and volunteer contribution reports

## Requirements
- Python 3.10+
- MySQL 8+ (or a compatible MySQL server)

## Setup on Ubuntu
1. Extract the project and open a terminal in the `CampusCrew` directory.
2. Create the database and tables:
   ```bash
   mysql -u root -p < schema.sql
   ```
   Or open MySQL and run `SOURCE /absolute/path/to/schema.sql;`.
3. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Set credentials in the same terminal:
   ```bash
   export DB_HOST=localhost
   export DB_PORT=3306
   export DB_USER=root
   export DB_PASSWORD='your_mysql_password'
   export DB_NAME=campuscrew
   ```
5. Run:
   ```bash
   python app.py
   ```
6. Open http://127.0.0.1:5000

## Important
- The Flask development server is for local development only. Do not expose it publicly with debug mode enabled.
- Before deployment, set a random `SECRET_KEY` environment variable and update `app.py` to use it.
- This starter has no login/role-based access control yet. Add authentication before using it with real student data.
- Volunteer allocation checks capacity and overlaps in the app. If multiple administrators will assign people simultaneously, add stronger database-level locking/transaction tests.
- Event overlap checks compare the event's date and time. For events at different dates/times, no conflict is reported.

## Adding your college's photos
The interface is built around photos. Put images in these folders (no code changes needed):

- `static/img/events/` - event photos (jpg, png, webp).
  - Name a file `event-12.jpg` to use it for event #12 only.
  - Any other file name goes into a shared pool and is handed out to events in rotation.
  - The first three photos in the folder also appear as the printed-photo collage on the dashboard.
- `static/img/clubs/` - optional club logos. Name each file after the club in lowercase with dashes, e.g. `gdg.png`, `coders-club.png`, `cybersecurity-club.png`.

Events without a photo show generated poster art instead, so nothing looks empty while you collect images.
Landscape photos around 1600x1200 px work best. Keep each under about 500 KB so pages load fast.

The Theme button in the top bar switches between light and dark and remembers the choice.

