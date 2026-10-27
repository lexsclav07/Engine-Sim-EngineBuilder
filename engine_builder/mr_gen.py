"""Engine project model + .mr script generator for engine-sim.

The project is a plain dict (saved as JSON). `generate_mr(project)` turns it
into a self-contained engine-sim script that only depends on the stock
`es/` library.

Phasing conventions (taken from the stock 2JZ / GM LS scripts):
  * bank angle 0 = vertical, the crank turns so a journal at angle `a`
    reaches TDC of bank `b` after (tdc - b - 90 + a) crank degrees
  * firing angles F live in a 0..720 deg cycle, cylinder fired first = 0
  * exhaust lobe centerline = 360 - exhaust_center + F
  * intake lobe centerline  = 360 + intake_center + F
  * ignition wire angle     = F
"""

import copy
import datetime
import math
import re

IMPULSE_RESPONSES = [
    "default_0", "real_engine_0", "real_engine_1", "real_engine_2",
    "sharp_0", "mild_exhaust_0", "mild_exhaust_0_reverb",
    "minimal_muffling_01", "minimal_muffling_02", "minimal_muffling_03",
]

FUEL_PRESETS = {
    "Gasoline (engine-sim default)": {
        "name": "Gasoline", "molecular_mass_g": 100.0, "energy_density_kj_g": 48.1,
        "density_kg_l": 0.755, "molecular_afr": 12.5,
    },
    "Methanol / glow fuel (experimental)": {
        "name": "Methanol", "molecular_mass_g": 32.04, "energy_density_kj_g": 19.9,
        "density_kg_l": 0.792, "molecular_afr": 1.5,
    },
    "Ethanol / E100 (experimental)": {
        "name": "Ethanol", "molecular_mass_g": 46.07, "energy_density_kj_g": 26.8,
        "density_kg_l": 0.789, "molecular_afr": 3.0,
    },
}


def baby_bee_defaults():
    """Cox Baby Bee .049 character, scaled up so engine-sim can run it.

    The real engine (10.3 mm bore, 0.8 cc) can't run in engine-sim: piston-ring
    friction is hard-coded in newtons (50 N breakaway + 20 N per m/s) and the
    constraint solver's error tolerance is a fixed 1e-4 N*s, both sized for car
    parts. This keeps the Baby Bee's bore/stroke (1.08) and rod/stroke (1.885)
    ratios, a light "prop" flywheel, wide overlapping cam timing and an open
    exhaust, at roughly the size of one Hayabusa cylinder (a stock engine-sim
    engine that revs to 11,000 rpm).
    """
    return {
        "engine": {
            "name": "Baby Bee (engine-sim scale)",
            "redline_rpm": 10000.0,
            "starter_torque_lbft": 40.0,
            "starter_speed_rpm": 600.0,
            "dyno_min_rpm": 1500.0,
            "dyno_max_rpm": 10000.0,
            "dyno_hold_step_rpm": 250.0,
            "throttle_gamma": 2.0,
            "simulation_frequency": 20000,
            "max_sle_solver_steps": 128,
            "fluid_simulation_steps": 8,
            "convolution": 1.0,
            "hf_gain": 0.01,
            "jitter": 0.5,
            "noise": 1.0,
            "heat_transfer_coefficient": 100.0,
            "block_temperature_c": 90.0,
        },
        "fuel": {
            "name": "Gasoline",
            "molecular_mass_g": 100.0,
            "energy_density_kj_g": 48.1,
            "density_kg_l": 0.755,
            "molecular_afr": 12.5,
            "max_burning_efficiency": 0.95,
            "burning_efficiency_randomness": 0.25,
            "low_efficiency_attenuation": 0.6,
            "max_turbulence_effect": 5.5,
            "max_dilution_effect": 1000.0,
            "flame_speed_multiplier": 1.0,
        },
        "geometry": {
            "bore_mm": 76.0,              # 10.31 mm x 7.37
            "stroke_mm": 70.4,            # keeps the Baby Bee's 1.08 bore/stroke
            "rod_length_mm": 132.7,       # keeps its 1.885 rod/stroke
            "rod_mass_g": 300.0,
            "compression_height_mm": 26.0,
            "deck_clearance_mm": 0.0,
            "piston_mass_g": 250.0,
            "wrist_pin_position_mm": 0.0,
            "blowby": 0.002,
        },
        "crank": {
            "crank_mass_g": 4000.0,
            "flywheel_mass_g": 3000.0,    # light, like the prop on the real one
            "flywheel_radius_mm": 130.0,
            "extra_moment": 0.002,        # cams, gears, etc [kg m^2]
            "friction_torque_nm": 2.0,
            "manual_moment": False,
            "moment_of_inertia": 0.03,
        },
        "layout": {
            "banks": [
                {"angle_deg": 0.0, "cylinders": 1, "flip": "auto",
                 "position_x_mm": 0.0, "position_y_mm": 0.0, "display_depth": 0.5},
            ],
            "numbering": "sequential",    # or "alternating"
            "firing_order": "1",
            "crank_mode": "auto_even",    # or "manual"
        },
        # one entry per cylinder, in cylinder-number order
        "cylinders": [
            {"journal_angle_deg": 0.0, "primary_length_in": 0.0,
             "sound_attenuation": 1.0, "blowby_scale": 1.0},
        ],
        "head": {
            "chamber_volume_cc": 33.6,    # 10.5:1
            "intake_runner_volume_cc": 110.0,
            "intake_runner_area_cm2": 14.0,
            "exhaust_runner_volume_cc": 40.0,
            "exhaust_runner_area_cm2": 18.0,
            "lift_step_thou": 50.0,
            "flow_scale": 1.0,
            "intake_flow": [[0, 0.0], [50, 35.0], [100, 70.0], [150, 110.0], [200, 141.0],
                            [250, 167.0], [300, 185.0], [350, 198.0], [400, 202.0],
                            [450, 211.0]],
            "exhaust_flow": [[0, 0.0], [50, 29.0], [100, 68.0], [150, 97.0], [200, 121.0],
                             [250, 135.0], [300, 145.0], [350, 155.0], [400, 160.0],
                             [450, 165.0]],
        },
        "cam": {
            "intake_duration_deg": 232.0,
            "intake_lift_mm": 8.5,
            "intake_gamma": 1.15,
            "exhaust_duration_deg": 236.0,
            "exhaust_lift_mm": 8.0,
            "exhaust_gamma": 1.15,
            "intake_center_deg": 104.0,
            "exhaust_center_deg": 106.0,
            "advance_deg": 0.0,
            "base_radius_mm": 16.0,
            "steps": 100,
        },
        "intake": {
            "plenum_volume_cc": 1500.0,
            "plenum_area_cm2": 20.0,
            "intake_flow_cfm": 300.0,
            "runner_flow_cfm": 250.0,
            "runner_length_in": 8.0,
            "idle_flow_cfm": 0.0,
            "idle_throttle_plate_position": 0.996,
            "throttle_gamma": 2.0,
            "velocity_decay": 0.5,
            "lambda": 1.0,
        },
        "exhaust": {
            "mode": "shared",             # or "per_bank"
            "outlet_flow_cfm": 800.0,
            "primary_tube_length_in": 8.0,
            "primary_flow_cfm": 400.0,
            "length_in": 16.0,            # short open pipe
            "collector_area_cm2": 20.0,
            "velocity_decay": 1.0,
            "audio_volume": 0.015,        # loudness ~ audio_volume / exhaust_length^2
            "impulse_response": "minimal_muffling_01",
            "backflow_atmospheric_mixing": 0.0,
        },
        "ignition": {
            "rev_limit_rpm": 10500.0,
            "limiter_duration_s": 0.1,
            "timing": [[0, 12.0], [1000, 12.0], [2000, 20.0], [3000, 28.0], [4000, 34.0],
                       [6000, 36.0], [8000, 36.0], [10000, 36.0], [12000, 36.0]],
        },
        "vehicle": {                      # a go-kart
            "mass_kg": 120.0,
            "drag_coefficient": 0.8,
            "cross_sectional_area_m2": 0.6,
            "diff_ratio": 5.5,
            "tire_radius_in": 5.5,
            "rolling_resistance_n": 80.0,
            "stiffness_lbft_deg": 50.0,
            "damping": 1.0,
            "max_flex_deg": 30.0,
            "limit_flex": True,
            "simulate_flex": False,
            "max_brake_force_n": 2000.0,
            "coeff_static_friction": 0.9,
            "coeff_dynamic_friction": 0.8,
            "wheel_base_in": 42.0,
            "track_in": 40.0,
            "max_brake_torque_lbft": 300.0,
            "center_of_mass_in": 8.0,
            "weight_transfer_bias": 1.0,
            "vehicle_asset_file": "",
        },
        "transmission": {
            "max_clutch_torque_lbft": 80.0,
            "max_clutch_flex_deg": 5.0,
            "limit_clutch_flex": True,
            "clutch_stiffness_lbft_deg": 50.0,
            "clutch_damping": 1.0,
            "simulate_flex": False,
            "gears": [2.8, 1.9, 1.45, 1.17, 1.0],
        },
    }


