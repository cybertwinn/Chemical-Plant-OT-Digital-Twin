#!/usr/bin/env python

"""
init.py
Creates (and/or re-initializes) the system3_db.sqlite database.
"""

from minicps.states import SQLiteState
from utils import PATH, SCHEMA, SCHEMA_INIT
from sqlite3 import OperationalError
import os

if __name__ == "__main__":
    try:
        os.remove(PATH)
        print(f"Removed old database {PATH}")
    except OSError:
        print(f"{PATH} does not exist (no removal).")

    try:
        SQLiteState._create(PATH, SCHEMA)
        SQLiteState._init(PATH, SCHEMA_INIT)
        print(f"{PATH} successfully created.")
    except OperationalError:
        print(f"{PATH} already exists or encountered an error.")
