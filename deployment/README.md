# Antithesis setup

The Compose layout runs four road containers, the read-only visualizer, and a workload container. The application and workload import the official `antithesis` Python SDK.

## Run locally

```bash
make antithesis-build
make antithesis-up
```

Open <http://127.0.0.1:8080>.

In another terminal, run a workload command:

```bash
docker compose -f deployment/config/docker-compose.yaml exec workload \
  /opt/antithesis/test/v1/traffic/parallel_driver_add_car.py

docker compose -f deployment/config/docker-compose.yaml exec workload \
  /opt/antithesis/test/v1/traffic/anytime_check_state.py

docker compose -f deployment/config/docker-compose.yaml exec workload \
  /opt/antithesis/test/v1/traffic/eventually_check_recovery.py
```

Stop and remove local test data:

```bash
make antithesis-down
```

## Images

- `junction-four-app` runs a road or the visualizer.
- `junction-four-workload` contains setup code and test commands.
- `junction-four-config` contains `/docker-compose.yaml`.

Build the config image with:

```bash
docker build -t junction-four-config:local deployment/config
```

Before upload, replace local image names in `config/docker-compose.yaml` with tenant registry names and push all three images.

Python files under `/app/junction` are linked into `/opt/antithesis/catalog` so Antithesis can catalog SDK assertions. The Python SDK currently supports assertion cataloging but not Python coverage instrumentation.
