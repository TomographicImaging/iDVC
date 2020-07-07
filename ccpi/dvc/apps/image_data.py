from PyQt5 import QtCore, QtWidgets, QtGui
from PyQt5.QtCore import QThreadPool
from PyQt5.QtWidgets import QProgressDialog, QDialog, QLabel, QComboBox, QDialogButtonBox, QFormLayout, QWidget, QVBoxLayout, QGroupBox, QLineEdit, QMessageBox

import os
import time
import numpy

from functools import partial
from os.path import isfile

import vtk

from ccpi.viewer.utils import Converter

from ccpi.viewer.utils import cilNumpyMETAImageWriter

from ccpi.viewer.QtThreading import Worker, WorkerSignals, ErrorObserver #

from vtk.util.vtkAlgorithm import VTKPythonAlgorithmBase

from ccpi.viewer.utils.conversion import cilNumpyResampleReader, cilBaseResampleReader

import imghdr

# ImageCreator class
class ImageDataCreator():   

    '''Converts an image file into VTK image data

        Takes an array of image file/s: image_files (list of image files)

        Takes a variable where a copy of the image data will be stored: output_image (vtkImageData)

        Option to convert image file to numpy format: convert_numpy (bool)

        Dictionary where info about image will be stored (such as vol_bit_depth and location of npy file): info_var (dict)

        Method to be carried out once the vtk image data creation is complete: finish_fn (method)

        Whether to resample the image (currently only for np and raw files): resample (bool)

        '''
   
    def createImageData(self, image_files, output_image, info_var = None, convert_numpy = False, finish_fn = None, resample = False):
        if len(image_files) ==1:
            image = image_files[0]
            file_extension = os.path.splitext(image)[1]

        else:
            for image in image_files:
                file_extension = imghdr.what(image)
                if file_extension != 'tiff':
                    self.e(
                            '', '', 'When reading multiple files, all files must TIFF formatted.')
                    error_title = "Read Error"
                    error_text = "Error reading file: ({filename})".format(filename=image)
                    displayFileErrorDialog(self,message=error_text, title=error_title)
                    return

        if file_extension in ['.mha', '.mhd']:
            reader = vtk.vtkMetaImageReader()
            reader.AddObserver("ErrorEvent", self.e)
            create_progress_window(self,"Converting", "Converting Image")
            image_worker = Worker(update_reader,reader, image, output_image, convert_numpy, info_var)

        elif file_extension in ['.npy']:
            print("file ext in npy")
            create_progress_window(self,"Converting", "Converting Image")
            image_worker = Worker(load_npy_image,image, output_image, info_var, resample)     

        elif file_extension in ['tif', 'tiff', '.tif', '.tiff']:
            reader = vtk.vtkTIFFReader()
            reader.AddObserver("ErrorEvent", self.e)
            create_progress_window(self,"Converting", "Converting Image")
            image_worker = Worker(load_tif,image_files,reader, output_image, convert_numpy, info_var)

        elif file_extension in ['.raw']:
            self.raw_import_dialog = createRawImportDialog(self, image, output_image, info_var, resample, finish_fn)
            dialog = self.raw_import_dialog['dialog'].show()
            return

        else:
            self.e('', '', 'File format is not supported. Accepted formats include: .mhd, .mha, .npy, .tif, .raw')
            error_title = "Error"
            error_text = "Error reading file: ({filename})".format(filename=image)
            displayFileErrorDialog(self,message=error_text, title=error_title)
            return

        
        self.progress_window.setValue(10)

        image_worker.signals.progress.connect(partial(progress,self.progress_window))
        if finish_fn is not None:
            image_worker.signals.finished.connect(finish_fn)
        self.threadpool = QThreadPool()
        self.threadpool.start(image_worker)

   
