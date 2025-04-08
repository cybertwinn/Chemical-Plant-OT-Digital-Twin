#!/usr/bin/env python

import time
import logging
from minicps.devices import PLC
from utils import (
    STATE, SFPLC200_PROTOCOL, SFPLC200_DATA,
    PLC_PERIOD_SEC, SFPLC200_ADDR,
    PI100, SV200, SV200_HMI,
    PRESSURE_LIMIT
)

logging.getLogger("enip").setLevel(logging.DEBUG)
logging.getLogger("cip").setLevel(logging.DEBUG)

def valve_str(val):
    return "open" if val==1 else "closed"

class SFPLC200(PLC):
    """
    Safety valve SV200 (pressure < PRESSURE_LIMIT).
    - override=1 => open if press < limit, else close
    - override=0 => close
    - symmetrical auto:
      if open & press >= limit => close
      if closed & press < limit => open
    """

    def pre_loop(self, sleep=0.5):
        print("DEBUG: SFPLC200 pre_loop. About to start CIP server on", SFPLC200_ADDR)
        logging.info(f"SFPLC200 => CIP server on {SFPLC200_ADDR} with tags: {SFPLC200_PROTOCOL['server']['tags']}")
        time.sleep(sleep)

    def main_loop(self):
        logging.basicConfig(
            filename='logs/SFPLC200.log',
            format='%(levelname)s %(asctime)s SFPLC200 %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )
        print("DEBUG: SFPLC200 main_loop starting...")

        last_press = 0.0
        last_sv = 0
        last_override_val = None

        while True:
            # 1) Read local memory for PI100
            try:
                raw_press = self.get(PI100)
                if raw_press is None:
                    press_db = last_press
                else:
                    press_db = float(raw_press)
                    last_press = press_db
            except (ValueError, TypeError):
                press_db = last_press

            # 2) Read local memory for SV200
            try:
                raw_sv = self.get(SV200)
                if raw_sv is None:
                    current_sv = last_sv
                else:
                    current_sv = int(raw_sv)
                    last_sv = current_sv
            except (ValueError, TypeError):
                current_sv = last_sv

            # 3) Update CIP memory
            self.set(PI100, press_db)
            self.send(PI100, press_db, SFPLC200_ADDR)
            self.set(SV200, current_sv)

            # 4) Read override from HMI
            try:
                raw_override_val = int(self.receive(SV200_HMI, SFPLC200_ADDR))
                if raw_override_val is not None:
                    override_val = int(raw_override_val)
                    last_override_val = override_val  # Update last known value
                else:
                    override_val = last_override_val  # Use last known override
            except (ValueError, TimeoutError) as e:
                print("[SFPLC200] WARNING: Failed to read HMI override. Using last known value.")
                override_val = last_override_val  # Fallback to last known value
            except:
                pass

            final_sv = current_sv

            # 5) Logic
            if override_val == 1:
                if press_db >= PRESSURE_LIMIT:
                    final_sv = 0
                else:
                    final_sv = 1
            elif override_val == 0:
                final_sv = 0

            # 6) Update if changed
            if final_sv != current_sv:
                self.set(SV200, final_sv)
                self.send(SV200, final_sv, SFPLC200_ADDR)
                self.set(SV200_HMI, final_sv)

            print(f"[SFPLC200] P={press_db:.2f} => SV200={valve_str(final_sv)}")
            time.sleep(PLC_PERIOD_SEC)

if __name__=="__main__":
    SFPLC200=SFPLC200(
        name='SFPLC200',
        state=STATE,
        protocol=SFPLC200_PROTOCOL,
        memory=SFPLC200_DATA,
        disk=SFPLC200_DATA
    )

