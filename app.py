import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", os.environ.get("DB_HOST", "db")),
    "port": os.environ.get("POSTGRES_PORT", os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("POSTGRES_DB", os.environ.get("DB_NAME", "diary")),
    "user": os.environ.get("POSTGRES_USER", os.environ.get("DB_USER", "diary_user")),
    "password": os.environ.get("POSTGRES_PASSWORD", os.environ.get("DB_PASSWORD", "diary_pass")),
}


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS entries (
                    id SERIAL PRIMARY KEY,
                    entry_date DATE NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()


@app.route("/")
def index():
    today = date.today()
    selected = request.args.get("date", today.isoformat())

    try:
        selected_date_obj = datetime.strptime(selected, "%Y-%m-%d").date()
    except ValueError:
        selected_date_obj = today

    if selected_date_obj > today:
        selected_date_obj = today

    selected = selected_date_obj.isoformat()

    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT entry_date FROM entries ORDER BY entry_date DESC;")
            dates_with_entries = [row["entry_date"].isoformat() for row in cur.fetchall()]

            cur.execute("SELECT * FROM entries WHERE entry_date = %s;", (selected,))
            entry = cur.fetchone()

    return render_template(
        "index.html",
        selected_date=selected,
        entry=entry,
        dates_with_entries=dates_with_entries,
        today=today.isoformat(),
    )


@app.route("/save", methods=["POST"])
def save():
    entry_date = request.form.get("entry_date")
    content = request.form.get("content", "").strip()

    if not entry_date:
        flash("Не выбрана дата", "error")
        return redirect(url_for("index"))

    try:
        selected = datetime.strptime(entry_date, "%Y-%m-%d").date()
    except ValueError:
        flash("Некорректная дата", "error")
        return redirect(url_for("index"))

    if selected > date.today():
        flash("Нельзя сделать запись на будущий день", "error")
        return redirect(url_for("index"))

    if not content:
        flash("Запись не может быть пустой", "error")
        return redirect(url_for("index", date=entry_date))

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO entries (entry_date, content)
                VALUES (%s, %s)
                ON CONFLICT (entry_date)
                DO UPDATE SET content = EXCLUDED.content,
                              updated_at = CURRENT_TIMESTAMP;
            """, (entry_date, content))
        conn.commit()

    flash("Запись сохранена!", "success")
    return redirect(url_for("index", date=entry_date))


@app.route("/delete/<entry_date>", methods=["POST"])
def delete(entry_date):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM entries WHERE entry_date = %s;", (entry_date,))
        conn.commit()
    flash("Запись удалена", "success")
    return redirect(url_for("index", date=entry_date))

try:
    init_db()
except Exception as e:
    print(f"[init_db] warning: {e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("WEB_CONTAINER_PORT", "5000")))
    app.run(host="0.0.0.0", port=port, debug=False)