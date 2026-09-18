# -*- coding: utf-8 -*-

from urllib.parse import quote

import xbmc
import xbmcgui

from platformcode import config


class MetastreamView(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self.results = []
        self.handle = -1

    def onInit(self):
        list_control = self.getControl(50)
        if list_control is None:
            xbmc.log('[METASTREAM-DEBUG] custom_view.xml missing control id=50', xbmc.LOGERROR)
            self.close()
            return

        list_control.reset()
        for result in self.results:
            title = result.get('title', 'Unknown title')
            quality = result.get('quality') or 'unknown'
            provider = result.get('provider') or 'unknown'
            magnet = result.get('magnet') or ''
            size = result.get('size') or ''

            list_item = xbmcgui.ListItem(label=title)
            list_item.setProperty('title', title)
            list_item.setProperty('quality', quality)
            list_item.setProperty('provider', provider)
            list_item.setProperty('size', str(size))
            list_item.setProperty('magnet', magnet)
            list_item.setProperty('plot', quality)
            list_item.setProperty('label2', f'{provider} • {size}' if size else provider)
            if result.get('thumbnail'):
                list_item.setArt({'thumb': result.get('thumbnail'), 'poster': result.get('thumbnail')})
            list_control.addItem(list_item)

        if list_control.size() > 0:
            list_control.selectItem(0)

    def onClick(self, control_id):
        if control_id == 50:
            self._open_selected()

    def onAction(self, action):
        action_id = action.getId() if hasattr(action, 'getId') else action
        if action_id in (10, 92):
            self.close()
            return
        if action_id == 7:
            self._open_selected()

    def _open_selected(self):
        list_control = self.getControl(50)
        if list_control is None or list_control.size() == 0:
            self.close()
            return

        selected_item = list_control.getSelectedItem()
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
