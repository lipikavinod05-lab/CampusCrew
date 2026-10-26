import re
from datetime import date, datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash
from mysql.connector import IntegrityError, Error
from db import db

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret-before-deployment"

CLUBS = [
    "Trendles", "Wildbeats", "GDG", "Coders Club",
    "BetaLabs", "Cybersecurity Club", "Enigma", "Elix"
]
ROLE_NAMES = [
    "Tech Volunteer",
    "Art Volunteer",
    "PR and Management Volunteer"
]



IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".svg"}

def _images(folder):
    path = Path(app.static_folder) / "img" / folder
    if not path.is_dir():
        return []
    return sorted(p.name for p in path.iterdir()
                  if p.suffix.lower() in IMG_EXT and not p.name.startswith("."))

@app.template_global()
def event_image(event_id):
    files = _images("events")
    if not files:
        return None
    for f in files:
        if Path(f).stem == f"event-{event_id}":
            return url_for("static", filename=f"img/events/{f}")
    pool = [f for f in files if not re.fullmatch(r"event-\d+", Path(f).stem)] or files
    return url_for("static", filename=f"img/events/{pool[event_id % len(pool)]}")

@app.template_global()
def hero_photos(limit=3):
    files = _images("events")
    return [url_for("static", filename=f"img/events/{f}") for f in files[:limit]]

@app.template_global()
def club_logo(club_name):
    slug = re.sub(r"[^a-z0-9]+", "-", club_name.lower()).strip("-")
    for f in _images("clubs"):
        if Path(f).stem == slug:
            return url_for("static", filename=f"img/clubs/{f}")
    return None

COLLEGE = "IIIT Kottayam"
COLLEGE_FULL = "Indian Institute of Information Technology Kottayam"

@app.context_processor
def inject_college():
    return {"college": COLLEGE, "college_full": COLLEGE_FULL}

@app.template_global()
def college_logo():
    """Official logo: save it as static/img/college-logo.png (or .svg/.jpg/.webp)."""
    for ext in IMG_EXT:
        if (Path(app.static_folder) / "img" / f"college-logo{ext}").is_file():
            return url_for("static", filename=f"img/college-logo{ext}")
    return None

@app.template_global()
def gallery_photos():
    """Event photos plus anything in static/img/gallery/ for the dashboard photo strip."""
    urls = [url_for("static", filename=f"img/events/{f}") for f in _images("events")]
    urls += [url_for("static", filename=f"img/gallery/{f}") for f in _images("gallery")]
    return urls

@app.template_global()
def club_names():
    return CLUBS

EVENT_SQL = """
    SELECT e.*, c.club_name,
      (SELECT COUNT(*) FROM roles r JOIN assignments a ON a.role_id=r.role_id
        WHERE r.event_id=e.event_id) AS assigned_count,
      (SELECT CAST(COALESCE(SUM(r.required_count),0) AS UNSIGNED) FROM roles r
        WHERE r.event_id=e.event_id) AS required_count
    FROM events e JOIN clubs c ON c.club_id=e.club_id
"""

