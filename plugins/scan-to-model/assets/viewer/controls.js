export function visibleInView(object, level, roofVisible) {
  if (level !== 'all' && object.stm_level !== level) return false;
  if ((level !== 'all' || !roofVisible) && ['roof', 'ceiling'].includes(object.stm_role)) return false;
  return true;
}

export function flightInput(keys) {
  const direction = [Number(keys.has('KeyD')) - Number(keys.has('KeyA')),
    Number(keys.has('KeyE')) - Number(keys.has('KeyQ')),
    Number(keys.has('KeyS')) - Number(keys.has('KeyW'))];
  const magnitude = Math.hypot(...direction);
  return magnitude ? direction.map(value => value / magnitude) : direction;
}

export function safeDelta(seconds) {
  return Math.min(.05, Math.max(0, seconds));
}
