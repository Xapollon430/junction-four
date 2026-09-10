// Renders observer data. Nothing in this file can command a road process.
const ROADS = ['north', 'east', 'south', 'west'];
const SVG_NS = 'http://www.w3.org/2000/svg';

const state = {
  nodes: {},
  connections: Object.fromEntries(ROADS.map((road) => [road, false])),
  incidents: [],
};

const ui = Object.fromEntries([
  'connection-lamp', 'system-status', 'clock', 'phase-summary', 'phase-stage',
  'phase-countdown', 'leader-name', 'term-value', 'commit-value', 'reason-value',
  'peer-count', 'peer-list', 'incident-count', 'incident-list', 'movement-layer',
  'collision-layer', 'critical-banner', 'critical-message',
].map((id) => [id, document.querySelector(`#${id}`)]));

const activeCars = new Map();
let bannerTimer;

function title(value) {
  return value ? value[0].toUpperCase() + value.slice(1).replaceAll('_', ' ') : 'None';
}

function formatTime(timestamp) {
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  }).format(timestamp);
}

function leader() {
  return Object.values(state.nodes).find((node) => node.role === 'leader') || null;
}

function controlNode() {
  return leader() || Object.values(state.nodes).sort((a, b) => b.commitIndex - a.commitIndex)[0] || null;
}

// Update the fixed dashboard from the latest snapshots.
function renderSignals() {
  for (const road of ROADS) {
    const node = state.nodes[road];
    const light = node?.light || 'red';
    const signal = document.querySelector(`#signal-${road}`);
    signal.dataset.state = light;
    signal.setAttribute('aria-label', `${title(road)} traffic light is ${light}`);
    document.querySelector(`#queue-${road}`).textContent = node?.queueLength ?? '—';
  }
}

function renderPhase() {
  const node = controlNode();
  const phase = node?.currentPhase;
  const stage = node?.stage || 'all_red';
  ui['phase-stage'].textContent = stage.replace('_', ' ').toUpperCase();
  ui['reason-value'].textContent = phase?.reason?.replaceAll('_', ' ') || 'standby';

  if (!phase) ui['phase-summary'].textContent = 'Waiting for a committed phase';
  else if (stage === 'green') ui['phase-summary'].textContent = `${title(phase.road)} road has green`;
  else if (stage === 'yellow') ui['phase-summary'].textContent = `${title(phase.road)} road is changing to red`;
  else if (stage === 'recovering') ui['phase-summary'].textContent = 'Road process is recovering';
  else ui['phase-summary'].textContent = 'All roads are red';
}

function renderAuthority() {
  const elected = leader();
  const current = controlNode();
  ui['leader-name'].textContent = elected ? elected.id.toUpperCase() : 'ELECTING';
  ui['term-value'].textContent = String(current?.term ?? 0);
  ui['commit-value'].textContent = current ? String(current.commitIndex) : '−';
}

function renderPeers() {
  const online = ROADS.filter((road) => state.connections[road]).length;
  ui['peer-count'].textContent = `${online} / 4 online`;
  ui['peer-list'].replaceChildren();

  for (const road of ROADS) {
    const node = state.nodes[road];
    const connected = Boolean(state.connections[road]);
    const row = document.createElement('div');
    row.className = 'peer-row';
    row.dataset.connected = String(connected);
    row.dataset.light = node?.light || 'red';

    const lamp = document.createElement('i');
    lamp.setAttribute('aria-hidden', 'true');
    const name = document.createElement('strong');
    name.textContent = title(road);
    const detail = document.createElement('span');
    detail.textContent = connected && node
      ? `${node.role.toUpperCase()} · COMMIT ${node.commitIndex}`
      : 'OFFLINE';
    row.append(lamp, name, detail);
    ui['peer-list'].append(row);
  }
}

function renderHealth() {
  const online = ROADS.filter((road) => state.connections[road]).length;
  const elected = leader();
  const recentCrash = state.incidents.some((incident) => Date.now() - incident.at < 8_000);

  if (recentCrash) {
    ui['connection-lamp'].dataset.state = 'fault';
    ui['system-status'].textContent = 'Car collision recorded';
  } else if (online === 4 && elected) {
    ui['connection-lamp'].dataset.state = 'online';
    ui['system-status'].textContent = `All roads connected · ${title(elected.id)} leads`;
  } else if (online === 4) {
    ui['connection-lamp'].dataset.state = 'starting';
    ui['system-status'].textContent = 'All roads connected · choosing a leader';
  } else {
    ui['connection-lamp'].dataset.state = online === 0 ? 'fault' : 'starting';
    ui['system-status'].textContent = `${online} of 4 roads connected`;
  }
}

function renderIncidents() {
  ui['incident-count'].textContent = `${state.incidents.length} crash${state.incidents.length === 1 ? '' : 'es'}`;
  ui['incident-list'].replaceChildren();
  if (state.incidents.length === 0) {
    const item = document.createElement('li');
    item.className = 'empty-register';
    item.innerHTML = '<svg viewBox="0 0 32 32" aria-hidden="true"><path d="m7 16 6 6L26 8"/></svg><span>No car collisions detected</span>';
    ui['incident-list'].append(item);
    return;
  }

  for (const incident of [...state.incidents].reverse().slice(0, 8)) {
    const item = document.createElement('li');
    item.className = 'incident-item';
    const time = document.createElement('time');
    time.dateTime = new Date(incident.at).toISOString();
    time.textContent = formatTime(incident.at);
    const kind = document.createElement('strong');
    kind.textContent = incident.kind.replaceAll('_', ' ');
    const message = document.createElement('span');
    message.textContent = incident.message;
    item.append(time, kind, message);
    ui['incident-list'].append(item);
  }
}

