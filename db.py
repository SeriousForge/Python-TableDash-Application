# db.py
import mysql.connector

DATABASE_CONFIG = {
    "host": "localhost",
    "user": "SeriousForge",
    "password": "1411Stud3nt!",
    "database": "TableDash"
}

def database_connect():
    return mysql.connector.connect(**DATABASE_CONFIG)
