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
from distutils.extension import Extension

cil_version = os.system('git describe')
fname = os.path.join(os.path.getcwd(), 'ccpi', 'apps', 'dvc', 'version.py')

if os.path.exists(fname):
    os.remove(fname)
with open(fname, 'w+') as f:
    f.write('version = \'{}\''.format(cil_version))

# sourcefiles = ["src/image_data.py"]

# extensions = [Extension("ccpi.apps.image_data", sourcefiles)]

setup(
      name="Digital Volume Correlation App",
      description='CCPi DVC Configurator',
	version=cil_version,
	packages = {'ccpi','ccpi.dvc.apps'},
      package_dir={'ccpi.dvc.apps': 'ccpi/dvc/apps'},
      package_data= {'ccpi.dvc.apps':['DVCIconSquare.png']}
      #ext_modules=extensions
)
