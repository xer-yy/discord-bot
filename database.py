import sqlite3

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS roles (
    guild_id INTEGER,
    user_id INTEGER,
    role_type TEXT
)
""")

conn.commit()

def set_role(guild_id, user_id, role_type):
    cursor.execute("DELETE FROM roles WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    cursor.execute("INSERT INTO roles VALUES (?, ?, ?)", (guild_id, user_id, role_type))
    conn.commit()

def get_role(guild_id, user_id):
    cursor.execute("SELECT role_type FROM roles WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    result = cursor.fetchone()
    return result[0] if result else "user"
