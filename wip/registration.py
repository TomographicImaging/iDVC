from ccpi.viewer.CILViewer2D import CILViewer2D, SLICE_ORIENTATION_XY, SLICE_ORIENTATION_XZ, SLICE_ORIENTATION_YZ
import vtk
from vtk.util.vtkAlgorithm import VTKPythonAlgorithmBase
from vtk.util import numpy_support
import glob
import numpy
import sys, os

class cilToRGB(VTKPythonAlgorithmBase):
    '''vtkAlgorithm to crop a vtkPolyData with a Mask

    This is really only meant for point clouds: see points2vertices function

    
    gm = cilToRGB()
    gm.SetInputConnection(0, translate.GetOutputPort())
    gm.SetColor(cilToRGB.GREEN)
    gm.Update()
    
    stack = gm.GetOutput()
    
    print ("that's what is in the image ", (
        stack.GetScalarComponentAsFloat(20,20,20,0) ,
        stack.GetScalarComponentAsFloat(20,20,20,1) , 
        stack.GetScalarComponentAsFloat(20,20,20,2)))

    gm2 = cilToRGB()
    gm2.SetInputConnection(0, voi.GetOutputPort())
    gm2.SetColor(cilToRGB.MAGENTA)
    gm2.Update()
    add = vtk.vtkImageMathematics()
    add.SetOperationToAdd()
    add.SetInputConnection(0,gm.GetOutputPort())
    add.SetInputConnection(1,gm2.GetOutputPort())
    add.Update()
    print ("that's what is in the image ", (
        stack.GetScalarComponentAsFloat(20,20,20,0) ,
        stack.GetScalarComponentAsFloat(20,20,20,1) , 
        stack.GetScalarComponentAsFloat(20,20,20,2)))
    '''
    GREEN = (0,1,0.5)
    MAGENTA = (1,0,0.5)

    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self, nInputPorts=1, nOutputPorts=1)
        self.__color = None
        ncolors = vtk.VTK_UNSIGNED_SHORT_MAX + 1

        
    def SetColor(self, color):
        '''Sets the value at which the mask is active'''
        if color not in [ cilToRGB.GREEN, cilToRGB.MAGENTA ] :
            raise ValueError('Color must be GREEN or MAGENTA. Got' , color)

        if color != self.__color:
            self.__color = color
            #color = (1.,1.,1.)
            self.Modified()

    def GetColor(self):
        return self.__color

    def FillInputPortInformation(self, port, info):
        if port == 0:
            info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        elif port == 1:
            info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        
        return 1

    def FillOutputPortInformation(self, port, info):
        info.Set(vtk.vtkDataObject.DATA_TYPE_NAME(), "vtkImageData")
        return 1

    def RequestData(self, request, inInfo, outInfo):
        self.point_in_mask = 0
        inimage1 = vtk.vtkDataSet.GetData(inInfo[0])
        output = vtk.vtkImageData.GetData(outInfo)
        
        stack = vtk.vtkImageData()
        sliced = inimage1.GetExtent()
        stack.SetExtent(sliced[0],sliced[1], 
                        sliced[2],sliced[3], 
                        sliced[4], sliced[5])
        stack.AllocateScalars(inimage1.GetScalarType(), 3)
        dims = inimage1.GetDimensions()
        stack_array = numpy.reshape(
        numpy_support.vtk_to_numpy(
                        stack.GetPointData().GetScalars()
                        ),
            (dims[0],dims[1],dims[2],3) , order='F'
        )
        im1 = numpy.reshape(
            numpy_support.vtk_to_numpy(
                        inimage1.GetPointData().GetScalars()
                        ),
            (dims[0],dims[1],dims[2]), order='F'
        )
        
        color = self.__color
        for channel in range(3):
            stack_array[:,:,:,channel] = im1 * color[channel]    
        # put the output in the out port
        output.ShallowCopy(stack)
        return 1 
    def GetOutput(self):
        return self.GetOutputDataObject(0)