# Layout presets only touch the "layout" section (+ cylinder table size).
# Bank entries: (angle, cylinders)
LAYOUT_PRESETS = {
    "Single": ([(0, 1)], "sequential", "1"),
    "2-stroke sound trick (360 deg twin)": ([(0, 2)], "sequential", "1 2"),
    "Parallel twin 270": ([(0, 2)], "sequential", "1 2"),
    "V-twin 45": ([(-22.5, 1), (22.5, 1)], "sequential", "1 2"),
    "V-twin 90": ([(-45, 1), (45, 1)], "sequential", "1 2"),
    "Inline 3": ([(0, 3)], "sequential", "1 3 2"),
    "Inline 4": ([(0, 4)], "sequential", "1 3 4 2"),
    "Inline 5": ([(0, 5)], "sequential", "1 2 4 5 3"),
    "Inline 6": ([(0, 6)], "sequential", "1 5 3 6 2 4"),
    "Flat 4 (boxer)": ([(-90, 2), (90, 2)], "alternating", "1 3 2 4"),
    "Flat 6 (boxer)": ([(-90, 3), (90, 3)], "alternating", "1 6 2 4 3 5"),
    "V6 60": ([(-30, 3), (30, 3)], "alternating", "1 2 3 4 5 6"),
    "V6 90 even fire": ([(-45, 3), (45, 3)], "alternating", "1 6 5 4 3 2"),
    "V8 cross-plane": ([(-45, 4), (45, 4)], "alternating", "1 8 7 2 6 5 4 3"),
    "V8 flat-plane": ([(-45, 4), (45, 4)], "sequential", "1 5 3 7 4 8 2 6"),
    "V10 72": ([(-36, 5), (36, 5)], "alternating", "1 6 5 10 2 7 3 8 4 9"),
    "V12 60": ([(-30, 6), (30, 6)], "alternating", "1 12 5 8 3 10 6 7 2 11 4 9"),
    "W/triple bank 3x2 (demo)": ([(-60, 2), (0, 2), (60, 2)], "alternating", "1 2 3 4 5 6"),
}

# Some layouts are not even-fire; they get manual journals.
_PRESET_MANUAL_JOURNALS = {
    "Parallel twin 270": [0.0, 270.0],
    "V-twin 45": [0.0, 0.0],   # shared pin, Harley style 315/405
    "V-twin 90": [0.0, 0.0],   # shared pin, Ducati style 270/450
}


def default_cylinder():
    return {"journal_angle_deg": 0.0, "primary_length_in": 0.0,
            "sound_attenuation": 1.0, "blowby_scale": 1.0}


def apply_layout_preset(project, preset_name):
    banks, numbering, firing = LAYOUT_PRESETS[preset_name]
    old_banks = project["layout"]["banks"]
    template = old_banks[0] if old_banks else {}
    project["layout"]["banks"] = [
        {"angle_deg": float(a), "cylinders": int(n), "flip": "auto",
         "position_x_mm": template.get("position_x_mm", 0.0),
         "position_y_mm": template.get("position_y_mm", 0.0),
         "display_depth": template.get("display_depth", 0.5)}
        for a, n in banks
    ]
    project["layout"]["numbering"] = numbering
    project["layout"]["firing_order"] = firing
    n = sum(b["cylinders"] for b in project["layout"]["banks"])
    resize_cylinders(project, n)
    manual = _PRESET_MANUAL_JOURNALS.get(preset_name)
    if manual:
        project["layout"]["crank_mode"] = "manual"
        for c, a in zip(project["cylinders"], manual):
            c["journal_angle_deg"] = a
    else:
        project["layout"]["crank_mode"] = "auto_even"


def resize_cylinders(project, n):
    cyls = project.setdefault("cylinders", [])
    while len(cyls) < n:
        cyls.append(copy.deepcopy(cyls[-1]) if cyls else default_cylinder())
    del cyls[n:]


