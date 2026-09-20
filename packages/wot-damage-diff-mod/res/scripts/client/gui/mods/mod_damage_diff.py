# -*- coding: utf-8 -*-
from __future__ import absolute_import
import json
import logging
import os

import BigWorld
import GUI
import Keys
from PlayerEvents import g_playerEvents
from gui import InputHandler, g_guiResetters
from gui.battle_control.battle_constants import PERSONAL_EFFICIENCY_TYPE as _PET
from gui.shared import EVENT_BUS_SCOPE, events, g_eventBus
from helpers import dependency
from skeletons.gui.battle_session import IBattleSessionProvider

MOD_VERSION = '{{VERSION}}'
_LOGGER = logging.getLogger(__name__)

_FONT = 'default_medium.font'
_DEFAULT_X = 0.0
_DEFAULT_Y = 0.72
_Z = 1.0
_COLOUR_POS = (90, 220, 90, 255)
_COLOUR_NEG = (255, 90, 90, 255)
_COLOUR_ZERO = (235, 235, 235, 255)
_CONFIG_PATH = 'res_mods/configs/me.wot-damage-diff/config.json'


def _session_provider():
    return dependency.instance(IBattleSessionProvider)


def _load_position():
    try:
        with open(_CONFIG_PATH, 'r') as fh:
            data = json.load(fh)
        return float(data.get('x', _DEFAULT_X)), float(data.get('y', _DEFAULT_Y))
    except Exception:
        return _DEFAULT_X, _DEFAULT_Y


def _save_position(x, y):
    folder = os.path.dirname(_CONFIG_PATH)
    try:
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        with open(_CONFIG_PATH, 'w') as fh:
            json.dump({'x': round(x, 4), 'y': round(y, 4)}, fh, indent=2)
    except Exception:
        _LOGGER.exception('failed to save overlay position')


def _clamp(value, lo=-0.95, hi=0.95):
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _mouse_pos():
    pos = GUI.mcursor().position
    try:
        return float(pos.x), float(pos.y)
    except Exception:
        return float(pos[0]), float(pos[1])


def _cursor_visible():
    try:
        return bool(GUI.mcursor().visible)
    except Exception:
        return False


