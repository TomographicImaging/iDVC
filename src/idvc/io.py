#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

#   Author: Laura Murgatroyd (UKRI-STFC)
#   Author: Edoardo Pasca (UKRI-STFC)

import imghdr
import os
import shutil
import sys
import time
from functools import partial

import numpy
import vtk
from ccpi.viewer.utils import Converter
from ccpi.viewer.utils.conversion import (cilRawCroppedReader,
                                          cilRawResampleReader,
                                          cilMetaImageCroppedReader,
                                          cilMetaImageResampleReader,
                                          cilNumpyCroppedReader,
                                          cilNumpyResampleReader,
                                          cilTIFFResampleReader,
                                          cilTIFFCroppedReader, 
                                          Converter)
from eqt.threading import Worker
from PySide2 import QtCore, QtGui
from PySide2.QtCore import QThreadPool
from PySide2.QtWidgets import (QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QLabel, QLineEdit,
                               QMessageBox, QProgressDialog, QVBoxLayout,
                               QWidget)

# ImageCreator class


class ImageDataCreator(object):

    '''Converts an image file into VTK image data

        Takes an array of image file/s: image_files (list of image files)

        Takes a variable where a copy of the image data will be stored: output_image (vtkImageData)

        Option to convert image file to numpy format: convert_numpy (bool)

        Option to save raw version of image file in case of metaimage files (bool)
        Note: this converts the entire image file not the downsampled/cropped version

        Dictionary where info about image will be stored (such as vol_bit_depth and location of npy file).
        If the image is a raw file, this dictionary may be used to provide details of the image file: info_var (dict)

        Method to be carried out once the vtk image data creation is complete: finish_fn (method)

        Whether to resample the image (currently only for np and raw files): resample (bool)

        Folder where to save converted image file. If not set, converted image is saved
        in same location as input image: output_dir (directory path)

        Arguments for the finish_fn: *finish_fn_args, **finish_fn_kwargs

        '''

    def createImageData(main_window, image_files, output_image, *finish_fn_args, info_var=None, convert_numpy=False, convert_raw=True,  resample=False, target_size=0.125, crop_image=False, origin=(0, 0, 0), target_z_extent=(0, 0), output_dir=None, finish_fn=None,  **finish_fn_kwargs):
        # print("Create image data")
        if len(image_files) == 1:
            image = image_files[0]
            file_extension = os.path.splitext(image)[1]

        else:
            for image in image_files:
                file_extension = imghdr.what(image)
                if file_extension.lower() not in ['tiff', 'tif']:
                    error_title = "Read Error"
                    error_text = "Error reading file: ({filename})".format(
                        filename=image)
                    displayFileErrorDialog(
                        main_window, message=error_text, title=error_title, detailed_message='When reading multiple files, all files must TIFF formatted.')
                    return

        if file_extension in ['.mha', '.mhd']:
            createProgressWindow(main_window, "Converting", "Converting Image")
            image_worker = Worker(loadMetaImage, main_window=main_window, image=image, output_image=output_image,
                                  image_info=info_var, resample=resample, target_size=target_size, crop_image=crop_image, origin=origin,
                                  target_z_extent=target_z_extent, convert_numpy=convert_numpy, convert_raw=convert_raw, output_dir=output_dir)

        elif file_extension in ['.npy']:
            createProgressWindow(main_window, "Converting", "Converting Image")
            # image_file, output_image, image_info = None, resample = False, target_size = 0.125, crop_image = False,
            # origin = (0,0,0), target_z_extent = (0,0), progress_callback=None
            image_worker = Worker(loadNpyImage, image_file=image, output_image=output_image, image_info=info_var, resample=resample, target_size=target_size,
                                  crop_image=crop_image, origin=origin, target_z_extent=target_z_extent)

        elif file_extension in ['tif', 'tiff', '.tif', '.tiff']:
            createProgressWindow(main_window, "Converting", "Converting Image")
            # filenames, reader, output_image,   convert_numpy = False,  image_info = None, progress_callback=None
            
            image_worker = Worker(loadTif, image_files, output_image, convert_numpy=convert_numpy, 
                                  image_info=info_var, resample=resample, crop_image=crop_image, target_size=target_size,
                                  origin=origin, target_z_extent=target_z_extent)

        elif file_extension in ['.raw']:
            if 'file_type' in info_var and info_var['file_type'] == 'raw':
                createConvertRawImageWorker(main_window, image, output_image, info_var,
                                            resample, target_size, crop_image, origin, target_z_extent, finish_fn)
                return
            else:  # if we aren't given the image dimensions etc, the user needs to enter them
                main_window.raw_import_dialog = createRawImportDialog(
                    main_window, image, output_image, info_var, resample, target_size, crop_image, origin, target_z_extent, finish_fn)
                dialog = main_window.raw_import_dialog['dialog'].show()
                return

        else:
            error_title = "Error"
            error_text = "Error reading file: ({filename})".format(
                filename=image)
            displayFileErrorDialog(
                main_window, message=error_text, title=error_title, 
                detailed_message='File format is not supported. Accepted formats include: .mhd, .mha, .npy, .tif, .raw')
            return

        main_window.progress_window.setValue(10)

        # connect signals and slots
        # connect error signal to an ErrorDialog
        ff = partial(displayErrorDialogFromWorker, main_window)
        image_worker.signals.error.connect(ff)

        image_worker.signals.progress.connect(partial(progress, main_window.progress_window))
        # the "finished" signal will call the connected slot irrespectively of whether there was an error or not
        # therefore we need to connect the "result" signal to a function that will check if there was an error
        if finish_fn is not None:
            rif = partial(runIfFinishedCorrectly, main_window=main_window, finish_fn=finish_fn, *finish_fn_args, **finish_fn_kwargs)
            image_worker.signals.result.connect(rif)
        
        main_window.threadpool = QThreadPool()
        main_window.threadpool.start(image_worker)
        print("Started worker")