def merge_defaults(project):
    """Fill in keys missing from older/hand-edited project files."""
    base = baby_bee_defaults()
    for section, values in base.items():
        if section not in project:
            project[section] = copy.deepcopy(values)
        elif isinstance(values, dict):
            for k, v in values.items():
                project[section].setdefault(k, copy.deepcopy(v))
    for b in project["layout"]["banks"]:
        for k, v in base["layout"]["banks"][0].items():
            b.setdefault(k, v)
    for c in project["cylinders"]:
        for k, v in default_cylinder().items():
            c.setdefault(k, v)
    resize_cylinders(project, sum(int(b["cylinders"]) for b in project["layout"]["banks"]))
    return project


# --------------------------------------------------------------------------
# Derived values
# --------------------------------------------------------------------------

class LayoutError(Exception):
    pass


def cylinder_list(project):
    """Return [(cyl_number, bank_index, index_in_bank)] ordered by bank then index."""
    banks = project["layout"]["banks"]
    counts = [int(b["cylinders"]) for b in banks]
    if not counts or any(c < 1 for c in counts):
        raise LayoutError("Every bank needs at least 1 cylinder.")
    out = []
    alternating = project["layout"]["numbering"] == "alternating"
    if alternating and len(set(counts)) != 1:
        raise LayoutError("Alternating numbering needs the same cylinder count in every bank.")
    nb = len(banks)
    num = 1
    for bi, cnt in enumerate(counts):
        for k in range(cnt):
            n = (k * nb + bi + 1) if alternating else num
            out.append((n, bi, k))
            num += 1
    return out


def parse_firing_order(text, n):
    parts = [p for p in re.split(r"[\s,\-]+", text.strip()) if p]
    try:
        order = [int(p) for p in parts]
    except ValueError:
        raise LayoutError("Firing order must be cylinder numbers, e.g. 1 3 4 2")
    if sorted(order) != list(range(1, n + 1)):
        raise LayoutError(f"Firing order must use each cylinder 1..{n} exactly once.")
    return order


def compute_phasing(project):
    """Work out tdc, journal angles and firing angles for every cylinder.

    Returns dict with:
      tdc_deg, journals [angles], cyl: {num: {bank, idx, journal, journal_angle, fire}}
    """
    cyls = cylinder_list(project)
    n = len(cyls)
    banks = project["layout"]["banks"]
    order = parse_firing_order(project["layout"]["firing_order"], n)
    bank_of = {num: bi for num, bi, _ in cyls}
    phi = {num: float(banks[bi]["angle_deg"]) for num, bi, _ in cyls}
    first = order[0]
    manual = project["layout"]["crank_mode"] == "manual"
    table = project["cylinders"]

    fire = {}
    alpha = {}
    if not manual:
        tdc = 90.0 + phi[first]
        for k, c in enumerate(order):
            fire[c] = k * 720.0 / n
            alpha[c] = (fire[c] - tdc + phi[c] + 90.0) % 360.0
    else:
        for num, _, _ in cyls:
            alpha[num] = float(table[num - 1]["journal_angle_deg"]) % 360.0
        tdc = 90.0 + phi[first] - alpha[first]
        prev = None
        for c in order:
            t = (tdc - phi[c] - 90.0 + alpha[c]) % 360.0
            if prev is None:
                f = t
            else:
                f = t
                while f <= prev + 1e-6:
                    f += 360.0
            if f >= 720.0 - 1e-6:
                raise LayoutError(
                    "That firing order isn't possible with these journal angles "
                    f"(cylinder {c} would fire at {f:.1f} deg, past the 720 deg cycle).")
            fire[c] = f
            prev = f

    journals = []
    info = {}
    for num, bi, idx in cyls:
        a = round(alpha[num], 4) % 360.0
        ji = None
        for i, ja in enumerate(journals):
            if abs(ja - a) < 1e-3:
                ji = i
                break
        if ji is None:
            journals.append(a)
            ji = len(journals) - 1
        info[num] = {"bank": bi, "idx": idx, "journal": ji,
                     "journal_angle": a, "fire": fire[num] % 720.0}
    return {"tdc_deg": tdc % 360.0, "journals": journals, "cyl": info,
            "order": order, "bank_of": bank_of}


def crank_moment(project):
    cr = project["crank"]
    if cr.get("manual_moment"):
        return float(cr["moment_of_inertia"])
    g = project["geometry"]
    throw = g["stroke_mm"] / 2000.0
    crank = 0.5 * (cr["crank_mass_g"] / 1000.0) * throw ** 2
    fly = 0.5 * (cr["flywheel_mass_g"] / 1000.0) * (cr["flywheel_radius_mm"] / 1000.0) ** 2
    return crank + fly + float(cr["extra_moment"])


def displacement_cc(project):
    g = project["geometry"]
    n = sum(int(b["cylinders"]) for b in project["layout"]["banks"])
    per = math.pi / 4.0 * (g["bore_mm"] / 10.0) ** 2 * (g["stroke_mm"] / 10.0)
    return per, per * n


def clearance_cc(project):
    g = project["geometry"]
    deck = math.pi / 4.0 * (g["bore_mm"] / 10.0) ** 2 * (g["deck_clearance_mm"] / 10.0)
    return project["head"]["chamber_volume_cc"] + deck


def compression_ratio(project):
    per, _ = displacement_cc(project)
    clr = clearance_cc(project)
    if clr <= 0:
        return float("inf")
    return (per + clr) / clr


def chamber_for_cr(project, cr):
    per, _ = displacement_cc(project)
    g = project["geometry"]
    deck = math.pi / 4.0 * (g["bore_mm"] / 10.0) ** 2 * (g["deck_clearance_mm"] / 10.0)
    return per / (cr - 1.0) - deck


# --------------------------------------------------------------------------
# engine-sim viability checks
#
# These numbers are hard-coded in engine-sim's C++ and don't scale with the
# engine, which is why very small engines misbehave:
#   * CombustionChamber::FrictionModelParams: ring friction 50 N breakaway,
#     20 N per m/s viscous, 6% of side force
#   * GaussSeidelSleSolver: stops when impulses change < 10% of max(1e-3, |x|),
#     i.e. a fixed 1e-4 N*s tolerance for light parts
#   * GenerateHarmonicCamLobeNode: lift = L * (0.5 + 0.5 cos(k x))^gamma
# --------------------------------------------------------------------------

ES_RING_BREAKAWAY_N = 50.0
ES_RING_VISCOUS_N_PER_MPS = 20.0
THOU_MM = 0.0254
STOCK_SOUND_FACTOR = (0.004, 0.15)


