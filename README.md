# Engine-Sim EngineBuilder

@ange-yaghi

A simple desktop GUI for building engines for
[engine-sim](https://github.com/ange-yaghi/engine-sim) without hand-writing `.mr` scripts.
Pick a few sliders (or every single parameter), hit **Build & Launch**, and drive it.

This repo contains only the builder. You need your own copy of engine-sim.

## Features

- **Simple mode**: engine type, size, rev limit, sound, cam, feel and vehicle sliders, plus
  presets (Super Snappy, Muscle V8, Eco 1.8 Atkinson, Torque Monster 7.4 V8, Top Speed 4.5 V8,
  F1 V10 20k) and "special tune" recipes. A live health check and an expected dyno line update
  as you drag.
- **Advanced mode**: every engine-sim parameter on tabs:
  - engine, fuel, bottom end, layout and cylinders, head and port flow, camshaft, intake,
    exhaust, ignition timing curve, vehicle, transmission
  - any layout: single, inline, V, boxer, multi-bank. Crank journals, cam lobes and ignition
    are phased automatically from the firing order.
  - a **Check** tab that flags things engine-sim can't handle (see below)
  - a **Dyno estimate** tab with an expected torque/power curve
  - a live `.mr` preview
- **Edit existing engine**: open any engine in `assets/engines`, tweak its numbers, and save a
  clone. Originals are never changed. There are one-click redline/limiter bumps, and every
  editable number is listed.
- **Launch engine-sim** from the builder. If engine-sim reports a script error, it pops up with
  the file and line.

See [FEATURES.md](FEATURES.md) for a full description of everything the app does.

## Requirements

- Windows (engine-sim is Windows-only)
- Python 3.9 or newer from [python.org](https://www.python.org/). Tkinter is included.
- engine-sim. Tested with v0.1.14a.

## Install

1. Copy the `engine_builder` folder into your engine-sim folder, next to `assets`, `bin` and `es`:
   ```
   engine-sim/
     assets/
     bin/
     es/
     engine_builder/   <- here
   ```
2. Double-click `engine_builder/Engine Builder.bat`, or run `py engine_builder/engine_builder.py`.

Engines are saved to `assets/engines/custom/<name>.mr`, with a `.json` project next to each one so
you can reopen it later. With "Make what I save the startup engine" ticked, engine-sim opens the
new engine the next time it starts. Otherwise use engine-sim's **Load Engine** button.

In engine-sim, **A** turns on the ignition, hold **S** for the starter, and **R** is full throttle.
**D** runs the dyno and **I** shows peak power and torque.

## Examples

- `examples/engines`: ready-made engines. Copy them into `assets/engines/custom`. Open the
  `.json` files in Advanced mode to edit them.
- `examples/themes`: engine-sim's default theme with km/h + Nm + kW (`default_kph.mr`) or km/h + Nm + hp
  (`default_kph_hp.mr`). Copy them into `assets/themes` and pick one with engine-sim's **Load Theme**.

## Things engine-sim can't do (and the Check tab warns about)

engine-sim hard-codes some physics in absolute units, tuned for car-sized engines:

- **Piston-ring friction** is a fixed 50 N + 20 N per m/s per piston. Engines with bores under
  about 50 mm lose most of their power to it, so tiny model engines can't run at their real size.
- **The constraint solver** has a fixed error tolerance, so pistons or rods under about 50 g jitter.
- **Combustion speed** follows piston speed, so very oversquare engines (big bore, short stroke)
  burn too slowly. The builder adds a **Flame speed multiplier** for this (set automatically in
  Simple mode).
- **No turbos, superchargers or diesels.**

The dyno estimate is a simplified copy of engine-sim's physics, so treat it as a ballpark.
engine-sim's own dyno is the real answer.

## Not affiliated

This is a fan-made tool and isn't affiliated with engine-sim or its author.
