import numpy as np
from scipy.interpolate import interp1d
from utils.constants import HBARC
from utils.analytic_functions import rho, u_x, u_y
from eom.base_eom import BaseEoM
from typing import Union, Optional, Dict
from eos.conformal_plasma_eos import ALPHA

class ConformalPlasmaEoM(BaseEoM):
    """
    Implements the equations of motion for the conformal plasma.
    Expects the state vector ys = [T, μ_B, μ_S, μ_Q, π_hat]. All three chemical potentials are allowed.
    """
    def __init__(self, eos_instance, eos_params: Dict[str, Union[float, np.ndarray]], eom_params: Dict[str, float] = {'CTAUR': 5, 'ETA_OVER_S': 0.2}):
        self.eos = eos_instance
        self.T_ast = eos_params['T_ast']
        self.mu_ast = eos_params['mu_ast']
        self.CTAUR = eom_params['CTAUR']
        self.ETA_OVER_S = eom_params['ETA_OVER_S']

    # Eq. (16) in the paper
    def tau_R(self, T, mu):
        e = self.eos.energy(T, mu)
        p = self.eos.pressure(T, mu)
        s = self.eos.entropy(T, mu)
        return self.CTAUR * self.ETA_OVER_S * s / (e + p)

    # Eq. (22a) in the paper
    def dT_drho(self, ys: np.ndarray, rho_value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        T_hat, muB_hat, muS_hat, muQ_hat, pi_hat = ys
        mu_hat = np.array([muB_hat, muS_hat, muQ_hat])
        ret_val = (1/3) * (pi_hat - 2) + pi_hat * np.sum(((self.T_ast * mu_hat) / (T_hat * self.mu_ast)) ** 2)
        ret_val *= T_hat * np.tanh(rho_value)
        return ret_val

    # Eq. (22b) in the paper
    def dmu_drho(self, ys: np.ndarray, rho_value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        T_hat, muB_hat, muS_hat, muQ_hat, pi_hat = ys
        mu_hat = np.array([muB_hat, muS_hat, muQ_hat])
        ret_val = -(2/3) * mu_hat * (1 + pi_hat) * np.tanh(rho_value)
        return ret_val

    # Eq. (20c) in the paper
    def dpi_drho(self, ys: np.ndarray, rho_value: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        T_hat, muB_hat, muS_hat, muQ_hat, pi_hat = ys
        mu_hat = np.array([muB_hat, muS_hat, muQ_hat])
        tau_R = self.tau_R(T_hat, mu_hat)
        ret_val = (4/(3 * self.CTAUR)) * np.tanh(rho_value)
        ret_val -= pi_hat / tau_R
        ret_val -= (4/3) * pi_hat ** 2 * np.tanh(rho_value)
        return ret_val

    # Computed .
    def denergy_drho(self, ys: np.ndarray, rho_val: Union[float, np.ndarray]) -> Union[float, np.ndarray]:
        """
        Compute the derivative of the energy density with respect to ρ.
        Based on the scaling relations and the derivatives of temperature and chemical potential.
        """
        # Unpack the state vector.
        T_hat, muB_hat, muS_hat, muQ_hat, _ = ys
        mu_hat = np.array([muB_hat, muS_hat, muQ_hat])
        # Compute a scaling quantity from T and chemical potentials.
        temp_value = (T_hat / self.T_ast)**2 + np.sum((mu_hat / self.mu_ast)**2)
        # Compute the derivatives dT/drho and dμ/drho:
        dT = self.dT_drho(ys, rho_val)
        dmu = self.dmu_drho(ys, rho_val)
        # Combine contributions. Here, we weight the temperature derivative and the chemical potential derivatives.
        value1 = T_hat * dT / (self.T_ast**2)
        value2 = np.sum(mu_hat * (dmu / (self.mu_ast**2)))
        return 12 * ALPHA * self.T_ast**4 * temp_value * (value1 + value2)

    # --- Milne conversion functions for conformal_plasma ---
    @staticmethod
    def milne_energy(tau: float,
                    x: Union[float, np.ndarray],
                    y: Union[float, np.ndarray],
                    q: float,
                    ads_T: interp1d,
                    ads_mu: list,
                    T_ast: float,
                    mu_ast: np.ndarray,
                    # eom_instance: ConformalPlasmaEoM,
                    eos,
                    tol: float = 1e-20) -> Union[float, np.ndarray]:
        r = np.sqrt(x**2 + y**2)
        rho_value = rho(tau, r, q)
        temp = ads_T(rho_value)
        mu = np.array([f(rho_value) for f in ads_mu])
        if isinstance(temp, np.ndarray):
            energy_val = eos.energy(temp, mu)
            return HBARC * energy_val / tau ** 4
        else:
            if temp <= tol:
                temp = tol
            energy_val = eos.energy(temp, mu)
            val = HBARC * energy_val / tau ** 4
            return tol if val < tol else val

    @staticmethod
    def milne_number(tau: float,
                    x: Union[float, np.ndarray],
                    y: Union[float, np.ndarray],
                    q: float,
                    ads_T: interp1d,
                    ads_mu: list,
                    T_ast: float,
                    mu_ast: np.ndarray,
                    # eom_instance: ConformalPlasmaEoM,
                    eos,
                    tol: float = 1e-20) -> Union[float, np.ndarray]:
        r = np.sqrt(x**2 + y**2)
        rh = rho(tau, r, q)
        temp = ads_T(rh)
        mu = np.array([f(rh) for f in ads_mu])
        if isinstance(temp, np.ndarray):
            number_val = eos.number(temp, mu)
            return number_val / tau ** 3
        else:
            if temp <= tol:
                temp = tol
            number_val = eos.number(temp, mu)
            n = number_val / tau ** 3
            n[np.where(n < tol)] = tol
            return n

    @staticmethod
    def milne_entropy(tau: float,
                    x: Union[float, np.ndarray],
                    y: Union[float, np.ndarray],
                    q: float,
                    ads_T: interp1d,
                    ads_mu: list,
                    T_ast: float,
                    mu_ast: np.ndarray,
                    # eom_instance: ConformalPlasmaEoM,
                    eos,
                    tol: float = 1e-20) -> Union[float, np.ndarray]:
        r = np.sqrt(x**2 + y**2)
        rh = rho(tau, r, q)
        temp = ads_T(rh)
        mu = np.array([f(rh) for f in ads_mu])
        if isinstance(temp, np.ndarray):
            entropy_val = eos.entropy(temp, mu)
            return entropy_val / tau**3
        else:
            if temp <= tol:
                temp = tol
            entropy_val = eos.entropy(temp, mu)
            s = entropy_val / tau**3
            return tol if s < tol else s

    @staticmethod
    def milne_pi(tau: float,
                x: Union[float, np.ndarray],
                y: Union[float, np.ndarray],
                q: float,
                ads_T: interp1d,
                ads_mu: list,
                ads_pi_bar_hat: interp1d,
                T_ast: float,
                mu_ast: np.ndarray,
                # eom_instance: ConformalPlasmaEoM,
                eos,
                tol: float = 1e-20,
                nonzero_xy: bool = False) -> list:
        r = np.sqrt(x**2 + y**2)
        rh = rho(tau, r, q)
        temp = ads_T(rh)
        mu = np.array([f(rh) for f in ads_mu])
        if not isinstance(temp, np.ndarray):
            if temp <= tol:
                temp = tol
        e_val = eos.energy(temp, mu)
        p_val = eos.pressure(temp, mu)
        pi_hat = HBARC * (e_val + p_val) * ads_pi_bar_hat(rh)
        pi_nn = pi_hat / tau**6
        pi_xx = -0.5 * (1 + u_x(tau, x, y, q)**2) * pi_hat / tau**4
        pi_yy = -0.5 * (1 + u_y(tau, x, y, q)**2) * pi_hat / tau**4
        if nonzero_xy:
            y = x
        pi_xy = -0.5 * u_x(tau, x, y, q) * u_y(tau, x, y, q) * pi_hat / tau**4
        if not isinstance(temp, np.ndarray):
            pi_nn = tol if np.fabs(pi_nn) < tol else pi_nn
            pi_xx = tol if np.fabs(pi_xx) < tol else pi_xx
            pi_yy = tol if np.fabs(pi_yy) < tol else pi_yy
            pi_xy = tol if np.fabs(pi_xy) < tol else pi_xy
        return [pi_xx, pi_yy, pi_xy, pi_nn]