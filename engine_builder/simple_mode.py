"""Simple mode: turn a handful of friendly settings into a full engine project.

Scaling rules are anchored on stock engine-sim engines that are known to run
(2JZ, GM LS, Hayabusa, Kohler), so whatever the sliders say, the result stays
inside the range engine-sim was tuned for.
"""

import math
import random

import mr_gen

# friendly name -> layout preset in mr_gen.LAYOUT_PRESETS
ENGINE_TYPES = {
    "Single (dirt bike / lawnmower)": "Single",
    "Twin, 270° crank (adventure bike)": "Parallel twin 270",
    "V-twin 45° (Harley potato-potato)": "V-twin 45",
    "V-twin 90° (Ducati)": "V-twin 90",
    "Inline 3 (thrummy triple)": "Inline 3",
    "Inline 4 (car / sportbike)": "Inline 4",
    "Flat 4 (boxer)": "Flat 4 (boxer)",
    "Inline 5 (warbly)": "Inline 5",
    "Inline 6 (silky)": "Inline 6",
    "Flat 6 (Porsche-ish)": "Flat 6 (boxer)",
    "V6": "V6 60",
    "V8 (muscle car)": "V8 cross-plane",
    "V8 flat-plane (Ferrari scream)": "V8 flat-plane",
    "V10 (supercar)": "V10 72",
    "V12 (luxury / old F1)": "V12 60",
    "2-stroke sound (360° twin)": "2-stroke sound trick (360 deg twin)",
}

VEHICLES = {
    "Go-kart": ({"mass_kg": 120.0, "drag_coefficient": 0.8, "cross_sectional_area_m2": 0.6,
                 "diff_ratio": 5.5, "tire_radius_in": 5.5, "rolling_resistance_n": 80.0,
                 "max_brake_force_n": 2000.0, "wheel_base_in": 42.0, "track_in": 40.0,
                 "max_brake_torque_lbft": 300.0, "center_of_mass_in": 8.0},
                [2.8, 1.9, 1.45, 1.17, 1.0]),
    "Motorcycle": ({"mass_kg": 260.0, "drag_coefficient": 0.6, "cross_sectional_area_m2": 0.6,
                    "diff_ratio": 2.4, "tire_radius_in": 12.5, "rolling_resistance_n": 100.0,
                    "max_brake_force_n": 4000.0, "wheel_base_in": 58.0, "track_in": 10.0,
                    "max_brake_torque_lbft": 400.0, "center_of_mass_in": 22.0},
                   [2.6, 1.94, 1.53, 1.29, 1.14, 1.04]),
    "Car": ({"mass_kg": 1400.0, "drag_coefficient": 0.3, "cross_sectional_area_m2": 2.2,
             "diff_ratio": 4.1, "tire_radius_in": 12.0, "rolling_resistance_n": 200.0,
             "max_brake_force_n": 8000.0, "wheel_base_in": 104.0, "track_in": 60.0,
             "max_brake_torque_lbft": 600.0, "center_of_mass_in": 20.0},
            [3.5, 2.1, 1.4, 1.0, 0.8]),
    "Sports car": ({"mass_kg": 1350.0, "drag_coefficient": 0.3, "cross_sectional_area_m2": 1.9,
                    "diff_ratio": 3.42, "tire_radius_in": 13.0, "rolling_resistance_n": 180.0,
                    "max_brake_force_n": 10000.0, "wheel_base_in": 100.0, "track_in": 62.0,
                    "max_brake_torque_lbft": 800.0, "center_of_mass_in": 17.0},
                   [2.97, 2.07, 1.43, 1.0, 0.84, 0.62]),
    "Truck": ({"mass_kg": 2600.0, "drag_coefficient": 0.45, "cross_sectional_area_m2": 3.5,
               "diff_ratio": 3.73, "tire_radius_in": 15.5, "rolling_resistance_n": 400.0,
               "max_brake_force_n": 12000.0, "wheel_base_in": 140.0, "track_in": 68.0,
               "max_brake_torque_lbft": 1000.0, "center_of_mass_in": 30.0},
              [4.0, 2.4, 1.5, 1.0, 0.75]),
    # gears given as {first, top, count}: worked out from the engine's redline
    "Eco hatchback": ({"mass_kg": 1350.0, "drag_coefficient": 0.25, "cross_sectional_area_m2": 2.2,
                       "diff_ratio": 3.27, "tire_radius_in": 12.3, "rolling_resistance_n": 130.0,
                       "max_brake_force_n": 8000.0, "wheel_base_in": 106.0, "track_in": 60.0,
                       "max_brake_torque_lbft": 600.0, "center_of_mass_in": 21.0},
                      {"first_kmh": 55, "top_kmh": 210, "count": 6}),
    "Top-speed GT": ({"mass_kg": 1450.0, "drag_coefficient": 0.28, "cross_sectional_area_m2": 1.9,
                      "diff_ratio": 3.42, "tire_radius_in": 13.0, "rolling_resistance_n": 180.0,
                      "max_brake_force_n": 10000.0, "wheel_base_in": 104.0, "track_in": 63.0,
                      "max_brake_torque_lbft": 800.0, "center_of_mass_in": 17.0},
                     {"first_kmh": 100, "top_kmh": 345, "count": 6}),
    "F1 car": ({"mass_kg": 605.0, "drag_coefficient": 0.9, "cross_sectional_area_m2": 1.5,
                "diff_ratio": 1.0, "tire_radius_in": 13.0, "rolling_resistance_n": 200.0,
                "max_brake_force_n": 15000.0, "wheel_base_in": 120.0, "track_in": 70.0,
                "max_brake_torque_lbft": 1500.0, "center_of_mass_in": 10.0,
                "coeff_static_friction": 1.8, "coeff_dynamic_friction": 1.6},
               {"first_kmh": 120, "top_kmh": 340, "count": 7}),
}

