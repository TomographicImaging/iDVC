# -*- coding: utf-8 -*-
#   Copyright 2019 - 2020 Edoardo Pasca
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
from distutils.core import setup
import subprocess

cmd = 'git describe'
dversion = subprocess.check_output(cmd, shell=True).strip().decode('utf-8')

print ('version {}'.format(dversion))

# if os.environ.get('CONDA_BUILD', 0) == 0:
#       cwd = os.getcwd()
# else:
#       cwd = os.path.join(os.environ.get('SRC_DIR'),'..')
# fname = os.path.abspath(os.path.join(cwd, 'ccpi', 'dvc', 'apps', 'version.py'))

# print ("Creating version.py in {}".format(fname))
# if os.path.exists(fname):
#     print ("path already exists, deleting")
#     os.remove(fname)
# with open(fname, 'w') as f:
#     f.write('version = \'{}\''.format(dversion))
#     print ("creating version.py in {}".format(os.path.dirname(fname)))

setup(
      name = "Digital Volume Correlation App",
      description = 'CCPi DVC Configurator',
	version = dversion,
	packages = {'ccpi','ccpi.dvc', 'ccpi.dvc.apps'},
      package_dir = {'ccpi.dvc.apps': 'ccpi/dvc/apps'},
      package_data = {'ccpi.dvc.apps':['DVCIconSquare.png']}
      
)
