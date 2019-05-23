from ccpi.viewer.QtThreading import Worker, WorkerSignals
import sys
from PyQt5 import QtCore
from PyQt5 import QtGui
#from PyQt5.QtWidgets import *
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWidgets import QAction
from PyQt5.QtWidgets import QDockWidget
from PyQt5.QtWidgets import QFrame
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtWidgets import QStyle
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWidgets import QTableWidget
from PyQt5.QtWidgets import QTableWidgetItem
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWidgets import QPushButton
from PyQt5.QtWidgets import QFormLayout
from PyQt5.QtWidgets import QGroupBox
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtWidgets import QLineEdit
from PyQt5.QtWidgets import QLabel
from PyQt5.QtWidgets import QComboBox
from PyQt5.QtWidgets import QProgressBar, QStatusBar
import vtk
from ccpi.viewer.QVTKCILViewer import QVTKCILViewer
from ccpi.viewer.QVTKWidget import QVTKWidget

from PyQt5.QtCore import QThreadPool, QTimer
import time
#from ccpi.apps.cast_tiff import processTiffStack, processListOfTiffStack
import tempfile, shutil, glob, functools
import os, sys
# import json
import glob
import vtk
from tqdm import tqdm
from vtk.util import numpy_support
import numpy
import matplotlib.pyplot as plt
import imghdr

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

def processTiffStack(wildcard_filenames, output_dir, bitdepth=16, 
                     extent=None, percentiles=None, crop=False, prettyprint=print, progress=None):
    '''reads a tiff stack and casts to UNSIGNED INT 8 or 16, saves to MetaImage'''
    tmp = glob.glob(wildcard_filenames)
    print ("Found {} files".format(len(tmp)))
    return processListOfTiffStack(tmp, output_dir, bitdepth, extent, percentiles, crop)
    
    # all_min, all_max , flist , vtk_type = findMinMaxInTiffStack(tmp, bitdepth=bitdepth, 
    #                                      extent=extent, crop=crop, prettyprint=print, progress=progress)
    # scale, bin_edges = createHistogramAndFindPercentiles(flist, dtype=vtk_type, extent=extent, 
    #                                   percentiles=percentiles, crop=crop, prettyprint=print, progress=callback)

    # saved_files = castTiffStackOnPercentiles(flist, output_dir, scale, bin_edges, dtype=vtk.VTK_UNSIGNED_CHAR, 
    #                  extent=None, crop=False, prettyprint=print, progress=None)
    # return saved_files
    