class cilImageMathematics(VTKPythonAlgorithmBase):
    '''vtkAlgorithm to do image mathematics with int images returning float images

    '''
    ADD = numpy.add
    SUBTRACT = numpy.subtract
    MULTIPLY = numpy.multiply
    DIVIDE = numpy.divide

    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self, nInputPorts=2, nOutputPorts=1)
        self.__operation = None
        self.__out_dtype = vtk.VTK_FLOAT

    def SetOperation(self, operation):
        '''Sets the value at which the mask is active'''
        if operation not in [cilImageMathematics.ADD, cilImageMathematics.SUBTRACT,
            cilImageMathematics.MULTIPLY, cilImageMathematics.DIVIDE]:
            raise ValueError('unsupported operation ', operation)
        
        if operation != self.__operation:
            self.__operation = operation
            #color = (1.,1.,1.)
            print ("operation set to", operation)
            self.Modified()

    def GetOperation(self):
        return self.__operation
    def SetOutputScalarTypeToFloat(self):
        self.__out_dtype = vtk.VTK_FLOAT
        self.Modified()
    def SetOutputScalarTypeToDouble(self):
        self.__out_dtype = vtk.VTK_DOUBLE
        self.Modified()
    def GetOutputType(self):
        return self.__out_dtype

    def FillInputPortInformation(self, port, info):
        if port == 0:
            info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        elif port == 1:
            info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        
        return 1

    def FillOutputPortInformation(self, port, info):
        info.Set(vtk.vtkDataObject.DATA_TYPE_NAME(), "vtkImageData")
        return 1

    def add_to_float(self,x,y, **kwargs):
        return float(x) + float(y)
    def subtract_to_float(self,x,y, **kwargs):
        return float(x) - float(y)
    def multiply_to_float(self,x,y, **kwargs):
        return float(x) * float(y)
    def divide_to_float(self,x,y, **kwargs):
        return float(x) / float(y)

    def RequestData(self, request, inInfo, outInfo):
        print ("RequestData")
        inimage1 = vtk.vtkDataSet.GetData(inInfo[0])
        inimage2 = vtk.vtkDataSet.GetData(inInfo[1])
        output = vtk.vtkImageData.GetData(outInfo)
        print ("inimage1 ", inimage1.GetScalarTypeAsString())
        print ("inimage2 ", inimage2.GetScalarTypeAsString())
        stack = vtk.vtkImageData()
        sliced = inimage1.GetExtent()
        stack.SetExtent(sliced[0],sliced[1], 
                        sliced[2],sliced[3], 
                        sliced[4], sliced[5])
        stack.AllocateScalars(self.__out_dtype, 1)
        print ("Allocated ", stack.GetScalarTypeAsString())
        dims = inimage1.GetDimensions()
        stack_array = numpy.reshape(
        numpy_support.vtk_to_numpy(
                        stack.GetPointData().GetScalars()
                        ),
            (dims[0],dims[1],dims[2]) , order='F'
        )
        im1 = numpy.reshape(
            numpy_support.vtk_to_numpy(
                        inimage1.GetPointData().GetScalars()
                        ),
            (dims[0],dims[1],dims[2]), order='F'
        )
        im2 = numpy.reshape(
            numpy_support.vtk_to_numpy(
                        inimage2.GetPointData().GetScalars()
                        ),
            (dims[0],dims[1],dims[2]), order='F'
        )
        print (im1.min(), im2.min(), im1.max(), im2.max(), stack_array.min(), stack_array.max())
        
        operation = self.__operation
        if operation == cilImageMathematics.ADD:
            func = self.add_to_float
            np_op = numpy.add
        elif operation == cilImageMathematics.SUBTRACT:
            func = self.subtract_to_float
            np_op = numpy.subtract
        elif operation == cilImageMathematics.MULTIPLY:
            func = self.multiply_to_float
            np_op = numpy.multiply
        elif operation == cilImageMathematics.DIVIDE:
            func = self.divide_to_float
            np_op = numpy.divide
        else:
            raise ValueError('Unsupported operation ', operation)
        print (func)
        #np_op = numpy.frompyfunc(func, 2, 1)
        print (np_op)
        if self.__out_dtype == vtk.VTK_FLOAT:
            dtype = numpy.float32
        elif self.__out_dtype == vtk.VTK_DOUBLE:
            dtype = numpy.float64
        print ("doing it", np_op)
        np_op(im1,im2, out=stack_array, dtype=dtype, order='F')
        a = im1 - im2
        #stack_array[:] = numpy.asarray(np_op(im1,im2), dtype=dtype)
        #stack_array[:,:,:] = a
        #print ("operation" , a)
        print (im1.min(), im2.min(), im1.max(), im2.max(), stack_array.min(), stack_array.max(), "a", a.min(), a.max())
        # put the output in the out port
        output.ShallowCopy(stack)
        return 1 
    def GetOutput(self):
        return self.GetOutputDataObject(0)

