# -*- coding: utf-8 -*-
"""
Created on Wed Jan 23 14:37:57 2019

@author: ofn77899
"""


def copyslices(indata, fromslice, zmin, zmax):
    cdef int x, y, z
    dims = indata.GetDimensions()
    for x in range(dims[0]):
        for y in range(dims[1]):
            for z in range(zmin, zmax):
                if z != fromslice:
                    val = indata.GetScalarComponentAsFloat(x,y,fromslice,0)
                    indata.SetScalarComponentFromFloat(x,y,z,0,val)
    return 1
