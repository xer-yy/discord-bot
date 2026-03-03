import sqlite3

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins (
    guild_id INTEGER,
    user_id INTEGER
)
""")

conn.commit()

def add_admin(guild_id, user_id):
    cursor.execute("INSERT INTO admins VALUES (?, ?)", (guild_id, user_id))
    conn.commit()

def remove_admin(guild_id, user_id):
    cursor.execute("DELETE FROM admins WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    conn.commit()

def is_admin(guild_id, user_id):
    cursor.execute("SELECT * FROM admins WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    return cursor.fetchone() is not None

def get_admins(guild_id):
    cursor.execute("SELECT user_id FROM admins WHERE guild_id=?", (guild_id,))
    return cursor.fetchall()
