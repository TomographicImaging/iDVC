# -*- coding: utf-8 -*-
"""
Created on Wed Jan 23 14:37:57 2019

@author: ofn77899
"""


def copyslices(indata, fromslice, zmin, zmax):
    cdef int x, y, z
    cdef double val
    dims = indata.GetDimensions()
    for z in range(zmin, zmax):
        for y in range(dims[1]):
            for x in range(dims[0]):
                if z != fromslice:
                    val = indata.GetScalarComponentAsDouble(x,y,fromslice,0)
                    if val != 0
                        indata.SetScalarComponentFromDouble(x,y,z,0,val)
    return 1