def runIfFinishedCorrectly(result, main_window=None, finish_fn=None, *args, **kwargs):
    if result is not None and result == 0:
        finish_fn(*args, **kwargs)

# For progress bars:
def createProgressWindow(main_window, title, text, max=100, cancel=None):
    main_window.progress_window = QProgressDialog(
        text, "Cancel", 0, max, main_window, QtCore.Qt.Window)
    main_window.progress_window.setWindowTitle(title)
    # This means the other windows can't be used while this is open
    main_window.progress_window.setWindowModality(QtCore.Qt.ApplicationModal)
    main_window.progress_window.setMinimumDuration(0.1)
    main_window.progress_window.setWindowFlag(
        QtCore.Qt.WindowCloseButtonHint, True)
    main_window.progress_window.setWindowFlag(
        QtCore.Qt.WindowMaximizeButtonHint, False)
    if cancel is None:
        main_window.progress_window.setCancelButton(None)
    else:
        main_window.progress_window.canceled.connect(cancel)


def progress(progress_window, value=None):
    if value is not None:
        if int(value) > progress_window.value():
            progress_window.setValue(value)

# Display errors:

def displayFileErrorDialog(main_window, message, title, detailed_message):
    '''
    Parameters
    ---------
    main_window : QMainWindow
        The main window of the application
    message : str
        The message to display in the dialog
    title : str
        The title of the dialog
    detailed_message : str
        The detailed message to display in the dialog       

    '''
    msg = QMessageBox(main_window)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setDetailedText(detailed_message)
    msg.open()


