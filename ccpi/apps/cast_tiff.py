# -*- coding: utf-8 -*-
"""
tiffTo8bit

Convert TIFF files to uint8 or uint16 bit

Usage:
 tiffTo8bit.py [ -h ] -i=<path> -o=<path> [ --dtype=8 ] 

Options:
 -i=path           input filename(s)
 -o=path           output directory
 --dtype=8         the bit depth (8 or 16)
 -h       display help
 
version = 1.0
Created on Thu Jan 24 14:54:50 2019
@author: ofn77899
"""

import docopt
import os
# import json
import glob
import vtk
from tqdm import tqdm

# VTK_SIGNED_CHAR,     # int8
# VTK_UNSIGNED_CHAR,   # uint8
# VTK_SHORT,           # int16
# VTK_UNSIGNED_SHORT,  # uint16
# VTK_INT,             # int32
# VTK_UNSIGNED_INT,    # uint32
# VTK_FLOAT,           # float32
# VTK_DOUBLE,          # float64
# VTK_FLOAT,           # float32
# VTK_DOUBLE,          #

def processTiffStack(wildcard_filenames, output_dir, bitdepth=16):
    '''reads a tiff stack and casts to UNSIGNED INT 8 or 16, saves to MetaImage'''
    flist = glob.glob(wildcard_filenames)
    if len(flist) > 0:
        reader = vtk.vtkTIFFReader()
        #  determine bit depth
        reader.SetFileName(flist[0])
        reader.Update()
        vtk_bit_depth = reader.GetOutput().GetScalarType()
        print ("Input Scalar type" , reader.GetOutput().GetScalarTypeAsString())
        if vtk_bit_depth == vtk.VTK_UNSIGNED_CHAR:
            bit_depth = 8
            all_min = vtk.VTK_UNSIGNED_CHAR_MAX
            all_max = vtk.VTK_UNSIGNED_CHAR_MIN
        elif vtk_bit_depth == vtk.VTK_SIGNED_CHAR:
            bit_depth = 8
            all_min = vtk.VTK_SIGNED_CHAR_MAX
            all_max = vtk.VTK_SIGNED_CHAR_MIN
        elif vtk_bit_depth == vtk.VTK_UNSIGNED_SHORT:
            bit_depth = 16
            all_min = vtk.VTK_UNSIGNED_SHORT_MAX
            all_max = vtk.VTK_UNSIGNED_SHORT_MIN
        elif vtk_bit_depth == vtk.VTK_SHORT:
            bit_depth = 16
            all_min = vtk.VTK_SIGNED_SHORT_MAX
            all_max = vtk.VTK_SIGNED_SHORT_MIN
        elif vtk_bit_depth == vtk.VTK_UNSIGNED_INT:
            bit_depth = 32
            all_min = vtk.VTK_UNSIGNED_INT_MAX
            all_max = vtk.VTK_UNSIGNED_INT_MIN
        elif vtk_bit_depth == vtk.VTK_INT:
            bit_depth = 32
            all_min = vtk.VTK_INT_MAX
            all_max = vtk.VTK_INT_MIN
        elif vtk_bit_depth == vtk.VTK_FLOAT:
            all_min = vtk.VTK_FLOAT_MAX
            all_max = vtk.VTK_FLOAT_MIN
            bit_depth = 32
        elif vtk_bit_depth == vtk.VTK_DOUBLE:
            all_min = vtk.VTK_DOUBLE_MAX
            all_max = vtk.VTK_DOUBLE_MIN
            bit_depth = 64
        else:
            raise TypeError('Cannot handle this type of images')
        # convert to 8 or 16 if 32
        if bit_depth != bitdepth and bit_depth > bitdepth:
            if bitdepth == 8:
                dtype = vtk.VTK_UNSIGNED_CHAR
                imax = vtk.VTK_UNSIGNED_CHAR_MAX
                imin = 0
                dtypestring = 'uint8'
            elif bitdepth == 16:
                dtype = vtk.VTK_UNSIGNED_SHORT
                imax = vtk.VTK_UNSIGNED_SHORT_MAX
                imin = 0
                dtypestring = 'uint16'
            print ("Casting images to {}".format(dtypestring))
            
            stats = vtk.vtkImageAccumulate()
            print ("looking for min max in the dataset")
            for fname in flist:
                reader.SetFileName(fname)
                reader.Update()
                stats.SetInputConnection(reader.GetOutputPort())
                stats.Update()
                iMin = stats.GetMin()[0]
                iMax = stats.GetMax()[0]
                all_max = all_max if iMax < all_max else iMax
                all_min = all_min if iMin > all_min else iMin
            
            writer = vtk.vtkTIFFWriter()
            
            scale = int( (imax - imin) / (all_max - all_min))
            print ("min {}\nmax {}\nscale {}".format(all_min, all_max, scale))
            shiftScaler = vtk.vtkImageShiftScale ()
            shiftScaler.SetInputConnection(reader.GetOutputPort())
            shiftScaler.SetScale(scale)
            shiftScaler.SetShift(-all_min)
            shiftScaler.SetOutputScalarType(dtype)
            
            writer.SetInputConnection(shiftScaler.GetOutputPort())
            
            # creates the output directory if not present
            if not os.path.exists(os.path.abspath(output_dir)):
                os.mkdir(os.path.abspath(output_dir))
                
            new_flist = []
            for i,fname in enumerate(tqdm(flist)):
                
                reader.SetFileName(fname)
                reader.Update()
                                
                shiftScaler.Update() 
                
                writer.SetFileName(os.path.join(os.path.abspath(output_dir), 
                                   '{}_{}'.format(dtypestring, os.path.basename(fname))))
                writer.Write()
                new_flist.append(writer.GetFileName())
            
            # save original flist 
            orig_flist = flist[:]
            # copy the new file list into flist
            flist = new_flist[:]
        else:
            print ("no need to cast image type")        
    else:
        raise ValueError('Could not find files in ', wildcard_filenames)

if __name__ == '__main__':
    # runcontrol = DVC()
    __version__ = '0.1.0'
    print ("Starting ... ")
    args = docopt.docopt(__doc__, version=__version__)
     
    if args['--dtype'] is None:
        args['--dtype'] = 8
    
    for k,v in args.items():
        print (k,v)
    processTiffStack(args['-i'], args['-o'], args['--dtype'])
        