#For progress bars:
def create_progress_window(self, title, text, max = 100, cancel = None):
        self.progress_window = QProgressDialog(text, "Cancel", 0,max, self, QtCore.Qt.Window) 
        self.progress_window.setWindowTitle(title)
        self.progress_window.setWindowModality(QtCore.Qt.ApplicationModal) #This means the other windows can't be used while this is open
        self.progress_window.setMinimumDuration(0.1)
        self.progress_window.setWindowFlag(QtCore.Qt.WindowCloseButtonHint, False)
        self.progress_window.setWindowFlag(QtCore.Qt.WindowMaximizeButtonHint, False)
        if cancel is None:
            self.progress_window.setCancelButton(None)
        else:
            self.progress_window.canceled.connect(cancel)

def progress(progress_window,value = None):
        if value is not None:
            if int(value) > progress_window.value():
                progress_window.setValue(value)

# Display errors:
def displayFileErrorDialog(self, message, title):
    msg = QMessageBox(self)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setDetailedText(self.e.ErrorMessage())
    msg.exec_()

def warningDialog(self, message='', window_title='', detailed_text=''):
    dialog = QMessageBox(self)
    dialog.setIcon(QMessageBox.Information)
    dialog.setText(message)
    dialog.setWindowTitle(window_title)
    dialog.setDetailedText(detailed_text)
    dialog.setStandardButtons(QMessageBox.Ok)
    retval = dialog.exec_()
    return retval

# Load images:

#mha and mhd:

def update_reader(reader, image, output_image, convert_numpy = False, image_info = None, progress_callback=None):
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(get_progress, progress_callback= progress_callback))
        reader.SetFileName(image)
        reader.Update()

        # image_data = vtk.vtkImageData()
        # image_data = reader.GetOutput()
        output_image.ShallowCopy(reader.GetOutput())
       
        progress_callback.emit(90)

        convert_numpy = True
       

        if convert_numpy:
            print("Converting metaimage to numpy") #this is for using in the dvc code
            filename = os.path.abspath(image)[:-4] + ".npy"
            numpy_array =  Converter.vtk2numpy(output_image, order = "F")
            numpy.save(filename,numpy_array)
            
            if image_info is not None:
                image_info['numpy_file'] = filename
                if (isinstance(numpy_array[0][0][0],numpy.uint8)):
                    image_info['vol_bit_depth'] = '8'
                elif(isinstance(numpy_array[0][0][0],numpy.uint16)):
                    image_info['vol_bit_depth'] = '16'
                if(numpy_array.flags["FNC"]):
                    print("F order")
                else:
                    print("Not F")
                #print(image_info['vol_bit_depth'])
                with open(filename, 'rb') as f:
                    header = f.readline()
                image_info['header_length'] = len(header)

        progress_callback.emit(100)


def load_npy_image(image_file, output_image, image_info = None, resample = False, progress_callback=None):
        if resample:
            reader = cilNumpyResampleReader()
            reader.SetFileName(image_file)
            reader.SetTargetShape((512,512,512))
            reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(get_progress, progress_callback= progress_callback))
            reader.Update()
            output_image.ShallowCopy(reader.GetOutput())
            print ("Spacing ", output_image.GetSpacing())
            header_length = reader.GetFileHeaderLength() 
            vol_bit_depth = reader.GetBytesPerElement()*8
            shape = reader.GetStoredArrayShape()
            if reader.GetIsFortran():
                shape = shape[::-1]
            # print("Header", header_length)
            # print("vol_bit_depth", vol_bit_depth)
        else:
        #print("Load npy")
            time.sleep(0.1)
            progress_callback.emit(5)

            with open(image_file, 'rb') as f:
                header = f.readline()
            header_length = len(header)

            numpy_array = numpy.load(image_file)
            shape = numpy.shape(numpy_array)

            if (isinstance(numpy_array[0][0][0],numpy.uint8)):
                vol_bit_depth = '8'
            elif(isinstance(numpy_array[0][0][0],numpy.uint16)):
                vol_bit_depth = '16'
            else:
                vol_bit_depth = None #in this case we can't run the DVC code
                output_image = None
                return

            Converter.numpy2vtkImage(numpy_array, output = output_image) #(3.2,3.2,1.5)
            progress_callback.emit(80)

        progress_callback.emit(100)

        if image_info is not None:
            image_info["header_length"]  = header_length
            image_info["vol_bit_depth"] =  vol_bit_depth
            image_info["shape"] = shape
        
        