def _lobe(dur50_deg, gamma, lift_mm):
    """engine-sim's harmonic lobe; returns (k per cam radian, lift in thou) or None."""
    lift = lift_mm / THOU_MM
    if lift <= 50.0 or gamma <= 0 or dur50_deg <= 0:
        return None
    s = (100.0 / lift) ** (1.0 / gamma) - 1.0
    return math.acos(s) / (math.radians(dur50_deg) / 4.0), lift


def _half_open_deg(lobe, gamma, threshold_thou):
    """Crank degrees from lobe centerline to where lift falls below threshold."""
    k, lift = lobe
    if threshold_thou >= lift:
        return 0.0
    c = 2.0 * (threshold_thou / lift) ** (1.0 / gamma) - 1.0
    return math.degrees(2.0 * math.acos(c) / k)


def piston_travel_mm(project, crank_deg_from_tdc):
    g = project["geometry"]
    r = g["stroke_mm"] / 2.0
    rod = g["rod_length_mm"]
    t = math.radians(crank_deg_from_tdc)
    return r * (1 - math.cos(t)) + rod - math.sqrt(max(rod * rod - (r * math.sin(t)) ** 2, 0.0))


def cam_report(project):
    C = project["cam"]
    li = _lobe(C["intake_duration_deg"], C["intake_gamma"], C["intake_lift_mm"])
    le = _lobe(C["exhaust_duration_deg"], C["exhaust_gamma"], C["exhaust_lift_mm"])
    if li is None or le is None:
        return {"ok": False}
    ci, ce, adv = C["intake_center_deg"], C["exhaust_center_deg"], C["advance_deg"]
    out = {"ok": True, "lift_thou": (li[1], le[1])}
    # "seat" = lift under 0.004 in, where the flow tables give ~no flow
    for name, th in (("seat", 4.0), ("050", 50.0)):
        hi = _half_open_deg(li, C["intake_gamma"], th)
        he = _half_open_deg(le, C["exhaust_gamma"], th)
        out[name] = {"ivo_btdc": hi - ci + adv, "ivc_abdc": ci - adv + hi - 180.0,
                     "evo_bbdc": ce + adv + he - 180.0, "evc_atdc": he - ce - adv,
                     "int_dur": 2 * hi, "exh_dur": 2 * he}
    s = out["seat"]
    out["closed_deg"] = 720.0 - ci - ce - (s["int_dur"] + s["exh_dur"]) / 2.0
    ivc_btdc = 360.0 - (ci - adv + s["int_dur"] / 2.0)
    clr = clearance_cc(project)
    if ivc_btdc <= 0 or clr <= 0:
        out["eff_cr"] = 1.0
    else:
        area_cm2 = math.pi / 4.0 * (project["geometry"]["bore_mm"] / 10.0) ** 2
        v = clr + area_cm2 * piston_travel_mm(project, min(ivc_btdc, 180.0)) / 10.0
        out["eff_cr"] = v / clr
    return out


def friction_report(project):
    g = project["geometry"]
    rpm = project["engine"]["redline_rpm"]
    area = math.pi / 4.0 * (g["bore_mm"] / 1000.0) ** 2
    stroke = g["stroke_mm"] / 1000.0
    v_mean = 2.0 * stroke * rpm / 60.0
    p_visc = ES_RING_VISCOUS_N_PER_MPS * (math.pi ** 2 / 8.0) * v_mean ** 2
    p_10bar = 1e6 * area * stroke * rpm / 120.0
    return {"v_mean": v_mean,
            "breakaway_bar": ES_RING_BREAKAWAY_N / (area * 1e5) if area > 0 else float("inf"),
            "viscous_frac": p_visc / p_10bar if p_10bar > 0 else float("inf")}


def sound_factor(project):
    """What engine-sim scales exhaust pressure by before its leveler (per cylinder)."""
    X = project["exhaust"]
    n = max(1, len(project["cylinders"]))
    worst = 0.0
    for c in project["cylinders"]:
        length = (c["primary_length_in"] + X["length_in"]) * 0.0254
        if length <= 0:
            return float("inf")
        worst = max(worst, X["audio_volume"] * c["sound_attenuation"] / n / length ** 2)
    return worst


def suggested_flame_multiplier(project):
    """engine-sim's flame speed scales with mean piston speed while the flame has to cross
    half the bore, so oversquare engines burn too slowly at its default. Real ones make up
    for it with chamber shape/tumble, which engine-sim doesn't model."""
    g = project["geometry"]
    ratio = g["bore_mm"] / g["stroke_mm"] if g["stroke_mm"] > 0 else 1.0
    return round(max(1.0, min(4.0, 1.0 + 1.6 * (ratio - 0.95))), 2)


