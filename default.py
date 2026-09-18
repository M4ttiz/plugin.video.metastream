# -*- coding: utf-8 -*-
# ------------------------------------------------------------
# XBMC entry point
# ------------------------------------------------------------

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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


class MetastreamPlayer(xbmc.Player):
    def __init__(self, *args, **kwargs):
        self.current_media_key = ''
        self.resume_point = 0.0
        self.scrobble_done = False
        super().__init__()

    def _persist_resume(self) -> None:
        try:
            db = DatabaseManager()
            key = self.current_media_key or self.getPlayingFile() or 'unknown'
            db.save_watch_progress(key, float(self.getTime() or 0.0), watched=self.scrobble_done)
        except Exception as exc:
            xbmc.log(f"Watch progress save failed: {exc}", xbmc.LOGERROR)

    def _trakt_scrobble(self) -> None:
        if self.scrobble_done:
            return
        try:
            token = os.environ.get('TRAKT_ACCESS_TOKEN') or config.get_setting('trakt_token', default='')
            if not token:
                return
            payload = {
                'progress': 100,
                'status': 'completed',
                'media_key': self.current_media_key or self.getPlayingFile() or 'unknown',
            }
            self.scrobble_done = True
            worker = threading.Thread(
                target=lambda: self._trakt_scrobble_request(payload, token),
                daemon=True,
            )
            worker.start()
        except Exception as exc:
            xbmc.log(f"Trakt scrobble enqueue failed: {exc}", xbmc.LOGERROR)

    def _trakt_scrobble_request(self, payload: dict, token: str) -> None:
        try:
            import script.module.requests as requests
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'trakt-api-version': '2',
            }
            requests.post('https://api.trakt.tv/scrobble', headers=headers, json=payload, timeout=8)
        except Exception as exc:
            xbmc.log(f"Trakt scrobble request failed: {exc}", xbmc.LOGERROR)

    def onPlayBackStarted(self):
        self.scrobble_done = False
        self.resume_point = 0.0
        self.current_media_key = self.getPlayingFile() or self.current_media_key

    def onPlayBackEnded(self):
        self.resume_point = float(self.getTime() or 0.0)
        self._persist_resume()
        self._trakt_scrobble()

    def onPlayBackStopped(self):
        self.resume_point = float(self.getTime() or 0.0)
        self._persist_resume()
        self._trakt_scrobble()


def _provider_search(provider, query: str, limit: int = 10) -> list[dict]:
    return provider.search(query, limit=limit)


def _search_all_providers(query: str) -> list[dict]:
    providers = [TorrentioProvider(), BitSearchProvider()]
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, len(providers))) as executor:
        future_map = {executor.submit(_provider_search, provider, query, 10): provider for provider in providers}
        for future in as_completed(future_map):
            provider = future_map[future]
            try:
                future_result = future.result(timeout=4)
                if future_result:
                    results.extend(future_result)
            except Exception as exc:
                xbmc.log(f"Provider search failed for {provider.name}: {exc}", xbmc.LOGERROR)
    return results


def _render_search(handle: int, query: str) -> None:
    results = _search_all_providers(query)

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
        window.query = query
        window.page = 1
        window.load_more_callback = lambda q, page: _search_all_providers(q)
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
            status = getattr(exc, 'status_code', None)
            if status in (401, 403, 500, 502, 503, 504):
                xbmc.log(f"Debrid fallback triggered for {client.name} due to HTTP {status}", xbmc.LOGWARNING)
            last_error = f"{client.name}: {exc}"
            xbmc.log(f"Debrid resolution failed for {client.name}: {exc}", xbmc.LOGERROR)

    if not resolved_url:
        xbmcgui.Dialog().notification('Errore Risoluzione', last_error, xbmcgui.NOTIFICATION_ERROR)
        return

    debug_log('RESOLVE OUTPUT', resolved_url)
    player = MetastreamPlayer()
    player.current_media_key = magnet
    player.play(resolved_url)


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
