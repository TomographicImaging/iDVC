# -*- coding: utf-8 -*-
"""
predvc

configure a DVC run from the graphical user interface 

Usage:
 predvc.py [ -h ] --ref <path> --cor <path> --guiconfig <path> -o output_fname

Options:
 --ref path            reference filename
 --cor path            correlate filename  
 --guiconfig path      output of DVC_configurator
 -o file name          output file name
 -h                    display help


Created on Tue Jan 29 13:38:37 2019

@author: ofn77899
"""

from docopt import docopt
import os
# from ccpi.dvc import DVC
import json
import glob
import vtk
import numpy
from ccpi.viewer.utils import parseNpyHeader
from ccpi.viewer.utils import cilNumpyMETAImageWriter, cilRegularPointCloudToPolyData, \
                              cilMaskPolyData


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
    '''reads a tiff stack and casts to UNSIGNED INT 8 or 16, saves to MetaImage'''
    flist = glob.glob(ref_fname)
    if len(flist) > 0:
        reader = vtk.vtkTIFFReader()
        #  determine bit depth
        reader.SetFileName(flist[0])
        reader.Update()
        vtk_bit_depth = reader.GetOutput().GetScalarType()
        print ("Scalar type" , reader.GetOutput().GetScalarTypeAsString())
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
            raise TypeError('Cannot handle non integer type of images')
        print ("Bit depth for input is {}".format(bit_depth))
        # convert to 8 or 16 if 32
        if bit_depth != bitdepth and bit_depth > bitdepth:
            print ("should cast image to")
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
            
            writer = vtk.vtkTIFFWriter()
            
            scale = int( (imax - imin) / (all_max - all_min))
            
            shiftScaler = vtk.vtkImageShiftScale ()
            shiftScaler.SetInputConnection(reader.GetOutputPort())
            shiftScaler.SetScale(scale)
            shiftScaler.SetShift(-all_min)
            shiftScaler.SetOutputScalarType(dtype)
            
            writer.SetInputConnection(shiftScaler.GetOutputPort())
                
            new_flist = []
            for fname in flist:
                reader.SetFileName(fname)
                reader.Update()
                                
                shiftScaler.Update() 
                
                writer.SetFileName(os.path.join(os.path.dirname(fname), 
                                   '{}bit_{}'.format(dtypestring, os.path.basename(fname))))
                writer.Write()
                new_flist.append(writer.GetFileName())
            
            # save original flist 
            orig_flist = flist[:]
            # copy the new file list into flist
            flist = new_flist[:]
        else:
            print ("no need to cast image type")
        
        
        # convert to Meta Image
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

def createPointCloud(mask_filename, shape, dimensionality, 
                     sliceno, overlap, radius, rotation):
    ## Create the PointCloud
    # 
    
    
    reader = vtk.vtkMetaImageReader()
    reader.SetFileName(mask_filename)
    reader.Update()
    origin = reader.GetOutput().GetOrigin()
    spacing = reader.GetOutput().GetSpacing()
    dimensions = reader.GetOutput().GetDimensions()
    
    
    pointCloud = cilRegularPointCloudToPolyData()   
    
    pointCloud.SetMode(shape)
    pointCloud.SetDimensionality(dimensionality) 
    pointCloud.SetSlice(sliceno)
    
    pointCloud.SetInputConnection(0, reader.GetOutputPort())
    
    pointCloud.SetOverlap(0,overlap[0])
    pointCloud.SetOverlap(1,overlap[1])
    pointCloud.SetOverlap(2,overlap[2])
    
    pointCloud.SetSubVolumeRadiusInVoxel(radius)
            
    pointCloud.Update()
    
    print ("pointCloud number of points", pointCloud.GetNumberOfPoints())
         
    # Erode the transformed mask of SubVolumeRadius because we don't want to have subvolumes 
    # outside the mask
    
    erode = vtk.vtkImageDilateErode3D()
    erode.SetErodeValue(1)
    erode.SetDilateValue(0)     
    
    
    # FIXME: Currently the 2D case is only XY
    # For 2D we need to set the Kernel size in the plane to 1, 
    # otherwise the erosion would erode the whole mask.
    ks = [pointCloud.GetSubVolumeRadiusInVoxel(), pointCloud.GetSubVolumeRadiusInVoxel(), 1]
    if pointCloud.GetDimensionality() == 3:
        ks[2]= pointCloud.GetSubVolumeRadiusInVoxel()
        
    
        
    # if shape is box or square to be sure that the subvolume is within
    # the mask we need to take the half of the diagonal rather than the
    # half of the size
    if shape == 'cube':
        ks = [round(1.41 * l) for l in ks]
    
    
    # the mask erosion takes a looong time. 
    erode.SetInputConnection(0,reader.GetOutputPort())
    erode.SetKernelSize(ks[0],ks[1],ks[2])
    erode.Update()
    print ("mask created")
    
    
    # Mask the point cloud with the eroded mask
    
    polydata_masker = cilMaskPolyData()
    polydata_masker.SetMaskValue(1)
    polydata_masker.SetInputConnection(1, erode.GetOutputPort())
    
    ## Create a Transform to modify the PointCloud
    # Translation and Rotation
    
    transform = vtk.vtkTransform()
    # rotate around the center of the image data
    transform.Translate(dimensions[0]/2*spacing[0], dimensions[1]/2*spacing[1],0)
    # rotation angles
    transform.RotateX(rotation[0])
    transform.RotateY(rotation[1])
    transform.RotateZ(rotation[2])
    transform.Translate(-dimensions[0]/2*spacing[0], -dimensions[1]/2*spacing[1],0)
    

    # Actual Transformation is done here
    t_filter = vtk.vtkTransformFilter()
    t_filter.SetTransform(transform)
    t_filter.SetInputConnection(pointCloud.GetOutputPort())
    
    polydata_masker.SetInputConnection(0, t_filter.GetOutputPort())
    
    polydata_masker.Update()
    
    mpc = polydata_masker.GetOutputDataObject(0)
    array = numpy.zeros((mpc.GetNumberOfPoints(), 4))
    for i in range(mpc.GetNumberOfPoints()):
        pp = mpc.GetPoint(i)
        array[i] = (i, *pp)
    # numpy.savetxt(fn[0], array, '%d\t%.3f\t%.3f\t%.3f', delimiter=';')
    return array