def findMinMaxInTiffStack(tmp, bitdepth=16, extent=None, crop=False, prettyprint=print, progress=None):
    
    if extent != None:
        prettyprint ("Volume of interest ", extent)
        if len(extent) == 4:
            flist = tmp
        elif len(extent) == 6:
            flist = [tmp[i] for i in range(extent[4], extent[5])] 
    else:
        flist = tmp
    prettyprint ("processing {} files of {}".format(len(flist), len(tmp)))
    if len(flist) > 0:
        reader = vtk.vtkTIFFReader()
        #  determine bit depth
        reader.SetFileName(flist[0])
        reader.Update()
        vtk_bit_depth = reader.GetOutput().GetScalarType()
        prettyprint ("Input Scalar type" , reader.GetOutput().GetScalarTypeAsString())
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
            prettyprint ("Casting images to {}".format(dtypestring))
            
            stats = vtk.vtkImageAccumulate()
            voi = vtk.vtkExtractVOI()
            prettyprint ("looking for min max in the dataset")
            
            
            for i,fname in tqdm(enumerate(flist)):
                if progress is not None:
                    progress.emit(i//len(flist))
                reader.SetFileName(fname)
                reader.Update()
                if extent is not None:
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
    return (all_min, all_max, flist, dtype)
def createHistogramAndFindPercentiles(flist, dtype=vtk.VTK_UNSIGNED_CHAR, extent=None, percentiles=None, crop=False, 
                                      prettyprint=print, progress=None):
    # create a histogram of the whole dataset
    if dtype == vtk.VTK_UNSIGNED_CHAR:
        nbins = vtk.VTK_UNSIGNED_CHAR_MAX + 1
    elif dtype == vtk.VTK_UNSIGNED_SHORT:
        nbins = vtk.VTK_UNSIGNED_SHORT_MAX + 1
    # nbins = 255
    prettyprint ("Constructing the histogram of the whole dataset: crop {}".format(crop))
    reader = vtk.vtkTIFFReader()
    voi = vtk.vtkExtractVOI()
    for i,fname in enumerate(tqdm(flist)):
        if progress is not None:
            progress.emit(i//len(flist))
        reader.SetFileName(fname)
        reader.Update()
        if extent is not None:
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

    # plt.plot(bin_edges[1:],histogram)
    # plt.axvline(x=bin_edges[min_perc])
    # plt.axvline(x=bin_edges[max_perc])
    # plt.show()
    scale = (imax - imin) / (bin_edges[max_perc] - bin_edges[min_perc])
    prettyprint ("min {}\tmax {}\nedge_min {}\tedge_max {}\nscale {}".format(
        all_min, all_max, bin_edges[min_perc] ,bin_edges[max_perc], scale))
    return (scale, bin_edges)
def castTiffStackOnPercentiles(flist, output_dir, scale, bin_edges, dtype=vtk.VTK_UNSIGNED_CHAR, 
                     extent=None, crop=False, prettyprint=print, progress=None):
    # scale and cast the image
    reader = vtk.vtkTIFFReader()
    voi = vtk.vtkExtractVOI()
    shiftScaler = vtk.vtkImageShiftScale ()
    shiftScaler.ClampOverflowOn()
    if extent is not None and crop:
        prettyprint("Scaling and cropping the volume on selection")
        voi.SetInputConnection(reader.GetOutputPort())
        voi.SetVOI(extent[0], extent[1], extent[2], extent[3], 0, 0)
        shiftScaler.SetInputConnection(voi.GetOutputPort())
    else:
        prettyprint("Scaling the volume on selection")
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
        if progress is not None:
            progress.emit(i//len(flist))
        reader.SetFileName(fname)
        reader.Update()
        
        shiftScaler.Update() 
        
        writer.SetFileName(os.path.join(os.path.abspath(output_dir), 
                            '{}_{}'.format(dtypestring, os.path.basename(fname))))
        writer.Write()
        new_flist.append(writer.GetFileName())
    
    # save original flist 
    #orig_flist = flist[:]
    # copy the new file list into flist
    #flist = new_flist[:]
    return new_flist
            
def processListOfTiffStack(tmp, output_dir, bitdepth=16, extent=None, 
                           percentiles=None, crop=False, prettyprint=print, progress=None,
                           downsample_factors=(1,1,1)):
    if progress is None:
        print ("NOOOOOOOOOOOOOOOOOONNNNNNNNNNNNNNNEEEEEEEEEEEEEEEEEEEEE")
    if extent is not None:
        prettyprint ("Volume of interest {}".format(extent))
        if len(extent) == 4:
            flist = tmp
        elif len(extent) == 6:
            flist = [tmp[i] for i in range(extent[4], extent[5])] 
    else:
        flist = tmp
    prettyprint ("processing {} files of {}".format(len(flist), len(tmp)))
    if len(flist) > 0:
        reader = vtk.vtkTIFFReader()
        #  determine bit depth
        reader.SetFileName(flist[0])
        reader.Update()
        vtk_bit_depth = reader.GetOutput().GetScalarType()
        prettyprint ("Input Scalar type {}".format(reader.GetOutput().GetScalarTypeAsString()))
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
            prettyprint ("Casting images to {}".format(dtypestring))
            
            stats = vtk.vtkImageAccumulate()
            voi = vtk.vtkExtractVOI()
            prettyprint ("looking for min max in the dataset")
            
            
            for i,fname in tqdm(enumerate(flist)):
                if progress is not None:
                    progress.emit(i/len(flist)*100)
                    
                reader.SetFileName(fname)
                reader.Update()
                if extent is not None:
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
            prettyprint ("Constructing the histogram of the whole dataset: crop {}".format(crop))
            for i,fname in enumerate(tqdm(flist)):
                if progress is not None:
                    progress.emit(i/len(flist)*100)
                reader.SetFileName(fname)
                reader.Update()
                if extent is not None:
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

            # plt.plot(bin_edges[1:],histogram)
            # plt.axvline(x=bin_edges[min_perc])
            # plt.axvline(x=bin_edges[max_perc])
            # plt.show()
            scale = (imax - imin) / (bin_edges[max_perc] - bin_edges[min_perc])
            prettyprint ("min {}\tmax {}\nedge_min {}\tedge_max {}\nscale {}".format(
                all_min, all_max, bin_edges[min_perc] ,bin_edges[max_perc], scale))
            
            # scale and cast the image
            shiftScaler = vtk.vtkImageShiftScale ()
            shiftScaler.ClampOverflowOn()
            if extent is not None and crop:
                prettyprint("Scaling and cropping the volume on selection")
                voi.SetInputConnection(reader.GetOutputPort())
                voi.SetVOI(extent[0], extent[1], extent[2], extent[3], 0, 0)
                shiftScaler.SetInputConnection(voi.GetOutputPort())
            else:
                prettyprint("Scaling the volume on selection")
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
                if progress is not None:
                    progress.emit(i/len(flist)*100)
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
            return flist
        else:
            prettyprint ("no need to cast image type")        
    else:
        raise ValueError('Could not find files in ', wildcard_filenames)


class ErrorObserver:

   def __init__(self):
       self.__ErrorOccurred = False
       self.__ErrorMessage = None
       self.CallDataType = 'string0'

   def __call__(self, obj, event, message):
       self.__ErrorOccurred = True
       self.__ErrorMessage = message

   def ErrorOccurred(self):
       occ = self.__ErrorOccurred
       self.__ErrorOccurred = False
       return occ

   def ErrorMessage(self):
       return self.__ErrorMessage


def sentenceCase(string):
    if string:
        first_word = string.split()[0]
        world_len = len(first_word)

        return first_word.capitalize() + string[world_len:]

    else:
        return ''



class ViewerCastWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle('CIL Viewer')
        self.setGeometry(50, 50, 600, 600)

        self.e = ErrorObserver()

        openAction = QAction("Open", self)
        openAction.setShortcut("Ctrl+O")
        openAction.triggered.connect(self.openFile)

        closeAction = QAction("Close", self)
        closeAction.setShortcut("Ctrl+Q")
        closeAction.triggered.connect(self.close)

        mainMenu = self.menuBar()
        fileMenu = mainMenu.addMenu('File')
        fileMenu.addAction(openAction)
        fileMenu.addAction(closeAction)

        self.frame = QFrame()
        self.vl = QVBoxLayout()
        self.vtkWidget = QVTKCILViewer(self.frame)
        self.iren = self.vtkWidget.getInteractor()
        self.vl.addWidget(self.vtkWidget)

        self.frame.setLayout(self.vl)
        self.setCentralWidget(self.frame)

        self.toolbar()

        self.progressbar = self.setup_progressbar()
        
        self.statusBar()
        self.statusBar().addPermanentWidget(self.progressbar)
        self.setStatusTip('Open file to begin visualisation...')

        self.show()

        self.threadpool = QThreadPool()

    def toolbar(self):
        # Initialise the toolbar
        self.toolbar = self.addToolBar('Viewer tools')

        # define actions
        openAction = QAction(self.style().standardIcon(QStyle.SP_DirOpenIcon), 'Open file', self)
        openAction.triggered.connect(self.openFile)

        saveAction = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), 'Save current render as PNG', self)
        # saveAction.setShortcut("Ctrl+S")
        saveAction.triggered.connect(self.saveFile)

        # Add actions to toolbar
        self.toolbar.addAction(openAction)
        self.toolbar.addAction(saveAction)
    
    def setup_progressbar(self):
        progress = QProgressBar(self)
        #progress.setGeometry(0, 0, 300, 25)
        progress.setMaximum(100)
        return progress

    def openFile(self):
        fn = QFileDialog.getOpenFileNames(self, 'Open File')

        # If the user has pressed cancel, the first element of the tuple will be empty.
        # Quit the method cleanly
        if not fn[0]:
            return

        # Single file selection
        if len(fn[0]) == 1:
            filename = fn[0][0]

            reader = vtk.vtkMetaImageReader()
            reader.AddObserver("ErrorEvent", self.e)
            reader.SetFileName(filename)
            reader.Update()

        # Multiple TIFF files selected
        else:
            # Make sure that the files are sorted 0 - end
            filenames = fn[0]

            # Basic test for tiff images
            for tfile in filenames:
                ftype = imghdr.what(tfile)
                if ftype != 'tiff':
                    # A non-TIFF file has been loaded, present error message and exit method
                    self.e('','','When reading multiple files, all files must TIFF formatted.')
                    tfile = tfile
                    self.displayFileErrorDialog(tfile)
                    return

            # get an idea of the shear size of the image
            reader = vtk.vtkTIFFReader()
            reader.SetFileName(filenames[0])
            reader.Update()
            dims = list(reader.GetOutput().GetDimensions())
            dims[2] = len(filenames)
            size = dims[0]*dims[1]*dims[2]
            dtype = reader.GetOutput().GetScalarType()
            if dtype == vtk.VTK_UNSIGNED_CHAR or dtype == vtk.VTK_SIGNED_CHAR:
                bit_depth = 8
            elif dtype == vtk.VTK_UNSIGNED_SHORT or dtype == vtk.VTK_SHORT:
                bit_depth = 16
            elif dtype == vtk.VTK_UNSIGNED_INT or dtype == vtk.VTK_INT:
                bit_depth = 32
            elif dtype == vtk.VTK_FLOAT:
                bit_depth = 32
            elif dtype == vtk.VTK_DOUBLE:
                bit_depth = 64
            else:
                raise ValueError('Unsupported Image Type ', reader.GetOutput().GetScalarTypeAsString())
            total_size = bit_depth * size 
            print ("Total size of the image is ", total_size, dims, size, bit_depth)
            print ("Total size of the image is {:f} Gb".format(total_size / (1024*1024*1024)) )

            # try a downsampling strategy
            # 1 Gb is the target size
            target_max_dim = (1024, 1024, 1024)
            target_max_size = target_max_dim[0] * target_max_dim[1] * target_max_dim[2] * 8
            #%%
            downsample_factors = [target_max_dim[i] / dims[i] if target_max_dim[i] / dims[i] < 1 else 1 for i in range(3) ]
            print (downsample_factors)
            self.downsample_factors = downsample_factors
            self.filenames = filenames
                
            if functools.reduce(lambda x,y: x or y<1, downsample_factors, False):
                # should downsample
                kwargs = {'on_result': self.start_cast_tiff_worker_resample, 
                          'on_progress': self.progress_fn, 
                          'on_finished': self.done_status_bar, 
                          'downsample_factors': downsample_factors,
                          'filenames': filenames}
                self.start_worker(self.downsample, **kwargs)
                return

            else:
                # Have passed basic test, can attempt to load1
                # launch a cast_tiff in a thread
                self.start_cast_tiff_worker()

    def done_status_bar(self):
        self.statusBar().showMessage('Done downsampling')
    def downsample(self, progress_callback, **kwargs):
        filenames = kwargs.get('filenames', self.filenames)
        downsample_factor = kwargs.get('downsample_factors', (1,1,1))
        output_dir = tempfile.mkdtemp(prefix='dvc_resample_')
        self.resample_output_dir = output_dir
        
        # set up a vtk chain
        reader = vtk.vtkTIFFReader()
        
        resampler = vtk.vtkImageResample()
        resampler.SetMagnificationFactors(downsample_factor[0], downsample_factor[1], 1)
        resampler.SetInputConnection(reader.GetOutputPort())
            
        writer = vtk.vtkTIFFWriter()
        writer.SetInputConnection(resampler.GetOutputPort())

        outfilenames = []
        for fname in tqdm(filenames):
            reader.SetFileName(fname)
            fn = os.path.basename(fname)
            outfname = os.path.join(os.path.abspath(output_dir), "resample_"+fn)
            outfilenames.append(outfname)
            writer.SetFileName(outfname)
            reader.Update()
            resampler.Update()
            writer.Write()
        return outfilenames
    def downsample_z(self):
        kwargs = {'on_result': self.async_viewer_data_loader, 
                    'on_progress': self.progress_fn, 
                    'on_finished': self.done_status_bar, 
                    'downsample_factors': downsample_factors,
                    'filenames': filenames}
        self.start_worker(self.downsample, **kwargs)
        
    def saveFile(self):
        dialog = QFileDialog(self)
        dialog.setAcceptMode(QFileDialog.AcceptSave)

        fn = dialog.getSaveFileName(self,'Save As','.',"Images (*.png)")

        # Only save if the user has selected a name
        if fn[0]:
            self.vtkWidget.viewer.saveRender(fn[0])

    def displayFileErrorDialog(self, file):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Critical)
        msg.setWindowTitle("READ ERROR")
        msg.setText("Error reading file: ({filename})".format(filename=file))
        msg.setDetailedText(self.e.ErrorMessage())
        msg.exec_()


    def close(self):
        try:
            shutil.rmtree(self.output_dir)
        except AttributeError as ae:
            pass
        self.app.quit()
    def start_cast_tiff_worker_resample(self, result):
        print ("on result of downsample")
        print (result[0])
        self.filenames = result[0]
        # the image has been downsampled xy
        self.downsample_factors[0] = 1
        self.downsample_factors[1] = 1
        if self.downsample_factors[2] != 1:
            on_result = self.downsample_z
        else:
            on_result = self.updateStatusTip

        kwargs = {'filenames': result[0], 
                  'bitdepth' : 8,
                  'extent' : None,
                  'percentiles' : None,
                  'crop' : False,
                  'on_result': on_result,
                  'on_finished' : self.thread_complete,
                  'on_progress' : print,
                  ''
        }
        self.start_worker(self.cast_tiff, **kwargs)
    def start_cast_tiff_worker(self):
        # Pass the function to execute
        # wildcard_filenames, output_dir, bitdepth=16, 
        #              extent=None, percentiles=None, crop=False, callback=None, progress=None
        kwargs = {'filenames': self.filenames, 
                  'bitdepth' : 8,
                  'extent' : None,
                  'percentiles' : None,
                  'crop' : False
        }
        worker = Worker(self.cast_tiff, **kwargs) # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.updateStatusTip)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(print)

        # Execute
        self.threadpool.start(worker)

    def start_worker(self, func, **kwargs):
        # Pass the function to execute
        #kwargs = {'filenames': self.filenames}

        on_result = kwargs.get('on_result', self.get_output)
        on_finished = kwargs.get('on_finished', self.thread_complete)
        on_progress = kwargs.get('on_progress', self.progress_fn)
        worker = Worker(func, **kwargs) # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(on_result)
        worker.signals.finished.connect(on_finished)
        worker.signals.progress.connect(on_progress)

        # Execute
        self.threadpool.start(worker)
    def get_output(self,result):
        self.statusBar().showMessage('Done')
        print ("output", result[0])
        self.filenames = result[0]
        #self.load_dataset_into_viewer(filenames)
        

    def cast_tiff(self, progress_callback, **kwargs):
        tmp = kwargs.get('filenames', None)
        print ("cast_tiff" , tmp)
        output_dir = tempfile.mkdtemp(prefix='dvc')
        self.output_dir = output_dir
        print("temporary dir ", output_dir)
        self.setStatusTip('Casting...')
        print ("progress_callback", progress_callback)
        return processListOfTiffStack(tmp, output_dir, bitdepth=8, extent=None, 
                               percentiles=None, crop=False, 
                               prettyprint=self.updateStatusTip,
                               progress=progress_callback,
                               downsample_factors=kwargs.get('downsample_factors', [1,1,1]))
    
    def thread_complete(self):
        print ("are we here yet?")
        self.statusBar().showMessage('Casting Complete... Loading')
        kwargs = {'filenames' : self.filenames, 
        'on_result' : self.load_dataset_into_viewer,
        'on_finished' : lambda: self.progressbar.setValue(0),
        'on_progress' : lambda: print}
        self.start_worker(self.load_dataset_thread, **kwargs)
    
    def async_viewer_data_loader(self, result):
        kwargs = {'filenames' : result[0], 
            'on_result' : self.load_dataset_into_viewer,
            'on_finished' : lambda: self.progressbar.setValue(0),
            'on_progress' : lambda: print}
        self.start_worker(self.load_dataset_thread, **kwargs)
        
    def update_progressbar(self, value):
        #self.progressbar.setValue(value)
        pass

    def load_dataset_thread(self, progress_callback, **kwargs):
        filenames = kwargs.get('filenames', None)
        print (filenames)
        reader = vtk.vtkTIFFReader()
        sa = vtk.vtkStringArray()
        #i = 0
        #while (i < 1054):
        # filenames = glob.glob(self.output_dir)

        for j,fname in enumerate(filenames):
            #fname = os.path.join(directory,"8bit-1%04d.tif" % i)
            i = sa.InsertNextValue(fname)
            progress_callback.emit(j/len(filenames)*100)
            
        print ("reading {} files".format( i + 1 ))
        
        reader.SetFileNames(sa)
        reader.Update()
        print ("read {} files".format( i + 1 ))
        return reader
        
    def load_dataset_into_viewer(self, result): 
        reader = result[0]
        self.vtkWidget.viewer.setInput3DData(reader.GetOutput())

    def progress_fn(self, n):
        print("%d%% done" % n)
        self.progressbar.setValue(n)
    def updateStatusTip(self, msg):
        print (str(msg))
        self.statusBar().showMessage(str(msg))
    def setApp(self, app):
        self.app = app


        