def OnKeyPressEvent(interactor, event):
    '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''
    trans = list(translate.GetTranslation())
    if interactor.GetKeyCode() == "j":
        trans[1] += 1
    elif interactor.GetKeyCode() == "n":
        trans[1] -= 1
    elif interactor.GetKeyCode() == "b":
        trans[0] -= 1
    elif interactor.GetKeyCode() == "m":
        trans[0] += 1
    translate.SetTranslation(*trans)
    translate.Update()
    subtract.Update()
    v.setInputData(subtract.GetOutput())

def OnKeyPressEventTransform(interactor, event):
    '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''
    shift = 0.5
    trans = [0,0,0]
    if interactor.GetKeyCode() == "j":
        trans[1] = shift
    elif interactor.GetKeyCode() == "n":
        trans[1] = -shift
    elif interactor.GetKeyCode() == "b":
        trans[0] = shift
    elif interactor.GetKeyCode() == "m":
        trans[0] = -shift
    transform.Translate(*trans)
    transform.Update()
    translate.Update()
    subtract.Update()
    v.setInputData(subtract.GetOutput())

def OnSliceEvent(interactor, event):
    '''https://gitlab.kitware.com/vtk/vtk/issues/15777'''
    # update the ROI 
    sliceno = v.style.GetActiveSlice()
    print (sliceno)
    orientation = v.style.GetSliceOrientation()
    extent = list(reader.GetOutput().GetExtent())
    # Calculate the size of the ROI
    if orientation == SLICE_ORIENTATION_XY:
        print ("slice orientation : YZ")
        extent[4] = sliceno
        extent[5] = sliceno + 1
    elif orientation == SLICE_ORIENTATION_XZ:
        print ("slice orientation : YZ")
        extent[2] = sliceno
        extent[3] = sliceno + 1

    elif orientation == SLICE_ORIENTATION_YZ:
        print ("slice orientation : YZ")
        extent[0] = sliceno
        extent[1] = sliceno + 1
    voi.SetVOI(extent)
    voi2.SetVOI(extent)
    voi.Update()
    voi2.Update()
    subtract.Update()

    extentc = list(subtract.GetOutput().GetExtent())
    if orientation == SLICE_ORIENTATION_XY:
        print ("slice orientation : YZ")
        extentc[4] = sliceno
        extentc[5] = sliceno + 1
    elif orientation == SLICE_ORIENTATION_XZ:
        print ("slice orientation : YZ")
        extentc[2] = sliceno
        extentc[3] = sliceno + 1

    elif orientation == SLICE_ORIENTATION_YZ:
        print ("slice orientation : YZ")
        extentc[0] = sliceno
        extentc[1] = sliceno + 1

    data.CopyAndCastFrom(subtract.GetOutput(), *extentc)
    # dims = data.GetDimensions()
    # im1 = numpy.reshape(
    #         numpy_support.vtk_to_numpy(
    #                     data.GetPointData().GetScalars()
    #                     ),
    #         (dims[0],dims[1],dims[2]), order='F'
    #     )
    # dims = subtract.GetOutput().GetDimensions()
    # im2 = numpy.reshape(
    #     numpy_support.vtk_to_numpy(
    #                 subtract.GetOutput().GetPointData().GetScalars()
    #                 ),
    #     (dims[0],dims[1],dims[2]), order='F'
    # )
    # if orientation == SLICE_ORIENTATION_XY:
    #     print ("slice orientation : YZ")
    #     im1[sliceno,:,:] = im2
    # elif orientation == SLICE_ORIENTATION_XZ:
    #     print ("slice orientation : YZ")
    #     im1[:,sliceno,:] = im2

    # elif orientation == SLICE_ORIENTATION_YZ:
    #     print ("slice orientation : YZ")
    #     im1[:,:,sliceno] = im2
    #v.setInputData(subtract.GetOutput())
    print ("data" , data.GetDimensions(), data.GetExtent())
    print ("subtract", subtract.GetOutput().GetDimensions(), subtract.GetOutput().GetExtent())
    v.setInputData(data)
    v.style.UpdatePipeline()


