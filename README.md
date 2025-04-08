# Mininet–MiniCPS Digital Twin: Pressurized Methanol-Nitrogen Vessel

This repository contains a digital twin of an industrial chemical process (a pressurized methanol-nitrogen vessel with steam heating) using Mininet and MiniCPS. It is designed to demonstrate both normal process control and various cybersecurity attack scenarios on the OT (Operational Technology) network of the ICS (Industrial Control System) .

## Table of Contents
1. [Overview]  
2. [Repository Layout]  
3. [Scripts & Directories] 
   - [Initialization and Database]
   - [Physical Process Simulation]
   - [Programmable Logic Controllers (PLCs)]
   - [Human-Machine Interface (HMI)]
   - [Graphical HMI (plots)]
   - [Network Topology]
   - [Shared Utilities]
   - [Run]
   - [Attacker Scripts]  

---

## Overview
This digital twin emulates both the physical plant dynamics (temperature, pressure, liquid level) and the industrial control network (switch, PLCs, Safety PLCs, HMI, attacker node) for a realistic testbed. By combining Mininet (for network emulation) and MiniCPS 
(for ICS-specific simulation), it provides:
- Real-time process simulation: A virtual methanol vessel with inlets (methanol, nitrogen, steam) managed by normal and safety valves.  
- ICS protocol-level communication: ENIP/CIP-based data exchange among PLCs, SFPLCs, and the HMI.  
- Cyberattack experimentation: Scripts to launch Man-in-the-Middle (MITM), packet injection, and other attacks to highlight vulnerabilities in ICS networks.  

---

## Repository Layout

```
Mininet-MiniCPS-DigitalTwin/
├── Functional_attacks/
│   ├── cip_injection_prompt.py
│   ├── dos_prompt.py
│   ├── mitm_icmp_prompt_ephemeral.py
│   ├── mitm_netfilter_queue_prompt.py
├── src/
│   ├── init.py
│   ├── physical_process.py
│   ├── PLC100.py
│   ├── PLC200.py
│   ├── PLC300.py
│   ├── SFPLC100.py
│   ├── SFPLC200.py
│   ├── SFPLC300.py
│   ├── HMI.py
│   ├── realtimeplot.py
│   ├── topo.py
│   ├── utils.py
│   └── run.py
├── system3_db.sqlite (created dynamically)
└── README.md
```

## Scripts & Directories

### Initialization and Database

- `init.py`  
  Creates (or re-initializes) the SQLite database (`system3_db.sqlite`) used by the digital twin. It:
  1. Removes any existing database file.
  2. Creates a fresh schema for storing sensor/actuator tag values.
  3. Initializes the database with default entries.

### Physical Process Simulation

- `physical_process.py`  
  Models the real-world physics and thermodynamics of a methanol vessel heated by steam and pressurized with nitrogen. It:
  - Updates liquid mass, temperature, headspace pressure, and valve states in discrete time steps.
  - Checks if safety limits are exceeded (e.g., relief valve logic).
  - Writes updated sensor data (level, pressure, temperature) back to the database to be read by PLCs.

  Key features:  
    - Simulates evaporation/condensation with simplified thermodynamics.  
    - Accounts for open/closed states of both normal and safety valves.  
    - Runs continuously in a loop with a set period (e.g., 1 second).

### Programmable Logic Controllers (PLCs)

Six main PLC scripts implement control logic for the normal (V100, V200, V300) and safety (SV100, SV200, SV300) valves:

1. `PLC100.py`  
   - Normal PLC controlling the methanol inlet valve V100.  
   - Opens/closes based on tank level (60% threshold).

2. `SFPLC100.py` (Safety PLC)  
   - Controls the safety methanol inlet valve SV100.  
   - Uses a higher threshold (80% tank level) for emergency closure, overriding normal PLC if necessary.

3. `PLC200.py`  
   - Normal PLC for nitrogen inlet valve V200.  
   - Logic depends on multiple conditions: methanol level, vessel temperature, and pressure thresholds.

4. `SFPLC200.py` (Safety PLC)  
   - Controls the safety valve SV200 for nitrogen.  
   - Opens/closes based on pressure (10 bar threshold)

5. `PLC300.py`  
   - Normal PLC for the steam inlet valve V300.  
   - Checks vessel temperature and methanol level (e.g., if below final target (100C), open; if above target or below 25% methanol level, close).

6. `SFPLC300.py` (Safety PLC)  
   - Controls the steam inlet safety valve SV300.  
   - Forces closure under extreme temperature conditions (200C).

