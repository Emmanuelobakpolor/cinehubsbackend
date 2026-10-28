import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Player from './Player';
import { MovieService, UserService } from '../api/services';
import { attachStream, endSession, playbackError, type PlaybackSession } from '../lib/streaming';

vi.mock('../api/services', () => ({
  MovieService: {
    fetchMovie: vi.fn(),
    startPlayback: vi.fn(),
    updateWatchProgress: vi.fn(),
  },
  UserService: { getProfile: vi.fn() },
}));

vi.mock('../lib/streaming', async (importActual) => ({
  ...(await importActual<typeof import('../lib/streaming')>()),
  attachStream: vi.fn(),
  endSession: vi.fn(),
}));

const movie = {
  id: 7,
  title: 'Night Train',
  trailerUrl: 'https://cdn/trailer.mp4',
  thrillerClipUrl: '',
  movieFileUrl: '',
};

const session = (n = 1): PlaybackSession => ({
  mode: 'hls',
  manifestUrl: `/api/stream/tok${n}/master.m3u8`,
  drm: null,
  expiresAt: '',
  endUrl: `/api/stream/tok${n}/end`,
});

const fetchMovie = vi.mocked(MovieService.fetchMovie);
const startPlayback = vi.mocked(MovieService.startPlayback);
const updateWatchProgress = vi.mocked(MovieService.updateWatchProgress);
const attach = vi.mocked(attachStream);
const end = vi.mocked(endSession);

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/watch/:id" element={<Player />} />
        <Route path="/movie/:id" element={<p>Movie detail page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const video = () => document.querySelector('video') as HTMLVideoElement;

beforeEach(() => {
  fetchMovie.mockResolvedValue(movie as never);
  vi.mocked(UserService.getProfile).mockResolvedValue({ id: 3, email: 'viewer@example.com' } as never);
  startPlayback.mockResolvedValue({ status: 'ok', session: session() });
  attach.mockResolvedValue(vi.fn());
});
afterEach(() => vi.clearAllMocks());

describe('Player', () => {
  it('plays public trailers from their file without a playback session', async () => {
    renderAt('/watch/7?trailer=1');
    await waitFor(() => expect(video()).toBeTruthy());
    expect(video().getAttribute('src')).toBe('https://cdn/trailer.mp4');
    expect(screen.getByText('Night Train — Trailer')).toBeTruthy();
    expect(startPlayback).not.toHaveBeenCalled();
    expect(attach).not.toHaveBeenCalled();
    expect(UserService.getProfile).not.toHaveBeenCalled();
  });

  it('plays full movies only through an authorized session, never a file URL', async () => {
    renderAt('/watch/7');
    await waitFor(() => expect(attach).toHaveBeenCalled());
    expect(startPlayback).toHaveBeenCalledWith(7);
    const [el, s, opts] = attach.mock.calls[0];
    expect(el).toBe(video());
    expect(s).toEqual(session());
    expect(opts.startAt).toBe(0);
    expect(video().hasAttribute('src')).toBe(false);
  });

  it('shows the viewer watermark on full movies', async () => {
    renderAt('/watch/7');
    await waitFor(() => expect(screen.getByText('viewer@example.com')).toBeTruthy());
  });

  it('tears down the stream, ends the session and saves progress on leave', async () => {
    const destroy = vi.fn();
    attach.mockResolvedValue(destroy);
    const { unmount } = renderAt('/watch/7');
    await waitFor(() => expect(attach).toHaveBeenCalled());
    await act(async () => {});
    Object.defineProperty(video(), 'currentTime', { configurable: true, value: 125.6 });
    unmount();
    expect(destroy).toHaveBeenCalled();
    expect(end).toHaveBeenCalledWith(session());
    expect(updateWatchProgress).toHaveBeenCalledWith(7, 125);
  });

  it('ends the session when the tab is closed or reloaded', async () => {
    renderAt('/watch/7');
    await waitFor(() => expect(attach).toHaveBeenCalled());
    fireEvent(window, new Event('pagehide'));
    expect(end).toHaveBeenCalledWith(session());
  });

  it('sends unentitled viewers back to the movie page to pay', async () => {
    startPlayback.mockResolvedValue({ status: 'payment_required' });
    renderAt('/watch/7');
    await waitFor(() => expect(screen.getByText('Movie detail page')).toBeTruthy());
    expect(attach).not.toHaveBeenCalled();
  });

  it('shows the backend reason when playback cannot be authorized', async () => {
    startPlayback.mockRejectedValue(new Error('This movie is being prepared for streaming. Please try again later.'));
    renderAt('/watch/7');
    expect((await screen.findByRole('alert')).textContent).toContain('being prepared for streaming');
    expect(screen.queryByRole('button', { name: /retry/i })).toBeNull();
  });

  it('explains unsupported browsers and offers Retry', async () => {
    attach.mockRejectedValue(playbackError('unsupported'));
    renderAt('/watch/7');
    expect((await screen.findByRole('alert')).textContent).toContain('cannot play protected video');
    expect(end).toHaveBeenCalledWith(session());

    startPlayback.mockResolvedValue({ status: 'ok', session: session(2) });
    attach.mockResolvedValue(vi.fn());
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    await waitFor(() => expect(attach).toHaveBeenLastCalledWith(expect.anything(), session(2), expect.anything()));
    // The ended session is never re-attached.
    expect(attach.mock.calls.filter(([, s]) => s.endUrl === session().endUrl)).toHaveLength(1);
  });

  it('gets a fresh session when the old one expires, resuming at the same spot', async () => {
    renderAt('/watch/7');
    await waitFor(() => expect(attach).toHaveBeenCalledTimes(1));
    Object.defineProperty(video(), 'currentTime', { configurable: true, value: 300 });
    fireEvent.timeUpdate(video());

    startPlayback.mockResolvedValue({ status: 'ok', session: session(2) });
    const { onError } = attach.mock.calls[0][2];
    act(() => onError(playbackError('auth')));

    await waitFor(() => expect(attach).toHaveBeenCalledTimes(2));
    expect(attach.mock.calls[1][1]).toEqual(session(2));
    expect(attach.mock.calls[1][2].startAt).toBe(300);
    expect(end).toHaveBeenCalledWith(session(1));
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('stops retrying automatically after one fresh session', async () => {
    renderAt('/watch/7');
    await waitFor(() => expect(attach).toHaveBeenCalledTimes(1));
    act(() => attach.mock.calls[0][2].onError(playbackError('auth')));
    await waitFor(() => expect(attach).toHaveBeenCalledTimes(2));
    act(() => attach.mock.calls[1][2].onError(playbackError('auth')));
    expect((await screen.findByRole('alert')).textContent).toContain('session expired');
    expect(startPlayback).toHaveBeenCalledTimes(2);
  });

  it('keeps the speed menu working', async () => {
    renderAt('/watch/7');
    await waitFor(() => expect(attach).toHaveBeenCalled());
    fireEvent.click(screen.getByRole('button', { name: 'Playback speed' }));
    fireEvent.click(screen.getByRole('menuitemradio', { name: '1.5x' }));
    expect(video().playbackRate).toBe(1.5);
    expect(screen.getByRole('button', { name: 'Playback speed' }).textContent).toBe('1.5x');
  });
});
