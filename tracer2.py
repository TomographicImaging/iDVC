# -*- coding: utf-8 -*-
"""
Created on Thu Dec  6 13:48:22 2018

@author: ofn77899
"""

#!/usr/bin/env python

# initial translation from the tcl by VTK/Utilities/tcl2py.py
# further cleanup and fixes to the translation by Charl P. Botha

import vtk
from vtk.util.misc import vtkGetDataRoot
VTK_DATA_ROOT = vtkGetDataRoot()
from ccpi.viewer.CILViewer2D import CILViewer2D
from ccpi.viewer.utils import Converter
from ccpi.viewer.CILViewer import CILViewer
import os
import numpy
from numbers import Integral, Number

from ccpi.viewer.utils import cilRegularPointCloudToPolyData
from ccpi.viewer.utils import cilMaskPolyData , cilClipPolyDataBetweenPlanes
from ccpi.viewer.utils import cilNumpyMETAImageWriter



def savePointCloud(polydata):
    print ("points ", polydata.GetNumberOfPoints())
    a = numpy.zeros((polydata.GetNumberOfPoints(), 4))
    for i in range(polydata.GetNumberOfPoints()):
        pp = polydata.GetPoint(i)
        a[i] = (i, *pp) 
    
    return numpy.asarray(a)


    


    
#%%

        
    
err = vtk.vtkFileOutputWindow()
err.SetFileName("tracer2.log")
vtk.vtkOutputWindow.SetInstance(err)
    
# Start by loading some data.
v16 = vtk.vtkMetaImageReader()
v16.SetFileName(os.path.abspath("../../../CCPi-Simpleflex/data/head.mha"))
v16.Update()

origin = v16.GetOutput().GetOrigin()
spacing = v16.GetOutput().GetSpacing()
dimensions = v16.GetOutput().GetDimensions()
sliceno = 3
orientation = 2



path = []
path.append( (74.66533660888672, 127.88501739501953, 0.0) )
#path.append( (76.09085845947266, 121.23255920410156, 0.0) )
#path.append( (76.09085845947266, 114.10491943359375, 0.0) )
#path.append( (76.5660400390625, 111.25386810302734, 0.0) )
path.append( (77.04121398925781, 110.30352020263672, 0.0) )
#path.append( (81.31779479980469, 104.12622833251953, 0.0) )
#path.append( (81.79296875, 104.12622833251953, 0.0) )
#path.append( (81.79296875, 103.65105438232422, 0.0) )
path.append( (82.26815032958984, 103.65105438232422, 0.0) )
#path.append( (82.74332427978516, 103.1758804321289, 0.0) )
#path.append( (85.59437561035156, 104.12622833251953, 0.0) )
#path.append( (87.49507904052734, 106.50211334228516, 0.0) )
path.append( (89.87095642089844, 108.40281677246094, 0.0) )
#path.append( (92.72201538085938, 110.30352020263672, 0.0) )
#path.append( (95.57306671142578, 112.67939758300781, 0.0) )
#path.append( (98.42412567138672, 114.5801010131836, 0.0) )
path.append( (98.89929962158203, 115.0552749633789, 0.0) )
#path.append( (103.1758804321289, 119.8070297241211, 0.0) )
#path.append( (103.65105438232422, 121.70773315429688, 0.0) )
#path.append( (104.60140991210938, 123.13326263427734, 0.0) )
path.append( (105.07658386230469, 126.9346694946289, 0.0) )
#path.append( (105.07658386230469, 128.36019897460938, 0.0) )
#path.append( (105.07658386230469, 128.8353729248047, 0.0) )
#path.append( (105.07658386230469, 129.310546875, 0.0) )
path.append( (105.07658386230469, 129.7857208251953, 0.0) )
#path.append( (104.12622833251953, 129.7857208251953, 0.0) )
#path.append( (100.80000305175781, 129.7857208251953, 0.0) )
#path.append( (95.57306671142578, 129.7857208251953, 0.0) )
path.append( (93.19718933105469, 129.7857208251953, 0.0) )
#path.append( (92.72201538085938, 129.7857208251953, 0.0) )
#path.append( (92.24684143066406, 129.7857208251953, 0.0) )
#path.append( (91.77165985107422, 129.7857208251953, 0.0) )
path.append( (89.87095642089844, 129.310546875, 0.0) )
#path.append( (88.92060852050781, 129.310546875, 0.0) )
#path.append( (88.4454345703125, 129.310546875, 0.0) )
#path.append( (86.54473114013672, 129.310546875, 0.0) )
path.append( (86.06954956054688, 129.310546875, 0.0) )
#path.append( (85.59437561035156, 129.310546875, 0.0) )
#path.append( (85.11920166015625, 129.310546875, 0.0) )
#path.append( (85.59437561035156, 129.7857208251953, 0.0) )

