# -*- coding: utf-8 -*-
"""
DataExplorer

UI to configure a DVC run

Usage:
 predvc.py [ -h ] [--reference=<path>] [--correlate=<path>] [--guiconfig=<path>]

Options:
 --reference=path      reference filename
 --correlate=path      correlate filename  
 --guiconfig=path      output of DVC_configurator
 -h       display help

Example:
    python DVC_configurator.py --imagedata ..\..\..\CCPi-Simpleflex\data\head.mha

Created on Tue Jan 29 13:38:37 2019

@author: ofn77899
"""

from docopt import docopt
import os
# from ccpi.dvc import DVC
import json
import glob
import vtk
from ccpi.viewer.utils import parseNpyHeader
from ccpi.viewer.utils import cilNumpyMETAImageWriter


example_config = '''
###############################################################################
#																	
#
#		example dvc process control file		
#
#
###############################################################################

# all lines beginning with a # character are ignored
# some parameters are conditionally required, depending on the setting of other parameters
# for example, if subvol_thresh is off, the threshold description parameters are not required

### file names

reference_filename	{reference_filename}		### reference tomography image volume
correlate_filename	{correlate_filename}		### correlation tomography image volume

point_cloud_filename	{point_cloud_filename}	### file of search point locations
output_filename		{output_filename}		### base name for output files

### description of the image data files, all must be the same size and structure

vol_bit_depth		{vol_bit_depth}			### 8 or 16
vol_hdr_lngth		{vol_hdr_lngth}		### fixed-length header size, may be zero
vol_wide		{vol_wide}			### width in pixels of each slice
vol_high		{vol_high}			### height in pixels of each slice
vol_tall		{vol_tall}			### number of slices in the stack

### parameters defining the subvolumes that will be created at each search point

subvol_geom		{subvol_geom}			### cube, sphere
subvol_size		{subvol_size}			### side length or diameter, in voxels
subvol_npts		{subvol_npts}			### number of points to distribute within the subvol

subvol_thresh		{subvol_thresh}			### on or off, evaluate subvolumes based on threshold
gray_thresh_min	{gray_thresh_min}			### lower limit of a gray threshold range if subvol_thresh is on
gray_thresh_max	{gray_thresh_max}			### upper limit of a gray threshold range if subvol_thresh is on
min_vol_fract\t\t{min_vol_fract}			### only search if subvol fraction is greater than

### required parameters defining the basic the search process

disp_max		{disp_max}			### in voxels, used for range checking and global search limits
num_srch_dof		{num_srch_dof}			### 3, 6, or 12
obj_function		{obj_function}			### sad, ssd, zssd, nssd, znssd 
interp_type		{interp_type}		### trilinear, tricubic

### optional parameters tuning and refining the search process

rigid_trans		{rigid_trans}		### rigid body offset of target volume, in voxels
basin_radius		{basin_radius}			### coarse-search resolution, in voxels, 0.0 = none
subvol_aspect		{subvol_aspect}		### subvolume aspect ratio
'''

#def convertTiffTo8bit(fname):
#    stats = vtk.vtkImageAccumulate()
#    stats.SetInputData(importer.GetOutput())
#    stats.Update()
#    iMin = stats.GetMin()[0]
#    iMax = stats.GetMax()[0]
#    if (iMax - iMin == 0):
#        scale = 1
#    else:
#        if dtype == vtk.VTK_UNSIGNED_SHORT:
#            scale = vtk.VTK_UNSIGNED_SHORT_MAX / (iMax - iMin)
#        elif dtype == vtk.VTK_UNSIGNED_INT:
#            scale = vtk.VTK_UNSIGNED_INT_MAX / (iMax - iMin)
#
#    self.rescale[1] = (scale, -iMin)
#    shiftScaler = vtk.vtkImageShiftScale ()
#    shiftScaler.SetInputData(importer.GetOutput())
#    shiftScaler.SetScale(scale)
#    shiftScaler.SetShift(-iMin)
#    shiftScaler.SetOutputScalarType(dtype)
#    shiftScaler.Update() 


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

