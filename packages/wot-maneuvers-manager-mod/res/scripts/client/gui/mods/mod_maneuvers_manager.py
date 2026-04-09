# -*- coding: utf-8 -*-
from __future__ import absolute_import
import logging
import urllib
from collections import OrderedDict

import BigWorld
from BWUtil import AsyncReturn
from gui import SystemMessages
from gui.impl.dialogs import dialogs
from gui.impl.dialogs.builders import FormattedSimpleDialogBuilder
from gui.impl.gen.view_models.constants.dialog_presets import DialogPresets
from gui.impl.gen.view_models.views.lobby.hangar.main_menu_model import MainMenuModel
from gui.impl.pub.dialog_window import DialogButtons
from gui.impl.lobby.hangar.presenters.utils import MenuItemEntry
from gui.shared.system_factory import registerMenuItems
from helpers import dependency
from skeletons.connection_mgr import IConnectionManager
from skeletons.gui.shared.utils import IHangarSpace
from adisp import adisp_process
from skeletons.gui.web import IWebController
from wg_async import wg_async, wg_await, await_callback

MOD_VERSION = '{{VERSION}}'
_LOGGER = logging.getLogger(__name__)

MENU_ID_MANEUVERS = 'maneuversManager'

hangarSpace = dependency.instance(IHangarSpace)


def _ssr_mod_installed():
    try:
        __import__('server_side_replay', level=0)
        return True
    except ImportError:
        return False


def _truncate_preview(s, head=14, tail=6):
    if not s or len(s) <= head + tail + 3:
        return s or u''
    return s[:head] + u'…' + s[-tail:]


def _build_auth_url(access_token, periphery_id, spa_id):
    # Local auth app URL; token + realm ids (same as WG clan/WGSH flows).
    unicode_type = type(u'')
    if access_token is None:
        return None
    if isinstance(access_token, unicode_type):
        token_str = access_token.encode('utf-8', errors='replace')
    else:
        token_str = access_token
    query = urllib.urlencode(
        [
            ('accessToken', token_str),
            ('periphery_id', str(periphery_id)),
            ('spa_id', str(spa_id)),
        ]
    )
    return 'http://localhost:3000/auth?' + query


@adisp_process
def _getAccessTokenData_adisp(web_ctrl, callback):
    # getAccessTokenData is @adisp_async: must be driven via yield inside @adisp_process
    # (see gui.platform.base.request.Request._getAccessTokenData).
    force = not web_ctrl.isLoggedOn()
    access_token_data = yield web_ctrl.getAccessTokenData(force)
    callback(access_token_data)


@wg_async
def _fetch_oauth_access_token():
    web_ctrl = dependency.instance(IWebController)
    if web_ctrl is None or not web_ctrl.isEnabled() or not web_ctrl.isAvailable():
        raise AsyncReturn(None)
    try:
        data = yield wg_await(await_callback(_getAccessTokenData_adisp)(web_ctrl))
    except Exception:
        _LOGGER.exception('getAccessTokenData failed')
        raise AsyncReturn(None)
    raise AsyncReturn(data)


@wg_async
def _run_access_token_only():
    oauth = yield wg_await(_fetch_oauth_access_token())
    if oauth is None:
        raise AsyncReturn(
            {
                u'error': u'Could not get OAuth access token (WGCG). Is WGCG enabled and are you logged in?',
            }
        )

    access_token = getattr(oauth, 'accessToken', None) or getattr(oauth, 'access_token', None)
    if not access_token:
        raise AsyncReturn({u'error': u'OAuth response had no accessToken.'})

    conn = dependency.instance(IConnectionManager)
    if conn is None:
        raise AsyncReturn({u'error': u'No connection manager.'})

    raise AsyncReturn(
        {
            u'access_token': access_token,
            u'periphery_id': conn.peripheryID,
            u'spa_id': conn.databaseID,
        }
    )