def displayErrorDialogFromWorker(main_window, error):
    '''This is a new version of displayFileErrorDialog that takes an error object as an argument.
    This function is meant to be used with the Worker class, which passes the error object to the error signal.
    
    The error object is a tuple containing (exctype, value, traceback.format_exc())
    https://github.com/paskino/qt-elements/blob/b34e7886f7e395683bbb618cc925ede8426fe8cd/eqt/threading/QtThreading.py#L83

    Additionally, this function does not make use of the main_window.e.ErrorMessage() function of ErrorObserver.

    Example Usage:
    Suppose you have a Worker, any error that occurs in the worker will emit the error signal, which can be 
    connected to this function.

    ff = partial(displayErrorDialogFromWorker, main_window)
    image_worker.signals.error.connect(ff)

    '''
    # (exctype, value, traceback.format_exc())
    title='Caught Exception'
    message = 'Except type {}\nvalue {}'.format(error[0], error[1])
    detailed_message = str(error[2])
    msg = QMessageBox(main_window)
    msg.setIcon(QMessageBox.Critical)
    msg.setWindowTitle(title)
    msg.setText(message)
    msg.setDetailedText(detailed_message)
    msg.exec_()

def warningDialog(main_window, message='', window_title='', detailed_text=''):
    dialog = QMessageBox(main_window)
    dialog.setIcon(QMessageBox.Information)
    dialog.setText(message)
    dialog.setWindowTitle(window_title)
    dialog.setDetailedText(detailed_text)
    dialog.setStandardButtons(QMessageBox.Ok)
    retval = dialog.exec_()
    return retval

# Load images:

# mha and mhd:

# def loadMetaImage(main_window, image, output_image,  image_info = None, resample = False, target_size = 0.125, crop_image = False, origin = (0,0,0), target_z_extent = (0,0), convert_numpy = False, convert_raw = True, output_dir = None, progress_callback=None):


def loadMetaImage(**kwargs):
    main_window = kwargs.get('main_window')
    image = kwargs.get('image')
    output_image = kwargs.get('output_image')
    image_info = kwargs.get('image_info', None)
    resample = kwargs.get('resample', False)
    target_size = kwargs.get('target_size', 0.125)
    crop_image = kwargs.get('crop_image', False)
    origin = kwargs.get('origin', (0, 0, 0))
    target_z_extent = kwargs.get('target_z_extent', (0, 0))
    convert_numpy = kwargs.get('convert_numpy', False)
    convert_raw = kwargs.get('convert_raw', True)
    output_dir = kwargs.get('output_dir', None)
    progress_callback = kwargs.get('progress_callback', None)

    if resample:
        reader = cilMetaImageResampleReader()
        #print("Target size: ", int(target_size * 1024*1024*1024))
        reader.SetTargetSize(int(target_size * 1024*1024*1024))
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))

    elif crop_image:
        reader = cilMetaImageCroppedReader()
        reader.SetOrigin(tuple(origin))
        reader.SetTargetZExtent(target_z_extent)
        if image_info is not None:
            image_info['sampled'] = False
            image_info['cropped'] = True

    else:
        reader = cilMetaImageResampleReader()
        # Forces use of resample reader but does not resample
        reader.SetTargetSize(int(1e12))
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        if image_info is not None:
            image_info['sampled'] = False

    reader.AddObserver("ErrorEvent", main_window.e)

    reader.SetFileName(image)
    reader.Update()

    output_image.ShallowCopy(reader.GetOutput())

    progress_callback.emit(90)

    if resample:
        loaded_image_size = reader.GetStoredArrayShape(
        )[0] * reader.GetStoredArrayShape()[1] * reader.GetStoredArrayShape()[2]
        resampled_image_size = reader.GetTargetSize()
        if image_info is not None:
            if loaded_image_size <= resampled_image_size:
                image_info['sampled'] = False
            else:
                image_info['sampled'] = True

    loaded_shape = reader.GetStoredArrayShape()

    if not reader.GetIsFortran():
        loaded_shape = loaded_shape[::-1]

    if image_info is not None:
        image_info['shape'] = loaded_shape
        image_info['vol_bit_depth'] = str(reader.GetBytesPerElement()*8)
        image_info['isBigEndian'] = reader.GetBigEndian()
        image_info['header_length'] = 0

    if convert_raw:
        filename = reader.GetFileName()
        if '.mha' in filename:
            headerlength = reader.GetFileHeaderLength()
            if output_dir is None:
                new_filename = image[:-4] + ".raw"
            else:
                new_filename = os.path.relpath(os.path.join(
                    output_dir, os.path.basename(image)[:-4] + ".raw"))

            with open(image, "rb") as image_file_object:
                end_slice = loaded_shape[2]
                image_location = headerlength
                with open(new_filename, "wb") as raw_file_object:
                    image_file_object.seek(image_location)
                    chunk = image_file_object.read()
                    raw_file_object.write(chunk)
        else:
            # TODO: fix this?
            file_ext = os.path.splitext(filename)[1]
            if output_dir is not None:
                new_filename = os.path.join(
                    output_dir, os.path.basename(filename))
                shutil.copyfile(filename, new_filename)
            else:
                new_filename = filename

        image_info['raw_file'] = new_filename
        image_info['header_length'] = 0

    if convert_numpy:
        # this is for using in the dvc code
        print("Converting metaimage to numpy")
        if output_dir is None:
            filename = os.path.abspath(image)[:-4] + ".npy"
        else:
            filename = os.path.join(
                output_dir, os.path.basename(image)[:-4] + ".npy")
        print(filename)
        numpy_array = Converter.vtk2numpy(reader.GetOutput(), order="F")
        numpy.save(filename, numpy_array)

        if image_info is not None:
            image_info['numpy_file'] = filename
            with open(filename, 'rb') as f:
                header = f.readline()
            image_info['header_length'] = len(header)

    progress_callback.emit(100)
    # all good, return 0
    return 0


