# Mininet–MiniCPS Digital Twin: Pressurized Methanol-Nitrogen Vessel

This repository contains a digital twin of an industrial chemical process (a pressurized methanol-nitrogen vessel with steam heating) using Mininet and MiniCPS. It is designed to demonstrate both normal process control and various cybersecurity attack scenarios on the 
ICS (Industrial Control System).

## Table of Contents
1. [Overview]  
2. [Repository Layout]  
3. [Scripts & Directories] 
   - [Initialization and Database]
   - [Physical Process Simulation] 
   - [Programmable Logic Controllers (PLCs)]
   - [Human-Machine Interface (HMI)] 
   - [Network Topology] 
   - [Attacker Scripts]  
4. [Running the Digital Twin] 

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

Six main PLC scripts implement control logic for the normal (N) and safety (S) valves:

1. `PLC100.py`  
   - Normal PLC controlling the methanol inlet valve V100.  
   - Opens/closes based on tank level (60% threshold).

2. `SFPLC100.py` (Safety PLC)  
   - Controls the safety methanol inlet valve SV100.  
   - Uses a higher threshold (80% of tank level) for emergency closure, overriding normal PLC if necessary.

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
   - Controls the steam coil safety valve SV300.  
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

### Network Topology and Orchestration

- `topo.py`  
  - Defines the Mininet topology, creating virtual hosts (the PLCs, HMI, physical process, attacker) and connecting them to a software-based switch.  
  - Mimics a typical ICS star topology over Ethernet.
 
### Shared Utilities
utils.py

A shared configuration module used throughout the simulation.

Defines:

CIP tag names (e.g. LI100, PI100, TI100) used by the PLCs, safety PLCs, and HMI.

IP addresses and port info for each PLC or SFPLC (e.g., PLC100_ADDR, SFPLC100_ADDR).

Thermodynamic constants and formulas (e.g. gas constant R_GAS, methanol density DENSITY_MEOH, partial pressure calculations).

Process thresholds (e.g., 60% or 80% tank level, final temperature).

Database paths, update periods, cross-sectional area of the tank, etc.

- `run.py`  
  - Launches Mininet with the custom topology.  
  - Spawns each host’s process in a new terminal (e.g., the physical process, PLC scripts, HMI).  
  - Opens an additional plotting window, i.e., HMI graphical view (`realtimeplot.py`).

### Attacker Scripts

- `Functional_attacks/`  
  Contains various Python scripts and/or shell scripts to demonstrate ICS cyberattacks on the CIP-based communications:
  - MITM attacks (ARP spoofing, CIP manipulation).  
  - CIP packet injection (crafting unauthorized read/write commands).  
  - Denial-of-Service (DoS) (SYN flood or ARP flooding).  