def getBitDepth(imagedata):
    vtk_bit_depth = imagedata.GetScalarType()
    print ("Input Scalar type" , imagedata.GetScalarTypeAsString())
    if vtk_bit_depth == vtk.VTK_UNSIGNED_CHAR:
        bit_depth = 8
    elif vtk_bit_depth == vtk.VTK_SIGNED_CHAR:
        bit_depth = 8
    elif vtk_bit_depth == vtk.VTK_UNSIGNED_SHORT:
        bit_depth = 16
    elif vtk_bit_depth == vtk.VTK_SHORT:
        bit_depth = 16
    else:
        raise TypeError('Cannot handle this type of images')
    return bit_depth

if __name__ == '__main__':
    # runcontrol = DVC()
    __version__ = '0.1.0'
    print ("Starting ... ")
    args = docopt(__doc__, version=__version__)
    
    #args = {'--guiconfig' : os.path.abspath('../../wip/r3_np100/pointcloud_config.json'),
    #        '--reference' : os.path.abspath('D:/Nghia_slices/rec_*.tif')}
    print ("Parsing args")
    print ("Passed args " , args)
    
    #with open(args['--guiconfig'], 'r') as f:
    #    guiconfig = json.load(f)

    
    ref_fname = args['--ref']
    cor_fname = args['--cor']
    config = args['--guiconfig']
    output = args['-o']
    
    ref_reader = vtk.vtkMetaImageReader()
    cor_reader = vtk.vtkMetaImageReader()
    
    ref_reader.SetFileName(os.path.abspath(ref_fname))
    cor_reader.SetFileName(os.path.abspath(cor_fname))
    
    # check that the dimensions of the reference and correlate are the same
    ref_reader.Update()
    cor_reader.Update()
    ref_dims = ref_reader.GetOutput().GetDimensions()
    cor_dims = cor_reader.GetOutput().GetDimensions()
    assert ref_dims == cor_dims 
           
    
    with open(config, 'r') as f:
        guiconfig = json.load(f)
        radius = config['radius_range']
        npoints = config['subvol_npoints_range']
        mask_file = config['mask_file']
        mask_reader = vtk.vtkMetaImageReader()
        mask_reader.SetFileName(mask_file)
        mask_reader.Update()
        
        # check that the dimensions of the mask are the same as the correlate 
        # and reference datasets
        mask_dims = mask_reader.GetOutput().GetDimensions()
        assert mask_dims == ref_dims
        
        #subvol_geom = config["subvol_geom"]: "cube", "vol_wide": 2560, "vol_high": 2560, "vol_tall": 7, "subvol_npoints_range": [2000, 3000, 4000], "shape": "cube", "dimensionality": 3, "current_slice": 3, "overlap": [0.4, 0.2, 0.2], "rotation": [0.0, 0.0, -23.6]
        for r in radius:
            # create the point cloud for the specific radius
            array = createPointCloud(mask_filename=mask_file, 
                                   shape=config['subvol_geom'],
                                   dimensionality=config['dimensionality'],
                                   sliceno=config['current_slice'],
                                   overlap=config['overlap'],
                                   radius=r,
                                   rotation=config['rotation']
                                   )
            # range on the number of points in the subvolume
            for n in npoints:
                # the number of points in the subvolume are not influencing the
                # actual point cloud
                run_dir = os.path.join('.', 'r{:d}_np{:d}'.format(r,n))
                os.mkdir(run_dir)
                fname = os.path.join(run_dir, 'pointcloud_r{:d}.roi'.format(r))
                numpy.savetxt(fname, array, '%d\t%.3f\t%.3f\t%.3f')
                
                
                bit_depth = getBitDepth(ref_reader.GetOutput())
        
    
    
                msg = example_config.format(
                                reference_filename=ref_fname , 
                                correlate_filename=cor_fname,
                                point_cloud_filename=fname,
                                output_filename=output,
                                vol_bit_depth=bit_depth, #: get from ref
                                vol_hdr_lngth='0',#: get from ref
                                vol_wide=guiconfig['vol_wide'],
                                vol_high=guiconfig['vol_high'],
                                vol_tall=guiconfig['vol_tall'],
                                subvol_geom=guiconfig['subvol_geom'],
                                subvol_size= r * 2,
                                subvol_npts= n,
                                subvol_thresh='off',
                                gray_thresh_min='27',
                                gray_thresh_max='127',
                                min_vol_fract='0.2',
                                disp_max='10',
                                num_srch_dof='6', 
                                obj_function='znssd',
                                interp_type='tricubic',
                                rigid_trans='74.0 0.0 0.0',
                                basin_radius='0.0',
                                subvol_aspect='1.0 1.0 1.0')
    #print (msg)
    
    