import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom has no media pipeline; stub what the player calls.
Object.assign(HTMLMediaElement.prototype, {
  play: vi.fn(() => Promise.resolve()),
  pause: vi.fn(),
  load: vi.fn(),
});

afterEach(() => cleanup());
