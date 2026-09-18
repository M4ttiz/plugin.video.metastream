# -*- coding: utf-8 -*-

import threading
from urllib.parse import quote

import xbmc
import xbmcgui

from platformcode import config


class MetastreamView(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.results = []
        self.handle = -1
        self.query = ''
        self.page = 1
        self.load_more_callback = None
        self.is_loading = False

    def _build_item(self, result):
        title = result.get('title', 'Unknown title')
        quality = result.get('quality') or 'unknown'
        provider = result.get('provider') or 'unknown'
        magnet = result.get('magnet') or ''
        size = result.get('size') or ''

        item = xbmcgui.ListItem(label=title)
        item.setProperty('title', title)
        item.setProperty('quality', quality)
        item.setProperty('provider', provider)
        item.setProperty('size', str(size))
        item.setProperty('magnet', magnet)
        item.setProperty('plot', quality)
        item.setProperty('label2', f'{provider} • {size}' if size else provider)
        if result.get('thumbnail'):
            item.setArt({'thumb': result.get('thumbnail'), 'poster': result.get('thumbnail')})
        return item

    def _append_items(self, items):
        panel = self.getControl(50)
        if panel is None:
            return
        for record in items:
            panel.addItem(self._build_item(record))

    def _load_next_page(self):
        if self.is_loading or not self.load_more_callback or not self.query:
            return
        self.is_loading = True

        def _worker():
            try:
                next_results = self.load_more_callback(self.query, self.page + 1)
                if next_results:
                    self.page += 1
                    self.results.extend(next_results)
                    for result in next_results:
                        result.setdefault('provider', 'unknown')
                    xbmc.executebuiltin('Container.Refresh')
                    self._append_items(next_results)
            except Exception as exc:
                xbmc.log(f"Infinite-scroll load failed: {exc}", xbmc.LOGERROR)
            finally:
                self.is_loading = False

        threading.Thread(target=_worker, daemon=True).start()

    def onInit(self):
        panel = self.getControl(50)
        if panel is None:
            xbmc.log('[METASTREAM-DEBUG] custom_view.xml missing control id=50', xbmc.LOGERROR)
            self.close()
            return

        panel.reset()
        self._append_items(self.results)
        if panel.size() > 0:
            panel.selectItem(0)

    def onClick(self, control_id):
        if control_id == 50:
            self._open_selected()

    def onAction(self, action):
        action_id = action.getId() if hasattr(action, 'getId') else action
        if action_id in (10, 92):
            self.close()
            return
        if action_id in (4, 5, 6, 7):
            panel = self.getControl(50)
            if panel is not None and panel.size() > 0:
                pos = panel.getSelectedPosition()
                if pos >= max(0, panel.size() - 2):
                    self._load_next_page()
            if action_id == 7:
                self._open_selected()

    def _open_selected(self):
        panel = self.getControl(50)
        if panel is None or panel.size() == 0:
            self.close()
            return

        selected_item = panel.getSelectedItem()
        magnet = selected_item.getProperty('magnet') if selected_item else ''
        if not magnet:
            self.close()
            return

        plugin_name = getattr(config, 'PLUGIN_NAME', 'plugin.video.s4me')
        xbmc.executebuiltin(
            'RunPlugin(plugin://{}/?action=resolve&magnet={})'.format(
                plugin_name,
                quote(magnet)
            )
        )
        self.close()