# def loadNpyImage(image_file, output_image, image_info = None, resample = False, target_size = 0.125, crop_image = False, origin = (0,0,0), target_z_extent = (0,0), progress_callback=None):
def loadNpyImage(**kwargs):
    image_file = kwargs.get('image_file')
    output_image = kwargs.get('output_image')
    image_info = kwargs.get('image_info', None)
    resample = kwargs.get('resample', False)
    target_size = kwargs.get('target_size', 0.125)
    crop_image = kwargs.get('crop_image', False)
    origin = kwargs.get('origin', (0, 0, 0))
    target_z_extent = kwargs.get('target_z_extent', (0, 0))
    progress_callback = kwargs.get('progress_callback', None)
    if resample:
        reader = cilNumpyResampleReader()
        reader.SetFileName(image_file)
        reader.SetTargetSize(int(target_size * 1024*1024*1024))
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.Update()
        output_image.ShallowCopy(reader.GetOutput())
        print("Spacing ", output_image.GetSpacing())
        header_length = reader.GetFileHeaderLength()
        print("Length of header: ", header_length)
        vol_bit_depth = reader.GetBytesPerElement()*8
        shape = reader.GetStoredArrayShape()
        if not reader.GetIsFortran():
            shape = shape[::-1]
        if image_info is not None:
            image_info['isBigEndian'] = reader.GetBigEndian()

            image_size = reader.GetStoredArrayShape(
            )[0] * reader.GetStoredArrayShape()[1]*reader.GetStoredArrayShape()[2]
            target_size = reader.GetTargetSize()
            print("array shape", image_size)
            print("target", target_size)
            if image_size <= target_size:
                image_info['sampled'] = False
            else:
                image_info['sampled'] = True
        # print("Header", header_length)
        # print("vol_bit_depth", vol_bit_depth)

    elif crop_image:
        print("Target z extent", target_z_extent)
        print("Origin", origin)
        reader = cilNumpyCroppedReader()
        reader.SetFileName(image_file)
        reader.SetOrigin(tuple(origin))
        reader.SetTargetZExtent(target_z_extent)
        reader.Update()
        output_image.ShallowCopy(reader.GetOutput())
        print("Spacing ", output_image.GetSpacing())
        header_length = reader.GetFileHeaderLength()
        vol_bit_depth = reader.GetBytesPerElement()*8
        shape = reader.GetStoredArrayShape()
        if not reader.GetIsFortran():
            shape = shape[::-1]
        if image_info is not None:
            image_info['isBigEndian'] = reader.GetBigEndian()

            image_info['cropped'] = True

    else:
        time.sleep(0.1)
        progress_callback.emit(5)

        with open(image_file, 'rb') as f:
            header = f.readline()
        header_length = len(header)
        print("Length of header: ", len(header))

        numpy_array = numpy.load(image_file)
        shape = numpy.shape(numpy_array)

        if (isinstance(numpy_array[0][0][0], numpy.uint8)):
            vol_bit_depth = '8'
        elif(isinstance(numpy_array[0][0][0], numpy.uint16)):
            vol_bit_depth = '16'
        else:
            vol_bit_depth = None  # in this case we can't run the DVC code
            output_image = None
            return

        if image_info is not None:
            image_info['sampled'] = False
            if numpy_array.dtype.byteorder == '=':
                if sys.byteorder == 'big':
                    image_info['isBigEndian'] = True
                else:
                    image_info['isBigEndian'] = False
            else:
                image_info['isBigEndian'] = None

                print(image_info['isBigEndian'])

        Converter.numpy2vtkImage(
            numpy_array, output=output_image)  # (3.2,3.2,1.5)
        progress_callback.emit(80)

    progress_callback.emit(100)

    if image_info is not None:
        image_info["header_length"] = header_length
        image_info["vol_bit_depth"] = vol_bit_depth
        image_info["shape"] = shape
    # all good, return 0
    return 0

