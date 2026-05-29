"""
GPU 3D spectrogram surface (Tk + pyopengltk + PyOpenGL).

Copyright 2025 Andre Lorbach

Licensed under the Apache License, Version 2.0.
"""

from __future__ import annotations

import math
import sys
import time
from tkinter import TclError

import numpy as np

GL_AVAILABLE = False
OpenGLFrame = None

try:
    from OpenGL.GL import (
        GL_COLOR_ARRAY,
        GL_COLOR_BUFFER_BIT,
        GL_CULL_FACE,
        GL_DEPTH_BUFFER_BIT,
        GL_DEPTH_TEST,
        GL_FLOAT,
        GL_LIGHTING,
        GL_LINES,
        GL_MODELVIEW,
        GL_PROJECTION,
        GL_SMOOTH,
        GL_TRIANGLES,
        GL_UNSIGNED_INT,
        GL_VERTEX_ARRAY,
        glBegin,
        glClear,
        glClearColor,
        glColor3f,
        glColorPointer,
        glDisable,
        glDisableClientState,
        glDrawElements,
        glEnable,
        glEnableClientState,
        glEnd,
        glLineWidth,
        glLoadIdentity,
        glMatrixMode,
        glShadeModel,
        glVertex3f,
        glVertexPointer,
        glViewport,
        glRasterPos3f,
    )
    from OpenGL.GLU import gluLookAt, gluPerspective
    from pyopengltk import OpenGLFrame as _OpenGLFrame

    OpenGLFrame = _OpenGLFrame
    GL_AVAILABLE = True
except ImportError:
    pass

# Center tone: ignore energy above this when finding centroid (reduces HF scroll jitter).
_CENTER_TONE_MAX_HZ = 3200.0
_CENTER_TONE_WIN_COLS = 12
_CENTER_TONE_CAP = 0.014
_CENTER_TONE_DISPLAY_SMOOTH = 0.93

_GLUT_INIT_OK = False
_glut_bitmap_char = None
_glut_font_id = None


def _ensure_glut_bitmap():
    global _GLUT_INIT_OK, _glut_bitmap_char, _glut_font_id
    if _GLUT_INIT_OK:
        return _glut_bitmap_char is not None
    try:
        from OpenGL.GLUT import GLUT_BITMAP_8_BY_13, glutBitmapCharacter, glutInit

        glutInit(sys.argv if sys.argv else ["spectrum_analyzer"])
        _glut_bitmap_char = glutBitmapCharacter
        _glut_font_id = GLUT_BITMAP_8_BY_13
        _GLUT_INIT_OK = True
        return True
    except Exception:
        _GLUT_INIT_OK = True
        return False


def build_cmap_lut(cmap_obj, n: int = 256) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n, dtype=np.float64)
    rgba = cmap_obj(t)
    return np.ascontiguousarray(rgba[:, :3], dtype=np.float32)


def subsample_axis(n: int, stride: int) -> np.ndarray:
    if n < 1:
        return np.array([0], dtype=np.int32)
    if stride <= 1:
        return np.arange(n, dtype=np.int32)
    idx = list(range(0, n, stride))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return np.array(idx, dtype=np.int32)


def _build_triangle_indices(nr_e: int, nc_e: int) -> np.ndarray:
    quads_i = nr_e - 1
    quads_j = nc_e - 1
    if quads_i < 1 or quads_j < 1:
        return np.zeros(0, dtype=np.uint32)
    ntri = quads_i * quads_j * 6
    out = np.empty(ntri, dtype=np.uint32)
    t = 0
    for a in range(quads_i):
        for b in range(quads_j):
            i00 = a * nc_e + b
            i10 = (a + 1) * nc_e + b
            i01 = a * nc_e + b + 1
            i11 = (a + 1) * nc_e + b + 1
            out[t] = i00
            out[t + 1] = i10
            out[t + 2] = i01
            out[t + 3] = i10
            out[t + 4] = i11
            out[t + 5] = i01
            t += 6
    return out


