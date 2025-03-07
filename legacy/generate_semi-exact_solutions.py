#/usr/bin/env python

import sys
import os

from pathlib import Path
from typing import Optional
from numpy import concatenate
from numpy import array
from numpy import arange
from numpy import linspace
from scipy.interpolate import interp1d
from scipy.integrate import odeint

import numpy as np

from tqdm import tqdm


from eos.variable_conversions import HBARC  # noqa: E402
from eos.variable_conversions import milne_pi  # noqa: E402
from eos.variable_conversions import milne_number  # noqa: E402
from eos.variable_conversions import milne_energy  # noqa: E402
from eos.variable_conversions import u_y  # noqa: E402
from eos.variable_conversions import u_x  # noqa: E402
from legacy.equations_of_motion import eom  # noqa: E402


class Config:
    def __init__(self):
        self.tau_0: Optional[float] = None
        self.tau_f: Optional[float] = None
        self.tau_step: Optional[float] = None
        self.x_min: Optional[float] = None
        self.x_max: Optional[float] = None
        self.x_step: Optional[float] = None
        self.y_min: Optional[float] = None
        self.y_max: Optional[float] = None
        self.y_step: Optional[float] = None
        self.temp_0: Optional[float] = None
        self.muB_0: Optional[float] = None
        self.muS_0: Optional[float] = None
        self.muQ_0: Optional[float] = None
        self.ceos_temp_0: Optional[float] = None
        self.ceos_muB_0: Optional[float] = None
        self.ceos_muS_0: Optional[float] = None
        self.ceos_muQ_0: Optional[float] = None
        self.pi_0: Optional[float] = None
        self.tol: Optional[float] = None
        self.output_dir: Optional[str] = None

        self.read_from_config()

    def read_from_config(self):
        with open('run.cfg', 'r') as f:
            lines = f.readlines()
            for line in lines:
                # Initialization stuff
                key, value = line.split()[:2]
                print(key, value)
                if key == 'tau_0':
                    self.tau_0 = float(value)
                elif key == 'tau_f':
                    self.tau_f = float(value)
                elif key == 'tau_step':
                    self.tau_step = float(value)
                elif key == 'x_min':
                    self.x_min = float(value)
                elif key == 'x_max':
                    self.x_max = float(value)
                elif key == 'x_step':
                    self.x_step = float(value)
                elif key == 'y_min':
                    self.y_min = float(value)
                elif key == 'y_max':
                    self.y_max = float(value)
                elif key == 'y_step':
                    self.y_step = float(value)
                elif key == 'temp_0':
                    self.temp_0 = float(value)
                elif key == 'muB_0':
                    self.muB_0 = float(value)
                    if self.muB_0 == 0:
                        self.muB_0 = 1e-20
                elif key == 'muS_0':
                    self.muS_0 = float(value)
                    if self.muS_0 == 0:
                        self.muS_0 = 1e-20
                elif key == 'muQ_0':
                    self.muQ_0 = float(value)
                    if self.muQ_0 == 0:
                        self.muQ_0 = 1e-20
                elif key == 'pi_0':
                    self.pi_0 = float(value)
                # EOS stuff
                elif key == 'ceos_temp_0':
                    self.ceos_temp_0 = float(value)
                elif key == 'ceos_muB_0':
                    self.ceos_muB_0 = float(value)
                elif key == 'ceos_muS_0':
                    self.ceos_muS_0 = float(value)
                elif key == 'ceos_muQ_0':
                    self.ceos_muQ_0 = float(value)
                # Utility
                elif key == 'tolerance':
                    self.tol = float(value)
                elif key == 'output_dir':
                    self.output_dir = value


