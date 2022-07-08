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
dversion = subprocess.check_output(cmd, shell=True).strip().decode('utf-8')[1:].rstrip()

print ('version {}'.format(dversion))

if os.environ.get('CONDA_BUILD', '0') == '1':
    cwd = os.path.join(os.environ.get('RECIPE_DIR'),'..')
else:
    cwd = os.path.dirname(__file__)

# update the version string
fname = os.path.join(cwd, 'src', 'idvc', 'version.py')

if os.path.exists(fname):
    os.remove(fname)
with open(fname, 'w') as f:
    f.write('version = \'{}\''.format(dversion))

setup(
      name = "idvc",
      description = 'CCPi DVC Configurator',
	version = dversion,
	packages = {'idvc'},
      package_dir = {'idvc': os.path.join('src','idvc')},
      package_data = {'idvc':['DVCIconSquare.png']},
      # metadata for upload to PyPI
      author="Edoardo Pasca, Laura Murgatroyd",
      author_email="edo.paskino@gmail.com",
      license="Apache v2.0",
      keywords="Digital Volume Correlation",
      url="http://www.ccpi.ac.uk",   # project home page, if any
      entry_points= {'console_scripts': ['idvc = idvc.dvc_interface:main']}
)
