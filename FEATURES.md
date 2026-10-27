# EngineBuilder features

EngineBuilder has three modes, picked from the bar at the top of the window: **Simple**,
**Advanced** and **Edit existing engine**. The same bar holds two controls that work in every
mode:

- **Make what I save the startup engine**: engine-sim opens your newest engine the next time it
  starts.
- **Launch engine-sim**: starts engine-sim, then watches its error log. If the engine script has
  a mistake, a popup shows the error with the file name and line number. If it loads cleanly,
  the status bar says so and reminds you of the controls.

The builder remembers which mode you were in and your Simple-mode sliders between sessions.

---

## Simple mode

Build an engine in a few clicks without knowing anything about cars.

### Controls
| Control | What it does |
|---|---|
| **Preset** | Loads a ready-made engine you can then tweak (see below). |
| **Name** | Shown in engine-sim and used as the file name. Leave blank for an automatic name. |
| **Engine type** | 16 layouts: single, 270° twin, Harley-style 45° V-twin, Ducati-style 90° V-twin, inline 3/4/5/6, flat 4, flat 6, V6, cross-plane V8, flat-plane V8, V10, V12, and a "2-stroke sound" 360° twin. |
| **Size** | Total displacement. The range adapts to the engine type so every cylinder stays a size engine-sim can run. Shows the resulting bore × stroke. |
| **Rev limit** | 2,500–21,000 rpm. Higher limits automatically get a shorter stroke, like real high-revving engines. |
| **Sound** | Quiet ↔ loud. Picks the exhaust character (muffled → open), pipe length and loudness. |
| **Cam** | Smooth idle ↔ lumpy race cam. More duration, lift and overlap give more top-end power and a choppier idle. |
| **Feel** | Heavy & smooth ↔ light & snappy. Sets flywheel weight, piston/rod weight, airbox size, friction and how crisply the rev limiter cuts. The top fifth of the slider is an "instant" race zone. |
| **Vehicle** | Go-kart, motorcycle, car, sports car, truck, eco hatchback, top-speed GT, F1 car. The last three work out their gear ratios from the engine's redline. |
| **Special tune** | An extra recipe on top of the sliders: **Eco** (Atkinson cycle, 13:1, lean burn), **Torque** (long stroke, long intake runners), **Top speed** (12.5:1, big ports), **F1** (huge bore, short stroke, 13.5:1, light parts). Tunes keep working when you move other sliders. |

### Presets
- **Super snappy**: 1.0 L superbike-style inline-4, 15,000 rpm, almost no flywheel, so it hits
  redline almost instantly.
- **Muscle V8**: the default 5.7 L cross-plane V8.
- **Eco 1.8 Atkinson**: Prius-style fuel saver in a slippery hatchback with tall gears.
- **Torque Monster 7.4 V8**: long-stroke big block in a truck.
- **Top Speed 4.5 V8**: flat-plane V8 revving to 9,000 in a low-drag GT geared for about 345 km/h.
- **F1 V10 20k**: 2005-style Formula 1 V10, 98 × 39.8 mm, 20,500 rpm limiter, in an F1 car.

### Buttons and live readouts
- **Surprise me!**: a random engine with a silly name.
- **BUILD & LAUNCH**: saves the engine and opens it in engine-sim in one click.
- **Build only**: saves it without launching.
- **Fine-tune in Advanced**: opens the same engine in Advanced mode with every detail editable.
- **Health line**: green when engine-sim should run the engine happily. Orange for warnings,
  red for problems, with the reason.
- **Facts line**: cylinders, displacement, redline, flywheel inertia and the file it will save as.
- **Expected dyno**: estimated peak power (kW and hp) and torque (Nm and lb-ft) with rpm.
  Recalculated in the background as you drag.

---

## Advanced mode

Every engine-sim parameter, on tabs. Use **New**, **Open project**, **Save project as** and
**GENERATE .mr** from the toolbar.

### Tabs
- **Engine**: name, redline, starter torque/speed, dyno range, throttle response, simulation
  frequency and solver steps, and audio settings (convolution, high-frequency gain, jitter,
  noise).
- **Check**: an engine-sim health report (see below).
- **Dyno estimate**: an expected torque and power curve against rpm, with the peaks marked and
  listed in kW, hp, Nm and lb-ft.
