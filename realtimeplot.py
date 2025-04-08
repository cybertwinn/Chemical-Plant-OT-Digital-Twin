#!/usr/bin/env python

import time
import sqlite3
import math
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.animation as animation
from utils import (
    SV100_HMI_REP, SV200_HMI_REP, SV300_HMI_REP,
    V100_HMI_REP,  V200_HMI_REP,  V300_HMI_REP,
)

DB_PATH = 'system3_db.sqlite'
TABLE   = 'system3_table'

# (name, pid) pairs for field-level
FIELD_TAGS = {
    'LI100':   ('LI100',   100),
    'PI100':   ('PI100',   200),
    'TI100':   ('TI100',   300),
    'V100':    ('V100',    110),
    'V200':    ('V200',    210),
    'V300':    ('V300',    310),
    'SV100':   ('SV100',   101),
    'SV200':   ('SV200',   201),
    'SV300':   ('SV300',   301),
    'PRV400':   ('PRV400',   400),
}

# (name, pid) pairs for HMI
HMI_TAGS = {
    'LI100_HMI': ('LI100_HMI', 120),
    'PI100_HMI': ('PI100_HMI', 220),
    'TI100_HMI': ('TI100_HMI', 320),
    'V100_HMI_REP':  ('V100_HMI_REP', 11099),
    'V200_HMI_REP':  ('V200_HMI_REP', 21099),
    'V300_HMI_REP':  ('V300_HMI_REP', 31099),
    'SV100_HMI_REP': ('SV100_HMI_REP', 10199),
    'SV200_HMI_REP': ('SV200_HMI_REP', 20199),
    'SV300_HMI_REP': ('SV300_HMI_REP', 30199),
}

# Store last HMI command in (name='HMI_CMD', pid=9999)
CMD_TAG = ('HMI_CMD', 9999)

