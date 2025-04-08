"""
topo.py
The topology includes s1, six PLCs, one HMI, and one attacker,
all connected to a single switch sw1.

System:
 s1, SFPLC100, PLC100, SFPLC200, PLC200, SFPLC300, PLC300, hmi, attacker
 single switch sw1
"""

from mininet.topo import Topo
from utils import (
  Physicalprocess_ADDR, Physicalprocess_MAC,
  SFPLC100_ADDR, SFPLC100_MAC,
  PLC100_ADDR, PLC100_MAC,
  SFPLC200_ADDR, SFPLC200_MAC,
  PLC200_ADDR, PLC200_MAC,
  SFPLC300_ADDR, SFPLC300_MAC,
  PLC300_ADDR, PLC300_MAC,
  HMI_ADDR, HMI_MAC,
  ATTACKER_ADDR, ATTACKER_MAC,
  NETMASK
)

class System3Topo(Topo):

    def build(self):
        sw1= self.addSwitch('sw1')

        Process= self.addHost('Process', ip=Physicalprocess_ADDR+NETMASK, mac=Physicalprocess_MAC)
        self.addLink(Process, sw1)

        SFPLC100= self.addHost('SFPLC100', ip=SFPLC100_ADDR+NETMASK, mac=SFPLC100_MAC)
        self.addLink(SFPLC100, sw1)

        PLC100= self.addHost('PLC100', ip=PLC100_ADDR+NETMASK, mac=PLC100_MAC)
        self.addLink(PLC100, sw1)

        SFPLC200= self.addHost('SFPLC200', ip=SFPLC200_ADDR+NETMASK, mac=SFPLC200_MAC)
        self.addLink(SFPLC200, sw1)

        PLC200= self.addHost('PLC200', ip=PLC200_ADDR+NETMASK, mac=PLC200_MAC)
        self.addLink(PLC200, sw1)

        SFPLC300= self.addHost('SFPLC300', ip=SFPLC300_ADDR+NETMASK, mac=SFPLC300_MAC)
        self.addLink(SFPLC300, sw1)

        PLC300= self.addHost('PLC300', ip=PLC300_ADDR+NETMASK, mac=PLC300_MAC)
        self.addLink(PLC300, sw1)

        HMI= self.addHost('HMI', ip=HMI_ADDR+NETMASK, mac=HMI_MAC)
        self.addLink(HMI, sw1)

        attacker= self.addHost('attacker', ip=ATTACKER_ADDR+NETMASK, mac=ATTACKER_MAC)
        self.addLink(attacker, sw1)
