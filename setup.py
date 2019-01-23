# -*- coding: utf-8 -*-
"""
Created on Wed Jan 23 14:33:56 2019

@author: ofn77899
"""

from distutils.core import setup
from Cython.Build import cythonize

setup(
    ext_modules = cythonize("vtkutils.pyx")
)