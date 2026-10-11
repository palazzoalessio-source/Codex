from pathlib import Path
import sqlite3

SCHEMA = Path(__file__).with_name('schema.sql')

def connect(path=':memory:'):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con

def initialize(con):
    con.executescript(SCHEMA.read_text(encoding='utf-8'))
    con.commit()
