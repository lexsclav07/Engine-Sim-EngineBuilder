"""Rough expected dyno curve for an Engine Builder project.

A 0D, one-cylinder cycle simulation run at fixed rpm, borrowing engine-sim's
own formulas where they matter:
  * harmonic cam lobes + the head's port-flow tables (cfm @ 28 inH2O)
  * engine-sim's flame model (laminar speed, turbulence = 0.5 x mean piston
    speed, default turbulence-to-flame-speed curve) and burn-efficiency formula
  * its intake mixture (oxygen-limited) and wall heat loss (100 W/m^2K to 90 C)
  * its hard-coded piston-ring friction (50 N breakaway, 20 N per m/s, 6% of
    side force) plus the crankshaft friction torque
Intake and exhaust are treated as steady reservoirs behind the throttle /
runners / primaries, so resonance (ram) effects are ignored. Treat the result
as a ballpark: engine-sim's own dyno (D, then I) is the real answer.
"""

import math

import mr_gen

R = 8.314
ATM = 101325.0
GAMMA = 1.4                        # engine-sim gases have 5 degrees of freedom
CV = 2.5 * R
CP = 3.5 * R
M_AIR = 0.029
CFM = 4.719474e-4                  # m^3/s per cfm
V_28 = math.sqrt(2 * 6974.6 / 1.204)   # air speed at 28 inH2O drop
V_15 = math.sqrt(2 * 5079.5 / 1.204)   # air speed at 1.5 inHg (carb rating)
T_IN = 298.15
T_WALL = 363.15


def _area_28(cfm):
    return cfm * CFM / V_28


def _area_carb(cfm):
    return cfm * CFM / V_15


def _orifice(area, p0, t0, p1):
    """Compressible mass flow (kg/s) from p0 to p1 (p0 >= p1)."""
    if area <= 0 or p0 <= p1:
        return 0.0
    pr = max(p1 / p0, (2 / (GAMMA + 1)) ** (GAMMA / (GAMMA - 1)))  # choked limit
    term = 2 * GAMMA / (GAMMA - 1) * (pr ** (2 / GAMMA) - pr ** ((GAMMA + 1) / GAMMA))
    return area * p0 / math.sqrt(R / M_AIR * t0) * math.sqrt(max(term, 0.0))


def _table(rows, scale):
    rows = sorted(rows)
    xs = [float(r[0]) for r in rows]
    ys = [float(r[1]) * scale for r in rows]

    def f(x):
        if x <= xs[0]:
            return ys[0]
        for i in range(1, len(xs)):
            if x <= xs[i]:
                t = (x - xs[i - 1]) / (xs[i] - xs[i - 1])
                return ys[i - 1] + t * (ys[i] - ys[i - 1])
        return ys[-1]
    return f


def _lobe_fn(dur50, gamma, lift_mm):
    lobe = mr_gen._lobe(dur50, gamma, lift_mm)
    if lobe is None:
        return lambda d: 0.0
    k, lift = lobe

    def f(delta_crank_deg):
        x = math.radians(delta_crank_deg) / 2.0          # cam radians
        if abs(k * x) >= math.pi:
            return 0.0
        return lift * (0.5 + 0.5 * math.cos(k * x)) ** gamma
    return f


def _wrap(d):
    d = (d + 360.0) % 720.0 - 360.0
    return d


def _advance(timing, rpm):
    pts = sorted(timing)
    if rpm <= pts[0][0]:
        return pts[0][1]
    for i in range(1, len(pts)):
        if rpm <= pts[i][0]:
            t = (rpm - pts[i - 1][0]) / (pts[i][0] - pts[i - 1][0])
            return pts[i - 1][1] + t * (pts[i][1] - pts[i - 1][1])
    return pts[-1][1]


def _turb_ratio(x, k=1.0):
    """engine-sim's default fuel turbulence_to_flame_speed_ratio curve (x Flame speed multiplier)."""
    x = min(x, 45.0)
    return k * (3.0 + 0.9 * x if x < 5.0 else 1.5 * x)


