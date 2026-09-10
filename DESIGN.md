---
name: Junction Four
description: A laboratory traffic analyzer for a distributed intersection.
colors:
  bench: "#d9ddd7"
  enamel: "#f4f3ea"
  enamel-deep: "#e7e7dc"
  ink: "#17211f"
  muted: "#5a6661"
  instrument: "#1a2624"
  road: "#263231"
  safe-green: "#1f8a58"
  luminous-green: "#5de38d"
  caution-yellow: "#d69a22"
  luminous-yellow: "#ffd45c"
  incident-red: "#bd3834"
  luminous-red: "#ff6f64"
  data-blue: "#246589"
typography:
  display:
    fontFamily: "Avenir Next, Avenir, Segoe UI, Helvetica, Arial, sans-serif"
    fontSize: "clamp(2rem, 4vw, 3.6rem)"
    fontWeight: 800
    lineHeight: 0.9
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Avenir Next, Avenir, Segoe UI, Helvetica, Arial, sans-serif"
    fontSize: "clamp(1.55rem, 2.2vw, 2.25rem)"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "-0.03em"
  body:
    fontFamily: "Avenir Next, Avenir, Segoe UI, Helvetica, Arial, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 400
    lineHeight: 1.4
  data:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.8rem"
    fontWeight: 700
    lineHeight: 1.2
rounded:
  readout: "6px"
  scope: "10px"
  module: "14px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "20px"
  lg: "28px"
  xl: "42px"
components:
  intersection-module:
    backgroundColor: "{colors.enamel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.module}"
    padding: "{spacing.lg}"
  phase-readout:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.luminous-green}"
    typography: "{typography.data}"
    rounded: "{rounded.readout}"
    padding: "8px 12px 10px"
  telemetry-rail:
    backgroundColor: "{colors.instrument}"
    textColor: "{colors.enamel}"
    rounded: "{rounded.module}"
    padding: "{spacing.lg}"
---

# Design system: Junction Four

## Overview

**Creative North Star: "The Bench Instrument"**

Junction Four looks like a traffic analyzer on an engineering bench. A pale enamel instrument face holds the intersection. The dark diagnostic rail carries authority, terms, queues, and incidents. The live geometry gets the space; status text stays compact and exact.

The interface is dense enough to inspect without looking like a generic monitoring dashboard. Signal color appears where it has operational meaning. Labels, positions, and shapes repeat the same state for users who cannot rely on color.

**Key characteristics:**

- One large live instrument face beside a narrow diagnostic rail.
- Cool enamel and graphite surfaces with sparse signal color.
- Tabular data readouts separated from ordinary explanatory text.
- Crisp SVG geometry and linear movement rather than decorative illustration.

## Colors

The palette comes from enamel equipment, asphalt, and real signal lamps.

### Primary

- **Instrument graphite:** Main telemetry surface and dark readouts.
- **Luminous green:** Active permission, connected peers, and elected authority.

### Secondary

- **Caution yellow:** Vehicle path and warning state.
- **Incident red:** Collisions, invalid permissions, and failed connections.
- **Data blue:** Queue values on the pale instrument face.

### Neutral

- **Bench gray:** Page ground.
- **Enamel:** Main instrument surface and queue labels.
- **Road charcoal:** Intersection geometry.
- **Muted steel:** Secondary copy, rules, and inactive equipment.

**The Signal Color Rule.** Green, yellow, and red only describe permission, caution, or failure. Do not use them as decoration.

## Typography

The interface uses a workhorse humanist sans for names and explanation. A system monospace carries time, terms, queue values, phase reasons, and machine state.

### Hierarchy

- **Authority display:** Heavy condensed readout treatment for the elected leader.
- **Surface headline:** Tight, bold sentence case for the live intersection.
- **Body:** Compact sans text for phase explanation and labels.
- **Data:** Tabular monospace for values and protocol state.
- **Instrument label:** Small uppercase sans for fixed register names.

**The Data Voice Rule.** Use monospace only for values produced by the running system.

## Layout

Desktop uses an asymmetric two-column workbench. The intersection takes the flexible column, while the diagnostic rail stays between 292 and 380 pixels. The layout stacks below 1030 pixels. On narrow screens the intersection remains first, the header drops nonessential status copy, and telemetry follows at full width.

Spacing moves through 8, 12, 20, 28, and 42 pixel steps. Tight values join a label to its reading. Larger values separate instrument regions.

## Elevation & Depth

The main module and telemetry rail use one ambient shadow with a visible downward offset. The SVG scope uses an inset shadow to read as recessed equipment. Internal registers rely on tonal changes and rules, not additional floating layers.

**The One Chassis Rule.** A major region may have one border or one shadow treatment. Do not nest raised cards inside it.

## Shapes

Major modules use 14-pixel corners. The recessed scope uses 10 pixels, and readouts use 6 to 8 pixels. All four signal housings use the same compact vertical shape. Pills are absent because no control needs that affordance.

## Components

### Intersection module

A pale enamel chassis with a recessed dark scope. Its heading and phase readout share one ruled header. The SVG fills the available width at a 4:3 ratio.

### Traffic signal

A vertical dark housing contains three fixed bulbs. All four roads use the same orientation and size. The road letter remains visible below the housing, so color never identifies the signal alone.

### Phase readout

A compact near-black display uses luminous green for the active stage and muted gray for the countdown.

### Telemetry rail

A dark continuous rail holds consensus authority, peers, and incidents. Fine horizontal rules separate registers. The leader name is the only oversized value.

### Safety register

The empty state is quiet and centered. Incidents switch to red timestamps and plain-language descriptions. A live critical incident also appears on the intersection itself.

## Do's and Don'ts

### Do:

- **Do** give the live intersection more space than protocol metadata.
- **Do** pair every signal color with a road label and fixed bulb position.
- **Do** reserve monospace for measured or protocol-generated values.
- **Do** keep the browser visibly read-only.

### Don't:

- **Don't** turn telemetry into a grid of interchangeable metric cards.
- **Don't** use signal colors for unrelated decoration.
- **Don't** add controls that imply the observer can change consensus state.
- **Don't** replace logical SVG movement with pixel-based collision checks.