def load_tif(filenames, reader, output_image,   convert_numpy = False,  image_info = None, progress_callback=None):
        #time.sleep(0.1) #required so that progress window displays
        #progress_callback.emit(10)

        sa = vtk.vtkStringArray()
        for fname in filenames:
            i = sa.InsertNextValue(fname)
        print("read {} files".format(i))

        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(get_progress, progress_callback= progress_callback))
        reader.SetFileNames(sa)

        dtype = vtk.VTK_UNSIGNED_CHAR

        if reader.GetOutput().GetScalarType() != dtype and False:
            # need to cast to 8 bits unsigned
            print("The if statement is true")

            stats = vtk.vtkImageAccumulate()
            stats.SetInputConnection(reader.GetOutputPort())
            stats.Update()
            iMin = stats.GetMin()[0]
            iMax = stats.GetMax()[0]
            if (iMax - iMin == 0):
                scale = 1
            else:
                scale = vtk.VTK_UNSIGNED_CHAR_MAX / (iMax - iMin)

            shiftScaler = vtk.vtkImageShiftScale()
            shiftScaler.SetInputConnection(reader.GetOutputPort())
            shiftScaler.SetScale(scale)
            shiftScaler.SetShift(-iMin)
            shiftScaler.SetOutputScalarType(dtype)
            shiftScaler.Update()

            tmpdir = tempfile.gettempdir()
            writer = vtk.vtkMetaImageWriter()
            writer.SetInputConnection(shiftScaler.GetOutputPort())
            writer.SetFileName(os.path.join(tmpdir, 'input8bit.mhd'))
            writer.Write()

            reader = shiftScaler
        reader.Update()

        progress_callback.emit(80)

        print("Convert np")

        image_data = reader.GetOutput()
        output_image.ShallowCopy(image_data)

        progress_callback.emit(90)

        if convert_numpy:
            filename = os.path.abspath(filenames[0])[:-4] + ".npy"
            numpy_array =  Converter.vtk2numpy(reader.GetOutput())
            #numpy_array =  Converter.tiffStack2numpy(filenames = filenames)
            numpy.save(filename,numpy_array)
            image_info['numpy_file'] = filename

            if image_info is not None:
                if (isinstance(numpy_array[0][0][0],numpy.uint8)):
                    image_info['vol_bit_depth'] = '8'
                elif(isinstance(numpy_array[0][0][0],numpy.uint16)):
                    image_info['vol_bit_depth'] = '16'
                print(image_info['vol_bit_depth'])

            #TODO: save volume header length
        progress_callback.emit(100)

def get_progress(caller, event, progress_callback):
        progress_callback.emit(caller.GetProgress()*80)


