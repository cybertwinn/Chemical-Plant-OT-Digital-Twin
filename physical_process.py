"""
physical_process.py

"""
import time
import math
from minicps.devices import Device
from utils import (
    # Database
    STATE, PP_PERIOD_SEC,

    # Thermodynamic parameters
    R_GAS, CP_MEOH, DENSITY_MEOH, MW_MEOH,
    DELTAH_VAP, U_COIL, AREA_COIL, T_STEAM, HEAT_LOSS,
    methanol_p_sat,

    # Flows and pressure setpoints
    N2_VOL_FLOW_STD, METHANOL_FLOW_RATE,
    PRESSURE_SET, PRESSURE_OPEN, PRESSURE_CLOSE, Press_N2,
    INIT_MASS_LIQ, INIT_MOLES_N2, INIT_MOLES_MEOH_VAP, T_amb,

    # Tank geometry
    TANK_VOLUME, TANK_CROSS_SECTION,

    # CIP tags
    LI100, PI100, TI100, PRV400,
    V100, V200, V300,
    SV100, SV200, SV300
)

ALPHA = 0.01  # [mol/s of "mass transfer capacity"]

class TankSystem(Device):
    """
    The TankSystem periodically updates:
     1) Mass of methanol liquid
     2) Moles of N2
     3) Moles of MeOH vapor
     4) Liquid temperature
     5) Pressure and relief valve logic
     6) Writes updated level, pressure, temperature to the DB
    """

    def __init__(self, name, protocol, state):
        # Initialize state
        self.mass_liq = INIT_MASS_LIQ  # [kg]
        self.n_n2 = INIT_MOLES_N2      # [mol]
        self.n_meoh_vap = INIT_MOLES_MEOH_VAP  # [mol]
        self.temp_liq = 20.0           # [degC]
        self.prv400_open = False       # Relief valve closed initially

        super(TankSystem, self).__init__(name, protocol, state)

    def _start(self):
        self.pre_loop()
        self.main_loop()

    def pre_loop(self):
        print("Physical process pre_loop...")

    def main_loop(self):
        while True:
            dt = PP_PERIOD_SEC

            # 1) Read normal + safety valves from DB
            try:
                v100 = int(self.get(V100))   # methanol normal
                sv100 = int(self.get(SV100)) # methanol safety

                v200 = int(self.get(V200))   # N2 normal
                sv200 = int(self.get(SV200)) # N2 safety

                v300 = int(self.get(V300))   # steam coil normal
                sv300 = int(self.get(SV300)) # steam coil safety

            except:
                print("Warning: can't read valve states. Skip loop.")
                time.sleep(dt)
                continue

            # 2) Methanol inflow (if both normal + safety are open)
            if (v100 == 1) and (sv100 == 1):
                # mass flow = volumetric_flow * density
                d_mass = METHANOL_FLOW_RATE * DENSITY_MEOH * dt 
                self.mass_liq += d_mass 

            # 3) N2 inflow (if both normal + safety are open)
            if (v200 == 1) and (sv200 == 1):
                # Convert from reference volumetric flow to actual moles
                # Ideal gas: n = p*V / (R*T)
                # p [Pa] = Press_N2 (bar) * 1e5
                # V = N2_VOL_FLOW_STD * dt
                # => dn2 [mol]
                n_in = (Press_N2 * 1e5) * (N2_VOL_FLOW_STD * dt) / (R_GAS * T_amb) 
                self.n_n2 += n_in 

            # 4) Calculate headspace volume
            vol_liq = self.mass_liq / DENSITY_MEOH  # [m^3] 
            if vol_liq > TANK_VOLUME:
                vol_liq = TANK_VOLUME
            v_head = TANK_VOLUME - vol_liq 
            if v_head < 1e-6:
                v_head = 1e-6  # avoid division by zero

            # 5) Evaporation/condensation logic
            T_k = self.temp_liq + 273.15  # [K]
            p_meoh = (self.n_meoh_vap * R_GAS * T_k * 1e-5) / v_head  # [bar] 
            p_sat = methanol_p_sat(self.temp_liq) # [bar] 

            mass_evap = 0.0
            mass_cond = 0.0

            # Evaporation if p_meoh < p_sat
            if (p_meoh < p_sat) and (self.mass_liq > 1e-6):
                dn_evap = ALPHA * (p_sat - p_meoh) / p_sat * dt  # [mol] 
                if dn_evap < 0:
                    dn_evap = 0
                mass_evap = dn_evap * (MW_MEOH * 1e-3)  # [kg] 
                # Do not evaporate more than available in liquid
                if mass_evap > self.mass_liq:
                    mass_evap = self.mass_liq
                    dn_evap = mass_evap / (MW_MEOH * 1e-3)
                self.mass_liq -= mass_evap 
                self.n_meoh_vap += dn_evap 

            # Condensation if p_meoh > p_sat
            elif (p_meoh > p_sat) and (self.n_meoh_vap > 1e-9):
                dn_cond = ALPHA * (p_meoh - p_sat) / p_meoh * dt 
                if dn_cond < 0:
                    dn_cond = 0
                if dn_cond > self.n_meoh_vap:
                    dn_cond = self.n_meoh_vap
                mass_cond = dn_cond * (MW_MEOH * 1e-3) 
                self.mass_liq += mass_cond 
                self.n_meoh_vap -= dn_cond 

            # 6) Heat input from steam coil
            if (v300 == 1) and (sv300 == 1):
                Q_in = U_COIL * AREA_COIL * (T_STEAM - self.temp_liq)  # [J/s] 
                if Q_in < 0:
                    Q_in = 0
            else:
                Q_in = 0

            # Latent heat from evaporation
            latent_out = (mass_evap * DELTAH_VAP)/dt  # [J/s=W]
            # Net heat
            Q_net = Q_in - HEAT_LOSS - latent_out 

            # 7) Update liquid temperature
            if self.mass_liq < 1e-6:
                # If tank is basically empty, clamp
                self.temp_liq = 20
            else:
                dT = Q_net * dt / (self.mass_liq * CP_MEOH) 
                self.temp_liq += dT
                if self.temp_liq < 20:
                    self.temp_liq = 20  # do not cool below ambient

            # 8) Total pressure
            n_total = self.n_n2 + self.n_meoh_vap 
            p_total_pa = (n_total * R_GAS * (self.temp_liq + 273.15)) / v_head 
            press_bar = p_total_pa / 1e5 

            # 9) Relief valve logic
            if not self.prv400_open:
                # If closed, check if there is a need to open
                if press_bar >= PRESSURE_OPEN: 
                    self.prv400_open = True
                    self.set(PRV400, 1)
                    print(f"[PHYS] PRV400 => open (pressure {press_bar:.2f} >= {PRESSURE_OPEN} bar).")
            else:
                # If open, keep venting until below close threshold
                if press_bar <= PRESSURE_CLOSE: 
                    self.prv400_open = False
                    self.set(PRV400, 0)
                    print(f"[PHYS] PRV400 => close (pressure {press_bar:.2f} <= {PRESSURE_CLOSE} bar).")
                else:
                    # Partial bleed
                    vent_fraction = 0.05  # fraction per second
                    n_total_gas = n_total 
                    if n_total_gas > 0:
                        n_remove = vent_fraction * n_total_gas * dt 
                        if n_remove > n_total_gas:
                            n_remove = n_total_gas 
                        x_n2 = self.n_n2 / n_total_gas 
                        x_meoh = self.n_meoh_vap / n_total_gas 
                        self.n_n2 -= n_remove * x_n2 
                        self.n_meoh_vap -= n_remove * x_meoh 

                        # Recompute pressure after vent
                        n_total = self.n_n2 + self.n_meoh_vap 
                        p_total_pa = (n_total * R_GAS * (self.temp_liq + 273.15)) / v_head 
                        press_bar = p_total_pa / 1e5 

            # 10) Write new sensor states to DB
            lvl_m = self.mass_liq / DENSITY_MEOH / TANK_CROSS_SECTION  # [m] 
            self.set(LI100, lvl_m)
            self.set(PI100, press_bar)
            self.set(TI100, self.temp_liq)

            print(f"[PHYS] L={lvl_m:.3f} m, P={press_bar:.2f} bar, T={self.temp_liq:.1f} °C, prv400_open={self.prv400_open}")

            # Sleep until next iteration
            time.sleep(dt)

    def _stop(self):
        print("Physical process stopped.")


if __name__ == "__main__":
    tank = TankSystem(
        name='tank-system',
        protocol=None,
        state=STATE
    )

