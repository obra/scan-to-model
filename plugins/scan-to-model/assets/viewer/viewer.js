import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { flightInput, safeDelta, visibleInView } from './controls.js';
import bundledMetadata from './model.json';
import modelBytes from './model.glb';

const $ = selector => document.querySelector(selector);
const canvas = $('#scene');
const viewport = $('#viewport');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.75));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.15;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
const scene = new THREE.Scene();
scene.background = new THREE.Color('#b8c6ce');
const camera = new THREE.PerspectiveCamera(65, 1, .025, 250);
const orbit = new OrbitControls(camera, canvas);
orbit.enableDamping = true;
orbit.dampingFactor = .08;
orbit.minDistance = .25;
orbit.maxDistance = 80;
orbit.maxPolarAngle = Math.PI * .95;
const pointer = new PointerLockControls(camera, canvas);
pointer.pointerSpeed = .75;
scene.add(new THREE.HemisphereLight(0xe8efff, 0x8d8068, 2.1));
const sun = new THREE.DirectionalLight(0xffefce, 3);
sun.position.set(-8, 20, 12);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = sun.shadow.camera.bottom = -18;
sun.shadow.camera.right = sun.shadow.camera.top = 18;
sun.shadow.camera.far = 60;
sun.shadow.normalBias = .025;
scene.add(sun);
scene.add(sun.target);
const keys = new Set();
const originalMaterials = new Map();
const amber = new THREE.MeshStandardMaterial({ color: 0xd79735, roughness: .8, side: THREE.DoubleSide });
const meshes = [];
let metadata;
let mode = 'orbit';
let ready = false;
const coarsePointer = matchMedia('(pointer: coarse)').matches;
const floor = $('#floor');
const roof = $('#roof');
const room = $('#room');
const direction = new THREE.Vector3();
const right = new THREE.Vector3();
const euler = new THREE.Euler(0, 0, 0, 'YXZ');
const up = new THREE.Vector3(0, 1, 0);

function resize() {
  const { width, height } = viewport.getBoundingClientRect();
  const previousAspect = camera.aspect;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  if (ready && room.value === 'exterior' && previousAspect !== camera.aspect) jump('exterior');
}
new ResizeObserver(resize).observe(viewport);

function updateVisibility() {
  for (const mesh of meshes) mesh.visible = visibleInView(mesh.userData, floor.value, roof.checked);
  $('#status').textContent = $('#diagnostic').checked ? 'Amber view · all geometry tentative' :
    'Source-guided appearance';
}

function setMode(next, requestPointer = false) {
  mode = next;
  keys.clear();
  orbit.enabled = mode === 'orbit';
  if (mode === 'orbit' && pointer.isLocked) pointer.unlock();
  if (mode === 'orbit') {
    camera.getWorldDirection(direction);
    orbit.target.copy(camera.position).addScaledVector(direction, 3);
  }
  for (const id of ['orbit', 'fly']) {
    $('#' + id).classList.toggle('active', id === mode);
    $('#' + id).setAttribute('aria-pressed', String(id === mode));
  }
  $('#crosshair').hidden = mode !== 'fly';
  $('#touch-controls').hidden = mode !== 'fly' || !coarsePointer;
  $('#place-note').textContent = mode === 'orbit' ? 'Drag to orbit · scroll to zoom · right-drag to pan' :
    coarsePointer ? 'Drag to look · use the arrows to move' : 'Click the model to look · WASD to move · Q/E down/up · Esc releases the mouse';
  $('#instructions').textContent = mode === 'orbit' ? 'Choose a room to look inside.' : 'WASD move · Q/E down/up · Shift faster · Esc release';
  if (requestPointer && mode === 'fly' && !coarsePointer) pointer.lock();
}

