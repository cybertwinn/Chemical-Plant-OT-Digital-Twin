#!/usr/bin/env python

import time
import logging
import sys
import select
from minicps.devices import HMI
from utils import (
    HMI_PROTOCOL, HMI_DATA, STATE,
    # sensors
    LI100, PI100, TI100,
    LI100_HMI, PI100_HMI, TI100_HMI,
    # valves
    V100, V200, V300,
    SV100, SV200, SV300,
    V100_HMI, V200_HMI, V300_HMI,
    SV100_HMI, SV200_HMI, SV300_HMI,
    PRV400,
    # PLC addresses
    SFPLC100_ADDR, SFPLC200_ADDR, SFPLC300_ADDR,
    PLC100_ADDR, PLC200_ADDR, PLC300_ADDR,
    SV100_HMI_REP, SV200_HMI_REP, SV300_HMI_REP,
    V100_HMI_REP,  V200_HMI_REP,  V300_HMI_REP,
    # period
    HMI_PERIOD_SEC
)

# Store the last command in (name='HMI_CMD', pid=9999).
CMD_TAG = ('HMI_CMD', 9999)

# For convenience, define a map from command => textual explanation
CMD_MAP = {
    's':  "[s] => Open all valves",
    'x':  "[x] => Close all valves",
    '1':  "[1] => Open SV100",
    '2':  "[2] => Close SV100",
    '3':  "[3] => Open SV200",
    '4':  "[4] => Close SV200",
    '5':  "[5] => Open SV300",
    '6':  "[6] => Close SV300",
    '7':  "[7] => Open V100",
    '8':  "[8] => Close V100",
    '9':  "[9] => Open V200",
    '10': "[10] => Close V200",
    '11': "[11] => Open V300",
    '12': "[12] => Close V300",
}

def valve_str(v):
    return "open" if v == 1 else "closed"

