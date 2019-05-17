# -*- coding: utf-8 -*-
"""
tiffTo8bit

Convert TIFF files to uint8 or uint16 bit

Usage:
 cast_tiff.py [ -h ] -i <path> -o <path> [ --dtype 8 ] [ --extent=xmin,xmax,ymin,ymax,zmin,zmax ]

Options:
 -i=path           input filename(s)
 -o=path           output directory
 --dtype=8         the bit depth (8 or 16)
 --extent=xmin,xmax,ymin,ymax,zmin,zmax
 -h       display help
 
version = 1.0
Created on Thu Jan 24 14:54:50 2019
@author: ofn77899
"""

import docopt
import os, sys
# import json
import glob
import vtk
from tqdm import tqdm
from vtk.util import numpy_support
import numpy
import matplotlib.pyplot as plt 

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

def processTiffStack(wildcard_filenames, output_dir, bitdepth=16, extent=None, percentiles=None):
    '''reads a tiff stack and casts to UNSIGNED INT 8 or 16, saves to MetaImage'''
    tmp = glob.glob(wildcard_filenames)
    print ("Found {} files".format(len(tmp)))
    
    if extent != None:
        print ("Volume of interest ", extent)
        flist = [tmp[i] for i in range(extent[4], extent[5])] 
    else:
        flist = tmp
    print ("processing {} files of {}".format(len(flist), len(tmp)))
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
            voi = vtk.vtkExtractVOI()
            print ("looking for min max in the dataset")
            
            
            for i,fname in tqdm(enumerate(flist)):
                reader.SetFileName(fname)
                reader.Update()
                if extent != None:
                    voi.SetInputConnection(reader.GetOutputPort())
                    voi.SetVOI(extent[0], extent[1], extent[2], extent[3], 0, 0)
                    voi.Update()
                    stats.SetInputConnection(voi.GetOutputPort())
                else:
                    stats.SetInputConnection(reader.GetOutputPort())
                stats.Update()
                iMin = stats.GetMin()[0]
                iMax = stats.GetMax()[0]
                all_max = all_max if iMax < all_max else iMax
                all_min = all_min if iMin > all_min else iMin
            
            
            # create a histogram of the whole dataset
            nbins = vtk.VTK_UNSIGNED_SHORT_MAX + 1
            nbins = 255
            print ("Constructing the histogram of the whole dataset")
            for i,fname in enumerate(tqdm(flist)):
                reader.SetFileName(fname)
                reader.Update()
                if extent != None:
                    voi.SetInputConnection(reader.GetOutputPort())
                    voi.SetVOI(extent[0], extent[1], extent[2], extent[3], 0, 0)
                    voi.Update()
                    img_data = numpy_support.vtk_to_numpy(
                        voi.GetOutput().GetPointData().GetScalars()
                        )
                else:
                    img_data = numpy_support.vtk_to_numpy(
                        reader.GetOutput().GetPointData().GetScalars()
                        )
                if i == 0:
                    histogram , bin_edges = numpy.histogram(img_data, nbins, (all_min, all_max))
                else:
                    h = numpy.histogram(img_data, nbins, (all_min, all_max))
                    histogram += h[0]

            if percentiles is None:
                percentiles = (1,99)
            # find the bin at which we have to cut for the percentiles
            nvoxels = histogram.sum()
            percentiles = [p * nvoxels / 100 for p in percentiles]
            current_perc = 0
            for i,el in enumerate(histogram):
                current_perc += el
                if current_perc > percentiles[0]:
                    break
            min_perc = i
            current_perc = 0
            for i,el in enumerate(histogram):
                current_perc += el
                if current_perc >= percentiles[1]:
                    break
            max_perc = i

            #plt.hist(histogram, range=(bin_edges[0], bin_edges[-1]), log=True)
            #plt.bar(bin_edges[1:], histogram, log=True)
            #plt.semilogy(bin_edges[1:],histogram)
            plt.plot(bin_edges[1:],histogram)
            plt.axvline(x=bin_edges[min_perc])
            plt.axvline(x=bin_edges[max_perc])
            plt.show()
            scale = (imax - imin) / (bin_edges[max_perc] - bin_edges[min_perc])
            print ("min {}\tmax {}\nedge_min {}\tedge_max {}\nscale {}".format(
                all_min, all_max, bin_edges[min_perc] ,bin_edges[max_perc], scale))
            
            #sys.exit(0)
            
            
            shiftScaler = vtk.vtkImageShiftScale ()
            shiftScaler.ClampOverflowOn()
            if extent != None and False:
                voi.SetInputConnection(reader.GetOutputPort())
                voi.SetVOI(extent[0], extent[1], extent[2], extent[3], 0, 0)
                shiftScaler.SetInputConnection(voi.GetOutputPort())
            else:
                shiftScaler.SetInputConnection(reader.GetOutputPort())
            shiftScaler.SetScale(scale)

            shiftScaler.SetShift(-bin_edges[min_perc])
  
            shiftScaler.SetOutputScalarType(dtype)
            
            writer = vtk.vtkTIFFWriter()
            
            writer.SetInputConnection(shiftScaler.GetOutputPort())
            
            # creates the output directory if not present
            if not os.path.exists(os.path.abspath(output_dir)):
                os.mkdir(os.path.abspath(output_dir))
                
            new_flist = []
            for i,fname in enumerate(tqdm(flist)):
                
                reader.SetFileName(fname)
                reader.Update()
                if extent != None and False:
                    voi.SetInputConnection(reader.GetOutputPort())
                    voi.SetVOI(extent[0], extent[1], extent[2], extent[3], 0, 0)
                    
                    voi.Update()
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




def main():
    # runcontrol = DVC()
    __version__ = '0.1.0'
    print ("Starting ... ")
    args = docopt.docopt(__doc__, version=__version__)
    for k,v in args.items():
        print (k,v) 
    if args['--dtype'] is None:
        args['--dtype'] = 8
    extent = args.get('--extent', None)
    if extent is not None:
        extent = eval('['+extent+']')
    print ("extent", extent)
    
    
    processTiffStack(args['-i'], args['-o'], args['--dtype'], extent=extent)

if __name__ == '__main__':
    main()