if __name__ == "__main__":
    cfg = Config()

    # Config file gives things in the units indicated by the comments.
    # Here we have to convert to the corresponding dimensionless variables
    #   for de Sitter space
    temp_0 = cfg.temp_0 * cfg.tau_0 / HBARC
    muB_0 = cfg.muB_0 * cfg.tau_0 / HBARC
    muS_0 = cfg.muS_0 * cfg.tau_0 / HBARC
    muQ_0 = cfg.muQ_0 * cfg.tau_0 / HBARC
    y0s = array([temp_0, muB_0, muS_0, muQ_0, cfg.pi_0])

    ceos_temp_0 = cfg.ceos_temp_0
    ceos_mu_0 = array([cfg.ceos_muB_0, cfg.ceos_muS_0, cfg.ceos_muQ_0])
    consts = {'temperature_0': ceos_temp_0, 'chem_potential_0': ceos_mu_0}

    rhos_1 = linspace(-10, 0, 1000)[::-1]
    rhos_2 = linspace(0, 10, 1000)

    soln_1 = odeint(eom, y0s, rhos_1, args=(ceos_temp_0, ceos_mu_0,))
    soln_2 = odeint(eom, y0s, rhos_2, args=(ceos_temp_0, ceos_mu_0,))
    t_hat = concatenate((soln_1[:, 0][::-1], soln_2[:, 0]))
    mu_hat = [concatenate((soln_1[:, i][::-1], soln_2[:, i]))
              for i in [1, 2, 3]]
    pi_bar_hat = concatenate((soln_1[:, 4][::-1], soln_2[:, 4]))
    rhos = concatenate((rhos_1[::-1], rhos_2))

    t_interp = interp1d(rhos, t_hat)
    mu_interp = [interp1d(rhos, f) for f in mu_hat]
    pi_interp = interp1d(rhos, pi_bar_hat)

    stepx = cfg.x_step
    stepy = cfg.y_step
    stepEta = 0.1
    xmax = cfg.x_max
    ymax = cfg.y_max
    xmin = cfg.x_min
    ymin = cfg.y_min
    etamin = -0.1
    hbarc = 0.1973269804

    # Write header
    dir_name = cfg.output_dir
    dir_path = Path(dir_name).absolute()
    if not os.path.exists(dir_path):
        os.mkdir(dir_path)
    file_name = f'init_conditions.txt'
    path = os.path.join(dir_path, file_name)
    #path = Path(cfg.output_dir).absolute() / file_name
    with open(str(path), 'w') as f:
        f.write(f'#0 {stepx} {stepy} {stepEta} 0 {xmin} {ymin} {etamin}\n')

    list_of_times = [t for t in np.arange(cfg.tau_0, cfg.tau_f+cfg.tau_step, cfg.tau_step)]
    print('Writing initial conditions for times: ',list_of_times)
    for tau in tqdm(list_of_times):
        file_name = f'tau={tau:.2f}.txt'
        path = Path(cfg.output_dir).absolute() / file_name
        with open(str(path), 'w') as f:
            f.write(f'#0 {stepx} {stepy} {stepEta} 0 {xmin} {ymin} {etamin}\n')

            for x in arange(xmin, xmax, stepx):
                for y in arange(ymin, ymax, stepy):
                    pis = milne_pi(
                        tau=tau,
                        x=x,
                        y=y,
                        q=1.0,
                        ads_T=t_interp,
                        ads_mu=mu_interp,
                        ads_pi_bar_hat=pi_interp,
                        **consts,
                        tol=cfg.tol
                    )
                    f.write('{} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {} {}\n'
                            .format(
                                x,
                                y,
                                0,  # eta
                                milne_energy(
                                    tau=tau,
                                    x=x,
                                    y=y,
                                    q=1.0,
                                    ads_T=t_interp,
                                    ads_mu=mu_interp,
                                    **consts,
                                    tol=cfg.tol
                                ),
                                *milne_number(
                                    tau=tau,
                                    x=x,
                                    y=y,
                                    q=1.0,
                                    ads_T=t_interp,
                                    ads_mu=mu_interp,
                                    **consts,
                                    tol=cfg.tol
                                ),
                                u_x(tau, x, y, 1.0),
                                u_y(tau, x, y, 1.0),
                                0,  # u_eta
                                0,  # bulk
                                pis[0],  # pi^xx
                                pis[2],  # pi^xy
                                0,  # pi^xeta
                                pis[1],  # pi^yy
                                0,  # pi^yeta
                                pis[3],  # pi^etaeta
                            ))