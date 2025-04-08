#!/usr/bin/env python

import time
import logging
from minicps.devices import PLC
from utils import (
    STATE, PLC300_PROTOCOL, PLC300_DATA,
    PLC_PERIOD_SEC, PLC300_ADDR, SFPLC300_ADDR, SFPLC100_ADDR, PLC100_ADDR,
    TI100, V100, V300, V300_HMI,
    FINAL_TEMP, MeOH_min_25pct, LI100
)

logging.getLogger("enip").setLevel(logging.DEBUG)
logging.getLogger("cip").setLevel(logging.DEBUG)

def valve_str(val):
    return "open" if val==1 else "closed"

class PLC300(PLC):
    """
    Normal valve V300 (temp < FINAL_TEMP).
    - override=1 => open if T < FINAL_TEMP and level >= 25%,
      else close
    - override=0 => close
    - symmetrical auto:
      close if T >= FINAL_TEMP or level < 25%
      open otherwise
    Also checks CIP from PLC110 => V100 as an interlock if needed.
    """

    def pre_loop(self, sleep=0.5):
        print("DEBUG: PLC300 pre_loop. About to start CIP server on", PLC300_ADDR)
        logging.info(f"PLC300 => CIP server on {PLC300_ADDR} with tags: {PLC300_PROTOCOL['server']['tags']}")
        time.sleep(sleep)

    def main_loop(self):
        logging.basicConfig(
            filename='logs/PLC300.log',
            format='%(levelname)s %(asctime)s PLC300 %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )
        print("DEBUG: PLC300 main_loop start...")

        last_temp = 0.0
        last_level = 0.0
        last_meoh_v = 0
        last_v300 = 0
        last_override_val = None

        while True:
            # 1) CIP read from PLC300 => TI100
            try:
                raw_temp = self.receive(TI100, SFPLC300_ADDR)
                if raw_temp:
                    temp_db = float(raw_temp)
                    last_temp = temp_db
                else:
                    temp_db = last_temp
            except (ValueError, TimeoutError):
                temp_db = last_temp

            # 2) Local get for V300
            try:
                raw_v300 = self.get(V300)
                if raw_v300 is None:
                    current_v = last_v300
                else:
                    current_v = int(raw_v300)
                    last_v300 = current_v
            except (ValueError, TypeError):
                current_v = last_v300
            
            self.set(V300, current_v)
            logging.debug(f"PLC300 => set CIP memory for 'V300' = {current_v}")

            # 3) CIP read from PLC100 => LI100
            try:
                raw_level = self.receive(LI100, SFPLC100_ADDR)
                if raw_level:
                    level_db = float(raw_level)
                    last_level = level_db
                else:
                    level_db = last_level
            except (ValueError, TimeoutError):
                level_db = last_level

            # 5) Read override for V300
            try:
                raw_override_val = int(self.receive(V300_HMI, PLC300_ADDR))
                if raw_override_val is not None:
                    override_val = int(raw_override_val)
                    last_override_val = override_val  # Update last known value
                else:
                    override_val = last_override_val  # Use last known override
            except (ValueError, TimeoutError) as e:
                print("[PLC300] WARNING: Failed to read HMI override. Using last known value.")
                override_val = last_override_val  # Fallback to last known value
            except:
                pass

            final_v = current_v

            # 6) Logic
            if override_val == 1:
                if temp_db < FINAL_TEMP and level_db >= MeOH_min_25pct:
                    final_v = 1
                else:
                    final_v = 0
            elif override_val == 0:
                final_v = 0

            if final_v != current_v:
                self.set(V300, final_v)
                self.send(V300, final_v, PLC300_ADDR)
                self.set(V300_HMI, final_v)

            print(f"[PLC300] T={temp_db:.1f}C, level={level_db:.2f} m, V300={valve_str(final_v)}")
            time.sleep(PLC_PERIOD_SEC)

if __name__=="__main__":
    PLC300= PLC300(
       name='PLC300',
       state=STATE,
       protocol=PLC300_PROTOCOL,
       memory=PLC300_DATA,
       disk=PLC300_DATA
    )

