# -*- coding: utf-8 -*-
#   Copyright 2019 Edoardo Pasca
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
"""
Created on Wed Jan 23 14:33:56 2019

@author: ofn77899
"""
import os
from distutils.core import setup
from Cython.Build import cythonize
from distutils.extension import Extension

cil_version=os.environ['CIL_VERSION']
if  cil_version == '':
    print("Please set the environmental variable CIL_VERSION")
    sys.exit(1)

sourcefiles = ["src/vtkutils.pyx"]

extensions = [Extension("ccpi.apps.vtkutils", sourcefiles)]

setup(
      name="DVC configurator app",
      description='CCPi DVC Configurator',
	   version=cil_version,
	   packages = {'ccpi','ccpi.apps'},
      ext_modules=cythonize(extensions)
)