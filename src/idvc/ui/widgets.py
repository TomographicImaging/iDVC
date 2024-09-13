from PySide2 import QtWidgets, QtCore
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from idvc.utils.manipulate_result_files import extractDataFromDispResultFile
from functools import partial
import shutil
import os
import tempfile
from eqt.threading import Worker
from scipy.stats import norm
import glob
from idvc.utilities import RunResults


class BaseResultsWidget(QtWidgets.QWidget):
    '''creates a dockable widget which will display graph results from runs of the DVC code
    '''
    def __init__(self, parent):
        '''
        Parameters
        ----------  
        results: RunResults
        displ_wrt_point0: bool
        '''
        super().__init__()
        self.parent = parent
        self.plt = plt
        self.figure = self.plt.figure()

        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)



    def addSubplot(self, figure, numRows, numColumns, plotNum, result, array): 
        '''plot the Gaussian curve, legend'''
        xlabel = result.data_label[plotNum-1]
        ax = figure.add_subplot(numRows, numColumns, int(plotNum))
        counts, bins, patches = ax.hist(array, bins=20)
        relative_counts = counts*100/ len(array)

        ax.clear()
        bin_widths = np.diff(bins)
        ax.bar(bins[:-1], relative_counts, width=bin_widths, align='edge')
        ax.set_ylabel("Relative frequency (% points in run)")
        ax.set_xlabel(xlabel)

        mean = array.mean()
        var = array.var()
        std = array.std()
        ax.axvline(mean, color='r', linestyle='--', label=f'mean = {mean:.2f}')
        ax.axvline(mean-std, color='g', linestyle='--', label=f'std = {std:.2f}')
        ax.axvline(mean+std, color='g', linestyle='--')

        x = np.linspace(min(array), max(array), 1000)
        gaussian = norm.pdf(x, mean, std) * (bins[1] - bins[0]) *100
        ax.plot(x, gaussian, 'b--', label='gaussian fit')

        ax.legend(loc='upper right')

class SingleRunResultsWidget(BaseResultsWidget):
    '''creates a dockable widget which will display results from a single run of the DVC code
    '''
    def __init__(self, parent):
        '''
        Parameters
        ----------  
        results: RunResults
        displ_wrt_point0: bool
        '''
        super().__init__(parent)
        
        
        #Layout
        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

    def addHistogramsToLayout(self, result, displ_wrt_point0 = False):
        '''
    
        Extracts the data from the disp file.
        Determines the number of graphs, rows and column to group them in.
        Hist makes an instogram with bins 20.
        
        Parameters
        ----------  
        result: RunResults
        displ_wrt_point0: bool
        '''
        self.plt.suptitle(f"Run {result.run_name}: points in subvolume {result.subvol_points}, subvolume size {result.subvol_size}")
        data, no_points, result_arrays = extractDataFromDispResultFile(result, displ_wrt_point0)
        numGraphs = len(result_arrays)
        if numGraphs <= 3:
            numRows = 1
        else:
            numRows = np.round(np.sqrt(numGraphs))
        numColumns = np.ceil(numGraphs/numRows)

        plotNum = 0
        for array in result_arrays:
            plotNum = plotNum + 1
            self.addSubplot(self.figure, int(numRows), int(numColumns), plotNum, result, array)

        plt.tight_layout() # Provides proper spacing between figures

        self.canvas.draw() 

