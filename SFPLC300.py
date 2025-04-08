#!/usr/bin/env python

import time
import logging
from minicps.devices import PLC
from utils import (
    STATE, SFPLC300_PROTOCOL, SFPLC300_DATA,
    PLC_PERIOD_SEC, SFPLC300_ADDR,
    TI100, SV300, SV300_HMI,
    TEMPERATURE_LIMIT
)

logging.getLogger("enip").setLevel(logging.DEBUG)
logging.getLogger("cip").setLevel(logging.DEBUG)

def valve_str(val):
    return "open" if val==1 else "closed"

class SFPLC300(PLC):
    """
    Safety valve SV300 (temp < TEMPERATURE_LIMIT).
    - override=1 => open if temp < limit, else close
    - override=0 => close
    - symmetrical auto:
      if open & temp >= limit => close
      if closed & temp < limit => open
    """

    def pre_loop(self, sleep=0.5):
        print("DEBUG: SFPLC300 pre_loop. About to start CIP server on", SFPLC300_ADDR)
        logging.info(f"SFPLC300 => CIP server on {SFPLC300_ADDR} with tags: {SFPLC300_PROTOCOL['server']['tags']}")
        time.sleep(sleep)

    def main_loop(self):
        logging.basicConfig(
            filename='logs/SFPLC300.log',
            format='%(levelname)s %(asctime)s SFPLC300 %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )
        print("DEBUG: SFPLC300 main_loop start...")

        last_temp = 0.0
        last_sv = 0
        last_override_val = None

        while True:
            # 1) Read local memory for TI100
            try:
                raw_temp = self.get(TI100)
                if raw_temp is None:
                    temp_db = last_temp
                else:
                    temp_db = float(raw_temp)
                    last_temp = temp_db
            except (ValueError, TypeError):
                temp_db = last_temp

            # 2) Read local memory for SV300
            try:
                raw_sv = self.get(SV300)
                if raw_sv is None:
                    current_sv = last_sv
                else:
                    current_sv = int(raw_sv)
                    last_sv = current_sv
            except (ValueError, TypeError):
                current_sv = last_sv

            # 3) Update CIP memory
            self.set(TI100, temp_db)
            self.set(SV300, current_sv)
            self.send(TI100, temp_db, SFPLC300_ADDR)

            # 4) Read override
            try:
                raw_override_val = int(self.receive(SV300_HMI, SFPLC300_ADDR))
                if raw_override_val is not None:
                    override_val = int(raw_override_val)
                    last_override_val = override_val  # Update last known value
                else:
                    override_val = last_override_val  # Use last known override
            except (ValueError, TimeoutError) as e:
                print("[SFPLC300] WARNING: Failed to read HMI override. Using last known value.")
                override_val = last_override_val  # Fallback to last known value
            except:
                pass

            final_sv = current_sv

            # 5) Logic
            if override_val==1:
                if temp_db>=TEMPERATURE_LIMIT:
                    final_sv=0
                else:
                    final_sv=1
            elif override_val==0:
                final_sv=0

            # 6) Update if changed
            if final_sv != current_sv:
                self.set(SV300, final_sv)
                self.send(SV300, final_sv, SFPLC300_ADDR)
                self.set(SV300_HMI, final_sv)

            print(f"[SFPLC300] T={temp_db:.1f}C, SV300={valve_str(final_sv)}")
            time.sleep(PLC_PERIOD_SEC)

if __name__=="__main__":
    SFPLC300=SFPLC300(
        name='SFPLC300',
        state=STATE,
        protocol=SFPLC300_PROTOCOL,
        memory=SFPLC300_DATA,
        disk=SFPLC300_DATA
    )