def check_engine(project):
    """Return (problems, warnings): problems mean it very likely won't run."""
    problems, warnings = [], []
    g, E, C, H = project["geometry"], project["engine"], project["cam"], project["head"]

    try:
        compute_phasing(project)
    except LayoutError as e:
        problems.append(f"Layout: {e}")

    fr = friction_report(project)
    msg = (f"Piston-ring friction takes ~{fr['viscous_frac'] * 100:.0f}% of the power at redline. "
           f"engine-sim uses a fixed 50 N + 20 N per m/s per piston no matter the size; at "
           f"{g['bore_mm']:g} mm bore the 50 N alone is {fr['breakaway_bar']:.2f} bar of cylinder pressure.")
    if fr["viscous_frac"] > 1.0 or fr["breakaway_bar"] > 1.5:
        problems.append(msg + " It probably won't run: use a bigger bore (60+ mm) or a lower redline.")
    elif fr["viscous_frac"] > 0.6 or fr["breakaway_bar"] > 0.5:
        warnings.append(msg + " Expect it to run out of breath before redline.")

    for label, grams in (("Piston", g["piston_mass_g"]), ("Con-rod", g["rod_mass_g"])):
        text = (f"{label} mass {grams:g} g: engine-sim's solver has a fixed error tolerance "
                "(0.0001 N*s), so light parts jitter or rock on their own. 50 g+ is safe and "
                "barely changes the sound.")
        if grams < 10:
            problems.append(text)
        elif grams < 50:
            warnings.append(text)
    if project["crank"]["crank_mass_g"] + project["crank"]["flywheel_mass_g"] < 1000:
        warnings.append("Crank + flywheel mass is under 1 kg. engine-sim only uses these masses to hold "
                        "the crank in place (spin uses the moment of inertia), and very light values "
                        "add solver jitter. Tick 'manual moment of inertia' if you want to raise them "
                        "without changing the spin.")

    # stock engines range from ~16 steps/rev (V12 at 18k) to 100+; CPU cost ~ cylinders x frequency
    steps = E["simulation_frequency"] / (E["redline_rpm"] / 60.0)
    load = E["simulation_frequency"] * len(project["cylinders"])
    if steps < 12:
        problems.append(f"Only {steps:.0f} simulation steps per crank revolution at redline; raise "
                        "the simulation frequency.")
    elif steps < 50:
        warnings.append(f"{steps:.0f} simulation steps per crank revolution at redline. It will run, but "
                        "100+ is more accurate if your PC can handle the extra load.")
    if load > 150000:
        warnings.append(f"Simulation load is {load:,.0f} cylinder-steps per second (stock engines use "
                        "60,000-80,000). It may run slower than real time and stutter; lower the "
                        "simulation frequency if it does.")

    cam = cam_report(project)
    if not cam["ok"]:
        problems.append("Cam lift must be over 0.050 in (1.27 mm): engine-sim builds the lobe from the "
                        "duration measured at 0.050 in of lift.")
    else:
        closed = cam["closed_deg"]
        text = (f"Both valves are only closed for {closed:.0f} deg of the 720 deg cycle. engine-sim "
                "lobes stay open much longer than 'duration @ 0.050' suggests when lift is small; "
                "shorten the durations or add lift.")
        # stock engine-sim engines keep both valves shut for ~210-275 deg
        if closed < 120:
            problems.append(text + " The cylinder can't build compression like this.")
        elif closed < 180:
            warnings.append(text)
        if cam["eff_cr"] < 4.5:
            warnings.append(f"Effective compression is only {cam['eff_cr']:.1f}:1 because the intake "
                            "closes so late. It will be hard to start and weak down low.")
        table_max = min(max(r[0] for r in H["intake_flow"]), max(r[0] for r in H["exhaust_flow"]))
        if max(cam["lift_thou"]) > table_max + 0.5:
            warnings.append(f"Cam lift ({max(cam['lift_thou']):.0f} thou) goes past the end of the port "
                            f"flow tables ({table_max:g} thou).")

    want = suggested_flame_multiplier(project)
    have = float(project["fuel"].get("flame_speed_multiplier", 1.0))
    if have < want - 0.4:
        g = project["geometry"]
        text = (f"Combustion will be slow: at {g['bore_mm']:g} x {g['stroke_mm']:g} mm the flame has a long "
                f"way to travel and engine-sim ties flame speed to piston speed. Set Fuel > Flame speed "
                f"multiplier to about {want:g} (now {have:g}).")
        (problems if have < want - 1.2 else warnings).append(text)

    equiv = 0.8 * project["intake"]["lambda"]
    if not 0.5 <= equiv <= 1.9:
        problems.append("Mixture multiplier (lambda) is outside what engine-sim will ignite "
                        "(roughly 0.63 to 2.4).")

    sf = sound_factor(project)
    lo, hi = STOCK_SOUND_FACTOR
    if sf > 30 * hi:
        warnings.append(f"Sound level factor {sf:.3g} is far above stock engines ({lo}-{hi}); the audio "
                        "will probably distort. Lower the audio volume or lengthen the exhaust.")
    elif sf < lo / 3:
        warnings.append(f"Sound level factor {sf:.3g} is below stock engines ({lo}-{hi}); it may be "
                        "very quiet. Raise the audio volume or shorten the exhaust.")
    return problems, warnings


def summary_text(project):
    lines = []
    problems, warnings = check_engine(project)
    lines.append("=== engine-sim checks ===")
    for p in problems:
        lines.append("PROBLEM: " + p)
    for w in warnings:
        lines.append("warning: " + w)
    if not problems and not warnings:
        lines.append("No problems found.")
    lines.append("")

    per, tot = displacement_cc(project)
    lines.append(f"Displacement: {tot:.3f} cc ({tot / 16.387:.4f} cu in), {per:.3f} cc per cylinder")
    cam = cam_report(project)
    eff = f", effective {cam['eff_cr']:.1f}:1 (from intake closing)" if cam["ok"] else ""
    lines.append(f"Compression ratio: {compression_ratio(project):.2f}:1{eff}")
    if cam["ok"]:
        a, s = cam["050"], cam["seat"]
        lines.append(f"Valve events @0.050\": intake opens {a['ivo_btdc']:.0f} BTDC, closes "
                     f"{a['ivc_abdc']:.0f} ABDC; exhaust opens {a['evo_bbdc']:.0f} BBDC, closes "
                     f"{a['evc_atdc']:.0f} ATDC; overlap {a['ivo_btdc'] + a['evc_atdc']:.0f}")
        lines.append(f"Seat-to-seat duration: intake {s['int_dur']:.0f}, exhaust {s['exh_dur']:.0f}; "
                     f"both valves closed for {cam['closed_deg']:.0f} of 720 deg")
    lines.append(f"Crank moment of inertia: {crank_moment(project):.6g} kg*m^2")
    g = project["geometry"]
    lines.append(f"Bore/stroke: {g['bore_mm'] / g['stroke_mm']:.3f}   "
                 f"rod/stroke: {g['rod_length_mm'] / g['stroke_mm']:.3f}")
    rpm = project["engine"]["redline_rpm"]
    fr = friction_report(project)
    lines.append(f"Mean piston speed at redline: {fr['v_mean']:.1f} m/s; ring friction ~"
                 f"{fr['viscous_frac'] * 100:.0f}% of power there")
    steps = project["engine"]["simulation_frequency"] / (rpm / 60.0)
    lines.append(f"Sim steps per crank rev at redline: {steps:.0f}")
    lines.append(f"Sound level factor: {sound_factor(project):.3g} "
                 f"(stock engines {STOCK_SOUND_FACTOR[0]}-{STOCK_SOUND_FACTOR[1]})")
    try:
        ph = compute_phasing(project)
    except LayoutError as e:
        lines.append("")
        lines.append("LAYOUT ERROR: " + str(e))
        return "\n".join(lines)
    lines.append("")
    lines.append(f"Crankshaft tdc: {ph['tdc_deg']:.2f} deg   journals: "
                 + ", ".join(f"{a:.1f}" for a in ph["journals"]))
    lines.append("Cyl  Bank  Journal(angle)   Fires at (deg of 720)")
    for c in sorted(ph["cyl"]):
        i = ph["cyl"][c]
        lines.append(f"{c:>3}  {i['bank']:>4}  rj{i['journal']} ({i['journal_angle']:6.1f})"
                     f"   {i['fire']:6.1f}")
    fires = sorted(i["fire"] for i in ph["cyl"].values())
    gaps = [(fires[(k + 1) % len(fires)] - fires[k]) % 720.0 or 720.0 for k in range(len(fires))]
    lines.append("Firing intervals: " + ", ".join(f"{x:.0f}" for x in gaps))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# .mr generation