def loadTif(*args, **kwargs):
    # filenames, reader, output_image,   convert_numpy = False,  image_info = None, progress_callback=None):
    # filenames, reader, output_image,   convert_numpy = False,  image_info = None, progress_callback=None
    # var,resample=resample, target_size=target_size,
    # origin=origin, target_z_extent=target_z_extent
    filenames, output_image = args
    image_info = kwargs.get('image_info', None)
    progress_callback = kwargs.get('progress_callback')
    resample = kwargs.get('resample', False)
    crop_image = kwargs.get('crop_image', False)
    target_size = kwargs.get('target_size', 0.125)
    origin = kwargs.get('origin', (0, 0, 0))
    target_z_extent = kwargs.get('target_z_extent', (0, 0))
    bits_per_byte = 8

    # time.sleep(0.1) #required so that progress window displays
    # progress_callback.emit(10)
    
    if resample:
        reader = cilTIFFResampleReader()
        reader.SetFileName(filenames)
        reader.SetTargetSize(int(target_size * 1024*1024*1024))
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.Update()
        output_image.ShallowCopy(reader.GetOutput())
        print("Spacing ", output_image.GetSpacing())
        header_length = reader.GetFileHeaderLength()
        print("Length of header: ", header_length)
        
        shape = reader.GetStoredArrayShape()
        if not reader.GetIsFortran():
            shape = shape[::-1]
        if image_info is not None:
            image_info['isBigEndian'] = reader.GetBigEndian()

            image_size = reader.GetStoredArrayShape(
            )[0] * reader.GetStoredArrayShape()[1]*reader.GetStoredArrayShape()[2]
            target_size = reader.GetTargetSize()
            if image_size <= target_size:
                image_info['sampled'] = False
            else:
                image_info['sampled'] = True

    elif crop_image:
        reader = cilTIFFCroppedReader()
        reader.SetOrigin(tuple(origin))
        reader.SetTargetZExtent(target_z_extent)
        if image_info is not None:
            image_info['sampled'] = False
            image_info['cropped'] = True
        
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.SetFileName(filenames)

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

        shape = reader.GetStoredArrayShape()
        
        progress_callback.emit(80)

        image_data = reader.GetOutput()
        output_image.ShallowCopy(image_data)

        progress_callback.emit(90)

        image_info['sampled'] = False

    # this is dangerous as reader might not be defined!!!
    vol_bit_depth = reader.GetBytesPerElement() * bits_per_byte

    if image_info is not None:
        image_info["vol_bit_depth"] = vol_bit_depth
        image_info["shape"] = shape
    progress_callback.emit(100)
    # all good, return 0
    return 0

def getProgress(caller, event, progress_callback):
    progress_callback.emit(caller.GetProgress()*80)


