/* Small browser-side assertions shared by visual acceptance harnesses.
 * These are intentionally framework-free so Playwright, browser-console, and
 * future fixture runners can reuse the same containment contract.
 */
function rect(element) {
  if (!element || typeof element.getBoundingClientRect !== 'function') throw new Error('layout assertion requires an element');
  return element.getBoundingClientRect();
}

export function assertNoOverlap(first, second, label='layout regions') {
  const a=rect(first), b=rect(second);
  const overlap=a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  if (overlap) throw new Error(`${label} overlap`);
  return true;
}

export function assertContained(child, parent, label='content') {
  const a=rect(child), b=rect(parent);
  if (a.left < b.left || a.top < b.top || a.right > b.right || a.bottom > b.bottom) throw new Error(`${label} is not contained`);
  return true;
}

export function assertVisible(element, label='element') {
  const a=rect(element);
  if (a.width <= 0 || a.height <= 0) throw new Error(`${label} is not visible`);
  return true;
}

export function assertNoViewportOverflow(element, viewport={width: window.innerWidth, height: window.innerHeight}, label='element') {
  const a=rect(element);
  if (a.left < -1 || a.top < -1 || a.right > viewport.width + 1 || a.bottom > viewport.height + 1) throw new Error(`${label} escapes viewport`);
  return true;
}