class MainWindow(QMainWindow):


    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)

        self.counter = 0

        layout = QVBoxLayout()

        self.l = QLabel("Start")
        b = QPushButton("DANGER!")
        b.pressed.connect(self.oh_no)

        layout.addWidget(self.l)
        layout.addWidget(b)

        w = QWidget()
        w.setLayout(layout)

        self.setCentralWidget(w)

        self.progressbar = self.setup_progressbar()
        
        self.statusBar()
        self.statusBar().addPermanentWidget(self.progressbar)
        
        self.show()

        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.recurring_timer)
        self.timer.start()

    def setup_progressbar(self):
        progress = QProgressBar(self)
        #progress.setGeometry(0, 0, 300, 25)
        progress.setMaximum(100)
        return progress

    def progress_fn(self, n):
        print("%d%% done" % n)
        self.progressbar.setValue(n)

    def execute_this_fn(self, progress_callback, *args, **kwargs):
        for el in args:
            print ('args', el)
        
        for k,v in kwargs.items():
            print ("kwargs" , k,v)

        a = []
        for n in range(0, 5):
            time.sleep(1)
            progress_callback.emit(n*100/4)
            a.append(n)

        return a

    def get_output(self, result):
        self.statusBar().showMessage('Done')
        print ("output", result[0])

    def thread_complete(self, *args, **kwargs):
        print("THREAD COMPLETE!")
        self.statusBar().showMessage("THREAD COMPLETE!")
        
        

    def oh_no(self):
        # Pass the function to execute
        kwargs = {'pippo': 1}
        worker = Worker(self.execute_this_fn, **kwargs) # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.get_output)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(self.progress_fn)

        # Execute
        self.threadpool.start(worker)


    def recurring_timer(self):
        self.counter +=1
        self.l.setText("Counter: %d" % self.counter)

if __name__ == '__main__':
    app = QApplication([])
    if False:
        window = MainWindow()
    else:
        window = ViewerCastWindow()
        window.setApp(app)
    app.exec_()