pathpoints = vtk.vtkPoints()
for p in path:
    pathpoints.InsertNextPoint(p[0],p[1],sliceno * v16.GetOutput().GetSpacing()[2])

# create a blank image
dims = v16.GetOutput().GetDimensions()

mask0 = Converter.numpy2vtkImporter(numpy.zeros(
                                     (dims[0],dims[1],dims[2]), 
                                     order='C', dtype=numpy.uint16) , 
                                   spacing = v16.GetOutput().GetSpacing(), 
                                   origin = v16.GetOutput().GetOrigin(),
                                   transpose=[2,1,0]
                                   )
# create an image with 1 in it
mask1 = Converter.numpy2vtkImporter(numpy.ones(
                                     (dims[0],dims[1],dims[2]), 
                                     order='C', dtype=numpy.uint16), 
                                   spacing = v16.GetOutput().GetSpacing(), 
                                   origin = v16.GetOutput().GetOrigin(),
                                   transpose=[2,1,0]
                                   )
    

mask0.Update()
mask1.Update()
print (mask0.GetOutput().GetScalarTypeAsString())
print (mask1.GetOutput().GetScalarTypeAsString())

#%%#%%
sumimage = vtk.vtkImageData()
sumimage.DeepCopy(mask0.GetOutput())
print (sumimage.GetScalarTypeAsString())

mat = vtk.vtkImageMathematics()
mat.SetInput1Data(mask0.GetOutput())
mat.SetInput2Data(mask1.GetOutput())
mat.SetOutput(sumimage)
mat.SetOperationToAddConstant()
mat.SetConstantC(2)
mat.Update()
print (sumimage.GetScalarComponentAsDouble(0,0,0,0))
print (mat.GetOutput().GetScalarComponentAsDouble(0,0,0,0))
    
lasso = vtk.vtkLassoStencilSource()
lasso.SetShapeToPolygon()
# pass the slice at which the lasso has to process
lasso.SetSlicePoints(sliceno , pathpoints)
lasso.SetSliceOrientation(2)
lasso.SetInformationInput(v16.GetOutput())


# Create a Mask from the lasso. 
stencil = vtk.vtkImageStencil()
stencil.SetInputConnection(mask1.GetOutputPort())
stencil.SetBackgroundInputData(mask0.GetOutput())
stencil.SetStencilConnection(lasso.GetOutputPort())
stencil.Update()

if True:
    # erode_np = Converter.vtk2numpy(stencil.GetOutput(), [2,1,0])
    # copy the slice from sliceno for 20 slices
    # print (erode_np[:,:,sliceno].mean())
    dims = stencil.GetOutput().GetDimensions()
    for x in range(dims[0]):
        for y in range(dims[1]):
            for z in range(2):
                v = stencil.GetOutput().GetScalarComponentAsFloat(x,y,sliceno,0)
                stencil.GetOutput().SetScalarComponentFromFloat(x,y,z+sliceno+1,0,v)
'''    fname = 'tmp'
    npMetaW = cilNumpyMETAImageWriter()
    npMetaW.SetFileName(fname)
    npMetaW.SetInputData(erode_np)
    npMetaW.SetSpacing(v16.GetOutput().GetSpacing())
    npMetaW.Write()
    
    stencilr = vtk.vtkMetaImageReader()
    stencilr.SetFileName(fname+'.mhd')
    stencilr.Update()
    
    print ('v1 origin' , v16.GetOutput().GetOrigin())
    '''
#%%


## Create the PointCloud

pointCloud = cilRegularPointCloudToPolyData()
pointCloud.SetMode(cilRegularPointCloudToPolyData.SPHERE)
pointCloud.SetDimensionality(3)
pointCloud.SetSlice(3)
pointCloud.SetInputConnection(0, v16.GetOutputPort())

pointCloud.SetOverlap(0,0.7)
pointCloud.SetOverlap(1,0.2)
pointCloud.SetOverlap(2,0.4)

