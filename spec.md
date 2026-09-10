# Peer-coordinated traffic intersection

## Problem

Build a small local distributed-system simulation for a four-way intersection. Four independent road processes coordinate their lights without a central controller. Each process generates local cars, maintains a bounded queue, and participates in consensus. A live browser view shows cars and reports unsafe vehicle movement such as two roads admitting cars at once.

## Decisions

- **Four peer processes.** North, east, south, and west run as independent processes and coordinate directly.
- **One shared Python program.** The same `junction.node` module powers every road. A process argument supplies its identity.
- **One main thread per process.** Process and network boundaries provide the distribution.
- **Leader-based consensus.** Peers elect a leader automatically using terms, votes, randomized election timeouts, heartbeats, majority replication, and stale-log checks.
- **Full-mesh TCP with JSONL.** Every peer has one full-duplex connection to every other peer. Addresses are configured at startup.
- **Durable consensus state.** Each peer persists its own term, vote, log, and committed index. There is no shared state file.
- **Fail closed.** A restarted peer remains red until it catches up. A new phase cannot begin until all four peers report the previous all-red barrier.
- **One road at a time.** The normal order is `north → east → south → west → repeat`. Empty roads are skipped.
- **Fixed timings.** Green lasts 5 seconds, yellow lasts 1.5 seconds, and all-red clearance lasts 1 second. Heartbeats run every 350 milliseconds. Election timeouts range from 1.2 to 2.2 seconds.
- **One committed cycle.** A phase entry contains the selected road, start time, timing periods, next round-robin position, and selection reason. Every peer derives its light color from that entry.
- **Natural car flow.** The selected road admits one queued car per second during green. Cars take one second to cross. Green controls entry; a car already admitted finishes.
- **Moderate random demand.** Each road generates one car every 6 to 12 seconds by default. This is slower than the original rate and should keep healthy queues below capacity over time.
- **Bounded queues.** Each road holds at most 20 cars. A full queue drops new arrivals and records the drop locally.
- **Simple load adaptation.** A road with at least 10 queued cars may jump ahead. Green duration remains fixed.
- **Cars are ephemeral.** Queued cars are local simulation state and are lost when their road process restarts. Consensus state remains durable.
- **Read-only visualizer.** `junction.visualizer` connects to every road, serves the browser, and streams updates. It never votes or changes traffic state.
- **Code-level crash detection.** The visualizer checks structured movement events and reported lights. SVG only renders the result.
- **Continue after crashes.** A detected collision is logged and shown without stopping the simulation.

## Data shapes

### Consensus log entry

A committed phase contains:

- phase identifier
- selected road
- start time
- green, yellow, and all-red durations
- next round-robin road
- selection reason
- consensus term and log index

### Local car state

A car has a local identifier, owning road, arrival time, and lifecycle state. Movement events include its start and finish times.

### Peer messages

JSONL peer messages cover elections, votes, heartbeats, log replication, acknowledgements, and queue summaries.

### Visualization updates

Roads publish signal changes, queue counts, car movements, peer status, leader state, and consensus position.

### Crash event

A crash identifies the cars, their roads and phases, the intersection center, and the overlapping time interval.

## Behaviors

### Startup and recovery

1. The launcher starts four `junction.node` processes and `junction.visualizer`.
2. Every road loads its own persistent consensus state and starts red.
3. Peers establish the TCP mesh and compare log positions.
4. The peers elect a leader when none exists.
5. A recovering peer stays red until a valid leader catches it up.
6. All four peers must reach the same all-red barrier before another green begins.

### Phase selection

1. Green ends and the selected road stops admitting cars.
2. Yellow runs for 1.5 seconds.
3. Every vehicle light becomes red.
4. The 1-second clearance period completes.
5. The leader reads the four queue summaries.
6. It chooses the next nonempty road in round-robin order, unless a queue of 10 or more cars receives the heavy-traffic override.
7. The leader replicates the phase decision.
8. After commitment, the selected road receives 5 seconds of green.

If every queue is empty, all lights remain red until a car arrives.

### Car movement

Each road generates cars independently every 6 to 12 seconds. A road queues arrivals up to the 20-car limit. During its green phase, it releases cars at one-second intervals. No car may start during yellow or red.

### Crash detection

The visualizer reports:

- **Concurrent green:** fresh state from more than one road says green.
- **Invalid movement:** a car starts without a matching green phase for its road.
- **Car collision:** cars from different roads occupy the intersection center during overlapping intervals.

The Python collision checker reports the property through the Antithesis SDK. Browser JavaScript shows the crash marker and log entry.

### Logs and visualization

Each road writes `consensus.json` and `events.jsonl` under `data/<road>/`. The visualizer writes incidents under `data/visualizer/`.

The browser shows four vertical traffic lights, one in each road arm, plus moving cars, queues, the leader, term, committed index, peer status, and crash history.

## Implementation checklist

- [x] Run north, east, south, and west from one configurable Python entrypoint.
- [x] Implement bounded local car queues and moderate random arrivals.
- [x] Admit one car per second during a five-second green.
- [x] Record local arrivals, movements, drops, and process events.
- [x] Implement the full-mesh TCP JSONL protocol.
- [x] Implement automatic leader election, terms, votes, and heartbeats.
- [x] Implement durable logs, majority replication, commitment, and restart replay.
- [x] Keep recovering peers red until they catch up.
- [x] Require all four peers at the all-red barrier before the next phase.
- [x] Implement round-robin selection, empty-road skipping, and the 10-car override.
- [x] Implement the read-only visualizer and live Server-Sent Events feed.
- [x] Render four vertical road signals and animated cars in SVG.
- [x] Detect concurrent greens, invalid movement, and overlapping car paths in `junction.visualizer`.
- [x] Render and log car collision incidents.
- [x] Add process supervision, tests, startup documentation, and reset tooling.
- [x] Remove pedestrian generation, state, protocol messages, scheduling, collision rules, tests, and UI.
- [x] Split the road entrypoint into focused road, consensus, peer-network, storage, scheduler, and phase modules without changing behavior.
- [x] Add direct tests for majority election, phase commitment, persistent-state round trips, and corrupt-state failure.
- [x] Add a local Antithesis container layout with one container per road, a workload container, setup signaling, controlled car inputs, and official Python SDK assertions.

## Progress log

- 2026-09-02: Created the initial specification from the design discussion. No implementation had started.
- 2026-09-06: Kept random car and pedestrian generation inside each road peer. Removed the separate arrival-source proposal.
- 2026-09-06: Implemented the first complete simulator and verified startup, replication, movement, and peer restart.
- 2026-09-06: Removed pedestrians from the product and code. Slowed car generation to one arrival per road every 6 to 12 seconds and simplified the intersection around four vertical signals.
- 2026-09-06: Split the runtime into focused road, consensus, networking, storage, scheduler, and phase modules. Refined the live SVG using external SVG accessibility and animation guidance.
- 2026-09-06: A read-only review found a skipped release slot during recovery, unsafe fallback on corrupt consensus files, incomplete SVG cleanup, and missing core tests. Fixed all four and reran the test and smoke suites.
- 2026-09-06: Converted the backend, tests, and workload to Python. The official Antithesis SDK now owns properties, random choices, and setup signaling.

## Out of scope

- Pedestrians and crosswalk controls.
- Turning vehicles.
- A central traffic controller or shared state file.
- Adaptive green duration or complex scheduling scores.
- Physics or pixel-based collision detection.
- Antithesis integration and test-specific hooks.
- A production-grade consensus implementation.

## Open questions

- None for the car-only version.
