#!/usr/bin/env python

import time
import logging
from minicps.devices import PLC
from utils import (
    STATE, PLC100_PROTOCOL, PLC100_DATA,
    PLC_PERIOD_SEC, PLC100_ADDR, SFPLC100_ADDR,
    LI100, V100, V100_HMI,
    LEVEL_60pct
)

logging.getLogger("enip").setLevel(logging.DEBUG)
logging.getLogger("cip").setLevel(logging.DEBUG)

def valve_str(val):
    return "open" if val==1 else "closed"

class PLC100(PLC):
    """
    Normal valve V100 (level < 60%).
    - override=1 => open if level<60, else close
    - override=0 => close
    - else symmetrical auto:
      if open & level>=60 => close
      if closed & level<60 => open
    """

    def pre_loop(self, sleep=0.5):
        print("DEBUG: PLC100 pre_loop. About to start CIP server on", PLC100_ADDR)
        logging.info(f"PLC100 => CIP server on {PLC100_ADDR} with tags: {PLC100_PROTOCOL['server']['tags']}")
        time.sleep(sleep)

    def main_loop(self):
        logging.basicConfig(
            filename='logs/PLC100.log',
            format='%(levelname)s %(asctime)s PLC100 %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )
        print("DEBUG: PLC100 main_loop starting...")
        
        last_level_db = 0.0
        last_v100 = 0
        last_override_val = None
        
        while True:
            # 1) CIP read for level from PLC100
            try:
                raw_data = self.receive(LI100, SFPLC100_ADDR)
                if not raw_data:
                    print("[PLC100] WARNING: No data from PLC100. Using fallback.")
                    level_db = last_level_db
                else:
                    level_db = float(raw_data)
                    last_level_db = level_db
            except (ValueError, TimeoutError) as e:
                print("[PLC100] CIP read failed or data invalid:", e)
                level_db = last_level_db

            # 2) Current V100
            try:
                raw_v100 = self.get(V100)
                if raw_v100 is None:
                    current_v = last_v100
                else:
                    current_v = int(raw_v100)
                    last_v100 = current_v
            except (ValueError, TimeoutError) as e:
                print("[PLC100] CIP read for V100 failed:", e)
                current_v = last_v100

            # 3) Save CIP memory
            self.set(V100, current_v)
            logging.debug(f"[PLC100] => level={level_db:.3f}, V100={current_v}")

            # 4) Read override
            try:
                raw_override_val = int(self.receive(V100_HMI, PLC100_ADDR))
                if raw_override_val is not None:
                    override_val = int(raw_override_val)
                    last_override_val = override_val  # Update last known value
                else:
                    override_val = last_override_val  # Use last known override
            except (ValueError, TimeoutError) as e:
                print("[PLC100] WARNING: Failed to read HMI override. Using last known value.")
                override_val = last_override_val  # Fallback to last known value
            except:
                pass

            final_v = current_v

            # 5) Logic
            if override_val == 1:
                if level_db >= LEVEL_60pct:
                    final_v = 0
                else:
                    final_v = 1
            elif override_val == 0:
                final_v = 0

            # 6) Update if changed
            if final_v != current_v:
                self.set(V100, final_v)
                self.send(V100, final_v, PLC100_ADDR)
                self.set(V100_HMI, final_v)

            print(f"[PLC100] level={level_db:.2f} m, V100={valve_str(final_v)}")
            time.sleep(PLC_PERIOD_SEC)

if __name__=="__main__":
    PLC100= PLC100(
       name='PLC100',
       state=STATE,
       protocol=PLC100_PROTOCOL,
       memory=PLC100_DATA,
       disk=PLC100_DATA
    )