class _Engine:
    def __init__(self, p):
        g, h, c, f, i, x = p["geometry"], p["head"], p["cam"], p["fuel"], p["intake"], p["exhaust"]
        self.n_cyl = len(p["cylinders"])
        self.bore = g["bore_mm"] / 1000
        self.r = g["stroke_mm"] / 2000
        self.rod = g["rod_length_mm"] / 1000
        self.area = math.pi / 4 * self.bore ** 2
        self.vc = mr_gen.clearance_cc(p) * 1e-6
        self.m_recip = (g["piston_mass_g"] + 0.5 * g["rod_mass_g"]) / 1000
        self.intake_flow = _table(h["intake_flow"], h["flow_scale"])
        self.exhaust_flow = _table(h["exhaust_flow"], h["flow_scale"])
        self.int_lift = _lobe_fn(c["intake_duration_deg"], c["intake_gamma"], c["intake_lift_mm"])
        self.exh_lift = _lobe_fn(c["exhaust_duration_deg"], c["exhaust_gamma"], c["exhaust_lift_mm"])
        self.int_center = 360.0 + c["intake_center_deg"] - c["advance_deg"]
        self.exh_center = 360.0 - c["exhaust_center_deg"] - c["advance_deg"]
        self.a_throttle = _area_carb(i["intake_flow_cfm"])
        self.a_runner = _area_carb(i["runner_flow_cfm"])
        self.a_primary = _area_carb(x["primary_flow_cfm"])
        n_exh = len(p["layout"]["banks"]) if x["mode"] == "per_bank" else 1
        self.a_outlet = _area_carb(x["outlet_flow_cfm"]) * n_exh
        self.timing = p["ignition"]["timing"]
        self.crank_friction = p["crank"]["friction_torque_nm"]
        # intake mixture (engine-sim Intake::process): air molecules per fuel molecule
        fuel_afr = f["molecular_afr"]
        ideal = 0.8 * fuel_afr * i["lambda"] * 4
        self.x_fuel = 1 / (1 + ideal)
        self.x_o2 = ideal / (1 + ideal) * 0.25
        self.equiv = (self.x_o2 / self.x_fuel) / fuel_afr
        burnable = min(self.x_fuel, self.x_o2 / fuel_afr)
        self.energy_per_mol = burnable * f["molecular_mass_g"] / 1000 * f["energy_density_kj_g"] * 1e6
        self.fuel_afr = fuel_afr
        self.flame_k = float(f.get("flame_speed_multiplier", 1.0))
        self.f = f

    def volume(self, theta):
        t = math.radians(theta)
        s = self.r * math.sin(t)
        x = self.r * (1 - math.cos(t)) + self.rod - math.sqrt(self.rod ** 2 - s * s)
        return self.vc + self.area * x, x

    def cycle_torque(self, rpm, p_man, p_exh, cycles=3, step=1.0):
        """Run cycles at fixed rpm; return (indicated+friction torque per cylinder, mean intake kg/s)."""
        w = rpm * 2 * math.pi / 60
        dt = math.radians(step) / w
        v_mean = 4 * self.r * rpm / 60
        turbulence = 0.5 * v_mean
        adv = _advance(self.timing, rpm)
        ign = 720.0 - adv
        V, _ = self.volume(0.0)
        T = 900.0
        n = p_exh * V / (R * T)
        resid = 1.0                                   # fraction of burned gas in the cylinder
        work = fric = m_in = 0.0
        lit = None
        prev_x = None
        prev_v = 0.0
        for cyc in range(cycles):
            record = cyc == cycles - 1
            theta = 0.0
            while theta < 720.0:
                V, x = self.volume(theta)
                P = n * R * T / V
                # --- gas exchange through the valves ---
                li = self.int_lift(_wrap(theta - self.int_center))
                le = self.exh_lift(_wrap(theta - self.exh_center))
                if li > 0.0:
                    av = _area_28(self.intake_flow(li))
                    a = av * self.a_runner / math.sqrt(av ** 2 + self.a_runner ** 2)
                    if p_man > P:
                        dn = _orifice(a, p_man, T_IN, P) * dt / M_AIR
                        dn = min(dn, max(0.0, p_man * V / (R * T) - n) + 1e-12)
                        T = (n * CV * T + dn * CP * T_IN) / ((n + dn) * CV)
                        resid = resid * n / (n + dn)
                        n += dn
                        if record:
                            m_in += dn * M_AIR
                    else:
                        dn = _orifice(a, P, T, p_man) * dt / M_AIR
                        dn = min(dn, max(0.0, n - p_man * V / (R * T)))
                        n -= dn
                        if record:
                            m_in -= dn * M_AIR
                if le > 0.0:
                    av = _area_28(self.exhaust_flow(le))
                    a = av * self.a_primary / math.sqrt(av ** 2 + self.a_primary ** 2)
                    P = n * R * T / V
                    if P > p_exh:
                        dn = _orifice(a, P, T, p_exh) * dt / M_AIR
                        dn = min(dn, max(0.0, n - p_exh * V / (R * T)))
                        n -= dn
                    else:
                        t_ex = 800.0
                        dn = _orifice(a, p_exh, t_ex, P) * dt / M_AIR
                        dn = min(dn, max(0.0, p_exh * V / (R * T) - n) + 1e-12)
                        T = (n * CV * T + dn * CP * t_ex) / ((n + dn) * CV)
                        resid = (resid * n + dn) / (n + dn)
                        n += dn
                # --- ignition + engine-sim style flame ---
                if lit is None and abs(theta - ign) < step / 2 + 1e-9 and 0.5 <= self.equiv <= 1.9:
                    P = n * R * T / V
                    er = self.equiv
                    s_l0 = 0.305 - 0.549 * (er - 1.21) ** 2
                    alpha = 2.4 - 0.271 * er ** 3.51
                    beta = -0.357 + 0.14 * er ** 2.77
                    s_l = max(0.05, s_l0) * (T / 298.0) ** alpha * (P / ATM) ** beta
                    fspeed = _turb_ratio(turbulence / s_l, self.flame_k) * s_l
                    p_o2 = (1 - resid) * self.x_o2
                    ideal_inert = max(p_o2 / 0.7, 1e-9)
                    dilution = (1 - p_o2 - (1 - resid) * self.x_fuel) / ideal_inert - 1
                    f = self.f
                    mix = 1 - (min(1, turbulence / f["max_turbulence_effect"])
                               * max(0.0, min(1.0, 1 - dilution / f["max_dilution_effect"])))
                    rand = f["low_efficiency_attenuation"] * (1 - 0.5 * f["burning_efficiency_randomness"])
                    eff = (mix * rand + (1 - mix)) * f["max_burning_efficiency"]
                    lit = {"tx": 0.0, "ty": 0.0, "v_last": V, "speed": fspeed,
                           "energy": n * (1 - resid) * self.energy_per_mol * eff, "frac": 0.0}
                if lit is not None:
                    ty_last = lit["ty"] * V / lit["v_last"]
                    tx = min(lit["tx"] + dt * lit["speed"], self.bore / 2)
                    ty = min(ty_last + dt * lit["speed"], V / self.area)
                    burned = tx * tx * math.pi * ty
                    prev_burned = lit["tx"] ** 2 * math.pi * ty_last
                    dfrac = max(0.0, burned - prev_burned) / V
                    dfrac = min(dfrac, 1.0 - lit["frac"])
                    T += lit["energy"] * dfrac / (n * CV)
                    lit["frac"] += dfrac
                    lit.update(tx=tx, ty=ty, v_last=V)
                    if dfrac <= 0.0 or lit["frac"] >= 1.0 or li > 0.0:
                        lit = None
                        resid = 1.0 if self.equiv >= 0.5 else resid
                # --- wall heat loss (engine-sim: 100 W/m^2K to 90 C) ---
                height = V / self.area
                wall = height * math.pi * self.bore + 2 * self.area
                T += (T_WALL - T) * wall * 100 * dt / (n * CV)
                # --- piston motion: work + ring friction ---
                theta_next = theta + step
                V2, x2 = self.volume(theta_next)
                T *= (V / V2) ** (GAMMA - 1)                      # adiabatic volume change
                P_mid = n * R * T / ((V + V2) / 2)
                if record:
                    work += P_mid * (V2 - V)
                    vel = (x2 - x) / dt
                    acc = (vel - prev_v) / dt if prev_x is not None else 0.0
                    t = math.radians(theta + step / 2)
                    phi = math.asin(self.r * math.sin(t) / self.rod)
                    f_axial = (P_mid - ATM) * self.area - self.m_recip * acc
                    side = abs(f_axial * math.tan(phi))
                    v = abs(vel)
                    f_coul = 0.06 * side
                    v_st, v_coul = 0.1 * math.sqrt(2), 0.01
                    f0 = math.sqrt(2) * math.e * (50.0 - f_coul)
                    f1 = v / v_st
                    ring = f0 * math.exp(-f1 * f1) * f1 + f_coul * math.tanh(v / v_coul) + 20.0 * v
                    fric += ring * v * dt
                    prev_v, prev_x = vel, x
                theta = theta_next
        cycle_time = 2 * 60 / rpm
        torque = (work - fric) / (4 * math.pi)
        return torque, m_in / cycle_time


