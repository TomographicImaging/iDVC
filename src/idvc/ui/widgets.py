from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from idvc.utils.manipulate_result_files import extractDataFromDispResultFile
from functools import partial
import shutil
import os
import tempfile
from eqt.threading import Worker
from scipy.stats import norm
from eqt.ui.NoBorderScrollArea import NoBorderScrollArea


class BaseResultsWidget(QtWidgets.QWidget):
    '''creates a dockable widget which will display graph results from runs of the DVC code
    '''
    def __init__(self, parent):
        '''
        Adds vertical layout.
        figure.
        canvas.
        sets minimum size so scrollbar works.
        Parameters
        ----------  
        results: RunResults
        displ_wrt_point0: bool
        '''
        super().__init__()
        self.parent = parent
        self.fig = Figure()
        self.fig, hist_plot = plt.subplots(figsize=(10, 8), layout="constrained")
        self.canvas = FigureCanvas(self.fig)
        self.fig.clf()
        self.canvas.setMinimumSize(400, 400) #needed for scrollbar
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)




    def addSubplot(self, plotNum, result, array, data_label): 
        '''plot the Gaussian curve, legend
        
        Returns
        -------
        matplotlib.pyplot
            A plot of the histogram
        """'''
        xlabel = data_label
        counts, bins, patches = plt.hist(array, bins=20)
        relative_counts = counts*100/ len(array)
        plt.cla()
        bin_widths = np.diff(bins)
        plt.bar(bins[:-1], relative_counts, width=bin_widths, align='edge')
        plt.ylabel("Relative frequency (% points in run)")
        plt.xlabel(xlabel)

        mean = array.mean()
        std = array.std()
        plt.axvline(mean, color='r', linestyle='--', label=f'mean = {mean:.2f}')
        plt.axvline(mean-std, color='g', linestyle='--', label=f'std = {std:.2f}')
        plt.axvline(mean+std, color='g', linestyle='--')

        x = np.linspace(min(array), max(array), 1000)
        gaussian = norm.pdf(x, mean, std) * (bins[1] - bins[0]) *100
        plt.plot(x, gaussian, 'b--', label='gaussian fit')

        plt.legend(loc='upper right')
        return plt

class SingleRunResultsWidget(BaseResultsWidget):
    '''creates a dockable widget which will display results from a single run of the DVC code
    '''
    def __init__(self, parent, result, displ_wrt_point0):
        '''
        Parameters
        ----------  
        results: RunResults
        displ_wrt_point0: bool
        '''
        super().__init__(parent)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas, stretch=1)
        self.setLayout(self.layout)
        self.addHistogramsToLayout(result, displ_wrt_point0)
            

    def addHistogramsToLayout(self, result, displ_wrt_point0):
        '''
    
        Extracts the data from the disp file.
        Determines the number of graphs, rows and column to group them in.
        Hist makes an instogram with bins 20.
        
        Parameters
        ----------  
        result: RunResults
        displ_wrt_point0: bool
        '''
        self.fig.suptitle(f"Run '{result.run_name}': points in subvolume {result.subvol_points}, subvolume size {result.subvol_size}",fontsize='xx-large')
        result_arrays = extractDataFromDispResultFile(result, displ_wrt_point0)
        numGraphs = len(result_arrays)
        if numGraphs <= 3:
            numRows = 1
        else:
            numRows = int(np.round(np.sqrt(numGraphs)))
        numColumns = int(np.ceil(numGraphs/numRows))


        plotNum = 0
        for array in result_arrays:
            data_label = result.data_label[plotNum]
            plotNum = plotNum + 1
            self.fig.add_subplot(numRows, numColumns, plotNum)
            subplot = self.addSubplot(plotNum, result, array, data_label)
            
        self.fig.subplots_adjust(hspace=0.5,wspace=0.5)

        self.canvas.draw() 
        return subplot

