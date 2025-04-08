"""
utils.py

"""

import math
import numpy as np
from minicps.utils import build_debug_logger

###############################################################################
# LOGGING
###############################################################################
system3_logger = build_debug_logger(
    name=__name__,
    bytes_per_file=10000,
    rotating_files=2,
    lformat='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    ldir='logs/',
    suffix=''
)

###############################################################################
# NETWORK CONFIGURATION
###############################################################################
NETMASK = '/24'

# Physical host 
Physicalprocess_ADDR = '10.0.0.50'
Physicalprocess_MAC  = '00:00:00:00:00:50'

# SFPLC100 (Methanol Safety) SV100
SFPLC100_ADDR = '10.0.0.101'
SFPLC100_MAC  = '00:1E:C9:41:57:32'
SFPLC100_TAGS = (
    ('LI100', 100, 'REAL'),
    ('SV100', 101, 'INT'),
    ('SV100_HMI', 102, 'INT'),
)

SFPLC100_SERVER = {
    'address': SFPLC100_ADDR,
    'tags': SFPLC100_TAGS
}

SFPLC100_PROTOCOL = {
    'name': 'enip',
    'mode': 1,  # server
    'server': SFPLC100_SERVER
}

# PLC100 (Methanol Normal) V100
PLC100_ADDR='10.0.0.111'
PLC100_MAC='00:1E:C9:41:57:33'
PLC100_TAGS=(
  ('V100',110,'INT'),
  ('V100_HMI',111,'INT'),
)
PLC100_SERVER={
  'address':PLC100_ADDR,
  'tags':PLC100_TAGS
}
PLC100_PROTOCOL={
  'name':'enip',
  'mode':1,
  'server':PLC100_SERVER
}

# SFPLC200 (Nitrogen Safety) SV200
SFPLC200_ADDR = '10.0.0.102'
SFPLC200_MAC  = '00:1E:C9:41:57:34'
SFPLC200_TAGS = (
    ('PI100', 200, 'REAL'),
    ('SV200', 201, 'INT'),
    ('SV200_HMI', 202, 'INT'),
)

SFPLC200_SERVER = {
    'address': SFPLC200_ADDR,
    'tags': SFPLC200_TAGS
}

SFPLC200_PROTOCOL = {
    'name': 'enip',
    'mode': 1,
    'server': SFPLC200_SERVER
}

# PLC200 (Nitrogen Normal) V200
PLC200_ADDR='10.0.0.112'
PLC200_MAC='00:1E:C9:41:57:35'
PLC200_TAGS=(
  ('V200',210,'INT'),
  ('V200_HMI',211,'INT'),
)
PLC200_SERVER={
 'address':PLC200_ADDR,
 'tags':PLC200_TAGS
}
PLC200_PROTOCOL={
 'name':'enip',
 'mode':1,
 'server':PLC200_SERVER
}

# SFPLC300 (Steam Safety) SV300
SFPLC300_ADDR = '10.0.0.103'
SFPLC300_MAC  = '00:1E:C9:41:57:36'
SFPLC300_TAGS = (
    ('TI100', 300, 'REAL'),
    ('SV300', 301, 'INT'),
    ('SV300_HMI', 302, 'INT'),
)

SFPLC300_SERVER = {
    'address': SFPLC300_ADDR,
    'tags': SFPLC300_TAGS
}

SFPLC300_PROTOCOL = {
    'name': 'enip',
    'mode': 1,
    'server': SFPLC300_SERVER
}

# PLC300 (Steam Normal) V300
PLC300_ADDR='10.0.0.113'
PLC300_MAC='00:1E:C9:41:57:37'
PLC300_TAGS=(
 ('V300',310,'INT'),
 ('V300_HMI',311,'INT'),
)
PLC300_SERVER={
 'address':PLC300_ADDR,
 'tags':PLC300_TAGS
}
PLC300_PROTOCOL={
 'name':'enip',
 'mode':1,
 'server':PLC300_SERVER
}

# HMI
HMI_ADDR = '10.0.0.150'
HMI_MAC  = '00:1E:C9:41:57:38'
HMI_TAGS = ()
HMI_SERVER = {
    'address': HMI_ADDR,
    'tags': HMI_TAGS
}
HMI_PROTOCOL = {
    'name': 'enip',
    'mode': 0,  # client only
    'server': HMI_SERVER
}