class BulkRunResultsWidget(BaseResultsWidget):
    '''creates a dockable widget which will display results from all runs in a bulk run
    '''
    def __init__(self, parent, folder, displ_wrt_point0 = False):
        super().__init__(parent)
        self.parent = parent

        self.layout = QtWidgets.QGridLayout()
        #self.layout.setSpacing(1)
        self.layout.setAlignment(Qt.AlignTop)

        



        self.figure = plt.figure()
        result_list = self.importResultList(folder)
        self.addWidgetstoLayout(result_list)
        self.button.clicked.connect(partial(self.addHistogramsToLayout,result_list, displ_wrt_point0))

        
        self.setLayout(self.layout)
        self.addHistogramsToLayout(result_list, displ_wrt_point0)

    def importResultList(self, results_folder):
        result_list=[]
        for folder in glob.glob(os.path.join(results_folder, "dvc_result_*")):
            result = RunResults(folder)
            result_list.append(result)
        return result_list

    def addWidgetstoLayout(self, result_list):
        widgetno=0

        if len(result_list) >=1:
            print(result_list)
            result = result_list[0] #These options were the same for all runs:

            self.results_details_label = QLabel(self)
            self.results_details_label.setText("Subvolume Geometry: {subvol_geom}\n\
Maximum Displacement: {disp_max}\n\
Degrees of Freedom: {num_srch_dof}\n\
Objective Function: {obj_function}\n\
Interpolation Type: {interp_type}\n\
Rigid Body Offset: {rigid_trans}".format(subvol_geom=result.subvol_geom, \
            disp_max=result.disp_max, num_srch_dof=str(result.num_srch_dof), obj_function=result.obj_function, \
            interp_type=result.interp_type, rigid_trans=str(result.rigid_trans)))
            self.layout.addWidget(self.results_details_label,widgetno,0,5,1)
            self.results_details_label.setAlignment(Qt.AlignTop)        
            widgetno+=1


        self.label = QLabel(self)
        self.label.setText("Select data: ")
        self.layout.addWidget(self.label,widgetno,1)

        self.data_label_widget = QComboBox(self)
        self.data_label_widget.addItems(result.data_label)
        self.layout.addWidget(self.data_label_widget,widgetno,2)  
        widgetno+=1

        self.label1 = QLabel(self)
        self.label1.setText("Select parameter: ")
        self.layout.addWidget(self.label1,widgetno,1)  
        
        self.param_list_widget = QComboBox(self)
        self.param_list = ["All","Sampling points in subvolume", "Subvolume size"]
        self.param_list_widget.addItems(self.param_list)
        self.layout.addWidget(self.param_list_widget,widgetno,2)
        widgetno+=1

        self.secondParamLabel = QLabel(self)
        self.secondParamLabel.setText("Subvolume size:")
        self.layout.addWidget(self.secondParamLabel,widgetno,1)
        
        self.secondParamCombo = QComboBox(self)
        self.secondParamList = [str(i) for i in self.subvol_sizes]
        self.secondParamCombo.addItems(self.secondParamList)
        self.layout.addWidget(self.secondParamCombo,widgetno,2)
        widgetno+=1

        self.param_list_widget.currentIndexChanged.connect(self.showSecondParam)
        self.secondParamLabel.hide()
        self.secondParamCombo.hide()

        self.button = QtWidgets.QPushButton("Plot Histograms")
        
        self.layout.addWidget(self.button,widgetno,2)
        widgetno+=1

        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.toolbar,widgetno,0,1,3)
        widgetno+=1
        self.layout.addWidget(self.canvas,widgetno,0,3,3)
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
        
    def addHistogramsToLayout(self, result_list, displ_wrt_point0):

        self.subvol_points=[]
        self.subvol_sizes=[]

        for result in result_list:
            if result.subvol_points not in self.subvol_points:
                self.subvol_points.append(result.subvol_points)
            if result.subvol_size not in self.subvol_sizes:
                self.subvol_sizes.append(result.subvol_size)
        self.subvol_points.sort()
        self.subvol_sizes.sort()


        self.figure.clear()

        param_index = self.param_list_widget.currentIndex()

        for result in result_list:




            if param_index == 1: # Points in subvolume is compared
                if result.subvol_size != float(self.secondParamCombo.currentText()):
                    pass

            elif param_index ==2:
                if result.subvol_points != float(self.secondParamCombo.currentText()):
                    pass

        no_points_list.sort()

        if param_index == 1 or param_index ==2:
            numRows = 1
            numColumns = len(result_list)

        no_points_list = []
        for result in result_list:
            if no_points not in no_points_list:
                    no_points_list.append(no_points)

        if param_index ==0:
            plotNum = 0
            
            for result in result_list:
                plotNum = plotNum + 1
                data, no_points, result_arrays = extractDataFromDispResultFile(result, displ_wrt_point0)
                subvol_size = result.subvol_size 
                subvol_points = result.subvol_points

                self.addSubplot(self.figure, int(numRows), int(numColumns), plotNum, result, result_arrays[self.data_label_widget.currentIndex()])
            
                
                if row ==1:
                    ax.set_title("Subvolume Size:" + str(result.subvol_size) )
                if column == 1:
                    text = str(result.subvol_points) 
                    ax.set_ylabel(text + " " + "Points in subvol")

            else:
                plotNum = plotNum + 1
                ax = self.figure.add_subplot(int(numRows), int(numColumns), int(plotNum))
    
                if param_index ==1:
                    text = str(result.subvol_points) 
                if param_index ==2:
                    text = str(result.subvol_size) 
                ax.set_ylabel(text + " " + self.param_list_widget.currentText())

            plot_data = [result_arrays_list[i][:,k] for k in range(5, result_arrays_list[i].shape[1])]

            self.addSubplot(self.figure, int(numRows), int(numColumns), plotNum, result, plot_data[self.data_label_widget.currentIndex()])
            
        self.figure.suptitle(self.data_label_widget.currentText(),size ="large")

        plt.tight_layout() # Provides proper spacing between figures
        plt.subplots_adjust(top=0.88) # Means heading doesn't overlap with subplot titles
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
