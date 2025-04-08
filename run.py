#!/usr/bin/env python

import time
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.term import makeTerm
from topo import System3Topo
import os

def main():
    # 1) Build and start the Mininet network
    topo = System3Topo()
    net = Mininet(topo=topo)
    net.start()
    net.pingAll()

    # 2) Get references to each node
    Process   = net.get('Process')
    SFPLC100  = net.get('SFPLC100')
    PLC100  = net.get('PLC100')
    SFPLC200  = net.get('SFPLC200')
    PLC200  = net.get('PLC200')
    SFPLC300  = net.get('SFPLC300')
    PLC300  = net.get('PLC300')
    HMI     = net.get('HMI')
    attacker= net.get('attacker')  

    # 3) Open xterms for the physical process  and each PLC
    makeTerm(Process,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python physical_process.py; exec bash'"
    )
    time.sleep(0.5)

    makeTerm(SFPLC100,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python SFPLC100.py; exec bash'"
    )
    makeTerm(PLC100,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python PLC100.py; exec bash'"
    )
    makeTerm(SFPLC200,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python SFPLC200.py; exec bash'"
    )
    makeTerm(PLC200,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python PLC200.py; exec bash'"
    )
    makeTerm(SFPLC300,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python SFPLC300.py; exec bash'"
    )
    makeTerm(PLC300,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python PLC300.py; exec bash'"
    )
    
    makeTerm(attacker, cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && cd Functional_attacks && cd Combined && exec bash'")
    makeTerm(attacker, cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && cd Functional_attacks && cd Combined && exec bash'")
    makeTerm(attacker, cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && cd Functional_attacks && cd Combined && exec bash'")

    # 4) Wait ~2 seconds so that all PLCs and physical process are running, then open HMI
    time.sleep(2)
    makeTerm(HMI,
        cmd="bash -c 'source ~/minicps/minicps-env/bin/activate && python HMI.py; exec bash'"
    )

    # 5) Open a real-time plotting script in a local xterm
    os.system('xterm -hold -e "bash -c \'cd ~/OTwin-MeOH-vessel/src && source ~/minicps/minicps-env/bin/activate && python realtimeplot.py; exec bash\'" &')

    # 6) Start Mininet CLI
    CLI(net)

    # 7) Stop the network when finished
    net.stop()

if __name__ == "__main__":
    main()
