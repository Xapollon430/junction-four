# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python 3.11, the Antithesis Python SDK, HTML, CSS, browser JavaScript, and SVG. No frontend framework is required.

## Users

The primary user is a developer running the simulator locally to watch a small distributed system coordinate an intersection and to spot unsafe behavior during failures.

## Product purpose

The simulator makes leader election, replicated phase decisions, car demand, and safety failures visible in one live intersection. Success means the user can run the system, understand which peer controls the current phase, and see when cars from incompatible roads move at the same time.

## Positioning

Four road processes own their local traffic and coordinate as peers. The browser is an observer, not a hidden traffic controller. Collision checks use reported process state and logical paths rather than SVG pixels.

## Operating context

The user launches four local road processes and one visualizer process. A browser stays open while cars appear, phases change, leaders fail or recover, and the crash log updates.

## Capabilities and constraints

- One shared Python module powers the north, east, south, and west peers.
- Peers communicate over direct TCP with JSONL messages.
- A small leader-based consensus protocol orders traffic phases.
- One road receives green at a time, for five seconds.
- Cars arrive locally every 6 to 12 seconds, queue up to 20, and cross at one-second intervals.
- A separate Python visualizer process serves and powers a live HTML/CSS/SVG view.
- The visualizer detects invalid vehicle permissions and overlapping car paths in code.
- The first implementation has no Antithesis-specific integration.

## Evidence on hand

The agreed behavior and architecture live in `spec.md`. There are no existing logos, brand assets, screenshots, benchmarks, or customer claims.

## Product principles

- Keep the distributed behavior real and the local implementation readable.
- Show the difference between consensus permission, local signal color, and car movement.
- Fail closed when a peer cannot confirm current control state.
- Make unsafe states obvious without letting the observer control the simulation.
- Prefer a small explainable model over traffic realism.

## Accessibility & inclusion

Signal states must use labels and shapes in addition to color. The dashboard must support keyboard navigation, reduced motion, and narrow screens.