#raw:
def createRawImportDialog(self, fname, output_image, info_var, resample, finish_fn):
        dialog = QDialog(self)
        ui = generateUIFormView()
        groupBox = ui['groupBox']
        formLayout = ui['groupBoxFormLayout']
        widgetno = 1

        title = "Config for " + os.path.basename(fname)
        dialog.setWindowTitle(title)
        
        # dimensionality
        dimensionalityLabel = QLabel(groupBox)
        dimensionalityLabel.setText("Dimensionality")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, dimensionalityLabel)
        dimensionalityValue = QComboBox(groupBox)
        dimensionalityValue.addItem("3D")
        dimensionalityValue.addItem("2D")
        dimensionalityValue.setCurrentIndex(0)
        # dimensionalityValue.currentIndexChanged.connect(lambda: \
        #             self.overlapZValueEntry.setEnabled(True) \
        #             if self.dimensionalityValue.currentIndex() == 0 else \
        #             self.overlapZValueEntry.setEnabled(False))
        
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, dimensionalityValue)
        widgetno += 1

        validator = QtGui.QIntValidator()
        # Add X size
        dimXLabel = QLabel(groupBox)
        dimXLabel.setText("Size X")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, dimXLabel)
        dimXValueEntry = QLineEdit(groupBox)
        dimXValueEntry.setValidator(validator)
        dimXValueEntry.setText("0")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, dimXValueEntry)
        widgetno += 1

        # Add Y size
        dimYLabel = QLabel(groupBox)
        dimYLabel.setText("Size Y")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, dimYLabel)
        dimYValueEntry = QLineEdit(groupBox)
        dimYValueEntry.setValidator(validator)
        dimYValueEntry.setText("0")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, dimYValueEntry)
        widgetno += 1
        
        # Add Z size
        dimZLabel = QLabel(groupBox)
        dimZLabel.setText("Size Z")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, dimZLabel)
        dimZValueEntry = QLineEdit(groupBox)
        dimZValueEntry.setValidator(validator)
        dimZValueEntry.setText("0")
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, dimZValueEntry)
        widgetno += 1
        
        # Data Type
        dtypeLabel = QLabel(groupBox)
        dtypeLabel.setText("Data Type")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, dtypeLabel)
        dtypeValue = QComboBox(groupBox)
        dtypeValue.addItems(["int8", "uint8", "int16", "uint16"])#, "int32", "uint32", "float32", "float64"])
        dtypeValue.setCurrentIndex(0)
        
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, dtypeValue)
        widgetno += 1

        # Endiannes
        endiannesLabel = QLabel(groupBox)
        endiannesLabel.setText("Byte Ordering")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, endiannesLabel)
        endiannes = QComboBox(groupBox)
        endiannes.addItems(["Big Endian","Little Endian"])
        endiannes.setCurrentIndex(1)
        
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, endiannes)
        widgetno += 1

        # Fortran Ordering
        fortranLabel = QLabel(groupBox)
        fortranLabel.setText("Fortran Ordering")
        formLayout.setWidget(widgetno, QFormLayout.LabelRole, fortranLabel)
        fortranOrder = QComboBox(groupBox)
        fortranOrder.addItem("Fortran Order: XYZ")
        fortranOrder.addItem("C Order: ZYX")
        fortranOrder.setCurrentIndex(1)
        # dimensionalityValue.currentIndexChanged.connect(lambda: \
        #             self.overlapZValueEntry.setEnabled(True) \
        #             if self.dimensionalityValue.currentIndex() == 0 else \
        #             self.overlapZValueEntry.setEnabled(False))
        
        formLayout.setWidget(widgetno, QFormLayout.FieldRole, fortranOrder)
        widgetno += 1

        buttonbox = QDialogButtonBox(QDialogButtonBox.Ok |
                                    QDialogButtonBox.Cancel)
        buttonbox.accepted.connect(lambda: raw_conversion(self,fname, output_image, info_var, resample, finish_fn))
        buttonbox.rejected.connect(dialog.close)
        formLayout.addWidget(buttonbox)

        dialog.setLayout(ui['verticalLayout'])
        dialog.setModal(True)

        return {'dialog': dialog, 'ui': ui, 
                'dimensionality': dimensionalityValue, 
                'dimX': dimXValueEntry, 'dimY': dimYValueEntry, 'dimZ': dimZValueEntry,
                'dtype': dtypeValue, 'endiannes' : endiannes, 'isFortran' : fortranOrder,
                'buttonBox': buttonbox}