pointCloud.SetSubVolumeRadiusInVoxel(3)
pointCloud.Update()

print ("pointCloud number of points", pointCloud.GetNumberOfPoints())
     

## Create a Transform to modify the PointCloud
# Translation and Rotation
rotate = (0.,0.,25.)
transform = vtk.vtkTransform()
# rotate around the center of the image data
transform.Translate(dimensions[0]/2*spacing[0], dimensions[1]/2*spacing[1],0)
# rotation angles
transform.RotateX(rotate[0])
transform.RotateY(rotate[1])
transform.RotateZ(rotate[2])
transform.Translate(-dimensions[0]/2*spacing[0], -dimensions[1]/2*spacing[1],0)

# Actual Transformation is done here
t_filter = vtk.vtkTransformFilter()
t_filter.SetTransform(transform)
t_filter.SetInputConnection(pointCloud.GetOutputPort())


# Erode the transformed mask of SubVolumeRadius because we don't want to have subvolumes 
# outside the mask
erode = vtk.vtkImageDilateErode3D()
erode.SetInputConnection(0,stencil.GetOutputPort())
erode.SetErodeValue(1)
erode.SetDilateValue(0) 
ks = [pointCloud.GetSubVolumeRadiusInVoxel(), pointCloud.GetSubVolumeRadiusInVoxel(), 1]
if pointCloud.GetDimensionality() == 3:
    ks[2]= pointCloud.GetSubVolumeRadiusInVoxel()


# in this particular example the mask (stencil) is on 2D so we need to set the Kernel size
# in the plane to 1, otherwise the erosion would erode the whole mask.
erode.SetKernelSize(ks[0],ks[1],1)
erode.Update()

# Mask the point cloud with the eroded mask
polydata_masker = cilMaskPolyData()
polydata_masker.SetMaskValue(1)
polydata_masker.SetInputConnection(0, t_filter.GetOutputPort())
polydata_masker.SetInputConnection(1, erode.GetOutputPort())
polydata_masker.Update()
print ("polydata_masker type", type(polydata_masker.GetOutputDataObject(0)))

array = savePointCloud(polydata_masker.GetOutputDataObject(0))
print (array)
numpy.savetxt('pointcloud.csv', array, '%d,%e,%e,%e', delimiter=';')
# create a mapper/actor for the point cloud

bpcpoints = cilClipPolyDataBetweenPlanes()
bpcpoints.SetInputConnection(polydata_masker.GetOutputPort())
bpcpoints.SetPlaneOriginAbove((0,0,3))
bpcpoints.SetPlaneOriginBelow((0,0,1))
bpcpoints.SetPlaneNormalAbove((0,0,1))
bpcpoints.SetPlaneNormalBelow((0,0,-1))
bpcpoints.Update()

mapper = vtk.vtkPolyDataMapper()
# mapper.SetInputConnection(bpc.GetOutputPort())
# mapper.SetInputConnection(polydata_masker.GetOutputPort())
# mapper.SetInputConnection(pointCloud.GetOutputPort())
mapper.SetInputConnection(bpcpoints.GetOutputPort())

# create an actor for the points as point
actor = vtk.vtkLODActor()
actor.SetMapper(mapper)
actor.GetProperty().SetPointSize(3)
actor.GetProperty().SetColor(1, .2, .2)
actor.VisibilityOn()


# create a mapper/actor for the point cloud with a CubeSource and with vtkGlyph3D
# which copies oriented and scaled glyph geometry to every input point

subv_glyph = vtk.vtkGlyph3D()
subv_glyph.SetScaleFactor(1.)

spacing = erode.GetOutput().GetSpacing()
radius = pointCloud.GetSubVolumeRadiusInVoxel()

# Spheres may be a bit complex to visualise if the spacing of the image is not homogeneous
sphere_source = vtk.vtkSphereSource()
sphere_source.SetRadius(radius * spacing[0])
sphere_source.SetThetaResolution(12)
sphere_source.SetPhiResolution(12)

# Cube source
cube_source = vtk.vtkCubeSource()
cube_source.SetXLength(spacing[0]*radius)
cube_source.SetYLength(spacing[1]*radius)
cube_source.SetZLength(spacing[2]*radius)