def _dialog_body(result):
    lines = []
    err = result.get(u'error')
    if err:
        lines.append(u'Error: ' + err)
        lines.append(u'')
        lines.append(u'Check python.log for details.')
        return u'\n'.join(lines)

    tok = result.get(u'access_token')
    lines.append(u'OAuth access token (WG client).')
    lines.append(u'')
    lines.append(u'access_token: ' + (u'(ok) ' + _truncate_preview(tok) if tok else u'(missing)'))
    lines.append(u'periphery_id: %s' % result.get(u'periphery_id'))
    lines.append(u'spa_id: %s' % result.get(u'spa_id'))
    lines.append(u'')
    lines.append(u'Confirm opens your browser at http://localhost:3000/auth with token and ids.')
    return u'\n'.join(lines)


@wg_async
def _show_maneuvers_modal():
    result = yield wg_await(_run_access_token_only())
    if not isinstance(result, dict):
        result = {u'error': u'Unexpected result'}

    body = _dialog_body(result)

    builder = FormattedSimpleDialogBuilder()
    builder.setMessagesAndButtons(
        DialogPresets.INFO,
        'Maneuvers Manager',
        body,
        [
            {DialogButtons.SUBMIT: 'Open browser'},
            {DialogButtons.CANCEL: 'Close'},
        ],
        DialogButtons.SUBMIT,
        None,
    )
    built = builder.buildInLobby()
    if built is None:
        _LOGGER.error('Maneuvers Manager: dialog build failed (lobby not ready?)')
        return
    dlg_result = yield wg_await(dialogs.show(built))
    if dlg_result is None:
        return
    if dlg_result.result == DialogButtons.SUBMIT:
        err = result.get(u'error')
        if err:
            SystemMessages.pushMessage(
                text=u'Cannot open browser: ' + err,
                type=SystemMessages.SM_TYPE.Warning,
            )
            return
        url = _build_auth_url(
            result.get(u'access_token'),
            result.get(u'periphery_id'),
            result.get(u'spa_id'),
        )
        if not url:
            SystemMessages.pushMessage(
                text=u'No access token to open.',
                type=SystemMessages.SM_TYPE.Warning,
            )
            return
        try:
            BigWorld.wg_openWebBrowser(url)
            SystemMessages.pushMessage(
                text=u'Opening http://localhost:3000/auth …',
                type=SystemMessages.SM_TYPE.Information,
            )
        except Exception:
            _LOGGER.exception('wg_openWebBrowser failed')


def _on_open_maneuvers():
    _show_maneuvers_modal()


def init():
    _LOGGER.info('[MANEUVERS_MANAGER] v%s', MOD_VERSION)

    registerMenuItems(
        'hangar',
        OrderedDict(
            [
                (
                    MENU_ID_MANEUVERS,
                    MenuItemEntry(_on_open_maneuvers, lambda: True, lambda: True),
                ),
            ]
        ),
    )

    if not _ssr_mod_installed():
        registerMenuItems(
            'hangar',
            OrderedDict(
                [
                    (
                        MainMenuModel.REPLAYS,
                        MenuItemEntry(_on_open_maneuvers, lambda: True, lambda: True),
                    ),
                ]
            ),
        )

    hangarSpace.onSpaceCreate += _on_hangar_space_create


def _on_hangar_space_create():
    hangarSpace.onSpaceCreate -= _on_hangar_space_create
    if _ssr_mod_installed():
        hint = u'Open Maneuvers from the hangar bottom menu (maneuvers item), if your client shows it.'
    else:
        hint = u'Open Maneuvers from the Replays button in the hangar bottom menu (reused while SSR mod is absent).'
    SystemMessages.pushMessage(
        text=(u'Maneuvers Manager v%s — %s') % (MOD_VERSION, hint),
        type=SystemMessages.SM_TYPE.InformationHeader,
        messageData={'header': 'MANEUVERS_MANAGER'},
    )
