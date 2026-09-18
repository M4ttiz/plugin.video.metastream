# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# XBMC entry point
# ------------------------------------------------------------

import json
import os
import sys
import threading
from urllib.parse import parse_qsl, quote, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from core.ui import MetastreamView


def debug_log(prefix, data):
    try:
        dump = json.dumps(data)
    except Exception:
        dump = str(data)
    xbmc.log(f"[METASTREAM-DEBUG] {prefix}: {dump}", xbmc.LOGINFO)

# functions that on kodi 19 moved to xbmcvfs
try:
    import xbmcvfs
    xbmc.translatePath = xbmcvfs.translatePath
    xbmc.validatePath = xbmcvfs.validatePath
    xbmc.makeLegalFilename = xbmcvfs.makeLegalFilename
except ImportError:
    xbmc.log('xmbcvfs unavailable; using default Kodi filesystem helpers.', xbmc.LOGINFO)

from platformcode import config, logger
from platformcode.database import DatabaseManager
from core.debrid import RealDebridClient, AllDebridClient, PremiumizeClient
from core.providers import TorrentioProvider, BitSearchProvider
from core.metadata import MetadataService

logger.info("init...")

librerias = xbmc.translatePath(os.path.join(config.get_runtime_path(), 'lib'))
sys.path.insert(0, librerias)
os.environ['TMPDIR'] = config.get_temp_file('')

from platformcode import launcher


def parse_kodi_params() -> tuple[int, dict]:
    handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else -1
    params = {}
    if len(sys.argv) > 2 and sys.argv[2].startswith('?'):
        params = dict(parse_qsl(sys.argv[2][1:]))
    return handle, params


def _render_search(handle: int, query: str) -> None:
    providers = [TorrentioProvider(), BitSearchProvider()]
    results: list[dict] = []

    for provider in providers:
        try:
            provider_results = provider.search(query, limit=10)
            results.extend(provider_results)
        except Exception as exc:
            xbmc.log(f"Provider search failed for {provider.name}: {exc}", xbmc.LOGERROR)

    for record in results:
        record.setdefault('provider', 'unknown')

    debug_log('PROVIDER PAYLOAD', results)

    if not results:
        empty_item = xbmcgui.ListItem(label='No results')
        xbmcplugin.addDirectoryItem(handle, '', empty_item, isFolder=False)
        xbmcplugin.endOfDirectory(handle)
        return

    try:
        window = MetastreamView('custom_view.xml', config.get_runtime_path())
        window.results = results
        window.handle = handle
        window.doModal()
        del window
        return
    except Exception as exc:
        xbmc.log(f"Custom search view failed, falling back to native list: {exc}", xbmc.LOGERROR)

    for record in results:
        title = record.get('title', 'Unknown title')
        quality = record.get('quality') or 'unknown'
        list_item = xbmcgui.ListItem(label=title)
        list_item.setInfo('video', {'title': title, 'plot': quality})
        list_item.setArt({'poster': '', 'fanart': '', 'thumb': ''})
        list_item.setProperty('IsPlayable', 'true')

        magnet = record.get('magnet') or ''
        encoded_magnet = quote(magnet)
        plugin_url = f"plugin://plugin.video.{config.PLUGIN_NAME}/?action=resolve&magnet={encoded_magnet}"
        xbmcplugin.addDirectoryItem(handle, plugin_url, list_item, isFolder=False)

    xbmcplugin.endOfDirectory(handle)

    def _persist_results() -> None:
        try:
            metadata = MetadataService()
            db = DatabaseManager()
            rows = []
            for item in results:
                title = item.get('title', 'Unknown title')
                media_info = metadata.get_media_details('movie', query=title) if title else {}
                imdb_id = media_info.get('imdb_id', '') if isinstance(media_info, dict) else ''
                tmdb_id = media_info.get('id', '') if isinstance(media_info, dict) else ''
                rows.append((imdb_id, str(tmdb_id), title, str(item)))
            if rows:
                db.bulk_insert(rows)
        except Exception as exc:
            xbmc.log(f"Async metadata persistence failed: {exc}", xbmc.LOGERROR)
        finally:
            xbmc.executebuiltin('Container.Refresh')

    worker = threading.Thread(target=_persist_results, daemon=True)
    worker.start()


def _resolve_magnet(handle: int, magnet: str) -> None:
    if not magnet:
        xbmcgui.Dialog().notification('Errore Risoluzione', 'Payload magnet mancante', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    resolved_url = ''
    last_error = 'payload non valido'
    debrid_clients = [RealDebridClient(), AllDebridClient(), PremiumizeClient()]
    for client in debrid_clients:
        try:
            resolved_url = client.resolve_magnet(magnet)
            if resolved_url:
                break
        except Exception as exc:
            last_error = f"{client.name}: {exc}"
            xbmc.log(f"Debrid resolution failed for {client.name}: {exc}", xbmc.LOGERROR)

    if not resolved_url:
        xbmcgui.Dialog().notification('Errore Risoluzione', last_error, xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem())
        return

    debug_log('RESOLVE OUTPUT', resolved_url)
    item = xbmcgui.ListItem(label='Resolved stream')
    item.setPath(resolved_url)
    item.setProperty('IsPlayable', 'true')
    xbmcplugin.setResolvedUrl(handle, True, item)


def _route() -> None:
    handle, params = parse_kodi_params()
    debug_log('ROUTER ENTRY', params)
    action = params.get('action')

    if action == 'search':
        query = params.get('query', '')
        if query:
            _render_search(handle, query)
            return

    if action == 'resolve':
        magnet = params.get('magnet', '') or params.get('torrent_id', '')
        debug_log('RESOLVE INPUT', magnet)
        if magnet:
            _resolve_magnet(handle, magnet)
            return

    if len(sys.argv) > 2 and sys.argv[2] == '':
        launcher.start()
    launcher.run()


if len(sys.argv) > 2 and sys.argv[2] == '':
    launcher.start()

_route()
