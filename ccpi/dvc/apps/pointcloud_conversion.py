import numpy
import csv
from numbers import Integral, Number

import vtk
from vtk.util.vtkAlgorithm import VTKPythonAlgorithmBase

class PointCloudConverter():
    @staticmethod
    def loadPointCloudFromCSV(filename, delimiter=','):
        # print ("loadPointCloudFromCSV")
        pointcloud = []
        with open(filename, 'r') as csvfile:
            read = csv.reader(csvfile, delimiter=delimiter)
            for row in read:
                #read in only numerical values
                #print (row)
                try:
                    row = list(map(lambda x: float(x),row))
                #print ("reduce " , reduce( lambda x,y: isinstance(x,Number) and \
                #          isinstance(y,Number) , row))
                #if reduce( lambda x,y: isinstance(x,Number) and \
                #          isinstance(y,Number) , row):
                    pointcloud.append(row)
                except ValueError as ve:
                    print ('Value Error' , ve)
        return pointcloud


class cilRegularPointCloudToPolyData(VTKPythonAlgorithmBase):
    '''vtkAlgorithm to create a regular point cloud grid for Digital Volume Correlation

    In DVC points between a reference volume and a correlation volume are correlated.
    The DVC process requires to track points whithin a subvolume of the entire
    volume that are around each point. For instance, points within a sphere of
    a certain radius (in voxel) around a point are part of the subvolume.

    The regular point cloud grid is laid out based on the overlap between
    two consecutive subvolumes. The overlap can be set indipendently on each
    axis.
    The user can provide the shape of the subvolume and the radius (for cubes
    the radius is the length of the side).

    Example:
        pointCloud = cilRegularPointCloudToPolyData()
        pointCloud.SetMode(cilRegularPointCloudToPolyData.CUBE)
        pointCloud.SetDimensionality(2)
        pointCloud.SetSlice(3)
        pointCloud.SetInputConnection(0, v16.GetOutputPort())
        pointCloud.SetOverlap(0,0.3)
        pointCloud.SetOverlap(1,0.5)
        pointCloud.SetOverlap(2,0.4)
        pointCloud.SetSubVolumeRadiusInVoxel(3)
        pointCloud.Update()

    '''
    CIRCLE = 'circle'
    SQUARE = 'square'
    CUBE   = 'cube'
    SPHERE = 'sphere'
    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self, nInputPorts=1, nOutputPorts=1)
        self.__Points = vtk.vtkPoints()
        self.__Vertices = vtk.vtkCellArray()
        self.__Orientation = 2
        self.__Overlap = [0.2, 0.2, 0.2] #: 3D overlap
        self.__Dimensionality = 3
        self.__SliceNumber = 0
        self.__Mode = self.CUBE
        self.__SubVolumeRadius = 1 #: Radius of the subvolume in voxels

    def GetPoints(self):
        '''Returns the Points'''
        return self.__Points
    def SetMode(self, value):
        '''Sets the shape mode'''
        if not value in [self.CIRCLE, self.SQUARE, self.CUBE, self.SPHERE]:
            raise ValueError('dimension must be in [circle, square, cube, sphere]. Got',
                             value)

        if value != self.__Mode:
            self.__Mode = value
            self.Modified()

    def GetMode(self):
        return self.__Mode

    def SetDimensionality(self, value):
        '''Whether the overlap is measured on 2D or 3D'''
        if not value in [2, 3]:
            raise ValueError('Dimensionality must be in [2, 3]. Got', value)
        if self.__Dimensionality != value:
            self.__Dimensionality = value
            self.Modified()
    def GetDimensionality(self):
        return self.__Dimensionality

    def SetOverlap(self, dimension, value):
        '''Set the overlap between'''
        if not isinstance(value, Number):
            raise ValueError('Overlap value must be a number. Got' , value)
        if not dimension in [0, 1, 2]:
            raise ValueError('dimension must be in [0, 1, 2]. Got' , value)
        if value != self.__Overlap[dimension]:
            self.__Overlap[dimension] = value
            self.Modified()
    def GetOverlap(self):
        return self.__Overlap

    def SetSlice(self, value):
        '''For 2D represents the slice on the data where you want to get points laid out'''
        if not isinstance(value, int):
            raise ValueError('Slice must be a positive integer. Got', value)
        if not value >= 0:
            raise ValueError('Slice must be a positive integer. Got', value)
        if self.__SliceNumber != value:
            self.__SliceNumber = value
            self.Modified()
    def GetSlice(self):
        return self.__SliceNumber

    def GetNumberOfPoints(self):
        '''returns the number of points in the point cloud'''
        return self.__Points.GetNumberOfPoints()

    def SetOrientation(self, value):
        '''For 2D sets the orientation of the working plane'''
        if not value in [0, 1, 2]:
            raise ValueError('Orientation must be in [0,1,2]. Got', value)
        if self.__Orientation != value:
            self.__Orientation = value
            self.Modified()

    def GetOrientation(self):
        return self.__Orientation

    def SetSubVolumeRadiusInVoxel(self, value):
        '''Set the radius of the subvolume in voxel'''
        if not isinstance(value, Integral):
            raise ValueError('SubVolumeRadius must be an integer larger than 1. Got', value)
        if not value > 1:
            raise ValueError('SubVolumeRadius must be an integer larger than 1. Got', value)
        if self.__SubVolumeRadius != value:
            self.__SubVolumeRadius = value
            self.Modified()

    def GetSubVolumeRadiusInVoxel(self):
        return self.__SubVolumeRadius

    def FillInputPortInformation(self, port, info):
        if port == 0:
            info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        return 1

    def FillOutputPortInformation(self, port, info):
        info.Set(vtk.vtkDataObject.DATA_TYPE_NAME(), "vtkPolyData")
        return 1

    def RequestData(self, request, inInfo, outInfo):

        # print ("Request Data")
        image_data = vtk.vtkDataSet.GetData(inInfo[0])
        pointPolyData = vtk.vtkPolyData.GetData(outInfo)

        # reset
        self.__Points = vtk.vtkPoints()
        self.__Vertices = vtk.vtkCellArray()
        # print ("orientation", orientation)
        dimensionality = self.GetDimensionality()
        # print ("dimensionality", dimensionality)

        overlap = self.GetOverlap()
        # print ("overlap", overlap)
        point_spacing = self.CalculatePointSpacing(overlap, mode=self.GetMode())
        # print ("point_spacing", point_spacing)

        sliceno = self.GetSlice()
        orientation = self.GetOrientation()

        if dimensionality == 3:
            self.CreatePoints3D(point_spacing, image_data, orientation, sliceno)
        else:
            if image_data.GetDimensions()[orientation] < sliceno:
                raise ValueError('Requested slice is outside the image.' , sliceno)

            self.CreatePoints2D(point_spacing, sliceno, image_data, orientation)

        self.FillCells()

        pointPolyData.SetPoints(self.__Points)
        pointPolyData.SetVerts(self.__Vertices)
        return 1

    def CreatePoints2D(self, point_spacing , sliceno, image_data, orientation):
        '''creates a 2D point cloud on the image data on the selected orientation

        input:
            point_spacing: distance between points in voxels (list or tuple)
            image_data: vtkImageData onto project the pointcloud
            orientation: orientation of the slice onto which create the point cloud

        returns:
            vtkPoints
        '''

        vtkPointCloud = self.__Points
        image_spacing = list ( image_data.GetSpacing() )
        image_origin  = list ( image_data.GetOrigin() )
        image_dimensions = list ( image_data.GetDimensions() )
        # print ("spacing    : ", image_spacing)
        # print ("origin     : ", image_origin)
        # print ("dimensions : ", image_dimensions)
        # print ("point spacing ", point_spacing)

        #label orientation axis as a, with plane being viewed labelled as bc
        
        # reduce to 2D on the proper orientation
        spacing_a = image_spacing.pop(orientation)
        origin_a = image_origin.pop(orientation)
        dim_a = image_dimensions.pop(orientation)

        # the total number of points on the axes of the plane
        max_b = image_dimensions[0] * image_spacing[0] / point_spacing[0]
        max_c = image_dimensions[1] * image_spacing [1]/ point_spacing[1]

        a = sliceno * spacing_a #- origin_a

        # skip the offset in voxels
        offset = [0, 0]

        # Loop through points in plane bc
        n_b = offset[0]

        while n_b < max_b:
            n_c = offset[1]

            while n_c < max_c:

                b = (n_b / max_b) * image_spacing[0] * image_dimensions[0] #- image_origin[0] #+ int(image_dimensions[0] * density[0] * .7)
                c = (n_c / max_c) * image_spacing[1] * image_dimensions[1]# - image_origin[1] #+ int(image_dimensions[1] * density[1] * .7)

                if self.GetOrientation() == 0: #YZ
                    vtkPointCloud.InsertNextPoint( a, b, c)
                    # print(c)
                    
                elif self.GetOrientation() == 1: #XZ
                    vtkPointCloud.InsertNextPoint( b, a, c)
                    # print(c)

                elif self.GetOrientation() == 2: #XY
                    vtkPointCloud.InsertNextPoint( b, c, a)
                    # print(a)

                n_c += 1

            n_b += 1

        return 1

    def CreatePoints3D(self, point_spacing , image_data, orientation, sliceno):
        '''creates a 3D point cloud on the image data on the selected orientation

        input:
            point_spacing: distance between points in voxels (list or tuple)
            image_data: vtkImageData onto project the pointcloud
            orientation: orientation of the slice onto which create the point cloud
            sliceno: the slice number in the orientation we are viewing. We must throw points on this slice.
           

        returns:
            vtkPoints
        '''
        vtkPointCloud = self.__Points
        image_spacing = list ( image_data.GetSpacing() )
        image_origin  = list ( image_data.GetOrigin() )
        image_dimensions = list ( image_data.GetDimensions() )

        # the total number of points on X and Y axis
        max_x = image_dimensions[0] * image_spacing[0] / point_spacing[0]
        max_y = image_dimensions[1] * image_spacing[1] / point_spacing[1]
        max_z = image_dimensions[2] * image_spacing [2] / point_spacing[2]

        # print ("max: {} {} {}".format((max_x, max_y, max_z), image_dimensions, point_spacing))
        # print ("max_y: {} {} {}".format(max_y, image_dimensions, density))

        # print ("Sliceno {} Z {}".format(sliceno, z))

        # skip the offset in voxels
        # radius = self.GetSubVolumeRadiusInVoxel()

        #Offset according to the orientation and slice no.
        offset = [0, 0, 0]

        if sliceno < point_spacing[orientation]:
            offset[orientation] = sliceno
        else:
            offset[orientation] = sliceno % point_spacing[orientation]
        
        n_x=0

        while n_x < max_x:
            # x axis
            n_y = 0
            while n_y < max_y:
                # y axis
                n_z = 0
                while n_z < max_z:
                    x = (n_x / max_x) * image_spacing[0] * image_dimensions[0] + offset[0] * image_spacing[0] #- image_origin[0] #+ int(image_dimensions[0] * density[0] * .7)
                    y = (n_y / max_y) * image_spacing[1] * image_dimensions[1] + offset[1] * image_spacing[1] # - image_origin[1] #+ int(image_dimensions[1] * density[1] * .7)
                    z = (n_z / max_z) * image_spacing[2] * image_dimensions[2] + offset[2] * image_spacing[2] # - image_origin[2] #+ int(image_dimensions[1] * density[1] * .7)

                    vtkPointCloud.InsertNextPoint( x, y, z )
                    n_z += 1

                n_y += 1

            n_x += 1

        return 1

    def FillCells(self):
        '''Fills the Vertices'''
        vertices = self.__Vertices
        number_of_cells = vertices.GetNumberOfCells()
        for i in range(self.GetNumberOfPoints()):
            if i >= number_of_cells:
                vertices.InsertNextCell(1)
                vertices.InsertCellPoint(i)

    def CalculatePointSpacing(self, overlap, mode=SPHERE):
        '''returns the ratio between the figure size (radius) and the distance between 2 figures centers in 3D'''
        print ("CalculateDensity", overlap)

        if isinstance (overlap, tuple) or isinstance(overlap, list):
            d = [self.distance_from_overlap(ovl, mode=mode) for ovl in overlap]
        elif isinstance(overlap, float):
            d = [self.distance_from_overlap(overlap, mode=mode)]
            d += [d[-1]]
            d += [d[-1]]
        return d


    def overlap(self, radius, center_distance, mode=SPHERE):
        '''Calculates the volume overlap for 2 shapes of radius and center distance'''
        if center_distance <= 2*radius:
            if mode == 'circle':
                overlap = (2 * numpy.acos(center_distance/radius/2.) - \
                           (center_distance/radius) *  numpy.sqrt(1 - \
                           (center_distance/radius/2.)*(center_distance/radius/2.)) \
                          ) / 3.1415
            elif mode == 'square':
                overlap = (1 - center_distance/radius )
            elif mode == 'cube':
                overlap = (1 - center_distance/radius )
            elif mode == 'sphere':
                overlap = (2. * radius - center_distance)**2  *\
                          (center_distance + 4 * radius) / \
                          (16 * radius ** 3 )
            else:
                raise ValueError('unsupported mode',mode)
        else:
            overlap = 0
        return overlap

    def distance_from_overlap(self, req, interp=False, N=1000, mode='sphere'):
        '''hard inversion of distance and overlap'''
        radius = self.GetSubVolumeRadiusInVoxel()
        x = [2.* i/N * radius for i in range(N+1)]
        y = [self.overlap(radius, x[i], mode=mode) - req for i in range(N+1)]
        # find the value closer to 0 for required overlap
        idx = (y.index(min (y, key=abs)))
        if interp:
            if y[idx] * y[idx+1] < 0:
                m = (y[idx] -y[idx+1]) / (x[idx] -x[idx+1])
            else:
                m = (y[idx] -y[idx-1]) / (x[idx] -x[idx-1])
            q = y[idx] - m * x[idx]
            x0 = -q / m
        else:
            x0 = x[idx]
        return x0