Each PLC script periodically:
- Reads relevant sensor values (via CIP-like calls or local DB states).  
- Applies threshold-based logic and any HMI overrides.  
- Writes the new valve state back to the database and notifies other controllers.

### Human-Machine Interface (HMI)

  - `HMI.py`  
  - A simple Python-based interface that emulates an operator station.  
  - Lets you send override commands (open/close valves) to the PLCs and SFPLCs.  
  - Receives sensor values and valve states, showing the operator’s perspective of tank level, pressure, and temperature.

### Graphical HMI (plots)
  - `realtimeplot.py`
  - Provides a live visualization of the tank’s level, pressure, and temperature, as well as valve states, by querying the same database the PLCs and HMI use. It shows:
  - Field-Level Data (actual sensor measurements from physical_process.py).
  - HMI-Level Data (what the operator’s station sees), which may diverge if a MITM or injection attack manipulates the values.
  - The script uses matplotlib animation to update bar charts and color-coded valve indicators in real time.

### Network Topology

  - `topo.py`  
  - Defines the Mininet topology, creating virtual hosts (the PLCs, HMI, physical process, attacker) and connecting them to a software-based switch.  
  - Mimics a typical ICS star topology over Ethernet.
 
### Shared Utilities
  - `utils.py`
  - A shared configuration module used throughout the simulation. 
  - Defines:
  - CIP tag names (e.g. LI100, PI100, TI100) used by the PLCs, safety PLCs, and HMI.
  - IP addresses and port info for each PLC or SFPLC (e.g., PLC100_ADDR, SFPLC100_ADDR).
  - Thermodynamic constants and formulas (e.g. gas constant R_GAS, methanol density DENSITY_MEOH, partial pressure calculations).
  - Process thresholds (e.g., 60% or 80% tank level, final temperature).
  - Database paths, update periods, cross-sectional area of the tank, etc.

### Run
  - `run.py`  
  - Launches Mininet with the custom topology.  
  - Spawns each host’s process in a new terminal (e.g., the physical process, PLC scripts, HMI).  
  - Opens an additional plotting window, i.e., HMI graphical view (`realtimeplot.py`).

### Attacker Scripts
- `Functional_attacks/`  
  Contains various Python scripts to demonstrate ICS cyberattacks on the CIP-based communications:
  - `mitm_icmp_prompt_ephemeral.py` (MITM Attack with ARP Spoofing and NetfilterQueue Redirection):
     - Goal: Intercept and forward CIP packets between PLCs and the HMI while remaining undetected.
     - Method: Uses ARP spoofing to trick devices into sending traffic through the attacker. The attacker then applies NetfilterQueue to inspect or modify CIP messages on-the-fly, leveraging ICMP redirect rules to maintain routing.
     - Impact: Enables the attacker to observe (or alter) process variables and operator commands in real-time, potentially causing deceptive displays on the HMI or masked sensor readings.
       
  - `mitm_netfilter_queue_prompt.py` (Payload Manipulation with NetfilterQueue):
     - Goal: Illustrate how the attacker can modify CIP payload data directly in transit.
     - Method: Hooks into NetfilterQueue within a Man-in-the-Middle (MITM) setup to intercept EtherNet/IP frames, parse CIP commands, and rewrite key fields (e.g., forcing valve states, falsifying sensor readings).
     - Impact: Allows on-the-fly manipulation of control commands, letting the attacker stealthily alter process behavior while maintaining seemingly valid traffic flows.
       
  - `cip_injection_prompt.py` (CIP Injection Attack Spoofing the HMI):
     - Goal: Send malicious CIP commands to PLCs by impersonating the legitimate HMI.
     - Method: Crafts CIP Write or Read requests (using tools like Scapy) that mimic the HMI’s IP and ports, bypassing authentication (which CIP lacks).
     - Impact: The attacker can change valve states, override safety thresholds, or feed phony sensor values to PLC memory, potentially jeopardizing plant safety and reliability.
       
  - `dos_prompt.py` (DoS Attack with ARP Spoofing and CIP Packet Dropping):
     - Goal: Disrupt critical ICS communications to cause delays, errors, or complete system unavailability.
     - Method: Floods ARP tables and selectively drops CIP packets via NetfilterQueue, overwhelming PLC/HMI connections or causing them to time out.
     - Impact: Prevents operators from issuing commands or reading sensor data, possibly leading to hazardous physical conditions if the control system cannot respond to process changes.
  