##############################################################################
# Helpers to read from DB (float or string)
##############################################################################
def read_db_float(name, pid):
    """Reads a float from the DB row (name,pid)."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM {} WHERE name=? AND pid=?".format(TABLE),
                  (name, pid))
        row = c.fetchone()
        conn.close()
        if row is not None:
            return float(row[0])
    except:
        pass
    return 0.0

def read_db_string(name, pid):
    """Reads a string from the DB row (name,pid)."""
    val = ""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM {} WHERE name=? AND pid=?".format(TABLE),
                  (name, pid))
        row = c.fetchone()
        conn.close()
        if row is not None:
            val = str(row[0])
    except:
        pass
    return val

###############################################################################
# Create the figure and subplots
###############################################################################
fig = plt.figure(figsize=(10,8))
fig.suptitle("Field-Level vs HMI", fontsize=12)

# A) Top region for the valve dials in a single subplot (ax_dials)
ax_dials = plt.subplot2grid((4,1), (0,0), rowspan=1)
ax_dials.set_xlim(0,10)
ax_dials.set_ylim(0,2)
ax_dials.set_xticks([])
ax_dials.set_yticks([])

# B) Three subplots for bar charts: level, pressure, temperature
ax_level   = plt.subplot2grid((3,3), (1,0), colspan=1, rowspan=3)
ax_pressure= plt.subplot2grid((3,3), (1,1), colspan=1, rowspan=3)
ax_temp    = plt.subplot2grid((3,3), (1,2), colspan=1, rowspan=3)

# Place text labels for Field-Level row vs. HMI row
ax_dials.text(0.1, 1.3, "Field-Level", ha='left', va='center', fontsize=11, color='black')
ax_dials.text(0.1, 0.3, "HMI",         ha='left', va='center', fontsize=11, color='black')

def create_dial(ax, x, y, label):
    # circle
    circle = mpatches.Circle((x,y), radius=0.20, facecolor='red', edgecolor='black')
    ax.add_patch(circle)
    # label above
    ax.text(x, y+0.35, label, ha='center', va='bottom', fontsize=8, color='black')
    return circle

# x positions for the 7 valves
x_positions = [2.0, 3.1, 4.2, 5.3, 6.4, 7.5, 8.6]
field_labels = ['V100','V200','V300','SV100','SV200','SV300','PRV400']
hmi_labels   = ['V100:HMI','V200:HMI','V300:HMI','SV100:HMI','SV200:HMI','SV300:HMI','(no PRV400)']

field_dials = {}
for x,label in zip(x_positions, field_labels):
    field_dials[label] = create_dial(ax_dials, x, 1.3, label)

hmi_dials = {}
for x,label in zip(x_positions, hmi_labels):
    if label == '(no PRV400)':
        hmi_dials[label] = None
        continue
    hmi_dials[label] = create_dial(ax_dials, x, 0.3, label)

# small legend for open/closed
open_patch   = mpatches.Patch(color='green', label='Open')
closed_patch = mpatches.Patch(color='red',   label='Closed')
ax_dials.legend(handles=[open_patch, closed_patch], loc='upper right', fontsize=8)

last_cmd_text = ax_dials.text(9.9, 0.3, "",
    ha='right', va='top', fontsize=9, color='blue',
    bbox=dict(facecolor='white', edgecolor='blue', boxstyle='round,pad=0.3')
)

def animate(_frame):
    # 1) read sensor values
    li_field = read_db_float(*FIELD_TAGS['LI100'])
    pi_field = read_db_float(*FIELD_TAGS['PI100'])
    ti_field = read_db_float(*FIELD_TAGS['TI100'])
    li_hmi   = read_db_float(*HMI_TAGS['LI100_HMI'])
    pi_hmi   = read_db_float(*HMI_TAGS['PI100_HMI'])
    ti_hmi   = read_db_float(*HMI_TAGS['TI100_HMI'])

    # 2) read valve states (field-level)
    v100  = read_db_float(*FIELD_TAGS['V100'])
    v200  = read_db_float(*FIELD_TAGS['V200'])
    v300  = read_db_float(*FIELD_TAGS['V300'])
    sv100 = read_db_float(*FIELD_TAGS['SV100'])
    sv200 = read_db_float(*FIELD_TAGS['SV200'])
    sv300 = read_db_float(*FIELD_TAGS['SV300'])
    prv400 = read_db_float(*FIELD_TAGS['PRV400'])

    # 3) read valve states (HMI)
    v100_hmi  = read_db_float(*HMI_TAGS['V100_HMI_REP'])
    v200_hmi  = read_db_float(*HMI_TAGS['V200_HMI_REP'])
    v300_hmi  = read_db_float(*HMI_TAGS['V300_HMI_REP'])
    sv100_hmi = read_db_float(*HMI_TAGS['SV100_HMI_REP'])
    sv200_hmi = read_db_float(*HMI_TAGS['SV200_HMI_REP'])
    sv300_hmi = read_db_float(*HMI_TAGS['SV300_HMI_REP'])

    # 4) update circle colors
    def set_color(circle, is_open):
        if circle is not None:
            circle.set_facecolor('green' if is_open else 'red')

    set_color(field_dials['V100'],  (v100==1))
    set_color(field_dials['V200'],  (v200==1))
    set_color(field_dials['V300'],  (v300==1))
    set_color(field_dials['SV100'], (sv100==1))
    set_color(field_dials['SV200'], (sv200==1))
    set_color(field_dials['SV300'], (sv300==1))
    set_color(field_dials['PRV400'], (prv400==1))

    set_color(hmi_dials['V100:HMI'],  (v100_hmi==1))
    set_color(hmi_dials['V200:HMI'],  (v200_hmi==1))
    set_color(hmi_dials['V300:HMI'],  (v300_hmi==1))
    set_color(hmi_dials['SV100:HMI'], (sv100_hmi==1))
    set_color(hmi_dials['SV200:HMI'], (sv200_hmi==1))
    set_color(hmi_dials['SV300:HMI'], (sv300_hmi==1))

    # 5) read the last HMI command string
    last_cmd = read_db_string(*CMD_TAG)
    if last_cmd is None or last_cmd.strip()=='':
        last_cmd = "(no cmd yet)"
    last_cmd_text.set_text(last_cmd)

    # 6) update bar plots
    ax_level.cla()
    ax_pressure.cla()
    ax_temp.cla()

    # A) LEVEL
    ax_level.set_title("Level (m)")
    ax_level.set_ylim([0,2.0])
    ax_level.bar("Field-Level", li_field,  color='#0B84A5', label="Field-Level")
    ax_level.bar("HMI", li_hmi, color='#0B84A5', hatch='//', edgecolor='black', label="HMI")
    ax_level.legend(loc='upper right')

    # B) PRESSURE
    ax_pressure.set_title("Pressure (bar)")
    ax_pressure.set_ylim([0,16])
    ax_pressure.bar("Field-Level", pi_field, color='#FFA056', label="Field-Level")
    ax_pressure.bar("HMI",         pi_hmi,   color='#FFA056', hatch='//', edgecolor='black', label="HMI")
    ax_pressure.legend(loc='upper right')

    # C) TEMPERATURE
    ax_temp.set_title("Temp (°C)")
    ax_temp.set_ylim([0,240])
    ax_temp.set_yticks(range(0, 241, 20))
    ax_temp.bar("Field-Level", ti_field, color='#9DD866', label="Field-Level")
    ax_temp.bar("HMI",         ti_hmi,   color='#9DD866', hatch='//', edgecolor='black', label="HMI")
    ax_temp.legend(loc='upper right')

ani = animation.FuncAnimation(fig, animate, interval=1000)
plt.show()