if GL_AVAILABLE:

    class SpectrumGLSurface(OpenGLFrame):
        """Scrolls spectrogram data from gui._spec; drag to orbit."""

        def __init__(
            self,
            master,
            gui,
            nr: int,
            nc: int,
            f_min: float,
            f_max: float,
            vmin: float,
            vmax: float,
            cmap_lut: np.ndarray,
            mesh_stride: int = 1,
            **kw,
        ):
            OpenGLFrame.__init__(self, master, **kw)
            self._gui = gui
            self._nr = nr
            self._nc = nc
            self._f_min = float(f_min)
            self._f_max = float(f_max)
            self._vmin = float(vmin)
            self._vmax = float(vmax)
            self._lut = np.ascontiguousarray(cmap_lut, dtype=np.float32)
            self._log_den = math.log10(self._f_max / self._f_min)
            self._sx = 2.25
            self._sy = 1.15
            self._sz = 0.6
            self._row_idx = subsample_axis(nr, mesh_stride)
            self._col_idx = subsample_axis(nc, mesh_stride)
            self._nr_e = len(self._row_idx)
            self._nc_e = len(self._col_idx)
            nv = self._nr_e * self._nc_e
            self._verts = np.zeros((nv, 3), dtype=np.float32)
            self._colors = np.zeros((nv, 3), dtype=np.float32)
            self._indices = np.ascontiguousarray(
                _build_triangle_indices(self._nr_e, self._nc_e), dtype=np.uint32
            )
            self._ni = len(self._indices)
            self._default_az = 0.62
            self._default_el = 0.28
            self._default_dist = 3.85
            self._orbit_az = self._default_az
            self._orbit_el = self._default_el
            self._orbit_dist = self._default_dist
            self._drag_x = 0
            self._drag_y = 0
            self._dragging = False
            self._redraw_after_id = None
            self._track_y_smooth = 0.0
            self._track_y_display = 0.0
            self._last_spin_time = time.monotonic()
            self._dist_min = 1.35
            self._dist_max = 22.0
            self._spin_rad_s = 0.42
            self._last_y_shift = 0.0
            self._use_glut_text = False
            self.bind("<Button-1>", self._on_button1)
            self.bind("<Double-Button-1>", self._on_double_reset)
            self.bind("<B1-Motion>", self._on_motion1)
            self.bind("<ButtonRelease-1>", self._on_release1)
            if sys.platform in ("win32", "darwin"):
                self.bind("<MouseWheel>", self._on_mousewheel)
            else:
                self.bind("<Button-4>", lambda _e: self._zoom_step(1))
                self.bind("<Button-5>", lambda _e: self._zoom_step(-1))

        def initgl(self):
            glClearColor(0.051, 0.051, 0.071, 1.0)
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_LIGHTING)
            glDisable(GL_CULL_FACE)
            glShadeModel(GL_SMOOTH)
            self._use_glut_text = _ensure_glut_bitmap()

        def _on_button1(self, event):
            try:
                self.focus_set()
            except TclError:
                pass
            self._dragging = True
            self._drag_x = event.x
            self._drag_y = event.y

        def _on_motion1(self, event):
            if not self._dragging:
                return
            dx = event.x - self._drag_x
            dy = event.y - self._drag_y
            self._drag_x = event.x
            self._drag_y = event.y
            self._orbit_az += dx * 0.012
            self._orbit_el += dy * 0.011
            lim = math.pi * 0.48
            self._orbit_el = max(-lim, min(lim, self._orbit_el))
            self.request_redraw()

        def _on_release1(self, _event):
            self._dragging = False

        def _on_double_reset(self, _event=None):
            try:
                self.focus_set()
            except TclError:
                pass
            self._dragging = False
            self._orbit_az = self._default_az
            self._orbit_el = self._default_el
            self._orbit_dist = self._default_dist
            self._track_y_smooth = 0.0
            self._track_y_display = 0.0
            self._last_spin_time = time.monotonic()
            self.request_redraw()

        def _on_mousewheel(self, event):
            if sys.platform == "darwin":
                d = 1 if event.delta > 0 else -1
            else:
                d = 1 if event.delta > 0 else -1
            self._zoom_step(d)

        def _zoom_step(self, direction):
            if direction > 0:
                self._orbit_dist *= 0.92
            else:
                self._orbit_dist *= 1.09
            self._orbit_dist = max(
                self._dist_min, min(self._dist_max, self._orbit_dist)
            )
            self.request_redraw()

        def request_redraw(self):
            if self._redraw_after_id is not None:
                try:
                    self.after_cancel(self._redraw_after_id)
                except TclError:
                    pass
                self._redraw_after_id = None

            def _run(attempt=0):
                self._redraw_after_id = None
                try:
                    self.update_idletasks()
                    self._display()
                except Exception:
                    if attempt < 10:
                        nxt = attempt + 1
                        self._redraw_after_id = self.after(
                            30, lambda n=nxt: _run(n)
                        )
                    else:
                        pass

            try:
                self._redraw_after_id = self.after_idle(lambda: _run(0))
            except tk.TclError:
                self._redraw_after_id = None

        def draw_now(self):
            try:
                self.update_idletasks()
                self._display()
            except Exception:
                pass

        def _update_mesh_from_gui(self):
            spec = self._gui._spec
            freqs = self._gui._disp_freqs
            log_scale = bool(self._gui._log_scale_var.get())
            track = bool(
                getattr(self._gui, "_gl_track_tone_var", None)
                and self._gui._gl_track_tone_var.get()
            )
            sub = spec[np.ix_(self._row_idx, self._col_idx)].astype(np.float64, copy=False)
            rng = self._vmax - self._vmin
            if rng <= 1e-9:
                t = np.zeros_like(sub)
            else:
                t = (sub - self._vmin) / rng
            np.clip(t, 0.0, 1.0, out=t)
            xc = (self._col_idx.astype(np.float64) / max(self._nc - 1, 1) - 0.5) * self._sx
            x_grid = np.broadcast_to(xc, sub.shape).astype(np.float32)
            if log_scale:
                fr = np.maximum(freqs[self._row_idx].astype(np.float64), self._f_min)
                y_norm = (np.log10(fr) - math.log10(self._f_min)) / self._log_den
            else:
                y_norm = self._row_idx.astype(np.float64) / max(self._nr - 1, 1)
            y_row = (y_norm - 0.5) * self._sy
            y_grid = np.broadcast_to(y_row[:, np.newaxis], sub.shape).astype(np.float32)

            if track:
                nw = min(_CENTER_TONE_WIN_COLS, spec.shape[1])
                col = np.mean(spec[:, -nw:], axis=1).astype(np.float64, copy=False)
                spread = float(col.max() - col.min())
                if spread >= 4.0:
                    freqv = freqs.astype(np.float64)
                    hf_mask = freqv <= _CENTER_TONE_MAX_HZ
                    if not np.any(hf_mask):
                        hf_mask = np.ones(self._nr, dtype=bool)
                    rel = col - float(np.max(col))
                    w = np.power(10.0, rel / 22.0)
                    w = np.maximum(w, 1e-14)
                    w = w * hf_mask.astype(np.float64)
                    wsum = float(np.sum(w))
                    if wsum < 1e-20:
                        w = hf_mask.astype(np.float64) + 1e-10
                        wsum = float(np.sum(w))
                    ri = np.arange(self._nr, dtype=np.float64)
                    ci_cent = float(np.sum(w * ri) / wsum)
                    ci_cent = max(0.0, min(float(self._nr - 1), ci_cent))
                    if log_scale:
                        fr = float(
                            np.interp(
                                ci_cent,
                                np.arange(self._nr, dtype=np.float64),
                                freqs.astype(np.float64),
                            )
                        )
                        fr = max(fr, self._f_min)
                        yn = (math.log10(fr) - math.log10(self._f_min)) / self._log_den
                    else:
                        yn = ci_cent / max(self._nr - 1, 1)
                    y_target = (yn - 0.5) * self._sy
                    dy = y_target - self._track_y_smooth
                    cap = _CENTER_TONE_CAP
                    if dy > cap:
                        dy = cap
                    elif dy < -cap:
                        dy = -cap
                    self._track_y_smooth += dy
                self._track_y_display = (
                    _CENTER_TONE_DISPLAY_SMOOTH * self._track_y_display
                    + (1.0 - _CENTER_TONE_DISPLAY_SMOOTH) * self._track_y_smooth
                )
                y_shift = self._track_y_display
            else:
                self._track_y_smooth *= 0.94
                self._track_y_display *= 0.94
                if abs(self._track_y_smooth) < 1e-4:
                    self._track_y_smooth = 0.0
                if abs(self._track_y_display) < 1e-4:
                    self._track_y_display = 0.0
                y_shift = self._track_y_display
            self._last_y_shift = float(y_shift)
            y_grid = y_grid - np.float32(y_shift)

            z_grid = (t * self._sz).astype(np.float32)
            self._verts[:, 0] = x_grid.ravel()
            self._verts[:, 1] = y_grid.ravel()
            self._verts[:, 2] = z_grid.ravel()
            li = (t * 255.999).astype(np.int32)
            np.clip(li, 0, 255, out=li)
            self._colors[:] = self._lut[li].reshape(-1, 3)

        def redraw(self):
            w = max(1, self.winfo_width())
            h = max(1, self.winfo_height())
            glViewport(0, 0, w, h)
            glClearColor(0.051, 0.051, 0.071, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(42.0, w / float(h), 0.06, 120.0)
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()

            ca = math.cos(self._orbit_el) * math.sin(self._orbit_az)
            cb = math.sin(self._orbit_el)
            cc = math.cos(self._orbit_el) * math.cos(self._orbit_az)
            ex = self._orbit_dist * ca
            ey = self._orbit_dist * cb
            ez = self._orbit_dist * cc
            gluLookAt(ex, ey, ez, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)

            if self._ni <= 0:
                return

            spin = bool(
                getattr(self._gui, "_gl_auto_spin_var", None)
                and self._gui._gl_auto_spin_var.get()
            )
            now = time.monotonic()
            dt = max(0.0, min(0.25, now - self._last_spin_time))
            self._last_spin_time = now
            if spin and dt > 0:
                self._orbit_az += self._spin_rad_s * dt

            self._update_mesh_from_gui()

            xm = float(self._verts[:, 0].min())
            xM = float(self._verts[:, 0].max())
            ym = float(self._verts[:, 1].min())
            yM = float(self._verts[:, 1].max())
            zm = float(self._verts[:, 2].min())
            zM = float(self._verts[:, 2].max())

            glEnable(GL_DEPTH_TEST)
            self._draw_axis_background_grids(xm, xM, ym, yM, zm)

            glEnableClientState(GL_VERTEX_ARRAY)
            glEnableClientState(GL_COLOR_ARRAY)
            glVertexPointer(3, GL_FLOAT, 0, self._verts)
            glColorPointer(3, GL_FLOAT, 0, self._colors)
            glDrawElements(GL_TRIANGLES, self._ni, GL_UNSIGNED_INT, self._indices)
            glDisableClientState(GL_COLOR_ARRAY)
            glDisableClientState(GL_VERTEX_ARRAY)

            self._draw_axis_lines()
            self._draw_axis_labels_3d(xm, xM, ym, yM, zm)

        def _row_world_y(self, row_idx: int, freqs, log_scale: bool) -> float:
            if log_scale:
                fr = max(float(freqs[int(row_idx)]), self._f_min)
                yn = (math.log10(fr) - math.log10(self._f_min)) / self._log_den
            else:
                yn = float(row_idx) / max(self._nr - 1, 1)
            return (yn - 0.5) * self._sy - self._last_y_shift

        def _draw_axis_background_grids(self, xm, xM, ym, yM, zm):
            glEnable(GL_DEPTH_TEST)
            glLineWidth(1.0)
            glBegin(GL_LINES)
            glColor3f(0.18, 0.2, 0.26)
            pairs = []
            if hasattr(self._gui, "_y_tick_row_labels"):
                try:
                    pairs = self._gui._y_tick_row_labels()
                except Exception:
                    pairs = []
            freqs = self._gui._disp_freqs
            log_scale = bool(self._gui._log_scale_var.get())
            z0 = zm - 0.008
            for row_idx, _lab in pairs:
                yw = self._row_world_y(row_idx, freqs, log_scale)
                if yw < ym - 0.02 or yw > yM + 0.02:
                    continue
                glVertex3f(xm, yw, z0)
                glVertex3f(xM, yw, z0)
            nc1 = max(self._nc - 1, 1)
            for k in (0, 0.25, 0.5, 0.75, 1.0):
                j = int(round(k * nc1))
                xw = (j / nc1 - 0.5) * self._sx
                glVertex3f(xw, ym, z0)
                glVertex3f(xw, yM, z0)
            glEnd()

        def _draw_glut_label(self, x: float, y: float, z: float, text: str):
            if not self._use_glut_text or _glut_bitmap_char is None:
                return
            try:
                glRasterPos3f(x, y, z)
                for ch in text:
                    _glut_bitmap_char(_glut_font_id, ord(ch))
            except Exception:
                pass

        def _draw_axis_labels_3d(self, xm, xM, ym, yM, zm):
            if not self._use_glut_text:
                return
            glDisable(GL_DEPTH_TEST)
            glColor3f(0.42, 0.45, 0.52)
            freqs = self._gui._disp_freqs
            log_scale = bool(self._gui._log_scale_var.get())
            zt = zm - 0.02
            x_left = xm - 0.14
            pairs = []
            if hasattr(self._gui, "_y_tick_row_labels"):
                try:
                    pairs = self._gui._y_tick_row_labels()
                except Exception:
                    pairs = []
            for row_idx, lab in pairs:
                yw = self._row_world_y(row_idx, freqs, log_scale)
                if yw < ym - 0.08 or yw > yM + 0.08:
                    continue
                self._draw_glut_label(x_left, yw - 0.02, zt, lab)
            nc1 = max(self._nc - 1, 1)
            y_bot = ym - 0.1
            for k, lab in [(0.0, "0"), (0.25, str(nc1 // 4)), (0.5, str(nc1 // 2)), (0.75, str(3 * nc1 // 4)), (1.0, str(nc1))]:
                j = int(round(k * nc1))
                xw = (j / nc1 - 0.5) * self._sx
                self._draw_glut_label(xw - 0.04, y_bot, zt, lab)
            glEnable(GL_DEPTH_TEST)

        def _draw_axis_lines(self):
            xm = float(self._verts[:, 0].min())
            xM = float(self._verts[:, 0].max())
            ym = float(self._verts[:, 1].min())
            yM = float(self._verts[:, 1].max())
            zm = float(self._verts[:, 2].min())
            zM = float(self._verts[:, 2].max())
            eps = 0.012
            glDisable(GL_DEPTH_TEST)
            glLineWidth(1.8)
            glBegin(GL_LINES)
            glColor3f(0.55, 0.42, 0.38)
            glVertex3f(xm, ym, zm - eps)
            glVertex3f(xM, ym, zm - eps)
            glVertex3f(xm, yM, zm - eps)
            glVertex3f(xM, yM, zm - eps)
            glColor3f(0.38, 0.48, 0.58)
            glVertex3f(xm, ym, zm - eps)
            glVertex3f(xm, yM, zm - eps)
            glVertex3f(xM, ym, zm - eps)
            glVertex3f(xM, yM, zm - eps)
            glColor3f(0.42, 0.52, 0.45)
            glVertex3f(xm, ym, zm - eps)
            glVertex3f(xm, ym, zM + eps)
            glVertex3f(xM, ym, zm - eps)
            glVertex3f(xM, ym, zM + eps)
            glVertex3f(xm, yM, zm - eps)
            glVertex3f(xm, yM, zM + eps)
            glVertex3f(xM, yM, zm - eps)
            glVertex3f(xM, yM, zM + eps)
            glEnd()
            glEnable(GL_DEPTH_TEST)

else:

    class SpectrumGLSurface:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("OpenGL / pyopengltk not available")