class System3HMI(HMI):

    def main_loop(self, sleep=0.2):
        """
        Does a loop that continuously:
         1) Reads sensor + valve states from PLCs
         2) Writes them to DB (including the “HMI sensor” tags)
         3) Checks for user input (non-blocking)
         4) If user typed a command, handle it, then store “last cmd” in the DB
         5) Sleep briefly, repeat
        """
        logging.basicConfig(
            filename='logs/hmi.log',
            format='%(levelname)s %(asctime)s HMI %(funcName)s %(message)s',
            datefmt='%m/%d/%Y %H:%M:%S',
            level=logging.DEBUG
        )

        print("HMI main_loop started. Press Enter for menu. If no input, keep polling...")

        while True:
            # 1) Read sensor values from PLC addresses
            try:
                lvl = float(self.receive(LI100, SFPLC100_ADDR))
            except:
                lvl = -1
            try:
                prs = float(self.receive(PI100, SFPLC200_ADDR))
            except:
                prs = -1
            try:
                tmp = float(self.receive(TI100, SFPLC300_ADDR))
            except:
                tmp = -1

            # 2) Read local relief valve state from DB
            try:
                rv_state = int(self.get(PRV400))
            except:
                rv_state = 0

            # 3) Read final valve states via CIP
            try:
                v100_st = int(self.receive(V100, PLC100_ADDR))
            except:
                v100_st=0
            self.set(V100_HMI_REP, v100_st)
            try:
                sv100_st = int(self.receive(SV100, SFPLC100_ADDR))
            except:
                sv100_st=0
            self.set(SV100_HMI_REP, sv100_st)
            try:
                v200_st = int(self.receive(V200, PLC200_ADDR))
            except:
                v200_st=0
            self.set(V200_HMI_REP, v200_st)
            try:
                sv200_st = int(self.receive(SV200, SFPLC200_ADDR))
            except:
                sv200_st=0
            self.set(SV200_HMI_REP, sv200_st)
            try:
                v300_st = int(self.receive(V300, PLC300_ADDR))
            except:
                v300_st=0
            self.set(V300_HMI_REP, v300_st)
            try:
                sv300_st = int(self.receive(SV300, SFPLC300_ADDR))
            except:
                sv300_st=0
            self.set(SV300_HMI_REP, sv300_st)

            # Print a small line (overwrites in place)
            print(f"[HMI loop] L={lvl:.2f} m, P={prs:.2f} bar, T={tmp:.1f} C, "
                  f"PRV400={'open' if rv_state else 'closed'} | "
                  f"V100={valve_str(v100_st)}, SV100={valve_str(sv100_st)}, "
                  f"V200={valve_str(v200_st)}, SV200={valve_str(sv200_st)}, "
                  f"V300={valve_str(v300_st)}, SV300={valve_str(sv300_st)}    ",
                  end='\r', flush=True)

            # Store the "as seen by HMI" sensor values into the DB
            self.set(LI100_HMI, lvl)
            self.set(PI100_HMI, prs)
            self.set(TI100_HMI, tmp)

            # 4) Check for user input (non-blocking). If none, proceed
            rlist, _, _ = select.select([sys.stdin], [], [], 0.0001)
            if rlist:
                cmd_line = sys.stdin.readline().strip()
                if cmd_line == '':
                    # user pressed Enter => show help
                    print("\nCommands:\n [s] Start => forcibly open all valves"
                          "\n [x] Stop => forcibly close all valves"
                          "\n [1]Open SV100 [2]Close SV100"
                          "\n [3]Open SV200 [4]Close SV200"
                          "\n [5]Open SV300 [6]Close SV300"
                          "\n [7]Open V100  [8]Close V100"
                          "\n [9]Open V200  [10]Close V200"
                          "\n [11]Open V300 [12]Close V300"
                          "\n [q]Quit")
                else:
                    # Possibly multiple tokens
                    tokens = cmd_line.split()
                    for cmd in tokens:
                        # handle single command
                        if cmd=='s':
                            self.set(CMD_TAG, CMD_MAP.get('s', 'OpenAll?'))
                            print("\nHMI => forcibly open all.")
                            #for _ in range(3):
                            self.send(V100_HMI,1,PLC100_ADDR)
                            self.send(V200_HMI,1,PLC200_ADDR)
                            self.send(V300_HMI,1,PLC300_ADDR)
                            self.send(SV100_HMI,1,SFPLC100_ADDR)
                            self.send(SV200_HMI,1,SFPLC200_ADDR)
                            self.send(SV300_HMI,1,SFPLC300_ADDR)
                            time.sleep(0.05)

                        elif cmd=='x':
                            self.set(CMD_TAG, CMD_MAP.get('x', 'CloseAll?'))
                            print("\nHMI => forcibly close all.")
                            #for _ in range(3):
                            self.send(V100_HMI,0,PLC100_ADDR)
                            self.send(V200_HMI,0,PLC200_ADDR)
                            self.send(V300_HMI,0,PLC300_ADDR)
                            self.send(SV100_HMI,0,SFPLC100_ADDR)
                            self.send(SV200_HMI,0,SFPLC200_ADDR)
                            self.send(SV300_HMI,0,SFPLC300_ADDR)
                            time.sleep(0.05)

                        elif cmd=='q':
                            self.set(CMD_TAG, "[q] => Quit HMI")
                            print("\nHMI shutting down.")
                            logging.info("HMI user quit.")
                            return

                        else:
                            # try to handle numeric commands
                            if cmd in CMD_MAP:
                                self.set(CMD_TAG, CMD_MAP[cmd])
                            else:
                                self.set(CMD_TAG, f"[{cmd}] => unknown command")

                            # Perform the actual action if recognized
                            if cmd=='1':
                                self.send(SV100_HMI,1,SFPLC100_ADDR)
                            elif cmd=='2':
                                self.send(SV100_HMI,0,SFPLC100_ADDR)
                            elif cmd=='3':
                                self.send(SV200_HMI,1,SFPLC200_ADDR)
                            elif cmd=='4':
                                self.send(SV200_HMI,0,SFPLC200_ADDR)
                            elif cmd=='5':
                                self.send(SV300_HMI,1,SFPLC300_ADDR)
                            elif cmd=='6':
                                self.send(SV300_HMI,0,SFPLC300_ADDR)
                            elif cmd=='7':
                                self.send(V100_HMI,1,PLC100_ADDR)
                            elif cmd=='8':
                                self.send(V100_HMI,0,PLC100_ADDR)
                            elif cmd=='9':
                                self.send(V200_HMI,1,PLC200_ADDR)
                            elif cmd=='10':
                                self.send(V200_HMI,0,PLC200_ADDR)
                            elif cmd=='11':
                                self.send(V300_HMI,1,PLC300_ADDR)
                            elif cmd=='12':
                                self.send(V300_HMI,0,PLC300_ADDR)
                            else:
                                if cmd not in ['s','x','q','1','2','3','4','5','6','7','8','9','10','11','12']:
                                    print("\nUnknown command:", cmd)

            time.sleep(sleep)

if __name__=="__main__":
    hmi = System3HMI(
      name='hmi',
      state=STATE,
      protocol=HMI_PROTOCOL,
      memory=HMI_DATA,
      disk=HMI_DATA
    )