function jump(id) {
  if (!ready) return;
  const place = metadata.viewpoints.find(view => view.id === id) || metadata.viewpoints[0];
  camera.position.fromArray(place.position);
  if (place.id === 'exterior' && camera.aspect < 1) {
    const target = new THREE.Vector3().fromArray(place.target);
    camera.position.sub(target).multiplyScalar(1 / camera.aspect).add(target);
  }
  camera.up.set(0, 1, 0);
  camera.lookAt(new THREE.Vector3().fromArray(place.target));
  orbit.target.fromArray(place.target);
  camera.fov = place.fov || 65;
  camera.updateProjectionMatrix();
  room.value = place.id;
  floor.value = 'all';
  roof.checked = true;
  updateVisibility();
  setMode(place.id === 'exterior' ? 'orbit' : 'fly');
  if (mode === 'orbit') orbit.target.fromArray(place.target);
}

$('#orbit').addEventListener('click', () => setMode('orbit'));
$('#fly').addEventListener('click', () => setMode('fly', true));
$('#home').addEventListener('click', () => jump('exterior'));
room.addEventListener('change', () => jump(room.value));
floor.addEventListener('change', () => {
  updateVisibility();
  if (floor.value !== 'all') {
    const bounds = new THREE.Box3();
    for (const mesh of meshes) if (mesh.visible) bounds.expandByObject(mesh);
    if (!bounds.isEmpty()) {
      const center = bounds.getCenter(new THREE.Vector3());
      const extent = Math.max(bounds.getSize(new THREE.Vector3()).length(), 1);
      camera.position.copy(center).add(new THREE.Vector3(extent*.6, extent, extent*.7));
      camera.lookAt(center);
      setMode('orbit');
      orbit.target.copy(center);
    }
  }
});
roof.addEventListener('change', updateVisibility);
$('#diagnostic').addEventListener('change', () => {
  for (const mesh of meshes) mesh.material = $('#diagnostic').checked ? amber : originalMaterials.get(mesh);
  updateVisibility();
});
canvas.addEventListener('click', () => { if (ready && mode === 'fly' && !coarsePointer && !pointer.isLocked) pointer.lock(); });
document.addEventListener('pointerlockerror', () => { $('#place-note').textContent = 'Mouse capture was unavailable. Drag on the model to look around.'; });
window.addEventListener('keydown', event => {
  if (event.target.matches('input, select, button') || event.ctrlKey || event.metaKey || event.altKey) return;
  if (mode === 'fly' && /^(Key[WASDQE]|ShiftLeft|ShiftRight)$/.test(event.code)) {
    event.preventDefault();
    keys.add(event.code);
  }
});
window.addEventListener('keyup', event => keys.delete(event.code));
window.addEventListener('blur', () => keys.clear());
document.addEventListener('visibilitychange', () => { if (document.hidden) keys.clear(); });
pointer.addEventListener('unlock', () => keys.clear());
let drag = null;
canvas.addEventListener('pointerdown', event => {
  if (mode === 'fly' && !pointer.isLocked) { drag = [event.clientX, event.clientY]; canvas.setPointerCapture(event.pointerId); }
});
canvas.addEventListener('pointermove', event => {
  if (!drag || pointer.isLocked || mode !== 'fly') return;
  euler.setFromQuaternion(camera.quaternion);
  euler.y -= (event.clientX - drag[0]) * .003;
  euler.x = THREE.MathUtils.clamp(euler.x - (event.clientY - drag[1]) * .003, -Math.PI / 2 + .01, Math.PI / 2 - .01);
  camera.quaternion.setFromEuler(euler);
  drag = [event.clientX, event.clientY];
});
for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) canvas.addEventListener(event, () => { drag = null; });
for (const button of document.querySelectorAll('[data-key]')) {
  button.addEventListener('pointerdown', event => { event.preventDefault(); keys.add(button.dataset.key); button.setPointerCapture(event.pointerId); });
  for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(event, () => keys.delete(button.dataset.key));
}
$('#fullscreen').hidden = !document.fullscreenEnabled;
$('#fullscreen').addEventListener('click', () => document.fullscreenElement ? document.exitFullscreen() : viewport.requestFullscreen());