class cilNumpyPointCloudToPolyData(VTKPythonAlgorithmBase):
    '''vtkAlgorithm to read a point cloud from a NumPy array
    '''
    def __init__(main_window):
        VTKPythonAlgorithmBase.__init__(main_window, nInputPorts=0, nOutputPorts=1)
        main_window.__Points = vtk.vtkPoints()
        main_window.__Vertices = vtk.vtkCellArray()
        main_window.__Data = None


    def GetPoints(main_window):
        '''Returns the Points'''
        return main_window.__Points
    def SetData(main_window, value):
        '''Sets the points from a numpy array or list'''
        if not isinstance (value, numpy.ndarray) :
            raise ValueError('Data must be a numpy array. Got', value)

        if not numpy.array_equal(value,main_window.__Data):
            main_window.__Data = value
            main_window.Modified()

    def GetData(main_window):
        return main_window.__Data


    def GetNumberOfPoints(main_window):
        '''returns the number of points in the point cloud'''
        return main_window.__Points.GetNumberOfPoints()


    def FillInputPortInformation(main_window, port, info):
        # if port == 0:
        #    info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        return 1

    def FillOutputPortInformation(main_window, port, info):
        info.Set(vtk.vtkDataObject.DATA_TYPE_NAME(), "vtkPolyData")
        return 1

    def RequestData(main_window, request, inInfo, outInfo):

        # print ("Request Data")
        # output_image = vtk.vtkDataSet.GetData(inInfo[0])
        pointPolyData = vtk.vtkPolyData.GetData(outInfo)
        vtkPointCloud = main_window.__Points
        for point in main_window.GetData():
            # point = id, x, y, z
            vtkPointCloud.InsertNextPoint( point[1] , point[2] , point[3])

        main_window.FillCells()

        pointPolyData.SetPoints(main_window.__Points)
        pointPolyData.SetVerts(main_window.__Vertices)
        return 1


    def FillCells(main_window):
        '''Fills the Vertices'''
        vertices = main_window.__Vertices
        number_of_cells = vertices.GetNumberOfCells()
        for i in range(main_window.GetNumberOfPoints()):
            if i >= number_of_cells:
                vertices.InsertNextCell(1)
                vertices.InsertCellPoint(i)
