# -*- coding: utf-8 -*-
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
      # cmdclass = {'build_ext': build_ext},
	   packages = {'ccpi','ccpi.apps'},
      ext_modules=cythonize(extensions)
)