def raw_conversion(self, fname, output_image, info_var, resample, finish_fn):
        create_progress_window(self,"Converting", "Converting Image")
        self.progress_window.setValue(10)
        image_worker = Worker(saveRawImageData, self, fname, output_image,  info_var, resample)
        image_worker.signals.progress.connect(partial(progress, self.progress_window))
        image_worker.signals.result.connect(partial(finish_raw_conversion,self,finish_fn))
        self.threadpool.start(image_worker)
              
def finish_raw_conversion(self,finish_fn, error = None):
        self.raw_import_dialog['dialog'].close()
        self.progress_window.setValue(100)
        if error is not None:
            if error['type'] == 'size':
                self.warningDialog(
                    detailed_text='Expected Data size: {}b\nFile Data size:     {}b\n'.format(error['expected_size'], error['file_size']),
                    window_title='File Size Error',
                    message='Expected Data Size does not match File size.')
                return
            elif error['type'] == 'hdr':
                error_title = "Write Error"
                error_text = "Error writing to file: ({filename})".format(filename=error['hdrfname'])
                displayFileErrorDialog(self,message=error_text, title=error_title)
                return

        if finish_fn is not None:
            finish_fn()
                
def generateUIFormView():
        '''creates a widget with a form layout group to add things to

        basically you can add widget to the returned groupBoxFormLayout and paramsGroupBox
        The returned dockWidget must be added with
        self.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
        '''
        dockWidgetContents = QWidget()


        # Add vertical layout to dock contents
        dockContentsVerticalLayout = QVBoxLayout(dockWidgetContents)
        dockContentsVerticalLayout.setContentsMargins(0, 0, 0, 0)

        # Create widget for dock contents
        internalDockWidget = QWidget(dockWidgetContents)

        # Add vertical layout to dock widget
        internalWidgetVerticalLayout = QVBoxLayout(internalDockWidget)
        internalWidgetVerticalLayout.setContentsMargins(0, 0, 0, 0)

        # Add group box
        paramsGroupBox = QGroupBox(internalDockWidget)


        # Add form layout to group box
        groupBoxFormLayout = QFormLayout(paramsGroupBox)

        # Add elements to layout
        internalWidgetVerticalLayout.addWidget(paramsGroupBox)
        dockContentsVerticalLayout.addWidget(internalDockWidget)
        #dockWidget.setWidget(dockWidgetContents)
        return {'widget': dockWidgetContents,
                'verticalLayout':dockContentsVerticalLayout, 
                'internalWidget': internalDockWidget,
                'internalVerticalLayout': internalWidgetVerticalLayout, 
                'groupBox' : paramsGroupBox,
                'groupBoxFormLayout': groupBoxFormLayout}