def estimate(project, points=None):
    """Return list of (rpm, torque_nm, power_w) across the dyno range."""
    eng = _Engine(project)
    e = project["engine"]
    lo = max(800.0, e["dyno_min_rpm"])
    hi = max(lo + 500, e["redline_rpm"])
    if points is None:
        n = 18
        points = [lo + (hi - lo) * k / (n - 1) for k in range(n)]
    out = []
    for rpm in points:
        p_man, p_exh = ATM, ATM
        for _ in range(3):
            tq, m_cyl = eng.cycle_torque(rpm, p_man, p_exh, cycles=2)
            m_tot = max(m_cyl, 0.0) * eng.n_cyl
            # steady pressure drops across the shared throttle and exhaust outlet
            p_man = ATM - min(0.6 * ATM, (m_tot / eng.a_throttle) ** 2 / (2 * 1.18))
            rho_ex = ATM * M_AIR / (R * 800.0)
            p_exh = ATM + min(1.0 * ATM, (m_tot / eng.a_outlet) ** 2 / (2 * rho_ex))
        torque = tq * eng.n_cyl - eng.crank_friction
        out.append((rpm, torque, torque * rpm * 2 * math.pi / 60))
    return out


def peaks(curve):
    p = max(curve, key=lambda r: r[2])
    t = max(curve, key=lambda r: r[1])
    return {"power_w": p[2], "power_rpm": p[0], "torque_nm": t[1], "torque_rpm": t[0]}
