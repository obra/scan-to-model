import test from 'node:test';
import assert from 'node:assert/strict';
import { flightInput, safeDelta, visibleInView } from '../assets/viewer/controls.js';

test('diagonal flight has the same speed as axial flight', () => {
  assert.equal(Math.hypot(...flightInput(new Set(['KeyW', 'KeyD', 'KeyE']))), 1);
  assert.deepEqual(flightInput(new Set(['KeyW', 'KeyS'])), [0, 0, 0]);
});

test('a suspended animation cannot jump through the model', () => {
  assert.equal(safeDelta(30), .05);
  assert.equal(safeDelta(-1), 0);
  assert.equal(safeDelta(.02), .02);
});

test('floor visibility uses declared levels and keeps furniture', () => {
  assert.equal(visibleInView({ stm_level: 'attic', stm_role: 'cabinet' }, 'attic', true), true);
  assert.equal(visibleInView({ stm_level: 'ground', stm_role: 'cabinet' }, 'attic', true), false);
});

test('roof controls hide roof surfaces without hiding walls', () => {
  assert.equal(visibleInView({ stm_level: 'attic', stm_role: 'roof' }, 'all', false), false);
  assert.equal(visibleInView({ stm_level: 'attic', stm_role: 'wall' }, 'all', false), true);
  assert.equal(visibleInView({ stm_level: 'attic', stm_role: 'ceiling' }, 'attic', true), false);
});