function render() {
  renderSignals();
  renderPhase();
  renderAuthority();
  renderPeers();
  renderHealth();
  renderIncidents();
}

function updateCountdown() {
  const node = controlNode();
  const phase = node?.currentPhase;
  if (!phase) {
    ui['phase-countdown'].textContent = 'standby';
    return;
  }
  let end = phase.startAt + phase.greenMs + phase.yellowMs + phase.allRedMs;
  if (node.stage === 'green') end = phase.startAt + phase.greenMs;
  if (node.stage === 'yellow') end = phase.startAt + phase.greenMs + phase.yellowMs;
  ui['phase-countdown'].textContent = `${(Math.max(0, end - Date.now()) / 1_000).toFixed(1)} s`;
}

function svg(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

// Cars animate from reported movement events. Their pixels are only a display.
function carPath(road) {
  return {
    north: { from: [362, -52], to: [362, 652], horizontal: false },
    east: { from: [852, 262], to: [-52, 262], horizontal: true },
    south: { from: [416, 652], to: [416, -52], horizontal: false },
    west: { from: [-52, 316], to: [852, 316], horizontal: true },
  }[road];
}

function removeCar(entityId, group) {
  activeCars.delete(entityId);
  group.remove();
}

function animateCar(group, path, event) {
  const now = Date.now();
  if (now >= event.endsAt) return removeCar(event.entityId, group);
  const progress = Math.max(0, Math.min(1, (now - event.startedAt) / (event.endsAt - event.startedAt)));
  const current = [
    path.from[0] + (path.to[0] - path.from[0]) * progress,
    path.from[1] + (path.to[1] - path.from[1]) * progress,
  ];

  if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
    group.setAttribute('transform', 'translate(400 300)');
    setTimeout(() => removeCar(event.entityId, group), event.endsAt - now);
    return;
  }

  const animation = group.animate([
    { transform: `translate(${current[0]}px, ${current[1]}px)` },
    { transform: `translate(${path.to[0]}px, ${path.to[1]}px)` },
  ], { duration: event.endsAt - now, easing: 'linear', fill: 'forwards' });
  animation.onfinish = () => removeCar(event.entityId, group);
}

function spawnCar(event) {
  if (event.entityType !== 'car' || activeCars.has(event.entityId) || Date.now() >= event.endsAt) return;
  const path = carPath(event.road);
  if (!path) return;
  const group = svg('g', { class: 'vehicle-entity' });
  group.dataset.entityId = event.entityId;
  const width = path.horizontal ? 44 : 24;
  const height = path.horizontal ? 24 : 44;
  group.append(
    svg('rect', { x: -width / 2, y: -height / 2, width, height, rx: 5 }),
    svg('path', path.horizontal ? { d: 'M-9-10h18l5 7h-28z' } : { d: 'M-10-9 0-15 10-9v8h-20z' }),
  );
  ui['movement-layer'].append(group);
  activeCars.set(event.entityId, group);
  animateCar(group, path, event);
}

function showIncident(incident) {
  state.incidents.push(incident);
  if (state.incidents.length > 200) state.incidents.shift();

  for (const entityId of incident.entities || []) {
    const car = activeCars.get(entityId);
    if (!car) continue;
    car.classList.add('crashed');
    for (const animation of car.getAnimations()) animation.pause();
    setTimeout(() => removeCar(entityId, car), 3_000);
  }

  const marker = svg('g', { class: 'collision-marker', transform: 'translate(400 300)' });
  marker.append(svg('circle', { r: 34 }), svg('path', { d: 'M-14-14 14 14M14-14-14 14' }));
  ui['collision-layer'].append(marker);
  setTimeout(() => marker.remove(), 8_000);

  ui['critical-message'].textContent = incident.message;
  ui['critical-banner'].hidden = false;
  clearTimeout(bannerTimer);
  bannerTimer = setTimeout(() => { ui['critical-banner'].hidden = true; }, 8_000);
  renderIncidents();
  renderHealth();
}

function applyInitialState(initial) {
  state.nodes = initial.nodes || {};
  state.connections = initial.connections || state.connections;
  state.incidents = initial.incidents || [];
  render();
  for (const event of initial.recentEvents || []) {
    if (event.type === 'movement_started') spawnCar(event);
  }
}

// The observer pushes snapshots, connection changes, movement, and incidents over SSE.
render();
const stream = new EventSource('/events');
stream.addEventListener('state', (message) => applyInitialState(JSON.parse(message.data)));
stream.addEventListener('snapshot', (message) => {
  const { road, node } = JSON.parse(message.data);
  state.nodes[road] = node;
  render();
});
stream.addEventListener('connection', (message) => {
  const { road, connected } = JSON.parse(message.data);
  state.connections[road] = connected;
  if (!connected) delete state.nodes[road];
  render();
});
stream.addEventListener('road_event', (message) => {
  const event = JSON.parse(message.data);
  if (event.type === 'movement_started') spawnCar(event);
});
stream.addEventListener('incident', (message) => showIncident(JSON.parse(message.data)));
stream.addEventListener('error', () => {
  ui['connection-lamp'].dataset.state = 'fault';
  ui['system-status'].textContent = 'Observer reconnecting';
});

setInterval(() => {
  ui.clock.textContent = formatTime(Date.now());
  updateCountdown();
  renderHealth();
}, 100);