- **Fuel**: fuel presets (gasoline, methanol, ethanol) and every fuel property: energy density,
  mixture, burn efficiency, turbulence and dilution effects, and the **flame speed multiplier**.
- **Bottom end**: bore, stroke, rod length and mass, piston mass and compression height, deck
  clearance, blowby. Also crankshaft and flywheel mass, friction, and moment of inertia
  (calculated or entered by hand). A "target compression ratio" button sets the chamber volume
  for you.
- **Layout & cylinders**: layout presets, any number of cylinder banks at any angle and position,
  cylinder numbering, firing order, and automatic even-fire or manual crank journals. Per-cylinder
  header length, sound attenuation and blowby. Shows the calculated crank, journal angles, firing
  angles and firing intervals.
- **Head & ports**: chamber volume, intake and exhaust runner volumes and sizes, and editable
  intake and exhaust port-flow tables.
- **Camshaft**: duration, lift and shape for intake and exhaust lobes, lobe centers, advance and
  base radius. Lobes for every bank are phased automatically from the firing order.
- **Intake**: plenum, throttle body, runners, idle air, throttle response and mixture (lambda).
- **Exhaust**: one shared exhaust or one per bank, flows, pipe lengths, collector, volume and the
  exhaust sound (impulse response).
- **Ignition**: rev limiter, limiter cut time and an editable timing advance curve.
- **Vehicle**: mass, drag, frontal area, final drive, tyres, rolling resistance, brakes, tyre
  grip, wheelbase, track, center of mass and driveline flex.
- **Transmission**: clutch strength and flex, and any number of gears.
- **Preview .mr**: the exact script that GENERATE will write.

### The Check tab
Warns about things engine-sim can't handle, because some of its physics is hard-coded for
car-sized engines:

- Piston-ring friction eating most of the power (small bores or very high piston speed).
- Pistons or rods light enough to make the physics solver jitter.
- Cams where the valves are open so long the cylinder can't build compression, effective
  compression ratio, and cam lift running past the port-flow table.
- Too few simulation steps per revolution, or a simulation load your PC may not keep up with.
- Combustion too slow for the bore and stroke (with a suggested flame speed multiplier).
- Mixtures engine-sim won't ignite.
- Exhaust sound levels likely to be too quiet or distorted.
- Layout and firing order mistakes.

Also shows displacement, geometric and effective compression, valve events, seat-to-seat
durations, crank inertia, mean piston speed and the full firing table. GENERATE asks before
saving an engine with serious problems.

---

## Edit existing engine

Change any engine in `assets/engines`, including engine-sim's built-in ones, without writing code.

- **Engine list**: every runnable engine, grouped by folder.
- **Engine name**: rename the copy.
- **Rev buttons**: −500, +500, +1,000 and +2,000 rpm change the redline and rev limiter together.
  A note tells you how many simulation steps per revolution engine-sim will get at the new
  limit, and suggests a higher simulation frequency if needed.
- **Friendly list**: the settings most people want, grouped. That covers rev limits, starting and
  idle, ignition timing, sound, gearbox, vehicle, cam, engine and simulation.
- **Show every number in the file**: every editable number, labeled with its line and where it
  sits in the script.
- **Save as clone**: writes a copy to `assets/engines/custom`. Only the numbers you changed are
  edited; the rest of the file is copied exactly. Originals are never modified. Imports of
  helper files are re-pointed so the copy still loads. Numbers engine-sim can't read, like `.5`,
  are fixed automatically.
- **Save changes to this clone**: updates a copy you made earlier.
- **Open in Advanced mode**: for engines made with the builder, reopens the full project.

---

## Files

- `engine_builder.py`: the GUI.
- `mr_gen.py`: the engine project format, `.mr` generator and Check-tab analysis.
- `simple_mode.py`: Simple-mode sliders, presets, tunes and vehicles.
- `mr_edit.py`: reading and safely patching existing `.mr` files for Edit mode.
- `dyno_estimate.py`: the expected dyno model (a one-cylinder cycle simulation using
  engine-sim's cam, port-flow, flame, friction and heat-loss formulas).
- `Engine Builder.bat`: double-click launcher.

Each engine is saved as `<name>.mr` (what engine-sim loads) plus `<name>.json` (the project file
the builder reopens).