class _DamageDiffOverlay(object):
    def __init__(self):
        self._taken = 0
        self._ctrl = None
        self._label = None
        self._retry_cb = None
        self._tick_cb = None
        self._dragging = False
        self._drag_dx = 0.0
        self._drag_dy = 0.0
        self._x, self._y = _load_position()

    def start(self):
        self.stop()
        self._x, self._y = _load_position()
        self._subscribe()
        self._create_label()
        self._refresh()

    def stop(self):
        if self._dragging:
            self._finish_drag()
        self._cancel_retry()
        self._cancel_tick()
        self._unsubscribe()
        self._unbind_input()
        self._destroy_label()
        self._taken = 0

    def _subscribe(self):
        self._unsubscribe()
        session = _session_provider()
        ctrl = None
        if session is not None and session.shared is not None:
            ctrl = session.shared.personalEfficiencyCtrl
        if ctrl is None:
            self._retry_cb = BigWorld.callback(0.2, self._retry_subscribe)
            return
        self._ctrl = ctrl
        ctrl.onTotalEfficiencyUpdated += self._on_total_efficiency_updated
        ctrl.onPersonalEfficiencyReceived += self._on_efficiency_received

    def _retry_subscribe(self):
        self._retry_cb = None
        if BigWorld.player() is None:
            return
        self._subscribe()
        self._refresh()

    def _unsubscribe(self):
        ctrl = self._ctrl
        self._ctrl = None
        if ctrl is None:
            return
        try:
            ctrl.onTotalEfficiencyUpdated -= self._on_total_efficiency_updated
        except Exception:
            pass
        try:
            ctrl.onPersonalEfficiencyReceived -= self._on_efficiency_received
        except Exception:
            pass

    def _bind_input(self):
        self._unbind_input()
        InputHandler.g_instance.onKeyDown += self._on_key_down
        InputHandler.g_instance.onKeyUp += self._on_key_up
        g_eventBus.addListener(
            events.GameEvent.HIDE_CURSOR, self._on_hide_cursor, EVENT_BUS_SCOPE.GLOBAL
        )

    def _unbind_input(self):
        try:
            InputHandler.g_instance.onKeyDown -= self._on_key_down
            InputHandler.g_instance.onKeyUp -= self._on_key_up
        except Exception:
            pass
        try:
            g_eventBus.removeListener(
                events.GameEvent.HIDE_CURSOR, self._on_hide_cursor, EVENT_BUS_SCOPE.GLOBAL
            )
        except Exception:
            pass

    def _cancel_retry(self):
        if self._retry_cb is None:
            return
        try:
            BigWorld.cancelCallback(self._retry_cb)
        except Exception:
            pass
        self._retry_cb = None

    def _cancel_tick(self):
        if self._tick_cb is None:
            return
        try:
            BigWorld.cancelCallback(self._tick_cb)
        except Exception:
            pass
        self._tick_cb = None

    def _create_label(self):
        self._destroy_label()
        try:
            label = GUI.Text('')
            label.font = _FONT
            label.colour = _COLOUR_ZERO
            label.horizontalAnchor = 'CENTER'
            label.verticalAnchor = 'CENTER'
            label.position = (self._x, self._y, _Z)
            label.visible = True
            GUI.addRoot(label)
            self._label = label
            g_guiResetters.add(self._on_gui_reset)
            self._bind_input()
        except Exception:
            _LOGGER.exception('failed to create damage-diff overlay')
            self._label = None

    def _destroy_label(self):
        try:
            g_guiResetters.discard(self._on_gui_reset)
        except Exception:
            pass
        label = self._label
        self._label = None
        if label is None:
            return
        try:
            GUI.delRoot(label)
        except Exception:
            pass

    def _apply_position(self):
        if self._label is None:
            return
        self._label.position = (self._x, self._y, _Z)

    def _set_pos(self, x, y):
        self._x = _clamp(x)
        self._y = _clamp(y)
        self._apply_position()

    def _on_gui_reset(self):
        self._apply_position()
        self._refresh()

    def _on_total_efficiency_updated(self, _diff):
        self._refresh()

    def _on_efficiency_received(self, events_list):
        for info in events_list:
            try:
                if info.getType() != _PET.RECEIVED_DAMAGE:
                    continue
                if getattr(info, 'isHidden', lambda: False)():
                    continue
                damage = info.getDamage()
                if damage:
                    self._taken += int(damage)
            except Exception:
                _LOGGER.exception('failed to apply received-damage event')
        self._refresh()

    def _on_key_down(self, event):
        if event.key != Keys.KEY_LEFTMOUSE or self._label is None or self._dragging:
            return
        if not _cursor_visible():
            return
        mx, my = _mouse_pos()
        if not self._hit_test(mx, my):
            return
        self._drag_dx = self._x - mx
        self._drag_dy = self._y - my
        self._dragging = True
        self._cancel_tick()
        self._tick_cb = BigWorld.callback(0.0, self._on_drag_tick)

    def _on_key_up(self, event):
        if event.key != Keys.KEY_LEFTMOUSE:
            return
        if self._dragging:
            self._finish_drag()

    def _on_hide_cursor(self, _event=None):
        if self._dragging:
            self._finish_drag()

    def _on_drag_tick(self):
        self._tick_cb = None
        if not self._dragging or self._label is None:
            return
        mx, my = _mouse_pos()
        self._set_pos(mx + self._drag_dx, my + self._drag_dy)
        self._tick_cb = BigWorld.callback(0.0, self._on_drag_tick)

    def _finish_drag(self):
        self._dragging = False
        self._cancel_tick()
        _save_position(self._x, self._y)

    def _hit_test(self, mx, my):
        half_w, half_h = self._hit_half_size()
        return abs(mx - self._x) <= half_w and abs(my - self._y) <= half_h

    def _hit_half_size(self):
        half_w = 0.06
        half_h = 0.03
        try:
            size = self._label.size
            width, height = float(size[0]), float(size[1])
            if width > 2.0 or height > 2.0:
                _sw, sh = GUI.screenResolution()
                sh = float(sh) or 1080.0
                width = width / sh * 2.0
                height = height / sh * 2.0
            if width > 0.0:
                half_w = max(width * 0.5, half_w)
            if height > 0.0:
                half_h = max(height * 0.5, half_h)
        except Exception:
            text = ''
            try:
                text = self._label.text or ''
            except Exception:
                pass
            half_w = max(0.012 * max(len(text), 1), half_w)
        return half_w + 0.01, half_h + 0.01

    def _dealt(self):
        ctrl = self._ctrl
        if ctrl is None:
            return 0
        try:
            return int(ctrl.getTotalEfficiency(_PET.DAMAGE) or 0)
        except Exception:
            return 0

    def _refresh(self):
        label = self._label
        if label is None:
            return
        delta = self._dealt() - self._taken
        if delta > 0:
            text = '+%d' % delta
            colour = _COLOUR_POS
        else:
            text = '%d' % delta
            colour = _COLOUR_NEG if delta < 0 else _COLOUR_ZERO
        try:
            label.text = text
            label.colour = colour
        except Exception:
            pass


_overlay = _DamageDiffOverlay()


def _on_avatar_ready():
    _overlay.start()


def _on_avatar_become_non_player():
    _overlay.stop()


def init():
    _LOGGER.info('[DAMAGE_DIFF] v%s', MOD_VERSION)
    g_playerEvents.onAvatarReady += _on_avatar_ready
    g_playerEvents.onAvatarBecomeNonPlayer += _on_avatar_become_non_player


def fini():
    g_playerEvents.onAvatarReady -= _on_avatar_ready
    g_playerEvents.onAvatarBecomeNonPlayer -= _on_avatar_become_non_player
    _overlay.stop()
