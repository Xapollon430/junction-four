# Junction Four

A local four-peer traffic intersection written in Python. Four road processes elect a leader, replicate phase decisions, generate local car demand, and fail closed when they cannot agree. A separate read-only observer checks traffic safety and serves the live SVG browser view.

## Run it

Python 3.11 or newer is required.

```bash
python3 -m pip install -r requirements.txt
make start
```

Open <http://127.0.0.1:8080>. Stop everything with `Ctrl+C`.

## Useful commands

```bash
make check                # compile-check Python files
make reset                # remove persistent state
make antithesis-build     # build the app and workload images
make antithesis-up        # run the container layout
make antithesis-down      # stop containers and delete their test data
```

To run processes separately:

```bash
python3 -m junction.node --id north
python3 -m junction.node --id east
python3 -m junction.node --id south
python3 -m junction.node --id west
python3 -m junction.visualizer
```

## Code map

```text
junction/node.py          starts one configured road
junction/road.py          queues, lights, cars, and phase scheduling
junction/consensus.py     elections, replicated logs, and commits
junction/peer_network.py  TCP connections and message delivery
junction/storage.py       persistent consensus state and event logs
junction/road_api.py      health and workload car endpoints
junction/scheduler.py     round-robin and heavy-queue selection
junction/phase.py         green, yellow, and all-red timing
junction/visualizer.py    observer, SDK properties, HTTP, and SSE
public/                   live browser view
deployment/               Antithesis images, Compose, and test template
```

## Traffic behavior

Only one road receives green at a time. Green lasts 5 seconds, yellow lasts 1.5 seconds, and the all-red clearance lasts 1 second. Cars cross once per second during green. Queues hold 20 cars. A queue of 10 or more may jump the normal north, east, south, west order.

Each peer stores its own term, vote, replicated log, commit index, and event history under `data/<road>/`. A recovering peer stays red until it synchronizes with the current leader.

## Safety checks

The project uses the official Antithesis Python SDK directly:

- `antithesis.assertions` reports local consensus and traffic properties.
- `antithesis.random` supplies election and arrival randomness.
- `antithesis.lifecycle` marks setup complete in the workload container.

The observer checks reported state and movement intervals, not SVG pixels. The browser remains read-only.

## Antithesis layout

The Docker layout runs every road in its own container so Antithesis can fault links and peers separately. Automatic arrivals are disabled there. The workload uses `antithesis.random.random_choice` to select a road, then sends `POST /cars` to that road.

See [`deployment/README.md`](deployment/README.md) for local commands and image details.