class CampusCrew:
    """Database operations for clubs, events, volunteers and assignments."""

    @staticmethod
    def rows(query, params=()):
        con = db.connect()
        cur = con.cursor(dictionary=True)
        try:
            cur.execute(query, params)
            return cur.fetchall()
        finally:
            cur.close()
            con.close()

    @staticmethod
    def one(query, params=()):
        con = db.connect()
        cur = con.cursor(dictionary=True)
        try:
            cur.execute(query, params)
            return cur.fetchone()
        finally:
            cur.close()
            con.close()

    @staticmethod
    def execute(query, params=()):
        con = db.connect()
        cur = con.cursor()
        try:
            cur.execute(query, params)
            con.commit()
            return cur.lastrowid
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()

    @staticmethod
    def ensure_seed_clubs():
        con = db.connect()
        cur = con.cursor()
        try:
            cur.executemany(
                "INSERT IGNORE INTO clubs(club_name) VALUES (%s)",
                [(name,) for name in CLUBS]
            )
            con.commit()
        finally:
            cur.close()
            con.close()

    @staticmethod
    def create_event(data):
        """Create an event and its three volunteer sections in one transaction."""
        con = db.connect()
        cur = con.cursor()
        try:
            start = datetime.strptime(data["start_time"], "%H:%M").time()
            end = datetime.strptime(data["end_time"], "%H:%M").time()
            if end <= start:
                raise ValueError("End time must be later than start time.")

            cur.execute("""
                INSERT INTO events
                (club_id, event_name, event_date, start_time, end_time, venue, description)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (
                data["club_id"], data["event_name"].strip(), data["event_date"],
                data["start_time"], data["end_time"], data["venue"].strip(),
                data["description"].strip()
            ))
            event_id = cur.lastrowid

            counts = [
                int(data.get("tech_count", 1)),
                int(data.get("art_count", 1)),
                int(data.get("pr_count", 1))
            ]
            if any(n < 1 or n > 500 for n in counts):
                raise ValueError("Each volunteer requirement must be between 1 and 500.")

            for role_name, count in zip(ROLE_NAMES, counts):
                cur.execute(
                    "INSERT INTO roles(event_id, role_name, required_count) VALUES (%s,%s,%s)",
                    (event_id, role_name, count)
                )
            con.commit()
            return event_id
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()

    @staticmethod
    def assign_volunteer(role_id, volunteer_id):
        """Assign only if capacity and event-time conflict checks pass."""
        con = db.connect()
        cur = con.cursor(dictionary=True)
        try:
            con.start_transaction()

            cur.execute("""
                SELECT r.role_id, r.event_id, r.required_count, r.role_name,
                       e.event_date, e.start_time, e.end_time, e.club_id
                FROM roles r JOIN events e ON e.event_id = r.event_id
                WHERE r.role_id = %s
                FOR UPDATE
            """, (role_id,))
            role = cur.fetchone()
            if not role:
                raise ValueError("That event section was not found.")

            cur.execute("SELECT volunteer_id FROM volunteers WHERE volunteer_id=%s",
                        (volunteer_id,))
            if not cur.fetchone():
                raise ValueError("Please select a valid volunteer.")

            cur.execute("SELECT COUNT(*) AS total FROM assignments WHERE role_id=%s",
                        (role_id,))
            if cur.fetchone()["total"] >= role["required_count"]:
                raise ValueError("This section is already full.")

            cur.execute("""
                SELECT COUNT(*) AS conflicts
                FROM assignments a
                JOIN roles r2 ON r2.role_id = a.role_id
                JOIN events e2 ON e2.event_id = r2.event_id
                WHERE a.volunteer_id = %s
                  AND e2.event_date = %s
                  AND e2.start_time < %s
                  AND e2.end_time > %s
            """, (volunteer_id, role["event_date"], role["end_time"], role["start_time"]))
            if cur.fetchone()["conflicts"] > 0:
                raise ValueError("This volunteer is already assigned to an overlapping event.")

            cur.execute("""
                INSERT INTO assignments(role_id, volunteer_id)
                VALUES (%s,%s)
            """, (role_id, volunteer_id))
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            cur.close()
            con.close()

    @staticmethod
    def update_attendance(assignment_id, attendance, hours):
        if attendance not in ("Not Marked", "Present", "Absent"):
            raise ValueError("Invalid attendance status.")
        hours = float(hours)
        if hours < 0 or hours > 24:
            raise ValueError("Hours must be between 0 and 24.")
        if attendance != "Present" and hours != 0:
            raise ValueError("Hours worked can only be recorded when the volunteer is present.")
        CampusCrew.execute("""
            UPDATE assignments
            SET attendance=%s, hours_worked=%s
            WHERE assignment_id=%s
        """, (attendance, hours, assignment_id))

@app.template_filter("datefmt")
def datefmt(value):
    if hasattr(value, "strftime"):
        return value.strftime("%d %b %Y")
    return value

@app.template_filter("timefmt")
def timefmt(value):
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return value

@app.route("/")
def dashboard():
    stats = {
        "volunteers": CampusCrew.one("SELECT COUNT(*) AS n FROM volunteers")["n"],
        "clubs": CampusCrew.one("SELECT COUNT(*) AS n FROM clubs")["n"],
        "events": CampusCrew.one("SELECT COUNT(*) AS n FROM events")["n"],
        "assignments": CampusCrew.one("SELECT COUNT(*) AS n FROM assignments")["n"],
    }
    # Show what is coming up first; fall back to the latest events if nothing is scheduled.
    upcoming = CampusCrew.rows(
        EVENT_SQL + " WHERE e.event_date >= CURDATE() ORDER BY e.event_date, e.start_time LIMIT 7")
    is_upcoming = bool(upcoming)
    if not upcoming:
        upcoming = CampusCrew.rows(
            EVENT_SQL + " ORDER BY e.event_date DESC, e.start_time DESC LIMIT 7")
    return render_template("dashboard.html", stats=stats, upcoming=upcoming,
                           is_upcoming=is_upcoming)

@app.route("/events")
def events():
    selected_club = request.args.get("club", "").strip()
    query = EVENT_SQL
    params = ()
    if selected_club.isdigit():
        query += " WHERE c.club_id=%s"
        params = (int(selected_club),)
    query += " ORDER BY e.event_date DESC, e.start_time DESC"
    return render_template("events.html", events=CampusCrew.rows(query, params),
                           clubs=CampusCrew.rows("SELECT * FROM clubs ORDER BY club_name"),
                           selected_club=selected_club)

@app.route("/events/new", methods=["GET", "POST"])
def add_event():
    clubs = CampusCrew.rows("SELECT * FROM clubs ORDER BY club_name")
    if request.method == "POST":
        try:
            required = ["club_id", "event_name", "event_date", "start_time",
                        "end_time", "venue"]
            if any(not request.form.get(field, "").strip() for field in required):
                raise ValueError("Please fill in all required fields.")
            datetime.strptime(request.form["event_date"], "%Y-%m-%d")
            event_id = CampusCrew.create_event(request.form)
            flash("Event created with all three volunteer sections!", "success")
            return redirect(url_for("event_detail", event_id=event_id))
        except (ValueError, Error) as exc:
            flash(str(exc) if isinstance(exc, ValueError) else "Could not save the event. Check the form and database.", "error")
    return render_template("event_form.html", clubs=clubs, today=date.today().isoformat())

@app.route("/events/<int:event_id>")
def event_detail(event_id):
    event = CampusCrew.one("""
        SELECT e.*, c.club_name FROM events e
        JOIN clubs c ON c.club_id=e.club_id WHERE e.event_id=%s
    """, (event_id,))
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events"))

    roles = CampusCrew.rows("""
        SELECT r.*,
          (SELECT COUNT(*) FROM assignments a WHERE a.role_id=r.role_id) AS assigned_count
        FROM roles r WHERE r.event_id=%s ORDER BY r.role_id
    """, (event_id,))
    assignments = CampusCrew.rows("""
        SELECT a.assignment_id, a.attendance, a.hours_worked,
               v.name, v.roll_no, r.role_name
        FROM assignments a
        JOIN volunteers v ON v.volunteer_id=a.volunteer_id
        JOIN roles r ON r.role_id=a.role_id
        WHERE r.event_id=%s ORDER BY r.role_id, v.name
    """, (event_id,))
    volunteers = CampusCrew.rows("SELECT volunteer_id, roll_no, name FROM volunteers ORDER BY name")
    return render_template("event_detail.html", event=event, roles=roles,
                           assignments=assignments, volunteers=volunteers)

@app.route("/events/<int:event_id>/assign", methods=["POST"])
def assign_volunteer(event_id):
    try:
        role_id = int(request.form["role_id"])
        volunteer_id = int(request.form["volunteer_id"])
        # Ensure role belongs to the event URL.
        role = CampusCrew.one("SELECT role_id FROM roles WHERE role_id=%s AND event_id=%s",
                              (role_id, event_id))
        if not role:
            raise ValueError("Invalid section for this event.")
        CampusCrew.assign_volunteer(role_id, volunteer_id)
        flash("Volunteer assigned successfully.", "success")
    except (ValueError, Error) as exc:
        if isinstance(exc, Error) and exc.errno == 1062:
            message = "This volunteer is already assigned to that section."
        elif isinstance(exc, ValueError):
            message = str(exc)
        else:
            message = "Could not assign volunteer. Check the database and try again."
        flash(message, "error")
    return redirect(url_for("event_detail", event_id=event_id))

@app.route("/assignments/<int:assignment_id>/attendance", methods=["POST"])
def attendance(assignment_id):
    event_id = request.form.get("event_id", type=int)
    try:
        CampusCrew.update_attendance(
            assignment_id, request.form.get("attendance", ""),
            request.form.get("hours_worked", "0")
        )
        flash("Attendance updated.", "success")
    except (ValueError, Error) as exc:
        flash(str(exc) if isinstance(exc, ValueError) else "Could not update attendance.", "error")
    if event_id:
        return redirect(url_for("event_detail", event_id=event_id))
    return redirect(url_for("reports"))

@app.route("/volunteers")
def volunteers():
    search = request.args.get("q", "").strip()
    if search:
        like = "%" + search + "%"
        rows = CampusCrew.rows("""
            SELECT v.*,
              (SELECT COUNT(*) FROM assignments a WHERE a.volunteer_id=v.volunteer_id) AS assignments_count,
              (SELECT COALESCE(SUM(a.hours_worked),0) FROM assignments a WHERE a.volunteer_id=v.volunteer_id) AS total_hours
            FROM volunteers v
            WHERE v.name LIKE %s OR v.roll_no LIKE %s OR v.email LIKE %s
            ORDER BY v.name
        """, (like, like, like))
    else:
        rows = CampusCrew.rows("""
            SELECT v.*,
              (SELECT COUNT(*) FROM assignments a WHERE a.volunteer_id=v.volunteer_id) AS assignments_count,
              (SELECT COALESCE(SUM(a.hours_worked),0) FROM assignments a WHERE a.volunteer_id=v.volunteer_id) AS total_hours
            FROM volunteers v ORDER BY v.name
        """)
    return render_template("volunteers.html", volunteers=rows, q=search)

@app.route("/volunteers/new", methods=["GET", "POST"])
def add_volunteer():
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        if not roll_no or not name:
            flash("Roll number and name are required.", "error")
        else:
            try:
                CampusCrew.execute("""
                    INSERT INTO volunteers(roll_no,name,email,phone)
                    VALUES (%s,%s,%s,%s)
                """, (roll_no, name, request.form.get("email", "").strip() or None,
                      request.form.get("phone", "").strip() or None))
                flash("Volunteer registered successfully.", "success")
                return redirect(url_for("volunteers"))
            except IntegrityError:
                flash("That roll number is already registered.", "error")
            except Error:
                flash("Could not register volunteer. Check your database connection.", "error")
    return render_template("volunteer_form.html")

@app.route("/reports")
def reports():
    summary = CampusCrew.rows("""
        SELECT e.event_id, e.event_name, e.event_date, c.club_name,
               COUNT(a.assignment_id) AS assigned_count,
               SUM(CASE WHEN a.attendance='Present' THEN 1 ELSE 0 END) AS present_count,
               COALESCE(SUM(a.hours_worked),0) AS total_hours
        FROM events e JOIN clubs c ON c.club_id=e.club_id
        LEFT JOIN roles r ON r.event_id=e.event_id
        LEFT JOIN assignments a ON a.role_id=r.role_id
        GROUP BY e.event_id,e.event_name,e.event_date,c.club_name
        ORDER BY e.event_date DESC
    """)
    top_volunteers = CampusCrew.rows("""
        SELECT v.name,v.roll_no,COUNT(a.assignment_id) AS assignment_count,
               COALESCE(SUM(a.hours_worked),0) AS total_hours
        FROM volunteers v LEFT JOIN assignments a ON a.volunteer_id=v.volunteer_id
        GROUP BY v.volunteer_id,v.name,v.roll_no
        ORDER BY total_hours DESC, assignment_count DESC LIMIT 10
    """)
    return render_template("reports.html", summary=summary, top_volunteers=top_volunteers)

@app.route("/clubs")
def clubs():
    rows = CampusCrew.rows("""
        SELECT c.club_id,c.club_name,COUNT(DISTINCT e.event_id) AS event_count
        FROM clubs c LEFT JOIN events e ON e.club_id=c.club_id
        GROUP BY c.club_id,c.club_name ORDER BY c.club_name
    """)
    return render_template("clubs.html", clubs=rows)

@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html"), 500

if __name__ == "__main__":
    # Seed the eight known college clubs if schema.sql has not already inserted them.
    try:
        CampusCrew.ensure_seed_clubs()
    except Error as exc:
        print("Database setup error:", exc)
        print("Check schema.sql, MySQL status, and DB credentials.")
        raise
    app.run(debug=True)