# Special tunes: recipes applied on top of the sliders (they keep working if sliders move)
TUNES = ["None", "Eco (Atkinson, lean)", "Torque (long stroke, long runners)",
         "Top speed (high compression, big ports)", "F1 (huge bore, pneumatic valves)"]
_TUNE_BORE_STROKE = {"Eco (Atkinson, lean)": 0.91, "Torque (long stroke, long runners)": 0.95,
                     "F1 (huge bore, pneumatic valves)": 2.46}

LITERS_PER_CYLINDER = (0.15, 1.0)   # below ~150 cc engine-sim's fixed friction takes over
REV_LIMIT_RANGE = (2500, 21000)
CYLINDER_STEP_BUDGET = 80000        # stock engines run ~60k-80k cylinder-steps per second

# port flow vs lift, shaped like the stock 2JZ head (11 points, last ones flat)
_INTAKE_SHAPE = [0, 0.206, 0.367, 0.555, 0.762, 0.886, 0.954, 0.996, 0.996, 1.0, 1.0]
_EXHAUST_SHAPE = [0, 0.150, 0.293, 0.459, 0.650, 0.797, 0.902, 0.955, 0.996, 1.0, 1.0]

_IMPULSES = ["mild_exhaust_0_reverb", "mild_exhaust_0", "default_0",
             "minimal_muffling_02", "minimal_muffling_01"]

DEFAULT_SETTINGS = {
    "name": "",
    "type": "V8 (muscle car)",
    "size_l": 5.7,
    "rev_limit": 6500,
    "sound": 65,
    "cam": 40,
    "feel": 45,
    "vehicle": "Sports car",
    "tune": "None",
}

