# Codebase orientation

## Current mental model

1. A workload sends `POST /cars` to one road.
2. That road owns the car in its local queue.
3. The elected leader gathers queue reports after all roads report all-red.
4. The leader chooses a road and replicates a phase command.
5. A majority commit makes the phase authoritative.
6. Every road derives its light from the same committed phase and clock.
7. The selected road emits a movement event.
8. The visualizer checks the movement and sends browser updates.

## Files to revisit

- `junction/road.py`: joins queueing, consensus, phases, and movement.
- `junction/consensus.py`: election and replicated-log rules.
- `junction/peer_network.py`: JSONL transport.
- `junction/visualizer.py`: external property checker and browser server.

## Retrieval prompts

- Why can only the leader propose a phase?
- Why does a phase start 500 ms in the future?
- What exact evidence must exist before another green?
- Which checks are local, and which require the visualizer?