# --------------------------------------------------------------------------

def fnum(x):
    """Float literal piranha accepts (no scientific notation, always has a '.')."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("non-finite number")
    s = f"{x:.12f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    if s in ("-0.0",):
        s = "0.0"
    return s


def inum(x):
    return str(int(round(float(x))))


def fbool(x):
    return "true" if x else "false"


def fstr(s):
    return '"' + str(s).replace("\\", "/").replace('"', "'") + '"'


def ident(name):
    s = re.sub(r"[^A-Za-z0-9_]", "_", name.strip()).strip("_").lower()
    s = re.sub(r"_+", "_", s)
    if not s:
        s = "custom_engine"
    if s[0].isdigit():
        s = "e_" + s
    return s


def file_stem(name):
    return ident(name)


def _flip(bank):
    f = bank.get("flip", "auto")
    if f == "auto":
        return float(bank["angle_deg"]) > 0
    return f in (True, "yes", "true")


def generate_mr(project, project_filename=None):
    p = project
    E, F, G, CR = p["engine"], p["fuel"], p["geometry"], p["crank"]
    H, C, I, X = p["head"], p["cam"], p["intake"], p["exhaust"]
    IG, V, T = p["ignition"], p["vehicle"], p["transmission"]
    banks = p["layout"]["banks"]
    ph = compute_phasing(p)
    cyls = cylinder_list(p)
    nid = "eb_" + ident(E["name"])
    n = len(cyls)

    o = []
    w = o.append
    w("// Generated by Engine Builder on "
      + datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    if project_filename:
        w(f"// Project file: {project_filename} (open it in Engine Builder to edit)")
    w("// Firing order: " + " ".join(str(c) for c in ph["order"]))
    w(f"// Displacement: {displacement_cc(p)[1]:.3f} cc, compression {compression_ratio(p):.2f}:1")
    w("")
    w('import "engine_sim.mr"')
    w("")
    w("units units()")
    w("constants constants()")
    w("impulse_response_library ir_lib()")
    w("")
    k_flame = float(F.get("flame_speed_multiplier", 1.0))
    if abs(k_flame - 1.0) > 1e-9:
        # engine-sim's default turbulence-to-flame-speed curve, scaled
        w(f"private node {nid}_flame_speed {{")
        w("    alias output __out:")
        w("        function(5.0)")
        pts = [(0.0, 3.0)] + [(float(x), 1.5 * x) for x in range(5, 50, 5)]
        for k_, (x, y) in enumerate(pts):
            w(f"            .add_sample({fnum(x)}, {fnum(y * k_flame)})" + (";" if k_ == len(pts) - 1 else ""))
        w("}")
        w("")
    w(f"private node {nid}_wires {{")
    for c in range(1, n + 1):
        w(f"    output wire{c}: ignition_wire();")
    w("}")
    w("")
    w(f"public node {nid} {{")
    w("    alias output __out: engine;")
    w("")
    w("    engine engine(")
    w(f"        name: {fstr(E['name'])},")
    w(f"        starter_torque: {fnum(E['starter_torque_lbft'])} * units.lb_ft,")
    w(f"        starter_speed: {fnum(E['starter_speed_rpm'])} * units.rpm,")
    w(f"        redline: {fnum(E['redline_rpm'])} * units.rpm,")
    w(f"        dyno_min_speed: {fnum(E['dyno_min_rpm'])} * units.rpm,")
    w(f"        dyno_max_speed: {fnum(E['dyno_max_rpm'])} * units.rpm,")
    w(f"        dyno_hold_step: {fnum(E['dyno_hold_step_rpm'])} * units.rpm,")
    w(f"        throttle_gamma: {fnum(E['throttle_gamma'])},")
    w("        fuel: fuel(")
    w(f"            name: {fstr(F['name'])},")
    w(f"            molecular_mass: {fnum(F['molecular_mass_g'])} * units.g,")
    w(f"            energy_density: {fnum(F['energy_density_kj_g'])} * units.kJ / units.g,")
    w(f"            density: {fnum(F['density_kg_l'])} * units.kg / units.L,")
    w(f"            molecular_afr: {fnum(F['molecular_afr'])},")
    w(f"            max_burning_efficiency: {fnum(F['max_burning_efficiency'])},")
    w(f"            burning_efficiency_randomness: {fnum(F['burning_efficiency_randomness'])},")
    w(f"            low_efficiency_attenuation: {fnum(F['low_efficiency_attenuation'])},")
    w(f"            max_turbulence_effect: {fnum(F['max_turbulence_effect'])},")
    w(f"            max_dilution_effect: {fnum(F['max_dilution_effect'])}"
      + ("," if abs(k_flame - 1.0) > 1e-9 else ""))
    if abs(k_flame - 1.0) > 1e-9:
        w(f"            turbulence_to_flame_speed_ratio: {nid}_flame_speed()")
    w("        ),")
    w(f"        simulation_frequency: {fnum(E['simulation_frequency'])},")
    w(f"        max_sle_solver_steps: {inum(E['max_sle_solver_steps'])},")
    w(f"        fluid_simulation_steps: {inum(E['fluid_simulation_steps'])},")
    w(f"        convolution: {fnum(E['convolution'])},")
    w(f"        hf_gain: {fnum(E['hf_gain'])},")
    w(f"        jitter: {fnum(E['jitter'])},")
    w(f"        noise: {fnum(E['noise'])},")
    w(f"        heat_transfer_coefficient: {fnum(E['heat_transfer_coefficient'])},")
    w(f"        block_temperature: celcius({fnum(E['block_temperature_c'])})")
    w("    )")
    w("")
    w(f"    {nid}_wires wires()")
    w("")

    # Crankshaft
    w("    crankshaft c0(")
    w(f"        throw: {fnum(G['stroke_mm'] / 2.0)} * units.mm,")
    w(f"        flywheel_mass: {fnum(CR['flywheel_mass_g'])} * units.g,")
    w(f"        mass: {fnum(CR['crank_mass_g'])} * units.g,")
    w(f"        friction_torque: {fnum(CR['friction_torque_nm'])} * units.Nm,")
    w(f"        moment_of_inertia: {fnum(crank_moment(p))},")
    w("        position_x: 0.0,")
    w("        position_y: 0.0,")
    w(f"        tdc: {fnum(ph['tdc_deg'])} * units.deg")
    w("    )")
    w("")
    for j, a in enumerate(ph["journals"]):
        w(f"    rod_journal rj{j}(angle: {fnum(a)} * units.deg)")
    w("    c0")
    for j in range(len(ph["journals"])):
        w(f"        .add_rod_journal(rj{j})")
    w("")

    # Piston / rod / bank
    rod_len = G["rod_length_mm"] / 1000.0
    rod_m = G["rod_mass_g"] / 1000.0
    w("    piston_parameters piston_params(")
    w(f"        mass: {fnum(G['piston_mass_g'])} * units.g,")
    w(f"        compression_height: {fnum(G['compression_height_mm'])} * units.mm,")
    w(f"        wrist_pin_position: {fnum(G['wrist_pin_position_mm'])} * units.mm,")
    w("        displacement: 0.0")
    w("    )")
    w("")
    w("    connecting_rod_parameters cr_params(")
    w(f"        mass: {fnum(G['rod_mass_g'])} * units.g,")
    w(f"        moment_of_inertia: {fnum(rod_m * rod_len ** 2 / 12.0)},")
    w("        center_of_mass: 0.0,")
    w(f"        length: {fnum(G['rod_length_mm'])} * units.mm")
    w("    )")
    w("")
    deck = G["stroke_mm"] / 2.0 + G["rod_length_mm"] + G["compression_height_mm"] + G["deck_clearance_mm"]
    w("    cylinder_bank_parameters bank_params(")
    w(f"        bore: {fnum(G['bore_mm'])} * units.mm,")
    w(f"        deck_height: {fnum(deck)} * units.mm")
    w("    )")
    w("")

    # Intake
    w("    intake intake(")
    w(f"        plenum_volume: {fnum(I['plenum_volume_cc'])} * units.cc,")
    w(f"        plenum_cross_section_area: {fnum(I['plenum_area_cm2'])} * units.cm2,")
    w(f"        intake_flow_rate: k_carb({fnum(I['intake_flow_cfm'])}),")
    w(f"        runner_flow_rate: k_carb({fnum(I['runner_flow_cfm'])}),")
    w(f"        runner_length: {fnum(I['runner_length_in'])} * units.inch,")
    w(f"        idle_flow_rate: k_carb({fnum(I['idle_flow_cfm'])}),")
    w(f"        idle_throttle_plate_position: {fnum(I['idle_throttle_plate_position'])},")
    w(f"        throttle_gamma: {fnum(I['throttle_gamma'])},")
    w(f"        velocity_decay: {fnum(I['velocity_decay'])},")
    w(f"        molecular_afr: {fnum(F['molecular_afr'] * I['lambda'])}")
    w("    )")
    w("")

    # Exhaust
    n_exh = len(banks) if X["mode"] == "per_bank" else 1
    w("    exhaust_system_parameters es_params(")
    w(f"        outlet_flow_rate: k_carb({fnum(X['outlet_flow_cfm'])}),")
    w(f"        primary_tube_length: {fnum(X['primary_tube_length_in'])} * units.inch,")
    w(f"        primary_flow_rate: k_carb({fnum(X['primary_flow_cfm'])}),")
    w(f"        length: {fnum(X['length_in'])} * units.inch,")
    w(f"        collector_cross_section_area: {fnum(X['collector_area_cm2'])} * units.cm2,")
    w(f"        velocity_decay: {fnum(X['velocity_decay'])},")
    w(f"        backflow_atmospheric_mixing: {fnum(X['backflow_atmospheric_mixing'])}")
    w("    )")
    w("")
    for e in range(n_exh):
        w(f"    exhaust_system exhaust{e}(")
        w("        es_params,")
        w(f"        audio_volume: {fnum(X['audio_volume'])},")
        w(f"        impulse_response: ir_lib.{X['impulse_response']}")
        w("    )")
    w("")

    # Cams
    w("    harmonic_cam_lobe intake_lobe(")
    w(f"        duration_at_50_thou: {fnum(C['intake_duration_deg'])} * units.deg,")
    w(f"        gamma: {fnum(C['intake_gamma'])},")
    w(f"        lift: {fnum(C['intake_lift_mm'])} * units.mm,")
    w(f"        steps: {inum(C['steps'])}")
    w("    )")
    w("")
    w("    harmonic_cam_lobe exhaust_lobe(")
    w(f"        duration_at_50_thou: {fnum(C['exhaust_duration_deg'])} * units.deg,")
    w(f"        gamma: {fnum(C['exhaust_gamma'])},")
    w(f"        lift: {fnum(C['exhaust_lift_mm'])} * units.mm,")
    w(f"        steps: {inum(C['steps'])}")
    w("    )")
    w("")
    w("    camshaft_parameters cam_params(")
    w(f"        advance: {fnum(C['advance_deg'])} * units.deg,")
    w(f"        base_radius: {fnum(C['base_radius_mm'])} * units.mm")
    w("    )")
    w("")
    by_bank = {bi: [] for bi in range(len(banks))}
    for num, bi, idx in cyls:
        by_bank[bi].append(num)
    for bi in range(len(banks)):
        w(f"    camshaft intake_cam_{bi}(cam_params, lobe_profile: intake_lobe)")
        w(f"    camshaft exhaust_cam_{bi}(cam_params, lobe_profile: exhaust_lobe)")
        w(f"    intake_cam_{bi}")
        for num in by_bank[bi]:
            f = ph["cyl"][num]["fire"]
            w(f"        .add_lobe({fnum(360.0 + C['intake_center_deg'] + f)} * units.deg) // cyl {num}")
        w(f"    exhaust_cam_{bi}")
        for num in by_bank[bi]:
            f = ph["cyl"][num]["fire"]
            w(f"        .add_lobe({fnum(360.0 - C['exhaust_center_deg'] + f)} * units.deg) // cyl {num}")
        w("")

    # Flow functions (one pair per bank)
    step = H["lift_step_thou"]
    scale = H["flow_scale"]
    for bi in range(len(banks)):
        for kind in ("intake", "exhaust"):
            w(f"    function {kind}_flow_{bi}({fnum(step)} * units.thou)")
            w(f"    {kind}_flow_{bi}")
            for lift, flow in H[f"{kind}_flow"]:
                w(f"        .add_flow_sample({fnum(lift)}, {fnum(flow * scale)})")
        w("")

    # Banks + cylinders
    for bi, bank in enumerate(banks):
        w(f"    cylinder_bank b{bi}(")
        w("        bank_params,")
        w(f"        angle: {fnum(bank['angle_deg'])} * units.deg,")
        w(f"        position_x: {fnum(bank['position_x_mm'])} * units.mm,")
        w(f"        position_y: {fnum(bank['position_y_mm'])} * units.mm,")
        w(f"        display_depth: {fnum(bank['display_depth'])}")
        w("    )")
        w(f"    b{bi}")
        exh = bi if n_exh > 1 else 0
        for num in by_bank[bi]:
            cy = p["cylinders"][num - 1]
            blowby = G["blowby"] * cy["blowby_scale"]
            w("        .add_cylinder(")
            w(f"            piston: piston(piston_params, blowby: k_28inH2O({fnum(blowby)})),")
            w("            connecting_rod: connecting_rod(cr_params),")
            w(f"            rod_journal: rj{ph['cyl'][num]['journal']},")
            w("            intake: intake,")
            w(f"            exhaust_system: exhaust{exh},")
            w(f"            ignition_wire: wires.wire{num},")
            w(f"            primary_length: {fnum(cy['primary_length_in'])} * units.inch,")
            w(f"            sound_attenuation: {fnum(cy['sound_attenuation'])}")
            w(f"        ) // cyl {num}")
        w("")
        w(f"    b{bi}.set_cylinder_head(")
        w("        generic_cylinder_head(")
        w(f"            chamber_volume: {fnum(H['chamber_volume_cc'])} * units.cc,")
        w(f"            intake_runner_volume: {fnum(H['intake_runner_volume_cc'])} * units.cc,")
        w(f"            intake_runner_cross_section_area: {fnum(H['intake_runner_area_cm2'])} * units.cm2,")
        w(f"            exhaust_runner_volume: {fnum(H['exhaust_runner_volume_cc'])} * units.cc,")
        w(f"            exhaust_runner_cross_section_area: {fnum(H['exhaust_runner_area_cm2'])} * units.cm2,")
        w(f"            intake_port_flow: intake_flow_{bi},")
        w(f"            exhaust_port_flow: exhaust_flow_{bi},")
        w("            valvetrain: standard_valvetrain(")
        w(f"                intake_camshaft: intake_cam_{bi},")
        w(f"                exhaust_camshaft: exhaust_cam_{bi}")
        w("            ),")
        w(f"            flip_display: {fbool(_flip(bank))}")
        w("        )")
        w("    )")
        w("")

    w("    engine")
    for bi in range(len(banks)):
        w(f"        .add_cylinder_bank(b{bi})")
    w("")
    w("    engine.add_crankshaft(c0)")
    w("")

    # Ignition
    timing = sorted(IG["timing"], key=lambda r: r[0])
    xs = [r[0] for r in timing]
    radius = (xs[-1] - xs[0]) / max(1, len(xs) - 1) if len(xs) > 1 else 1000.0
    w(f"    function timing_curve({fnum(radius)} * units.rpm)")
    w("    timing_curve")
    for rpm, adv in timing:
        w(f"        .add_sample({fnum(rpm)} * units.rpm, {fnum(adv)} * units.deg)")
    w("")
    w("    ignition_module ignition_module(")
    w("        timing_curve: timing_curve,")
    w(f"        rev_limit: {fnum(IG['rev_limit_rpm'])} * units.rpm,")
    w(f"        limiter_duration: {fnum(IG['limiter_duration_s'])}")
    w("    )")
    w("    ignition_module")
    for c in ph["order"]:
        w(f"        .connect_wire(wires.wire{c}, {fnum(ph['cyl'][c]['fire'])} * units.deg)")
    w("")
    w("    engine.add_ignition_module(ignition_module)")
    w("}")
    w("")

    # Vehicle
    w(f"private node {nid}_vehicle {{")
    w("    alias output __out:")
    w("        vehicle(")
    w(f"            mass: {fnum(V['mass_kg'])} * units.kg,")
    w(f"            drag_coefficient: {fnum(V['drag_coefficient'])},")
    w(f"            cross_sectional_area: {fnum(V['cross_sectional_area_m2'])} * units.m2,")
    w(f"            diff_ratio: {fnum(V['diff_ratio'])},")
    w(f"            tire_radius: {fnum(V['tire_radius_in'])} * units.inch,")
    w(f"            rolling_resistance: {fnum(V['rolling_resistance_n'])} * units.N,")
    w(f"            stiffness: {fnum(V['stiffness_lbft_deg'])} * units.lb_ft / units.deg,")
    w(f"            damping: {fnum(V['damping'])},")
    w(f"            max_flex: {fnum(V['max_flex_deg'])} * units.deg,")
    w(f"            limit_flex: {fbool(V['limit_flex'])},")
    w(f"            simulate_flex: {fbool(V['simulate_flex'])},")
    w(f"            max_brake_force: {fnum(V['max_brake_force_n'])} * units.N,")
    w(f"            coeff_static_friction: {fnum(V['coeff_static_friction'])},")
    w(f"            coeff_dynamic_friction: {fnum(V['coeff_dynamic_friction'])},")
    w(f"            wheel_base: {fnum(V['wheel_base_in'])} * units.inch,")
    w(f"            track: {fnum(V['track_in'])} * units.inch,")
    w(f"            max_brake_torque: {fnum(V['max_brake_torque_lbft'])} * units.lb_ft,")
    w(f"            center_of_mass: {fnum(V['center_of_mass_in'])} * units.inch,")
    w(f"            weight_transfer_bias: {fnum(V['weight_transfer_bias'])},")
    w(f"            vehicle_asset_file: {fstr(V['vehicle_asset_file'])}")
    w("        );")
    w("}")
    w("")

    # Transmission
    gears = [g for g in T["gears"]]
    if not gears:
        raise LayoutError("The transmission needs at least one gear.")
    w(f"private node {nid}_transmission {{")
    w("    alias output __out:")
    w("        transmission(")
    w(f"            max_clutch_torque: {fnum(T['max_clutch_torque_lbft'])} * units.lb_ft,")
    w(f"            max_clutch_flex: {fnum(T['max_clutch_flex_deg'])} * units.deg,")
    w(f"            limit_clutch_flex: {fbool(T['limit_clutch_flex'])},")
    w(f"            clutch_stiffness: {fnum(T['clutch_stiffness_lbft_deg'])} * units.lb_ft / units.deg,")
    w(f"            clutch_damping: {fnum(T['clutch_damping'])},")
    w(f"            simulate_flex: {fbool(T['simulate_flex'])}")
    w("        )")
    for k, g in enumerate(gears):
        w(f"        .add_gear({fnum(g)})" + (";" if k == len(gears) - 1 else ""))
    w("}")
    w("")
    w("public node main {")
    w("    run(")
    w(f"        engine: {nid}(),")
    w(f"        transmission: {nid}_transmission(),")
    w(f"        vehicle: {nid}_vehicle()")
    w("    )")
    w("}")
    w("")
    w("main()")
    w("")
    return "\n".join(o)