class BulkRunResultsWidget(BaseResultsWidget):
    '''creates a dockable widget which will display results from all runs in a bulk run
    '''
    def __init__(self, parent, result_data_frame):
        super().__init__(parent)


        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.layout.addLayout(self.grid_layout,0)

        single_result = result_data_frame.iloc[0]['result']
        self.run_name = single_result.run_name
        self.subvol_sizes = result_data_frame['subvol_size'].unique()
        self.subvol_points = result_data_frame['subvol_points'].unique()
        self.addWidgetstoGridLayout(single_result)
        self.button.clicked.connect(partial(self.addHistogramsToLayout, result_data_frame))
        
        scroll_area_widget = NoBorderScrollArea(self.canvas)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(scroll_area_widget,1)
        self.addHistogramsToLayout(result_data_frame)

    def addWidgetstoGridLayout(self, result):
        widgetno=0

        self.results_details_label = QLabel(self)
        self.results_details_label.setText("Subvolume Geometry: {subvol_geom}\n\
Maximum Displacement: {disp_max}\n\
Degrees of Freedom: {num_srch_dof}\n\
Objective Function: {obj_function}\n\
Interpolation Type: {interp_type}\n\
Rigid Body Offset: {rigid_trans}".format(subvol_geom=result.subvol_geom, \
        disp_max=result.disp_max, num_srch_dof=str(result.num_srch_dof), obj_function=result.obj_function, \
        interp_type=result.interp_type, rigid_trans=str(result.rigid_trans)))
        self.grid_layout.addWidget(self.results_details_label,widgetno,0,5,1)
        self.results_details_label.setAlignment(Qt.AlignTop)        
        widgetno+=1


        self.label = QLabel(self)
        self.label.setText("Select data: ")
        self.grid_layout.addWidget(self.label,widgetno,1)

        self.data_label_widget = QComboBox(self)
        self.data_label_widget.addItems(result.data_label)
        self.grid_layout.addWidget(self.data_label_widget,widgetno,2)  
        widgetno+=1

        self.label1 = QLabel(self)
        self.label1.setText("Select parameter: ")
        self.grid_layout.addWidget(self.label1,widgetno,1)  
        
        self.param_list_widget = QComboBox(self)
        self.param_list = ["All","Sampling points in subvolume", "Subvolume size"]
        self.param_list_widget.addItems(self.param_list)
        self.grid_layout.addWidget(self.param_list_widget,widgetno,2)
        widgetno+=1

        self.secondParamLabel = QLabel(self)
        self.secondParamLabel.setText("Subvolume size:")
        self.grid_layout.addWidget(self.secondParamLabel,widgetno,1)
        
        self.secondParamCombo = QComboBox(self)
        self.secondParamCombo.addItems(self.subvol_sizes)
        self.grid_layout.addWidget(self.secondParamCombo,widgetno,2)
        widgetno+=1

        self.param_list_widget.currentIndexChanged.connect(self.showSecondParam)
        self.secondParamLabel.hide()
        self.secondParamCombo.hide()

        self.button = QtWidgets.QPushButton("Plot Histograms")
        
        self.grid_layout.addWidget(self.button,widgetno,2)
        widgetno+=1

        self.grid_layout.addWidget(self.toolbar,widgetno,0,1,3)
        widgetno+=1

    def showSecondParam(self):
        index = self.param_list_widget.currentIndex()
        if index ==0:
            self.secondParamLabel.hide()
            self.secondParamCombo.hide()

        elif index == 1:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Subvolume Size:")
            self.secondParamCombo.clear()
            self.secondParamCombo.addItems([str(i) for i in self.subvol_sizes])

        elif index == 2:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Points in Subvolume:")
            self.secondParamCombo.clear()
            newList = []
            self.secondParamCombo.addItems([str(i) for i in self.subvol_points])   
        
    def addHistogramsToLayout(self, result_data_frame):
        self.fig.clf()
        param_index = self.param_list_widget.currentIndex()
        
        self.fig.suptitle(f"Bulk Run '{self.run_name}': {self.data_label_widget.currentText()}",fontsize='xx-large')
        
        numRows = len(self.subvol_sizes)
        numColumns = len(self.subvol_points)
        plotNum = 0
        
        for row in result_data_frame.itertuples():
            result = row.result

            if param_index == 1: 
                numRows = 1
                if result.subvol_size != float(self.secondParamCombo.currentText()):
                    continue
            elif param_index ==2:
                numColumns = 1
                if result.subvol_points != float(self.secondParamCombo.currentText()):
                    continue
            data_label = f"{self.data_label_widget.currentText()}"
            data_index = self.data_label_widget.currentIndex()
            plotNum = plotNum + 1
            subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
            self.addSubplot(plotNum, result, row.result_arrays[data_index], data_label)
            subplot.set_title(f"Points in subvolume = {result.subvol_points}, Subvolume size = {result.subvol_size}", fontsize='x-large', pad=20)

        self.fig.subplots_adjust(hspace=2,wspace=0.5)
        self.canvas.draw()


        