# clip between planes
bpcvolume = cilClipPolyDataBetweenPlanes()
bpcvolume.SetInputConnection(subv_glyph.GetOutputPort())
bpcvolume.SetPlaneOriginAbove((0,0,3))
bpcvolume.SetPlaneOriginBelow((0,0,1))
bpcvolume.SetPlaneNormalAbove((0,0,1))
bpcvolume.SetPlaneNormalBelow((0,0,-1))
bpcvolume.Update()


# mapper for the glyphs
sphere_mapper = vtk.vtkPolyDataMapper()
# sphere_mapper.SetInputConnection( subv_glyph.GetOutputPort() )
sphere_mapper.SetInputConnection( bpcvolume.GetOutputPort() )

subv_glyph.SetInputConnection( polydata_masker.GetOutputPort() )

subv_glyph.SetSourceConnection( sphere_source.GetOutputPort() )
# subv_glyph.SetSourceConnection( cube_source.GetOutputPort() )

subv_glyph.SetVectorModeToUseNormal()

# actor for the glyphs
sphere_actor = vtk.vtkActor()
sphere_actor.SetMapper(sphere_mapper)
sphere_actor.GetProperty().SetColor(1, 0, 0)
sphere_actor.GetProperty().SetOpacity(0.2)
sphere_actor.GetProperty().SetRepresentationToWireframe()

def UpdateClippingPlanes(interactor, event):
    normal = [0, 0, 0]
    origin = [0, 0, 0]
    norm = 1
    orientation = v.GetSliceOrientation()
    from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY
    from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XZ
    from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_YZ
    if orientation == SLICE_ORIENTATION_XY:
        norm = 1
    elif orientation == SLICE_ORIENTATION_XZ:
        norm = -1
    elif orientation == SLICE_ORIENTATION_YZ:
        norm = 1
    beta = 0
    if event == "MouseWheelForwardEvent":
        # this is pretty absurd but it seems the
        # plane cuts too much in Forward...
        beta =+ 2
    
    spac = v.img3D.GetSpacing()
    orig = v.img3D.GetOrigin()
    slice_thickness = spac[orientation]
    
    normal[orientation] = norm
    origin [orientation] = (v.style.GetActiveSlice() + beta ) * slice_thickness - orig[orientation]
    # print("event {} origin above {} beta {}".format(event, origin, beta))        
        
    # print("slice {} beta {} orig {} spac {} normal {}".format(v.GetActiveSlice(), beta,
    #      orig, spac , normal))
    # print("origin", origin, orientation)
    # print("<<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>")
    
    bpcpoints.SetPlaneOriginAbove(origin)
    bpcpoints.SetPlaneNormalAbove(normal)
    
    bpcvolume.SetPlaneOriginAbove(origin)
    bpcvolume.SetPlaneNormalAbove(normal)
    
    
    # update the  plane below
    #beta += 1
    slice_below = v.style.GetActiveSlice() -1 + beta
    if slice_below < 0:
        slice_below = 0
        
    origin_below = [i for i in origin]
    origin_below[orientation] = ( slice_below ) * slice_thickness - orig[orientation]
    print("event {} origin below {} beta {}".format(event, origin_below, beta))        
    
    bpcpoints.SetPlaneOriginBelow(origin_below)
    bpcpoints.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))
    bpcvolume.SetPlaneOriginBelow(origin_below)
    bpcvolume.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))
    
    bpcpoints.Update()
    bpcvolume.Update()
    print (">>>>>>>>>>>>>>>>>>>>>")

if True:
    
    
    v = CILViewer2D()
    priority = 0.3
    v.style.AddObserver("MouseWheelForwardEvent" ,  UpdateClippingPlanes , priority)
    v.style.AddObserver("MouseWheelBackwardEvent" , UpdateClippingPlanes, priority)
    v.setInput3DData(v16.GetOutput())
    # v.setInput3DData(stencil.GetOutput())
    # v.setInput3DData(erode.GetOutput())
    
    v.style.SetActiveSlice(3)
    v.ren.AddActor(actor)
    v.ren.AddActor(sphere_actor)
    # v.showActor(actor)
    # v.showActor(sphere_actor)
    actors = v.ren.GetActors()
    a0 = actors.GetLastActor()
    print (id (a0) , id(actor), id(sphere_actor))
    
    print (v.ren.GetActors())
    
    v.startRenderLoop()
    poly = vtk.vtkPolyData()
    v.imageTracer.GetPath(poly)
    for i in range(poly.GetPoints().GetNumberOfPoints()):
        print (poly.GetPoints().GetPoint(i))