# raw:
def createRawImportDialog(main_window, fname, output_image, info_var, resample, target_size, crop_image, origin, target_z_extent, finish_fn):
    dialog = QDialog(main_window)
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
    #             main_window.overlapZValueEntry.setEnabled(True) \
    #             if main_window.dimensionalityValue.currentIndex() == 0 else \
    #             main_window.overlapZValueEntry.setEnabled(False))

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
    # , "int32", "uint32", "float32", "float64"])
    dtypeValue.addItems(["int8", "uint8", "int16", "uint16"])
    dtypeValue.setCurrentIndex(1)

    formLayout.setWidget(widgetno, QFormLayout.FieldRole, dtypeValue)
    widgetno += 1

    # Endiannes
    endiannesLabel = QLabel(groupBox)
    endiannesLabel.setText("Byte Ordering")
    formLayout.setWidget(widgetno, QFormLayout.LabelRole, endiannesLabel)
    endiannes = QComboBox(groupBox)
    endiannes.addItems(["Big Endian", "Little Endian"])
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
    fortranOrder.setCurrentIndex(0)
    # dimensionalityValue.currentIndexChanged.connect(lambda: \
    #             main_window.overlapZValueEntry.setEnabled(True) \
    #             if main_window.dimensionalityValue.currentIndex() == 0 else \
    #             main_window.overlapZValueEntry.setEnabled(False))

    formLayout.setWidget(widgetno, QFormLayout.FieldRole, fortranOrder)
    widgetno += 1

    buttonbox = QDialogButtonBox(QDialogButtonBox.Ok |
                                 QDialogButtonBox.Cancel)
    buttonbox.accepted.connect(lambda: createConvertRawImageWorker(
        main_window, fname, output_image, info_var, resample, target_size, crop_image, origin, target_z_extent, finish_fn))
    buttonbox.rejected.connect(dialog.close)
    formLayout.addWidget(buttonbox)

    dialog.setLayout(ui['verticalLayout'])
    dialog.setModal(True)

    return {'dialog': dialog, 'ui': ui,
            'dimensionality': dimensionalityValue,
            'dimX': dimXValueEntry, 'dimY': dimYValueEntry, 'dimZ': dimZValueEntry,
            'dtype': dtypeValue, 'endiannes': endiannes, 'isFortran': fortranOrder,
            'buttonBox': buttonbox}


def createConvertRawImageWorker(main_window, fname, output_image, info_var, resample, target_size, crop_image, origin, target_z_extent, finish_fn):
    createProgressWindow(main_window, "Converting", "Converting Image")
    main_window.progress_window.setValue(10)
    image_worker = Worker(saveRawImageData, main_window=main_window, fname=fname, output_image=output_image,
                          info_var=info_var, resample=resample, target_size=target_size, crop_image=crop_image, origin=origin, target_z_extent=target_z_extent)
    image_worker.signals.progress.connect(
        partial(progress, main_window.progress_window))
    image_worker.signals.result.connect(
        partial(finishRawConversion, main_window, finish_fn))
    main_window.threadpool.start(image_worker)


def finishRawConversion(main_window, finish_fn, error=None):
    main_window.raw_import_dialog['dialog'].close()
    main_window.progress_window.setValue(100)
    if error is not None:
        if error['type'] == 'size':
            main_window.warningDialog(
                detailed_text='Expected Data size: {}b\nFile Data size:     {}b\n'.format(
                    error['expected_size'], error['file_size']),
                window_title='File Size Error',
                message='Expected Data Size does not match File size.')
            return
        elif error['type'] == 'hdr':
            error_title = "Write Error"
            # : ({filename})".format(filename=error['hdrfname'])
            error_text = "Error writing to file"
            displayFileErrorDialog(
                main_window, message=error_text, title=error_title, detailed_message="")
            return

    if finish_fn is not None:
        finish_fn()


