#!/usr/bin/env python

import time
import logging
from minicps.devices import PLC
from utils import (
    STATE, SFPLC100_PROTOCOL, SFPLC100_DATA,
    PLC_PERIOD_SEC, SFPLC100_ADDR,
    LI100, SV100, SV100_HMI,
    LEVEL_80pct
)

logging.getLogger("enip").setLevel(logging.DEBUG)
logging.getLogger("cip").setLevel(logging.DEBUG)

def valve_str(val):
    return "open" if val == 1 else "closed"

class SFPLC100(PLC):
    """
    Safety valve SV100 (level < 80%).
    - If override=1 => try to open; if level>=80 => forcibly close.
    - If override=0 => forcibly close.
    - Otherwise symmetrical auto logic:
       if open & level>=80 => close,
       if closed & level<80 => open.
    Uses fallback so it doesn't crash if CIP or local memory is empty.
    """

    def pre_loop(self, sleep=0.5):
        print("DEBUG: SFPLC100 pre_loop. About to start CIP server on", SFPLC100_ADDR)
        logging.info(f"SFPLC100 => CIP server on {SFPLC100_ADDR} with tags: {SFPLC100_PROTOCOL['server']['tags']}")
        time.sleep(sleep)

    def main_loop(self):
        logging.basicConfig(
            filename='logs/SFPLC100.log',
            format='%(levelname)s %(asctime)s SFPLC100 %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )
        print("DEBUG: SFPLC100 main_loop starting...")

        last_level = 0.0
        last_sv = 0
        last_override_val = None

        while True:
            # 1) Read local memory (level)
            try:
                raw_level = self.get(LI100)
                if raw_level is None:
                    print("[SFPLC100] WARNING: No local memory data for LI100. Using last known:", last_level)
                    level = last_level
                else:
                    level = float(raw_level)
                    last_level = level
            except (ValueError, TypeError):
                print("[SFPLC100] WARNING: Invalid or empty data for LI100. Fallback to last known:", last_level)
                level = last_level

            # 2) Read local memory (SV100)
            try:
                raw_sv = self.get(SV100)
                if raw_sv is None:
                    print("[SFPLC100] WARNING: No local memory data for SV100. Using last known:", last_sv)
                    current_sv = last_sv
                else:
                    current_sv = int(raw_sv)
                    last_sv = current_sv
            except (ValueError, TypeError):
                print("[SFPLC100] WARNING: Invalid or empty data for SV100. Fallback to last known:", last_sv)
                current_sv = last_sv

            # 3) Update local DB + CIP memory
            self.set(LI100, level)
            self.set(SV100, current_sv)
            self.send(LI100, level, SFPLC100_ADDR)
            logging.debug(f"SFPLC100 => set CIP memory for 'LI100' = {level:.3f}")

            # 4) Check override from HMI
            try:
                raw_override_val = int(self.receive(SV100_HMI, SFPLC100_ADDR))
                if raw_override_val is not None:
                    override_val = int(raw_override_val)
                    last_override_val = override_val  # Update last known value
                else:
                    override_val = last_override_val  # Use last known override
            except (ValueError, TimeoutError) as e:
                print("[SFPLC100] WARNING: Failed to read HMI override. Using last known value.")
                override_val = last_override_val  # Fallback to last known value
            except:
                pass

            final_sv = current_sv

            # 5) Logic
            if override_val == 1:
                if level >= LEVEL_80pct:
                    final_sv = 0
                else:
                    final_sv = 1
            elif override_val == 0:
                final_sv = 0

            # 6) Update if changed
            if final_sv != current_sv:
                self.set(SV100, final_sv)
                self.send(SV100, final_sv, SFPLC100_ADDR)
                self.set(SV100_HMI, final_sv)

            print(f"[SFPLC100] level={level:.2f} m, SV100={valve_str(final_sv)}")
            time.sleep(PLC_PERIOD_SEC)

if __name__ == "__main__":
    SFPLC100 = SFPLC100(
        name='SFPLC100',
        state=STATE,
        protocol=SFPLC100_PROTOCOL,
        memory=SFPLC100_DATA,
        disk=SFPLC100_DATA
    )