# ATTACKER
ATTACKER_ADDR = '10.0.0.200'
ATTACKER_MAC  = '00:1E:C9:41:57:39'

###############################################################################
# PHYSICAL PROCESS TAGS
###############################################################################
LI100 = ('LI100', 100)
SV100 = ('SV100', 101)
SV100_HMI = ('SV100_HMI', 102)

PI100 = ('PI100', 200)
SV200 = ('SV200', 201)
SV200_HMI = ('SV200_HMI', 202)

TI100 = ('TI100', 300)
SV300 = ('SV300', 301)
SV300_HMI = ('SV300_HMI', 302)

PRV400 = ('PRV400', 400)

V100=('V100',110)
V100_HMI=('V100_HMI',111)

V200=('V200',210)
V200_HMI=('V200_HMI',211)

V300=('V300',310)
V300_HMI=('V300_HMI',311)

LI100_HMI = ('LI100_HMI', 120)
PI100_HMI = ('PI100_HMI', 220)
TI100_HMI = ('TI100_HMI', 320)

SV100_HMI_REP = ('SV100_HMI_REP', 10199)
SV200_HMI_REP = ('SV200_HMI_REP', 20199)
SV300_HMI_REP = ('SV300_HMI_REP', 30199)
V100_HMI_REP  = ('V100_HMI_REP',  11099)
V200_HMI_REP  = ('V200_HMI_REP',  21099)
V300_HMI_REP  = ('V300_HMI_REP',  31099)

###############################################################################
# INITIAL VALUES (All valves closed at start)
###############################################################################
SFPLC100_DATA = {
    'LI100': '0.0',  # initial level in [m]
    'SV100': '0',    # 0 => closed
    'SV100_HMI': '0',
}
PLC100_DATA={
  'V100':'0',
  'V100_HMI':'0',
}
SFPLC200_DATA = {
    'PI100': '1.0',  # 1 bar = ~ atmospheric
    'SV200': '0',    # 0 => closed
    'SV200_HMI': '0',
}
PLC200_DATA={
 'V200':'0',
 'V200_HMI':'0',
}
SFPLC300_DATA = {
    'TI100': '20.0', # 20 degC (room temperature)
    'SV300': '0',    # 0 => closed
    'SV300_HMI': '0',
}
PLC300_DATA={
 'V300':'0',
 'V300_HMI':'0',
}
HMI_DATA = {
    # local HMI memory
}

###############################################################################
# SIMULATION PERIODS
###############################################################################
PLC_PERIOD_SEC = 1      # PLC logic scanning period
PP_PERIOD_SEC  = 1      # physical process scanning period
HMI_PERIOD_SEC = 0.1    # HMI scanning period

###############################################################################
# THERMODYNAMIC CONSTANTS
###############################################################################
R_GAS = 8.314         # J/(mol*K)
DENSITY_MEOH = 791  # kg/m^3
CP_MEOH = 2500      # J/(kg*K)
MW_MEOH = 32        # g/mol => 0.032 kg/mol
DELTAH_VAP = 1.2e6    # J/kg (approx. latent heat of methanol)

# Antoine params for methanol (for saturation pressure in bar)
ANT_A = 5.22
ANT_B = 1609
ANT_C = -30.02

def methanol_p_sat(temp_c):
    """ Return saturation pressure of methanol [Pa]. """
    if temp_c < 10:
        temp_c = 10
    p_bar = 10 ** (ANT_A - ANT_B / (temp_c + 273.15 + ANT_C))
    return p_bar

###############################################################################
# HEAT TRANSFER
###############################################################################
U_COIL       = 1000    # W/(m^2*K)
AREA_COIL    = 2.5       # m^2
T_STEAM      = 220     # degC
HEAT_LOSS    = 10000   # W

###############################################################################
# TANK GEOMETRY
###############################################################################
TANK_DIAMETER = 0.86 # m
TANK_HEIGHT   = 1.67 # m
TANK_CROSS_SECTION = math.pi * (TANK_DIAMETER/2.0)**2 # m2
TANK_VOLUME   = 1.0   # m3