def generateUIFormView():
    '''creates a widget with a form layout group to add things to

    basically you can add widget to the returned groupBoxFormLayout and paramsGroupBox
    The returned dockWidget must be added with
    main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, dockWidget)
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
    # dockWidget.setWidget(dockWidgetContents)
    return {'widget': dockWidgetContents,
            'verticalLayout': dockContentsVerticalLayout,
            'internalWidget': internalDockWidget,
            'internalVerticalLayout': internalWidgetVerticalLayout,
            'groupBox': paramsGroupBox,
            'groupBoxFormLayout': groupBoxFormLayout}


# def saveRawImageData(main_window, fname, output_image, info_var, resample, target_size, crop_image, origin, target_z_extent, progress_callback):
def saveRawImageData(**kwargs):
    main_window = kwargs.get('main_window')
    fname = kwargs.get('fname')
    output_image = kwargs.get('output_image')
    info_var = kwargs.get('info_var', None)
    resample = kwargs.get('resample', False)
    target_size = kwargs.get('target_size', 0.125)
    crop_image = kwargs.get('crop_image', False)
    origin = kwargs.get('origin', (0, 0, 0))
    target_z_extent = kwargs.get('target_z_extent', (0, 0))
    progress_callback = kwargs.get('progress_callback', None)
    errors = {}
    #print ("File Name", fname)

    if 'file_type' in info_var and info_var['file_type'] == 'raw':
        dimensionality = len(info_var['dimensions'])
        dimX = info_var['dimensions'][0]
        dimY = info_var['dimensions'][1]
        if dimensionality == 3:
            dimZ = info_var['dimensions'][2]
        isFortran = info_var['isFortran']
        isBigEndian = info_var['isBigEndian']
        typecode = info_var['typcode']

    else:
        # retrieve info about image file from interface
        dimensionality = [
            3, 2][main_window.raw_import_dialog['dimensionality'].currentIndex()]
        dimX = int(main_window.raw_import_dialog['dimX'].text())
        dimY = int(main_window.raw_import_dialog['dimY'].text())
        if dimensionality == 3:
            dimZ = int(main_window.raw_import_dialog['dimZ'].text())
        isFortran = True if main_window.raw_import_dialog['isFortran'].currentIndex(
        ) == 0 else False
        isBigEndian = True if main_window.raw_import_dialog['endiannes'].currentIndex(
        ) == 0 else False
        typecode = main_window.raw_import_dialog['dtype'].currentIndex()

        # save to info_var dictionary:
        info_var['file_type'] = 'raw'
        if dimensionality == 3:
            info_var['dimensions'] = [dimX, dimY, dimZ]
        else:
            info_var['dimensions'] = [dimX, dimY]

        info_var['isFortran'] = isFortran
        info_var['isBigEndian'] = isBigEndian
        info_var['typcode'] = typecode

    if isFortran:
        shape = (dimX, dimY)
    else:
        shape = (dimY, dimX)
    if dimensionality == 3:
        if isFortran:
            shape = (dimX, dimY, dimZ)
        else:
            shape = (dimZ, dimY, dimX)

    info_var["shape"] = shape

    if info_var is not None:
        if typecode == 0 or typecode == 1:
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

    if typecode in [0, 1]:
        mul = 1
    elif typecode in [2, 3]:
        mul = 2
    elif typecode in [4, 5, 6]:
        mul = 4
    else:
        mul = 8
    expected_size *= mul
    if file_size != expected_size:
        errors = {"type": "size", "file_size": file_size,
                  "expected_size": expected_size}
        return (errors)

    if resample:
        reader = cilRawResampleReader()
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.SetFileName(fname)
        reader.SetTargetSize(int(target_size * 1024*1024*1024))
        reader.SetBigEndian(isBigEndian)
        reader.SetIsFortran(isFortran)
        reader.SetTypeCodeName(
            main_window.raw_import_dialog['dtype'].currentText())
        reader.SetStoredArrayShape(shape)
        # We have not set spacing or origin
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.Update()
        output_image.ShallowCopy(reader.GetOutput())
        #print ("Spacing ", output_image.GetSpacing())
        image_size = reader.GetStoredArrayShape(
        )[0] * reader.GetStoredArrayShape()[1]*reader.GetStoredArrayShape()[2]
        target_size = reader.GetTargetSize()
        print("array shape", image_size)
        print("target", target_size)
        if info_var is not None:
            if image_size <= target_size:
                info_var['sampled'] = False
            else:
                info_var['sampled'] = True
    elif crop_image:
        reader = cilRawCroppedReader()
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.SetFileName(fname)
        reader.SetTargetZExtent(target_z_extent)
        reader.SetOrigin(tuple(origin))
        reader.SetBigEndian(isBigEndian)
        reader.SetIsFortran(isFortran)
        reader.SetTypeCodeName(
            main_window.raw_import_dialog['dtype'].currentText())
        reader.SetStoredArrayShape(shape)
        # We have not set spacing or origin
        reader.AddObserver(vtk.vtkCommand.ProgressEvent, partial(
            getProgress, progress_callback=progress_callback))
        reader.Update()
        output_image.ShallowCopy(reader.GetOutput())
        #print ("Spacing ", output_image.GetSpacing())
        image_size = reader.GetStoredArrayShape(
        )[0] * reader.GetStoredArrayShape()[1]*reader.GetStoredArrayShape()[2]
        # print("array shape", image_size)
        if info_var is not None:
            info_var['cropped'] = True

    else:
        if info_var is not None:
            info_var['sampled'] = False
        header = generateMetaImageHeader(
            fname, typecode, shape, isFortran, isBigEndian, header_size=0, spacing=(1, 1, 1), origin=(0, 0, 0))

        #print (header)
        ff, fextension = os.path.splitext(os.path.basename(fname))
        hdrfname = os.path.join(os.path.dirname(fname),  ff + '.mhd')
        with open(hdrfname, 'w') as hdr:
            hdr.write(header)

        progress_callback.emit(50)

        # main_window.raw_import_dialog['dialog'].reject()
        # expects to read a MetaImage File
        reader = vtk.vtkMetaImageReader()
        reader.AddObserver("ErrorEvent", main_window.e)
        reader.SetFileName(hdrfname)
        reader.Update()
        progress_callback.emit(80)

    # TODO: fix the error reporting - with the below included this error message shows up when we have a different downsampling rate- thsi is not necessary
    # if main_window.e.ErrorOccurred():
    #     errors = {"type": "hdr"} #, "hdrfname": hdrfname}
    #     return (errors)
    # else:
        # image_data = vtk.vtkImageData()
        # image_data = reader.GetOutput()
        # output_image.DeepCopy(image_data)
    output_image.ShallowCopy(reader.GetOutput())

    print("Finished saving")

    return(None)

    # main_window.setStatusTip('Ready')


def generateMetaImageHeader(datafname, typecode, shape, isFortran, isBigEndian, header_size=0, spacing=(1, 1, 1), origin=(0, 0, 0)):
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
        header += 'ElementSpacing = {} {} {}\n'.format(
            spacing[0], spacing[1], spacing[2])
        header += 'Position = {} {} {}\n'.format(
            origin[0], origin[1], origin[2])

    header += 'ElementType = {}\n'.format(ar_type)
    # MSB (aka big-endian)
    MSB = 'True' if isBigEndian else 'False'
    header += 'ElementByteOrderMSB = {}\n'.format(MSB)

    header += 'HeaderSize = {}\n'.format(header_size)
    header += 'ElementDataFile = {}'.format(os.path.basename(datafname))
    return header

def save_tiff_stack_as_raw(filenames: list, output_fname: str) ->None :
    '''Converts a TIFF stack to a raw file'''
    reader = vtk.vtkTIFFReader()
    reader.SetOrientationType(1) # TopLeft
    with open(os.path.abspath(output_fname), 'wb') as f:
        for el in filenames:
            reader.SetFileName(el)
            reader.Update()
            slice_data = Converter.vtk2numpy(reader.GetOutput())
            f.write(slice_data.tobytes())
            

