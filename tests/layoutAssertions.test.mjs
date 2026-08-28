import test from 'node:test';
import assert from 'node:assert/strict';
import { assertContained, assertNoOverlap, assertVisible, assertNoViewportOverflow } from '../static/js/layoutAssertions.js';

const element = (box) => ({ getBoundingClientRect: () => box });
const box = (left, top, width, height) => ({left, top, right:left+width, bottom:top+height, width, height});

test('layout assertions accept contained, visible, non-overlapping regions', () => {
  assert.equal(assertContained(element(box(10, 10, 20, 20)), element(box(0, 0, 100, 100))), true);
  assert.equal(assertNoOverlap(element(box(0, 0, 20, 20)), element(box(30, 0, 20, 20))), true);
  assert.equal(assertVisible(element(box(0, 0, 1, 1))), true);
});

test('layout assertions reject overlap, escape, and zero-sized content', () => {
  assert.throws(() => assertNoOverlap(element(box(0, 0, 20, 20)), element(box(10, 10, 20, 20))), /overlap/);
  assert.throws(() => assertContained(element(box(-1, 0, 20, 20)), element(box(0, 0, 100, 100))), /contained/);
  assert.throws(() => assertVisible(element(box(0, 0, 0, 20))), /visible/);
  assert.throws(() => assertNoViewportOverflow(element(box(0, 0, 102, 20)), {width:100,height:100}), /viewport/);
});

test('layout assertions accept a viewport-contained window', () => {
  assert.equal(assertNoViewportOverflow(element(box(0, 0, 100, 100)), {width:100,height:100}), true);
});
