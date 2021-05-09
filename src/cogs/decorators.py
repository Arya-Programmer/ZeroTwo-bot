import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "../info.db")


def connectToDB(func):
    db = sqlite3.connect(DB_DIR)
    cursor = db.cursor()

    def wrapper(*args, **kwargs):
        return func(*args, cursor, **kwargs)

    cursor.close()
    db.close()

    return wrapper