#%%
if __name__ == '__main__':
    err = vtk.vtkFileOutputWindow()
    err.SetFileName("viewer.log")
    vtk.vtkOutputWindow.SetInstance(err)

    #v.style.AddObserver('MouseWheelForwardEvent', OnSliceEvent, 0.5)
    #v.style.AddObserver('MouseWheelBackwardEvent', OnSliceEvent, 0.5)

    if len(sys.argv) >= 3:
        fname1 = os.path.abspath(sys.argv[1])
        fname2 = os.path.abspath(sys.argv[2])
    else:
        fname1 = '../../../../CCPi-Simpleflex/data/head.mha'
        fname2 = fname1
    print ("Reading image 1")
    reader = vtk.vtkMetaImageReader()
    reader.SetFileName(fname1)
    reader.Update()
    print ("Done")
    extent = (200, 700, 200, 700, 200, 500)
    
    print ("Extracting selection")
    voi = vtk.vtkExtractVOI()
    voi.SetInputData(reader.GetOutput())
    voi.SetVOI(*extent)
    voi.Update()
    print ("Done")

    #voi = reader
    data1 = vtk.vtkImageData()
    data1.DeepCopy(voi.GetOutput())
    
    print ("Reading image 2")
    reader.SetFileName(fname2)
    reader.Update()
    print ("Extracting selection")
    voi.Update()
    print ("Done")

    data2 = vtk.vtkImageData()
    data2.DeepCopy(voi.GetOutput())
    print ("clearing memory")
    del voi
    del reader
    print ("clearing memory done")

    v = CILViewer2D()
    
    if len(sys.argv) >= 4:
        if sys.argv[3] == 'translate':
            #voi = reader
            print("translate")
            translate = vtk.vtkImageTranslateExtent()
            translate.SetTranslation(0,0,0)
            translate.SetInputData(data2)
            translate.Update()

            v.style.AddObserver('KeyPressEvent', OnKeyPressEvent, 0.5)
        elif sys.argv[3] == 'transform':
            # doesn't work
            print("transform")
            translate = vtk.vtkTransformFilter()
            transform = vtk.vtkTransform()
            transform.Translate(0,0,0)
            translate.SetInputData(data2)
            translate.SetTransform(transform)
            translate.Update()
            print (translate.GetOutput().GetDimensions())
            v.style.AddObserver('KeyPressEvent', OnKeyPressEventTransform, 0.5)
        else:
            raise ValueError('no method')
    else:
        print ("no method specified")



    # print ("out of the reader", reader.GetOutput())
    
    use_vtk = True
    if use_vtk:
        cast1 = vtk.vtkImageCast()
        cast2 = vtk.vtkImageCast()
        cast1.SetInputData(data1)
        cast1.SetOutputScalarTypeToFloat()
        cast2.SetInputConnection(translate.GetOutputPort())
        cast2.SetOutputScalarTypeToFloat()
        
        subtract = vtk.vtkImageMathematics()
        subtract.SetOperationToSubtract()
        # subtract.SetInput1Data(voi.GetOutput())
        # subtract.SetInput2Data(translate.GetOutput())
        subtract.SetInputConnection(1,cast1.GetOutputPort())
        subtract.SetInputConnection(0,cast2.GetOutputPort())
        
        subtract.Update()
    else:
        # this won't work as the shape of the image is not constant
        subtract = cilImageMathematics()
        subtract.SetOperation(cilImageMathematics.SUBTRACT)
        #subtract.SetOperation('pippo')
        subtract.SetOutputScalarTypeToFloat()
        subtract.SetInputConnection(0,voi.GetOutputPort())
        subtract.SetInputConnection(1,translate.GetOutputPort())
        subtract.Update()

    print ("subtract type", subtract.GetOutput().GetScalarTypeAsString(), subtract.GetOutput().GetDimensions())
    
    stats = vtk.vtkImageHistogramStatistics()
    stats.SetInputConnection(subtract.GetOutputPort())
    stats.Update()
    print ("stats ", stats.GetMinimum(), stats.GetMaximum(), stats.GetMean(), stats.GetMedian())
    
    

    v.setInputData(subtract.GetOutput())
    v.startRenderLoop()