async function load() {
  try {
    metadata = bundledMetadata;
    document.title = metadata.title;
    document.querySelector('.brand span').textContent = metadata.title;
    document.querySelector('.badge').textContent = `Geometry: ${metadata.geometry_status}`;
    document.querySelector('#native-link').hidden = !metadata.native_available;
    document.querySelector('#tour-link').hidden = !metadata.stills_available;
    for (const level of metadata.levels) floor.add(new Option(level, level));
    const gltf = await new GLTFLoader().parseAsync(modelBytes.buffer, '');
    scene.add(gltf.scene);
    gltf.scene.traverse(object => {
      if (!object.isMesh) return;
      let owner = object;
      while (owner && !owner.userData.stm_id) owner = owner.parent;
      if (!owner) throw new Error('A model mesh is missing its room identity.');
      object.userData = { ...owner.userData, ...object.userData };
      object.castShadow = object.userData.stm_role !== 'glazing';
      object.receiveShadow = true;
      object.frustumCulled = true;
      for (const material of Array.isArray(object.material) ? object.material : [object.material]) material.side = THREE.DoubleSide;
      originalMaterials.set(object, object.material);
      meshes.push(object);
    });
    const bounds = new THREE.Box3().setFromObject(gltf.scene);
    const center = bounds.getCenter(new THREE.Vector3());
    sun.position.copy(center).add(new THREE.Vector3(-metadata.extent, metadata.extent*2, metadata.extent));
    sun.target.position.copy(center);
    sun.shadow.camera.left = sun.shadow.camera.bottom = -metadata.extent;
    sun.shadow.camera.right = sun.shadow.camera.top = metadata.extent;
    sun.shadow.camera.far = metadata.extent*5;
    sun.shadow.camera.updateProjectionMatrix();
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(metadata.extent*6, metadata.extent*6), new THREE.MeshStandardMaterial({ color: 0x89947d, roughness: 1 }));
    ground.rotation.x = -Math.PI / 2;
    ground.position.set(center.x, bounds.min.y - .04, center.z);
    ground.receiveShadow = true;
    scene.add(ground);
    for (const place of metadata.viewpoints.slice(1)) room.add(new Option(place.title, place.id));
    for (const fill of metadata.lights || []) {
      const point = new THREE.PointLight(0xffefdb, 7, 6, 1.4);
      point.position.fromArray(fill.position);
      scene.add(point);
    }
    ready = true;
    document.body.dataset.modelLoaded = 'true';
    document.body.dataset.modelMeshes = String(meshes.length);
    $('#loading').hidden = true;
    jump(location.hash.slice(1) || 'exterior');
  } catch (error) {
    $('#loading h1').textContent = 'The model could not open';
    $('#load-message').textContent = `${error.message} Make sure the complete checkout includes viewer.bundle.js, then reopen this page.`;
    $('.spinner').hidden = true;
    console.error(error);
  }
}

let previousTime = performance.now();
renderer.setAnimationLoop(time => {
  const delta = safeDelta((time - previousTime) / 1000);
  previousTime = time;
  if (mode === 'fly' && ready) {
    const [x, y, z] = flightInput(keys);
    const speed = (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 6 : 2) * delta;
    camera.getWorldDirection(direction);
    right.crossVectors(direction, up).normalize();
    camera.position.addScaledVector(right, x * speed).addScaledVector(direction, -z * speed);
    camera.position.y += y * speed;
  }
  if (orbit.enabled) orbit.update();
  renderer.render(scene, camera);
});

// Expose a small read-only view state for browser behavior verification and reproducible camera reports.
window.modelViewState = () => ({ ready, mode, position: camera.position.toArray(), room: room.value, floor: floor.value,
  meshCount: meshes.length, visibleMeshes: meshes.filter(mesh => mesh.visible).length,
  objectIds: [...new Set(meshes.map(mesh => mesh.userData.stm_id))],
  visibleObjectIds: [...new Set(meshes.filter(mesh => mesh.visible).map(mesh => mesh.userData.stm_id))],
  diagnostic: $('#diagnostic').checked, calls: renderer.info.render.calls, triangles: renderer.info.render.triangles });
resize();
load();