###############################################################################
# PRESSURE AND TEMPERATURE RANGES
###############################################################################
PRESSURE_LIMIT = 10 # bar
PRESSURE_SET   = 11 # bar
PRESSURE_OPEN  = 1.09 * PRESSURE_SET   # ~12 bar => PRV400 opens
PRESSURE_CLOSE = 0.82 * PRESSURE_SET  # ~9 bar => PRV400 closes
TEMPERATURE_LIMIT = 200  # degC 
LEVEL_60pct= 0.6* TANK_HEIGHT # 1 m
LEVEL_80pct= 0.8* TANK_HEIGHT #1.34 m
MeOH_min_25pct = 0.25 * TANK_HEIGHT
FINAL_TEMP= 100 # C
FINAL_PRESS= 5 # C

###############################################################################
# VOLUMETRIC FLOW RATES / REFERENCE CONDITIONS
###############################################################################
N2_VOL_FLOW_STD      = 0.003      # m^3/s
METHANOL_FLOW_RATE   = 0.01     # m^3/s
Press_N2             = 10       # bar
T_amb                = 293.15   # K

###############################################################################
# INITIAL CONDITIONS
###############################################################################
INIT_LIQ_VOLUME = 0.0 # m3
INIT_MASS_LIQ = DENSITY_MEOH * INIT_LIQ_VOLUME  # kg
# Start with nitrogen at ~1 bar, 20 degC => n_N2 ~ ...
P_init   = 1.0   # bar
T_init   = 293.15 # K
INIT_MOLES_N2 = (P_init * TANK_VOLUME * 1e5) / (R_GAS * T_init) # ol
INIT_MOLES_MEOH_VAP = 0.0 # mol

###############################################################################
# DB PATH
###############################################################################
PATH = 'system3_db.sqlite'
NAME = 'system3_table'

STATE = {
    'name': NAME,
    'path': PATH
}

###############################################################################
# SCHEMA
###############################################################################
SCHEMA = """
CREATE TABLE system3_table (
    name  TEXT NOT NULL,
    pid   INTEGER NOT NULL,
    value TEXT,
    PRIMARY KEY (name, pid)
);
"""

SCHEMA_INIT = f"""
INSERT INTO system3_table VALUES ('LI100', 100, '0.0');
INSERT INTO system3_table VALUES ('SV100', 101, '0');
INSERT INTO system3_table VALUES ('SV100_HMI', 102, '0');
INSERT INTO system3_table VALUES ('PI100', 200, '1.0');
INSERT INTO system3_table VALUES ('SV200', 201, '0');
INSERT INTO system3_table VALUES ('SV200_HMI', 202, '0');
INSERT INTO system3_table VALUES ('TI100', 300, '20.0');
INSERT INTO system3_table VALUES ('SV300', 301, '0');
INSERT INTO system3_table VALUES ('SV300_HMI', 302, '0');
INSERT INTO system3_table VALUES ('PRV400',400,'0');
INSERT INTO system3_table VALUES ('V100',110,'0');
INSERT INTO system3_table VALUES ('V100_HMI',111,'0');
INSERT INTO system3_table VALUES ('V200',210,'0');
INSERT INTO system3_table VALUES ('V200_HMI',211,'0');
INSERT INTO system3_table VALUES ('V300',310,'0');
INSERT INTO system3_table VALUES ('V300_HMI',311,'0');

-- Newly added for HMI-sensor values
INSERT INTO system3_table VALUES ('LI100_HMI',120,'0.0');
INSERT INTO system3_table VALUES ('PI100_HMI',220,'0.0');
INSERT INTO system3_table VALUES ('TI100_HMI',320,'0.0');
INSERT INTO system3_table VALUES('HMI_CMD',9999,'(None)');

-- NEW: HMI_REP tags for CIP success messages
INSERT INTO system3_table VALUES ('SV100_HMI_REP', 10199, '0');
INSERT INTO system3_table VALUES ('SV200_HMI_REP', 20199, '0');
INSERT INTO system3_table VALUES ('SV300_HMI_REP', 30199, '0');
INSERT INTO system3_table VALUES ('V100_HMI_REP',  11099, '0');
INSERT INTO system3_table VALUES ('V200_HMI_REP',  21099, '0');
INSERT INTO system3_table VALUES ('V300_HMI_REP',  31099, '0');
"""