class SaveObjectWindow(QtWidgets.QWidget):
    '''a window which will appear when saving a mask or pointcloud
    '''
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent, object_type, save_only):
        super().__init__()

        #print(save_only)

        self.parent = parent
        self.object = object_type

        if self.object == "mask":
            self.setWindowTitle("Save Existing Mask")
            self.label = QLabel("Save mask as:")
        elif self.object == "pointcloud":
            self.setWindowTitle("Save Existing Point Cloud")
            self.label = QLabel("Save Point Cloud as:")


        self.setWindowModality(QtCore.Qt.ApplicationModal)
        #self.setInputMode(QtWidgets.QInputDialog.TextInput)

        self.textbox = QLineEdit(self)
        rx = QRegExp("[A-Za-z0-9]+")
        validator = QRegExpValidator(rx, self.textbox) #need to check this
        self.textbox.setValidator(validator)

        self.save_button = QPushButton("Save")
        self.quit_button = QPushButton("Discard")
        self.save_button.clicked.connect(lambda: self.save(save_only))
        self.quit_button.clicked.connect(self.quit)
        
        self.setWindowFlags(QtCore.Qt.WindowTitleHint )
        #self.setCancelButtonText("New Session")
        #self.setAttribute(Qt.WA_DeleteOnClose)
        self.layout = QtWidgets.QFormLayout()
        self.layout.addRow(self.label)
        self.layout.addRow(self.textbox)
        self.layout.addRow(self.save_button, self.quit_button)
        self.setLayout(self.layout)


    def save(self, save_only):
        if self.object == "mask":
            #Load Saved Session
            #print("Write mask to file, then carry on")
            filename = self.textbox.text() + ".mha"
            shutil.copyfile(os.path.join(tempfile.tempdir, self.parent.mask_file), os.path.join(tempfile.tempdir, "Masks", filename))
            self.parent.mask_parameters['masksList'].addItem(filename)
            self.parent.mask_details[filename] = self.parent.mask_details['current']
            #print(self.parent.mask_details)

            self.parent.mask_parameters['loadButton'].setEnabled(True)
            self.parent.mask_parameters['masksList'].setEnabled(True)


            if not save_only:
                #print("Not save only")
                #would be better to move this elsewhere
                self.parent.mask_worker = Worker(self.parent.extendMask)
                self.parent.create_progress_window("Loading", "Loading Mask")
                self.parent.mask_worker.signals.progress.connect(self.parent.progress)
                self.parent.mask_worker.signals.finished.connect(self.parent.DisplayMask)
                self.parent.threadpool.start(self.parent.mask_worker)
                self.parent.progress_window.setValue(10)
            
        if self.object == "pointcloud":
            filename = self.textbox.text() + ".roi"
            shutil.copyfile(os.path.join(tempfile.tempdir, "latest_pointcloud.roi"), os.path.join(tempfile.tempdir, filename))

            self.parent.pointcloud_parameters['loadButton'].setEnabled(True)
            self.parent.pointcloud_parameters['pointcloudList'].setEnabled(True)
            self.parent.pointcloud_parameters['pointcloudList'].addItem(filename)
            self.parent.pointCloud_details[filename] = self.parent.pointCloud_details['latest_pointcloud.roi']
            #print(self.parent.pointCloud_details)
            #self.parent.createPointCloud()
            if not save_only:
                self.parent.PointCloudWorker("create")
            

        self.close()

    def quit(self):
        if self.object == "mask":
            #would be better to move this elsewhere
            self.parent.mask_worker = Worker(self.parent.extendMask)
            self.parent.create_progress_window("Loading", "Loading Mask")
            self.parent.mask_worker.signals.progress.connect(self.parent.progress)
            self.parent.mask_worker.signals.finished.connect(self.parent.DisplayMask)
            self.parent.threadpool.start(self.parent.mask_worker)
            self.parent.progress_window.setValue(10)

        if self.object == "pointcloud":
            self.parent.PointCloudWorker("create")
            #self.parent.createPointCloud()

        self.close()
