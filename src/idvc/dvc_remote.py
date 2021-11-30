import os

class PrepareDVCRemote(object):
    def __init__(self, parent):
        self._config_json = None
        self._remote_workdir = None
        self.parent = parent

    
    @property
    def config_json(self):
        return self._config_json


    def set_config_json(self, value):
        self._config_json = os.path.abspath(value)


    @property
    def remote_workdir(self):
        return self._remote_workdir

    
    def set_remote_workdir(self):
        self._remote_workdir = self.parent.settings_window