def processTiffStack(ref_fname, output_fname, bitdepth=16):
    flist = glob.glob(ref_fname)
    if len(flist) > 0:
        reader = vtk.vtkTIFFReader()
        #  determine bit depth
        reader.SetFileName(flist[0])
        reader.Update()
        vtk_bit_depth = reader.GetOutput().GetScalarType()
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
        elif vtk_bit_depth == vtk.VTK_SIGNED_SHORT:
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
        else:
            raise TypeError('Cannot handle non integer type of images')
        print ("Bit depth for input is {}".format(bit_depth))
        # convert to 8 or 16 if 32
        if bit_depth != bitdepth and bit_depth > bitdepth:
            print ("should cast image to")
            if bitdepth == 8:
                dtype = vtk.VTK_UNSIGNED_CHAR
            elif bitdepth == 16:
                dtype = vtk.VTK_UNSIGNED_SHORT
            print ("should cast image to {}".format(dtype))
            
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
            
            writer = vtk.vtkMetaImageWriter()
            shiftScaler = vtk.vtkImageShiftScale ()
            
            new_flist = []
            for fname in flist:
                reader.SetFileName(fname)
                reader.Update()
            
                if reader.GetOutput().GetScalarType() == vtk.VTK_UNSIGNED_SHORT:
                    imax = vtk.VTK_UNSIGNED_SHORT_MAX
                elif reader.GetOutput().GetScalarType() == vtk.VTK_SIGNED_SHORT:
                    imax = vtk.VTK_SIGNED_SHORT_MAX
                elif vtk_bit_depth == vtk.VTK_UNSIGNED_INT:
                    imax = vtk.VTK_UNSIGNED_INT_MAX
                elif reader.GetOutput().GetScalarType() == vtk.VTK_INT:
                    imax = vtk.VTK_INT_MAX
                scale = int(imax / (all_max - all_min))
            
                shiftScaler.SetInputConnection(reader.GetOutputPort())
                shiftScaler.SetScale(scale)
                shiftScaler.SetShift(-all_min)
                shiftScaler.SetOutputScalarType(dtype)
                shiftScaler.Update() 
                
                writer.SetFileName('{}bit_{}'.format(bitdepth, fname))
                writer.SetInputConnection(shiftScaler.GetOutputPort())
                writer.Write()
                new_flist.append(writer.GetFileName())
            
            # save original flist 
            orig_flist = flist[:]
            # copy the new file list into flist
            flist = new_flist[:]
        else:
            print ("no need to cast image type")
            
        # load the whole bitdepth (16 bit)
        sa = vtk.vtkStringArray()
        for fname in flist:
            #fname = os.path.join(directory,"8bit-1%04d.tif" % i)
            i = sa.InsertNextValue(fname)

            print("read {} files".format(i))

        reader.SetFileNames(sa)
        reader.Update()
        # write it as META image
        
        writer = vtk.vtkMetaImageWriter()
        writer.SetFileName(output_fname+'.mhd')
        writer.SetCompression(0)
        writer.SetInputConnection(reader.GetOutputPort())
        writer.Write()
        
    else:
        raise ValueError('File Not Found')

if __name__ == '__main__':
    # runcontrol = DVC()
    __version__ = '0.1.0'
    print ("Starting ... ")
    args = docopt(__doc__, version=__version__)
    print ("Parsing args")
    print ("Passed args " , args)
    
    with open(args['--guiconfig'], 'r') as f:
        guiconfig = json.load(f)

    if '--reference' in args.keys():
        ref_fname = args['--reference']
        processTiffStack(ref_fname, 'prova')        
            
        
        
    # cor_fname = args['--correlate']
    
    msg = example_config.format(reference_filename='reference_filename' , 
                                correlate_filename='correlate_filename',
                                point_cloud_filename=guiconfig['point_cloud_filename'],
                                output_filename='output_filename',
                                vol_bit_depth='8',
                                vol_hdr_lngth='80',
                                vol_wide=guiconfig['vol_wide'],
                                vol_high=guiconfig['vol_high'],
                                vol_tall=guiconfig['vol_tall'],
                                subvol_geom=guiconfig['subvol_geom'],
                                subvol_size=guiconfig['subvol_size'],
                                subvol_npts=guiconfig['subvol_npts'],
                                subvol_thresh='off',
                                gray_thresh_min='27',
                                gray_thresh_max='127',
                                min_vol_fract='0.2',
                                disp_max='38',
                                num_srch_dof='6', 
                                obj_function='znssd',
                                interp_type='tricubic',
                                rigid_trans='74.0 0.0 0.0',
                                basin_radius='0.0',
                                subvol_aspect='1.0 1.0 1.0')
    #print (msg)
    
    