def saveRawImageData(self,fname, output_image, info_var, resample, progress_callback):
        errors = {} 
        print ("File Name", fname)
        print ('Dimensionality', self.raw_import_dialog['dimensionality'].currentIndex())
        dimensionality = [3,2][self.raw_import_dialog['dimensionality'].currentIndex()]
        dimX = int ( self.raw_import_dialog['dimX'].text() )
        dimY = int ( self.raw_import_dialog['dimY'].text() )
        isFortran = True if self.raw_import_dialog['isFortran'].currentIndex() == 0 else False
        if isFortran:
            shape = (dimX, dimY)
        else:
            shape = (dimY, dimX)
        if dimensionality == 3:
            dimZ = int ( self.raw_import_dialog['dimZ'].text() )
            if isFortran:
                shape = (dimX, dimY, dimZ)
            else:
                shape = (dimZ, dimY, dimX)
        
        isBigEndian = True if self.raw_import_dialog['endiannes'].currentIndex() == 0 else False
        typecode = self.raw_import_dialog['dtype'].currentIndex()

        if info_var is not None:
            if typecode == 0 or 1:
                info_var['vol_bit_depth'] = '8'
                bytes_per_element = 1
            else:
                info_var['vol_bit_depth'] = '16'
                bytes_per_element = 2

        # basic sanity check
        file_size = os.stat(fname).st_size

        expected_size = 1
        for el in shape:
            expected_size *= el
            
        if typecode in [0,1]:
            mul = 1
        elif typecode in [2,3]:
            mul = 2
        elif typecode in [4,5,6]:
            mul = 4
        else:
            mul = 8
        expected_size *= mul
        if file_size != expected_size:
            errors = {"type": "size", "file_size": file_size, "expected_size": expected_size}
            return (errors)

        resample = False
        if resample:
            reader = cilBaseResampleReader()
            reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(get_progress, progress_callback= progress_callback))
            reader.SetFileName(fname)
            reader.SetTargetShape((512,512,512))
            reader.SetBytesPerElement(bytes_per_element)
            reader.SetBigEndian(isBigEndian)
            reader.SetIsFortran(isFortran)
            typecode = numpy.dtype(self.raw_import_dialog['dtype'].currentText()).char
            reader.SetNumpyTypeCode(typecode)
            reader.SetOutputVTKType(Converter.numpy_dtype_char_to_vtkType[typecode])
            reader.SetStoredArrayShape(shape)
            #We have not set spacing or origin
            reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(get_progress, progress_callback= progress_callback))
            reader.Update()
            output_image.ShallowCopy(reader.GetOutput())
            #print ("Spacing ", output_image.GetSpacing())

        else:

            header = generateMetaImageHeader(fname, typecode, shape, isFortran, isBigEndian, header_size=0, spacing=(1,1,1), origin=(0,0,0))

            #print (header)
            ff, fextension = os.path.splitext(os.path.basename(fname))
            hdrfname = os.path.join(os.path.dirname(fname),  ff + '.mhd' )
            with open(hdrfname , 'w') as hdr:
                hdr.write(header)

            progress_callback.emit(50)

            #self.raw_import_dialog['dialog'].reject()
            # expects to read a MetaImage File
            reader = vtk.vtkMetaImageReader()
            reader.AddObserver("ErrorEvent", self.e)
            reader.SetFileName(hdrfname)
            reader.Update()
            progress_callback.emit(80)

        if self.e.ErrorOccurred():
            errors = {"type": "hdr", "hdrfname": hdrfname}
            return (errors)
        else:
            # image_data = vtk.vtkImageData()
            # image_data = reader.GetOutput()
            # output_image.DeepCopy(image_data)
            output_image.ShallowCopy(reader.GetOutput())

        print("Finished saving")

        return(None)

        #self.setStatusTip('Ready')

