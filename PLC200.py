#!/usr/bin/env python

import time
import logging
from minicps.devices import PLC
from utils import (
    STATE, PLC200_PROTOCOL, PLC200_DATA,
    PLC_PERIOD_SEC, PLC200_ADDR, SFPLC100_ADDR, SFPLC200_ADDR, SFPLC300_ADDR,
    LI100, TI100, PI100,
    V200, V200_HMI,
    LEVEL_60pct, FINAL_TEMP, FINAL_PRESS
)

logging.getLogger("enip").setLevel(logging.DEBUG)
logging.getLogger("cip").setLevel(logging.DEBUG)

def valve_str(val):
    return "open" if val == 1 else "closed"

class PLC200(PLC):
    """
    Normal valve V200 (N2).
    If override=1 => open if (level>=60%, temp>=FINAL_TEMP, press<FINAL_PRESS), else close
    If override=0 => close
    Otherwise symmetrical auto:
      if open & conditions fail => close,
      if closed & conditions pass => open.
    Uses fallback for CIP reads from PLC100, PLC200, PLC300.
    """

    def pre_loop(self, sleep=0.5):
        print("DEBUG: PLC200 pre_loop. About to start CIP server on", PLC200_ADDR)
        logging.info(f"PLC200 => CIP server on {PLC200_ADDR} with tags: {PLC200_PROTOCOL['server']['tags']}")
        time.sleep(sleep)

    def main_loop(self):
        logging.basicConfig(
            filename='logs/PLC200.log',
            format='%(levelname)s %(asctime)s PLC200 %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )
        print("DEBUG: PLC200 main_loop starting...")

        last_level = 0.0
        last_press = 0.0
        last_temp = 0.0
        last_v200 = 0
        last_override_val = None

        while True:
            # 1) Read local memory for V200
            try:
                raw_v200 = self.get(V200)
                if raw_v200 is None:
                    current_v = last_v200
                else:
                    current_v = int(raw_v200)
                    last_v200 = current_v
            except (ValueError, TypeError):
                current_v = last_v200

            # 2) CIP read from PLC100 => LI100
            try:
                raw_lvl = self.receive(LI100, SFPLC100_ADDR)
                if raw_lvl:
                    level_db = float(raw_lvl)
                    last_level = level_db
                else:
                    level_db = last_level
            except:
                level_db = last_level

            # 3) CIP read from PLC200 => PI100
            try:
                raw_prs = self.receive(PI100, SFPLC200_ADDR)
                if raw_prs:
                    press_db = float(raw_prs)
                    last_press = press_db
                else:
                    press_db = last_press
            except:
                press_db = last_press

            # 4) CIP read from PLC300 => TI100
            try:
                raw_tmp = self.receive(TI100, SFPLC300_ADDR)
                if raw_tmp:
                    tmp_db = float(raw_tmp)
                    last_temp = tmp_db
                else:
                    tmp_db = last_temp
            except:
                tmp_db = last_temp

            # 5) Read override
            try:
                raw_override_val = int(self.receive(V200_HMI, PLC200_ADDR))
                if raw_override_val is not None:
                    override_val = int(raw_override_val)
                    last_override_val = override_val  # Update last known value
                else:
                    override_val = last_override_val  # Use last known override
            except (ValueError, TimeoutError) as e:
                print("[PLC200] WARNING: Failed to read HMI override. Using last known value.")
                override_val = last_override_val  # Fallback to last known value
            except:
                pass

            final_v = current_v

            # 6) Logic
            if override_val == 1:
                if not (level_db >= LEVEL_60pct and tmp_db >= FINAL_TEMP and press_db < FINAL_PRESS):
                    final_v = 0
                else:
                    final_v = 1
            elif override_val == 0:
                final_v = 0

            if final_v != current_v:
                self.set(V200, final_v)
                self.send(V200, final_v, PLC200_ADDR)
                self.set(V200_HMI, final_v)

            print(f"[PLC200] level={level_db:.2f} m, temp={tmp_db:.1f}C, press={press_db:.2f} bar, V200={valve_str(final_v)}")
            time.sleep(PLC_PERIOD_SEC)

if __name__=="__main__":
    PLC200= PLC200(
       name='PLC200',
       state=STATE,
       protocol=PLC200_PROTOCOL,
       memory=PLC200_DATA,
       disk=PLC200_DATA
    )

