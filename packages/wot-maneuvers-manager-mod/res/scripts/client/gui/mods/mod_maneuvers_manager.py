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
# Replaced at build time (see packages/wot-maneuvers-manager-mod/build.cfg).
AUTH_ORIGIN = '{{AUTH_ORIGIN}}'
_LOGGER = logging.getLogger(__name__)

MENU_ID_MANEUVERS = 'maneuversManager'

hangarSpace = dependency.instance(IHangarSpace)


def _auth_base():
    return AUTH_ORIGIN.rstrip('/') + '/auth'


def _build_auth_url(access_token, periphery_id, spa_id):
    # Prod or local origin from AUTH_ORIGIN; token + realm ids (same as WG clan/WGSH flows).
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
    return _auth_base() + '?' + query


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


@wg_async
def _show_maneuvers_modal():
    result = yield wg_await(_run_access_token_only())
    if not isinstance(result, dict):
        result = {u'error': u'Unexpected result'}

    err = result.get(u'error')
    if err:
        _LOGGER.error('Maneuvers Manager: %s', err)
        body = u'Could not open Maneuvers Manager. Try again in a moment.'
        buttons = [{DialogButtons.CANCEL: 'Close'}]
        default_button = DialogButtons.CANCEL
    else:
        body = u'Open Maneuvers Manager in your browser?'
        buttons = [
            {DialogButtons.SUBMIT: 'Open'},
            {DialogButtons.CANCEL: 'Close'},
        ]
        default_button = DialogButtons.SUBMIT

    builder = FormattedSimpleDialogBuilder()
    builder.setMessagesAndButtons(
        DialogPresets.INFO,
        'Maneuvers Manager',
        body,
        buttons,
        default_button,
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
            return
        url = _build_auth_url(
            result.get(u'access_token'),
            result.get(u'periphery_id'),
            result.get(u'spa_id'),
        )
        if not url:
            _LOGGER.error('Maneuvers Manager: no access token to open')
            SystemMessages.pushMessage(
                text=u'Could not open Maneuvers Manager. Try again in a moment.',
                type=SystemMessages.SM_TYPE.Warning,
            )
            return
        try:
            BigWorld.wg_openWebBrowser(url)
            SystemMessages.pushMessage(
                text=u'Opening Maneuvers Manager…',
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

    hangarSpace.onSpaceCreate += _on_hangar_space_create


def _on_hangar_space_create():
    hangarSpace.onSpaceCreate -= _on_hangar_space_create
    hint = u'Open Maneuvers Manager from the hangar menu.'
    SystemMessages.pushMessage(
        text=(u'Maneuvers Manager v%s — %s') % (MOD_VERSION, hint),
        type=SystemMessages.SM_TYPE.InformationHeader,
        messageData={'header': 'MANEUVERS_MANAGER'},
    )