def generateMetaImageHeader(datafname, typecode, shape, isFortran, isBigEndian, header_size=0, spacing=(1,1,1), origin=(0,0,0)):
        '''create MetaImageHeader for datafname based on the specifications in parameters'''
        # __typeDict = {'0':'MET_CHAR',    # VTK_SIGNED_CHAR,     # int8
        #               '1':'MET_UCHAR',   # VTK_UNSIGNED_CHAR,   # uint8
        #               '2':'MET_SHORT',   # VTK_SHORT,           # int16
        #               '3':'MET_USHORT',  # VTK_UNSIGNED_SHORT,  # uint16
        #               '4':'MET_INT',     # VTK_INT,             # int32
        #               '5':'MET_UINT',    # VTK_UNSIGNED_INT,    # uint32
        #               '6':'MET_FLOAT',   # VTK_FLOAT,           # float32
        #               '7':'MET_DOUBLE',  # VTK_DOUBLE,          # float64
        #       }
        __typeDict = ['MET_CHAR',    # VTK_SIGNED_CHAR,     # int8
                    'MET_UCHAR',   # VTK_UNSIGNED_CHAR,   # uint8
                    'MET_SHORT',   # VTK_SHORT,           # int16
                    'MET_USHORT',  # VTK_UNSIGNED_SHORT,  # uint16
                    'MET_INT',     # VTK_INT,             # int32
                    'MET_UINT',    # VTK_UNSIGNED_INT,    # uint32
                    'MET_FLOAT',   # VTK_FLOAT,           # float32
                    'MET_DOUBLE',  # VTK_DOUBLE,          # float64
        ]


        ar_type = __typeDict[typecode]
        # save header
        # minimal header structure
        # NDims = 3
        # DimSize = 181 217 181
        # ElementType = MET_UCHAR
        # ElementSpacing = 1.0 1.0 1.0
        # ElementByteOrderMSB = False
        # ElementDataFile = brainweb1.raw
        header = 'ObjectType = Image\n'
        header = ''
        header += 'NDims = {0}\n'.format(len(shape))
        if len(shape) == 2:
            header += 'DimSize = {} {}\n'.format(shape[0], shape[1])
            header += 'ElementSpacing = {} {}\n'.format(spacing[0], spacing[1])
            header += 'Position = {} {}\n'.format(origin[0], origin[1])
        
        elif len(shape) == 3:
            header += 'DimSize = {} {} {}\n'.format(shape[0], shape[1], shape[2])
            header += 'ElementSpacing = {} {} {}\n'.format(spacing[0], spacing[1], spacing[2])
            header += 'Position = {} {} {}\n'.format(origin[0], origin[1], origin[2])
        
        header += 'ElementType = {}\n'.format(ar_type)
        # MSB (aka big-endian)
        MSB = 'True' if isBigEndian else 'False'
        header += 'ElementByteOrderMSB = {}\n'.format(MSB)

        header += 'HeaderSize = {}\n'.format(header_size)
        header += 'ElementDataFile = {}'.format(os.path.basename(datafname))
        return header



class cilNumpyPointCloudToPolyData(VTKPythonAlgorithmBase): #This class is copied from dvc_configurator.py
    '''vtkAlgorithm to read a point cloud from a NumPy array
    '''
    def __init__(self):
        VTKPythonAlgorithmBase.__init__(self, nInputPorts=0, nOutputPorts=1)
        self.__Points = vtk.vtkPoints()
        self.__Vertices = vtk.vtkCellArray()
        self.__Data = None


    def GetPoints(self):
        '''Returns the Points'''
        return self.__Points
    def SetData(self, value):
        '''Sets the points from a numpy array or list'''
        if not isinstance (value, numpy.ndarray) :
            raise ValueError('Data must be a numpy array. Got', value)

        if not numpy.array_equal(value,self.__Data):
            self.__Data = value
            self.Modified()

    def GetData(self):
        return self.__Data


    def GetNumberOfPoints(self):
        '''returns the number of points in the point cloud'''
        return self.__Points.GetNumberOfPoints()


    def FillInputPortInformation(self, port, info):
        # if port == 0:
        #    info.Set(vtk.vtkAlgorithm.INPUT_REQUIRED_DATA_TYPE(), "vtkImageData")
        return 1

    def FillOutputPortInformation(self, port, info):
        info.Set(vtk.vtkDataObject.DATA_TYPE_NAME(), "vtkPolyData")
        return 1

    def RequestData(self, request, inInfo, outInfo):

        # print ("Request Data")
        # output_image = vtk.vtkDataSet.GetData(inInfo[0])
        pointPolyData = vtk.vtkPolyData.GetData(outInfo)
        vtkPointCloud = self.__Points
        for point in self.GetData():
            # point = id, x, y, z
            vtkPointCloud.InsertNextPoint( point[1] , point[2] , point[3])

        self.FillCells()

        pointPolyData.SetPoints(self.__Points)
        pointPolyData.SetVerts(self.__Vertices)
        return 1


    def FillCells(self):
        '''Fills the Vertices'''
        vertices = self.__Vertices
        number_of_cells = vertices.GetNumberOfCells()
        for i in range(self.GetNumberOfPoints()):
            if i >= number_of_cells:
                vertices.InsertNextCell(1)
                vertices.InsertCellPoint(i)

