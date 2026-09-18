import importlib
import sys
import types


class _DummyDialog:
    def notification(self, *args, **kwargs):
        return None


xbmc = types.ModuleType('xbmc')
xbmc.LOGERROR = 0
xbmc.LOGINFO = 1
xbmc.log = lambda *args, **kwargs: None
xbmc.executeJSONRPC = lambda payload: '{"result": {"value": true}}'
xbmcgui = types.ModuleType('xbmcgui')
xbmcgui.Dialog = lambda: _DummyDialog()

sys.modules.setdefault('xbmc', xbmc)
sys.modules.setdefault('xbmcgui', xbmcgui)


def test_debrid_clients_are_available():
    debrid = importlib.import_module('core.debrid')
    assert hasattr(debrid, 'RealDebridClient')
    assert hasattr(debrid, 'AllDebridClient')
    assert hasattr(debrid, 'PremiumizeClient')


def test_provider_parsers_are_available():
    providers = importlib.import_module('core.providers')
    assert hasattr(providers, 'TorrentioProvider')
    assert hasattr(providers, 'BitSearchProvider')


def test_metadata_service_is_available():
    metadata = importlib.import_module('core.metadata')
    assert hasattr(metadata, 'MetadataService')


def test_database_manager_has_indexes():
    db_module = importlib.import_module('platformcode.database')
    assert hasattr(db_module, 'DatabaseManager')
    manager = db_module.DatabaseManager(':memory:')
    assert 'CREATE INDEX IF NOT EXISTS idx_media_cache_imdb_id' in manager.index_sql()
    assert 'CREATE INDEX IF NOT EXISTS idx_media_cache_tmdb_id' in manager.index_sql()