# Ready-made slider settings (Simple mode "Preset" picker)
PRESETS = {
    # superbike-style 1.0 L inline 4: tiny inertia, light internals, small airbox,
    # 15,000 rpm limiter with a short cut so it bounces off it crisply
    "Super snappy (revs instantly)": {
        "name": "Super Snappy",
        "type": "Inline 4 (car / sportbike)",
        "size_l": 1.0,
        "rev_limit": 15000,
        "sound": 85,
        "cam": 65,
        "feel": 100,
        "vehicle": "Motorcycle",
        "tune": "None",
    },
    "Muscle V8 (the default)": dict(DEFAULT_SETTINGS, name="Muscle V8"),
    "Eco 1.8 Atkinson (fuel saver)": {
        "name": "Eco 1.8 Atkinson", "type": "Inline 4 (car / sportbike)", "size_l": 1.8,
        "rev_limit": 5500, "sound": 15, "cam": 0, "feel": 20, "vehicle": "Eco hatchback",
        "tune": "Eco (Atkinson, lean)"},
    "Torque Monster 7.4 V8": {
        "name": "Torque Monster 7.4 V8", "type": "V8 (muscle car)", "size_l": 7.4,
        "rev_limit": 5250, "sound": 60, "cam": 5, "feel": 0, "vehicle": "Truck",
        "tune": "Torque (long stroke, long runners)"},
    "Top Speed 4.5 V8": {
        "name": "Top Speed 4.5 V8", "type": "V8 flat-plane (Ferrari scream)", "size_l": 4.5,
        "rev_limit": 9500, "sound": 90, "cam": 85, "feel": 75, "vehicle": "Top-speed GT",
        "tune": "Top speed (high compression, big ports)"},
    "F1 V10 20k (highest revving)": {
        "name": "F1 V10 20k", "type": "V10 (supercar)", "size_l": 3.0,
        "rev_limit": 20500, "sound": 100, "cam": 100, "feel": 100, "vehicle": "F1 car",
        "tune": "F1 (huge bore, pneumatic valves)"},
}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _lerp(a, b, t):
    return a + (b - a) * t


def cylinders_for(type_name):
    banks, _, _ = mr_gen.LAYOUT_PRESETS[ENGINE_TYPES[type_name]]
    return sum(n for _, n in banks)


def size_range(type_name):
    n = cylinders_for(type_name)
    return round(LITERS_PER_CYLINDER[0] * n, 2), round(LITERS_PER_CYLINDER[1] * n, 2)


def typical_size(type_name):
    n = cylinders_for(type_name)
    return round((0.4 if n == 1 else 0.5) * n, 2)


def default_name(s):
    if s.get("name", "").strip():
        return s["name"].strip()
    return "My " + s["type"].split(" (")[0]


def feel_inertia_factor(feel):
    """Flywheel multiplier for Feel 0..1: 2.0 (heavy) -> 0.25 at 0.8 -> 0.08 at 1.0.

    The last fifth of the slider is a "race" zone: almost no flywheel, so the
    engine hits redline nearly instantly (and idles rough, so idle air goes up).
    """
    if feel <= 0.8:
        return 2.0 * 0.125 ** (feel / 0.8)
    return 0.25 * 0.32 ** ((feel - 0.8) / 0.2)


def bore_stroke(s):
    """Revvier engines get a shorter stroke, like real ones do (unless a tune says otherwise)."""
    n = cylinders_for(s["type"])
    per_cyl_mm3 = s["size_l"] / n * 1e6
    ratio = _TUNE_BORE_STROKE.get(s.get("tune", "None"))
    if ratio is None:
        ratio = _clamp(0.85 + (s["rev_limit"] - 3000) * (0.6 / 12000), 0.8, 1.5)
    bore = (4 * per_cyl_mm3 * ratio / math.pi) ** (1 / 3)
    return bore, bore / ratio


def build_simple(s):
    """Return a complete project dict for the simple-mode settings `s`."""
    p = mr_gen.baby_bee_defaults()
    mr_gen.apply_layout_preset(p, ENGINE_TYPES[s["type"]])
    n = len(p["cylinders"])
    size = float(s["size_l"])
    per_l = size / n
    rl = float(s["rev_limit"])
    cam = _clamp(s["cam"] / 100.0, 0, 1)
    snd = _clamp(s["sound"] / 100.0, 0, 1)
    feel = _clamp(s["feel"] / 100.0, 0, 1)
    bore, stroke = bore_stroke(s)
    bore_area = math.pi / 4 * (bore / 10) ** 2           # cm^2

    E = p["engine"]
    E["name"] = default_name(s)
    E["redline_rpm"] = round(0.95 * rl / 100) * 100
    E["dyno_min_rpm"] = 1500.0 if cam > 0.6 else 1000.0
    E["dyno_max_rpm"] = E["redline_rpm"]
    E["starter_torque_lbft"] = round(_clamp(40 + 40 * size, 40, 250))
    E["starter_speed_rpm"] = 400.0
    freq = min(math.ceil(rl / 60 * 100 / 500) * 500, CYLINDER_STEP_BUDGET / n)
    E["simulation_frequency"] = int(max(5000, freq // 500 * 500))
    E["jitter"] = round(_lerp(0.3, 0.6, snd), 2)

    p["fuel"]["burning_efficiency_randomness"] = round(_lerp(0.15, 0.45, cam), 2)

    G = p["geometry"]
    G["bore_mm"] = round(bore, 1)
    G["stroke_mm"] = round(stroke, 1)
    G["rod_length_mm"] = round(1.7 * stroke, 1)
    G["compression_height_mm"] = round(0.32 * bore, 1)
    # Feel: heavy & smooth <-> light & snappy. Snappy means a light flywheel, light
    # pistons/rods (less inertia and ring friction at high rpm), less crank friction,
    # a smaller airbox and a crisper limiter.
    G["piston_mass_g"] = round(max(60.0, 4.5e-4 * bore ** 3 * _lerp(1.15, 0.5, feel)))
    G["rod_mass_g"] = round(1.3 * G["piston_mass_g"])

    cyl_factor = {1: 2.2, 2: 1.5, 3: 1.25}.get(n, 1.0)     # singles and twins need more flywheel
    C = p["crank"]
    C["manual_moment"] = True
    C["moment_of_inertia"] = round(0.08 * size * cyl_factor * feel_inertia_factor(feel), 5)
    C["crank_mass_g"] = round((5 + 3 * size) * 1000)
    C["flywheel_mass_g"] = round((3 + 2 * size) * 1000)
    C["flywheel_radius_mm"] = 150.0
    C["friction_torque_nm"] = round((2 + 2.5 * size) * _lerp(1.2, 0.6, feel), 1)

    H = p["head"]
    H["chamber_volume_cc"] = round(per_l * 1000 / 9.5, 1)          # 10.5:1
    H["intake_runner_volume_cc"] = round(per_l * 1000 * 0.35, 1)
    H["intake_runner_area_cm2"] = round(0.4 * bore_area, 1)
    H["exhaust_runner_volume_cc"] = round(per_l * 1000 * 0.1, 1)
    H["exhaust_runner_area_cm2"] = round(0.3 * bore_area, 1)
    step = round(50 * bore / 86, 1)
    peak = 4.7 * bore_area * (1 + 0.15 * cam)
    H["lift_step_thou"] = step
    H["flow_scale"] = 1.0
    H["intake_flow"] = [[round(i * step, 1), round(f * peak, 1)] for i, f in enumerate(_INTAKE_SHAPE)]
    H["exhaust_flow"] = [[round(i * step, 1), round(f * peak * 0.78, 1)]
                         for i, f in enumerate(_EXHAUST_SHAPE)]

    K = p["cam"]
    K["intake_duration_deg"] = round(_lerp(205, 250, cam))
    K["exhaust_duration_deg"] = round(_lerp(209, 254, cam))
    K["intake_center_deg"] = round(_lerp(116, 104, cam), 1)
    K["exhaust_center_deg"] = round(_lerp(116, 106, cam), 1)
    K["intake_lift_mm"] = round(bore * _lerp(0.11, 0.14, cam), 2)
    K["exhaust_lift_mm"] = round(K["intake_lift_mm"] * 0.95, 2)
    K["intake_gamma"] = K["exhaust_gamma"] = 1.1
    K["advance_deg"] = 0.0
    K["base_radius_mm"] = round(0.18 * bore, 1)

    I = p["intake"]
    I["plenum_volume_cc"] = round(max(300.0, 600 * size * _lerp(1.4, 0.5, feel)))
    I["plenum_area_cm2"] = round(10 + 4 * size, 1)
    I["intake_flow_cfm"] = round(30 * size * rl / 1000 * (1 + 0.3 * cam))
    I["runner_flow_cfm"] = round(max(60.0, 50 * per_l * rl / 1000))
    I["runner_length_in"] = round(_clamp(120000 / rl, 6, 40), 1)
    idle_k = size * _lerp(0.9, 2.5, cam) * (1.6 if n <= 2 else 1.0)
    idle_k *= 1 + 1.5 * _clamp((feel - 0.6) / 0.4, 0, 1)   # light flywheels need a faster idle
    I["idle_throttle_plate_position"] = round(
        _clamp(2 / math.pi * math.acos(min(1.0, idle_k / I["intake_flow_cfm"])), 0.9, 0.999), 4)
    I["idle_flow_cfm"] = 0.0
    I["throttle_gamma"] = 2.0

    X = p["exhaust"]
    X["mode"] = "per_bank" if len(p["layout"]["banks"]) > 1 else "shared"
    X["impulse_response"] = _IMPULSES[min(len(_IMPULSES) - 1, int(snd * len(_IMPULSES)))]
    X["length_in"] = round(_lerp(100, 20, snd))
    X["collector_area_cm2"] = round(20 + 8 * size, 1)
    X["outlet_flow_cfm"] = round(_clamp(250 * size * rl / 7000, 200, 1500) * _lerp(0.6, 1.4, snd))
    X["primary_tube_length_in"] = round(_lerp(30, 10, snd))
    X["primary_flow_cfm"] = round(_clamp(800 * per_l * rl / 7000, 150, 600))
    X["velocity_decay"] = 1.0
    target = _lerp(0.03, 0.12, snd)                   # sound level factor, stock ~0.004-0.15
    X["audio_volume"] = round(target * n * (X["length_in"] * 0.0254) ** 2, 4)

    # slightly different header lengths per cylinder, like real headers
    for num, bank, idx in mr_gen.cylinder_list(p):
        cyl = p["cylinders"][num - 1]
        cyl["primary_length_in"] = 0.0 if n == 1 else float((idx * 2) % 6)
        cyl["sound_attenuation"] = 1.0 if n == 1 else round(1.0 - 0.04 * (idx % 3), 2)

    IG = p["ignition"]
    IG["rev_limit_rpm"] = rl
    IG["limiter_duration_s"] = round(_lerp(0.12, 0.04, feel), 3)
    base = 12 + 6 * cam
    top = max(8000, rl + 2000)
    IG["timing"] = [[r, round(min(36.0, base + 5.5 * r / 1000), 1)]
                    for r in range(0, int(top) + 1, 1000)]

    _apply_tune(p, s.get("tune", "None"), n, size)
    p["fuel"]["flame_speed_multiplier"] = mr_gen.suggested_flame_multiplier(p)

    vehicle, gears = VEHICLES[s["vehicle"]]
    p["vehicle"].update(vehicle)
    if isinstance(gears, dict):
        r = p["vehicle"]["tire_radius_in"] * 0.0254
        w = p["engine"]["redline_rpm"] * 2 * math.pi / 60 / p["vehicle"]["diff_ratio"]
        g1, gn = r * w / (gears["first_kmh"] / 3.6), r * w / (gears["top_kmh"] / 3.6)
        step = (gn / g1) ** (1 / (gears["count"] - 1))
        p["transmission"]["gears"] = [round(g1 * step ** i, 3) for i in range(gears["count"])]
    else:
        p["transmission"]["gears"] = list(gears)
    p["transmission"]["max_clutch_torque_lbft"] = round(max(60.0, 2 * 64.5 * size))
    return p


def _chamber_for(p, cr):
    p["head"]["chamber_volume_cc"] = round(mr_gen.displacement_cc(p)[0] / (cr - 1), 1)


def _apply_tune(p, tune, n, size):
    k, g = p["cam"], p["geometry"]
    if tune == "Eco (Atkinson, lean)":
        _chamber_for(p, 13.0)
        k["intake_center_deg"] = round(k["intake_center_deg"] + 12, 1)     # late intake close
        k["intake_duration_deg"] = round(k["intake_duration_deg"] + 20)
        p["intake"]["lambda"] = 1.15                                     # lean burn
        p["intake"]["runner_length_in"] = 20.0
        p["crank"]["friction_torque_nm"] = round(p["crank"]["friction_torque_nm"] * 0.75, 1)
        p["fuel"].update(max_burning_efficiency=0.95, burning_efficiency_randomness=0.1)
    elif tune == "Torque (long stroke, long runners)":
        _chamber_for(p, 10.0)
        p["intake"]["runner_length_in"] = 26.0
        p["intake"]["plenum_volume_cc"] = round(800 * size)
        k["intake_center_deg"] = max(k["intake_center_deg"], 114.0)
        k["exhaust_center_deg"] = max(k["exhaust_center_deg"], 116.0)
    elif tune == "Top speed (high compression, big ports)":
        _chamber_for(p, 12.5)
        p["head"]["flow_scale"] = 1.2
        k["intake_lift_mm"] = round(g["bore_mm"] * 0.135, 2)
        k["exhaust_lift_mm"] = round(k["intake_lift_mm"] * 0.95, 2)
    elif tune == "F1 (huge bore, pneumatic valves)":
        _chamber_for(p, 13.5)
        p["head"]["flow_scale"] = 1.35
        k["intake_lift_mm"] = round(g["bore_mm"] * 0.14, 2)
        k["exhaust_lift_mm"] = round(k["intake_lift_mm"] * 0.95, 2)
        k["intake_duration_deg"] = round(k["intake_duration_deg"] + 12)
        k["exhaust_duration_deg"] = round(k["exhaust_duration_deg"] + 4)
        g["rod_length_mm"] = round(2.6 * g["stroke_mm"], 1)
        g["piston_mass_g"] = round(max(60.0, g["piston_mass_g"] * 0.9))
        g["rod_mass_g"] = round(g["piston_mass_g"] * 1.2)
        e = p["engine"]
        e["dyno_min_rpm"] = round(e["redline_rpm"] * 0.2 / 100) * 100
        e["simulation_frequency"] = int(max(e["simulation_frequency"],
                                            min(120000 / n, e["redline_rpm"] / 60 * 100) // 500 * 500))
        p["ignition"]["timing"] = [[r, min(40.0, 18 + 4 * r / 1000)]
                                   for r in range(0, int(p["ignition"]["rev_limit_rpm"]) + 2001, 1000)]
        p["fuel"].update(max_burning_efficiency=1.0, burning_efficiency_randomness=0.15)
        p["intake"]["runner_length_in"] = 6.0


_ADJECTIVES = ["Angry", "Sleepy", "Turbo-less", "Grumpy", "Screaming", "Lumpy", "Tiny", "Mighty",
               "Wobbly", "Thunder", "Buzzy", "Rusty", "Feral", "Cosmic"]
_NOUNS = ["Hornet", "Toaster", "Badger", "Kettle", "Comet", "Goose", "Blender", "Mule",
          "Rocket", "Walrus", "Lawnmower", "Dragon", "Pickle", "Bumblebee"]


def random_settings():
    t = random.choice(list(ENGINE_TYPES))
    lo, hi = size_range(t)
    size = round(math.exp(random.uniform(math.log(max(lo, 0.3)), math.log(hi))), 2)
    per = size / cylinders_for(t)
    # small cylinders rev higher
    rev_hi = _clamp(15000 - per * 9000, 5000, 15000)
    rev = int(random.uniform(4500, rev_hi) // 250 * 250)
    return {
        "name": f"{random.choice(_ADJECTIVES)} {random.choice(_NOUNS)}",
        "type": t,
        "size_l": size,
        "rev_limit": rev,
        "sound": random.randint(10, 100),
        "cam": random.randint(0, 100),
        "feel": random.randint(0, 100),
        "vehicle": random.choice(list(VEHICLES)),
        "tune": "None",
    }
