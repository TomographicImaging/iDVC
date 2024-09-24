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
    def __init__(self, parent, result_data_frame):
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
        self.result_data_frame = result_data_frame
        single_result = result_data_frame.iloc[0]['result']
        self.run_name = single_result.run_name
        self.data_label = single_result.data_label
        self.subvol_sizes = result_data_frame['subvol_size'].unique()
        self.subvol_points = result_data_frame['subvol_points'].unique()
        super().__init__(parent = parent)
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.layout.addLayout(self.grid_layout,0)
        self.addInfotoGridLayout(single_result)

        self.fig = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.fig)
        self.fig.clf()
        self.canvas.setMinimumSize(400, 400) #needed for scrollbar
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.toolbar)

        scroll_area_widget = NoBorderScrollArea(self.canvas)
        self.layout.addWidget(scroll_area_widget,1)  
        
    def addInfotoGridLayout(self, result):
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

    def selectRow(self, result_data_frame, selected_subvol_points, selected_subvol_size):
        df = result_data_frame
        if len(df) > 1: 
            df = df[(df['subvol_points'].astype(str) == selected_subvol_points) & (df['subvol_size'].astype(str) == selected_subvol_size)]
        elif len(df) == 1: 
            df = self.result_data_frame
        row = df.iloc[0]   
        return row         

    def addPlotsToLayout(self):
        pass

    def addWidgetsToGridLayout(self, result):
        print("parent grid")
        pass

    def addHistogramSubplot(self, plot, array, xlabel, mean, std): 
        '''plot the Gaussian curve, legend
        
        Returns
        -------
        matplotlib.pyplot
            A plot of the histogram
        """'''
        counts, bins = plot.hist(array, bins=20)[0:2]
        relative_counts = counts*100/ len(array)
        plot.cla()
        bin_widths = np.diff(bins)
        plot.bar(bins[:-1], relative_counts, width=bin_widths, align='edge')
        plot.set_ylabel("Relative frequency (% points in run)")
        plot.set_xlabel(xlabel)
        plot.axvline(mean, color='r', linestyle='--', label=f'mean = {mean:.3f}')
        plot.axvline(mean-std, color='g', linestyle='--', label=f'std = {std:.3f}')
        plot.axvline(mean+std, color='g', linestyle='--')

        x = np.linspace(min(array), max(array), 1000)
        gaussian = norm.pdf(x, mean, std) * (bins[1] - bins[0]) *100
        plot.plot(x, gaussian, 'b--', label='gaussian fit')

        plot.legend(loc='upper right')

    def addStatisticalAnalysisPlot(self, subplot, xlabel, ylabel, xpoints, ypoints, color):
        # Create the plot
        subplot.plot(xpoints, ypoints, color+'-')
        subplot.set_ylabel(ylabel)
        subplot.set_xlabel(xlabel)
        

class SingleRunResultsWidget(BaseResultsWidget):
    '''creates a dockable widget which will display results from a single run of the DVC code
    '''
    def __init__(self, parent, result_data_frame):
        '''
        Parameters
        ----------  
        results: RunResults
        displ_wrt_point0: bool
        '''
        super().__init__(parent, result_data_frame)
        if len(result_data_frame) > 1:
            self.addWidgetsToGridLayout()
        self.addPlotsToLayout()
        
    def addWidgetsToGridLayout(self):
        self.secondParamCombo_subvol_sizes = self.subvol_sizes
        self.secondParamCombo_subvol_points = self.subvol_points
        
        widgetno=1

        self.subvol_points_label = QLabel(self)
        self.subvol_points_label.setText("Select points in subvolume: ")
        self.grid_layout.addWidget(self.subvol_points_label,widgetno,1)  
        
        self.subvol_points_widget = QComboBox(self)
        self.subvol_points_widget.addItems(self.secondParamCombo_subvol_points)
        self.grid_layout.addWidget(self.subvol_points_widget,widgetno,2)
        widgetno+=1

        self.subvol_size_label = QLabel(self)
        self.subvol_size_label.setText("Select subvolume size: ")
        self.grid_layout.addWidget(self.subvol_size_label,widgetno,1)  
        
        self.subvol_size_widget = QComboBox(self)
        self.subvol_size_widget.addItems(self.secondParamCombo_subvol_sizes)
        self.grid_layout.addWidget(self.subvol_size_widget,widgetno,2)
        widgetno+=1

        self.button = QtWidgets.QPushButton("Plot histograms")
        self.button.clicked.connect(partial(self.addPlotsToLayout))
        self.grid_layout.addWidget(self.button,widgetno,2)
        widgetno+=1

    def addPlotsToLayout(self):
        '''
    
        Extracts the data from the disp file.
        Determines the number of graphs, rows and column to group them in.
        Hist makes an instogram with bins 20.
        
        Parameters
        ----------  
        result: RunResults
        displ_wrt_point0: bool
        '''
        self.fig.clf()
        numRows = 2
        numColumns = 2
        if len(self.result_data_frame) > 1:
            current_subvol_points = self.subvol_points_widget.currentText()
            current_subvol_size = self.subvol_size_widget.currentText()
            row = self.selectRow(self.result_data_frame, current_subvol_points, current_subvol_size)
        elif len(self.result_data_frame) == 1:
            row = self.selectRow(self.result_data_frame, None, None)
        result_arrays = row.result_arrays
        mean_array = row.mean_array
        std_array = row.std_array
        self.fig.suptitle(f"Run '{self.run_name}': points in subvolume {row.subvol_points}, subvolume size {row.subvol_size}",fontsize='xx-large')
        for plotNum, array in enumerate(result_arrays):
            data_label = self.data_label[plotNum]
            mean = mean_array[plotNum]
            std = std_array[plotNum]
            subplot = self.fig.add_subplot(numRows, numColumns, plotNum + 1)
            self.addHistogramSubplot(subplot, array, data_label, mean, std)
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])
        self.canvas.draw() 


class BulkRunResultsBaseWidget(BaseResultsWidget):
    '''creates a dockable widget which will display results from all runs in a bulk run
    '''
    def __init__(self, parent, result_data_frame, param_list, button_text = "Plot"):
        super().__init__(parent, result_data_frame)
        single_result = result_data_frame.iloc[0]['result']
        self.addWidgetstoGridLayout(single_result, param_list, button_text)
        self.addPlotsToLayout()

    def addWidgetstoGridLayout(self, result, param_list, button_text):
        print("second grid")
        widgetno=1

        self.label = QLabel(self)
        self.label.setText("Select result to plot: ")
        self.grid_layout.addWidget(self.label,widgetno,1)

        self.data_label_widget = QComboBox(self)
        self.data_label_widget.addItems(result.data_label)
        self.grid_layout.addWidget(self.data_label_widget,widgetno,2)  
        widgetno+=1

        self.label1 = QLabel(self)
        self.label1.setText("Select parameter to fix: ")
        self.grid_layout.addWidget(self.label1,widgetno,1)  
        
        self.param_list_widget = QComboBox(self)
        self.param_list_widget.addItems(param_list)
        
        self.grid_layout.addWidget(self.param_list_widget,widgetno,2)
        widgetno+=1

        self.secondParamLabel = QLabel(self)
        self.secondParamLabel.setText("Subvolume size:")
        self.grid_layout.addWidget(self.secondParamLabel,widgetno,1)
        
        self.secondParamCombo = QComboBox(self)
        self.secondParamCombo_subvol_sizes = self.subvol_sizes
        self.secondParamCombo_subvol_points = self.subvol_points
        self.secondParamCombo.addItems(self.secondParamCombo_subvol_sizes)
        self.grid_layout.addWidget(self.secondParamCombo,widgetno,2)
        widgetno+=1

        self.param_list_widget.currentIndexChanged.connect(self.showSecondParam)
        self.showSecondParam()

        self.button = QtWidgets.QPushButton(button_text)
        self.button.clicked.connect(partial(self.addPlotsToLayout))
        
        self.grid_layout.addWidget(self.button,widgetno,2)
        widgetno+=1

    def showSecondParam(self):
        index = self.param_list_widget.currentIndex()

        if index == 0:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Subvolume size:")
            self.secondParamCombo.clear()
            self.secondParamCombo.addItems([str(i) for i in self.secondParamCombo_subvol_sizes])

        elif index == 1:
            self.secondParamLabel.show()
            self.secondParamCombo.show()
            self.secondParamLabel.setText("Points in subvolume:")
            self.secondParamCombo.clear()
            self.secondParamCombo.addItems([str(i) for i in self.secondParamCombo_subvol_points])   
        
        elif index ==2:
            self.secondParamLabel.hide()
            self.secondParamCombo.hide()


class BulkRunResultsWidget(BulkRunResultsBaseWidget):
    def __init__(self, parent, result_data_frame):
        print("init2")
        param_list = ["Subvolume size", "Sampling points in subvolume", "None"]
        super().__init__(parent, result_data_frame, param_list, "Plot histograms")
        
    def addPlotsToLayout(self):
        """And stores mean and std"""#
        print("addplotb")
        self.fig.clf()
        param_index = self.param_list_widget.currentIndex()
        
        self.fig.suptitle(f"Bulk Run '{self.run_name}': {self.data_label_widget.currentText()}",fontsize='xx-large')
        
        numRows = len(self.subvol_sizes)
        numColumns = len(self.subvol_points)
        plotNum = 0
        
        for row in self.result_data_frame.itertuples():
            result = row.result

            if param_index == 0: 
                numRows = 1
                if result.subvol_size != float(self.secondParamCombo.currentText()):
                    continue
            elif param_index == 1:
                numColumns = 1
                if result.subvol_points != float(self.secondParamCombo.currentText()):
                    continue
            data_label = f"{self.data_label_widget.currentText()}"
            data_index = self.data_label_widget.currentIndex()
            mean = row.mean_array[data_index]
            std = row.std_array[data_index]
            plotNum = plotNum + 1
            subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
            self.addHistogramSubplot(subplot, row.result_arrays[data_index], data_label, mean, std)
            subplot.set_title(f"Points in subvolume = {result.subvol_points}, Subvolume size = {result.subvol_size}", fontsize='x-large', pad=20)
        self.fig.subplots_adjust(hspace=2,wspace=0.5)
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])
        self.canvas.draw()

class StatisticsResultsWidget(BulkRunResultsBaseWidget):
    def __init__(self, parent, result_data_frame):
        print("init 3")
        param_list = ["Subvolume size", "Sampling points in subvolume"]
        super().__init__(parent, result_data_frame, param_list)
        
        self.secondParamCombo_subvol_sizes = self.subvol_sizes
        self.secondParamCombo_subvol_points = self.subvol_points
        self.secondParamCombo_subvol_sizes = np.append(self.secondParamCombo_subvol_sizes, "All")
        self.secondParamCombo_subvol_points = np.append(self.secondParamCombo_subvol_points, "All")
        self.secondParamCombo.addItems(["All"])

    def addPlotsToLayout(self):
        print("addplots")
        self.fig.clf()
        df = self.result_data_frame
        param_index = self.param_list_widget.currentIndex()
        
        
        
        numColumns = 2
        plotNum = 0
        self.fig.suptitle(f"Bulk Run 'self.run_name': self.data_label_widget.currentText()",fontsize='xx-large')
        if param_index == 2: 
            pass
        else:
            if param_index == 0: 
                data_type = 'subvol_points'
                other_type ='subvol_size'
                numRows = len(self.subvol_sizes)
                for subvol_size in self.subvol_sizes:
                    if str(subvol_size) != self.secondParamCombo.currentText():
                        if self.secondParamCombo.currentText() == "All":
                            pass
                        else:
                            continue
                    data_label = f"{self.data_label_widget.currentText()}"
                    data_index = self.data_label_widget.currentIndex()
                    df_sz = df[(df[other_type] == subvol_size)]
                    xpoints = df_sz[data_type]

                    plotNum = plotNum + 1
                    subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
                    ypoints = df_sz['mean_array'].apply(lambda array: array[data_index])
                    self.addStatisticalAnalysisPlot(subplot, f"{data_type}", data_label +" mean",xpoints,ypoints, 'r')
                    subplot.set_title(f"{other_type}: {subvol_size}", fontsize='x-large', pad=20)
                    
                    plotNum = plotNum + 1
                    subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
                    ypoints = df_sz['std_array'].apply(lambda array: array[data_index])
                    self.addStatisticalAnalysisPlot(subplot, f"{data_type}", data_label + " std", xpoints,ypoints, 'g')
                    subplot.set_title(f"{other_type}: {subvol_size}", fontsize='x-large', pad=20)
                        
            #self.fig.subplots_adjust(hspace=0.5,wspace=0.5)
            elif param_index == 1: 
                data_type = 'subvol_size'
                other_type = 'subvol_points'
                numRows = len(self.subvol_points)
                for subvol_points in self.subvol_points:
                    if str(subvol_points) != self.secondParamCombo.currentText():
                        if self.secondParamCombo.currentText() == "All":
                            pass
                        else:
                            continue
                    data_label = f"{self.data_label_widget.currentText()}"
                    data_index = self.data_label_widget.currentIndex()
                    df_sz = df[(df[other_type] == subvol_points)]
                    xpoints = df_sz[data_type]

                    plotNum = plotNum + 1
                    subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
                    ypoints = df_sz['mean_array'].apply(lambda array: array[data_index])
                    self.addStatisticalAnalysisPlot(subplot, f"{data_type}", data_label +" mean",xpoints,ypoints, 'r')
                    subplot.set_title(f"{other_type}: {subvol_points}", fontsize='x-large', pad=20)
                    
                    plotNum = plotNum + 1
                    subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
                    ypoints = df_sz['std_array'].apply(lambda array: array[data_index])
                    self.addStatisticalAnalysisPlot(subplot, f"{data_type}", data_label + " std", xpoints,ypoints, 'g')
                    subplot.set_title(f"{other_type}: {subvol_points}", fontsize='x-large', pad=20)
        
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])        
        self.canvas.draw() 

        
class SaveObjectWindow(QtWidgets.QWidget):
    '''a window which will appear when saving a mask or pointcloud
    '''
        #self.copy_files_label = QLabel("Allow a copy of the image files to be stored: ")

    def __init__(self, parent, object_type, save_only):
        super().__init__(parent = parent)

        #print(save_only)
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
            shutil.copyfile(os.path.join(tempfile.tempdir, self.parent().mask_file), os.path.join(tempfile.tempdir, "Masks", filename))
            self.parent().mask_parameters['masksList'].addItem(filename)
            self.parent().mask_details[filename] = self.parent().mask_details['current']
            #print(self.parent().mask_details)

            self.parent().mask_parameters['loadButton'].setEnabled(True)
            self.parent().mask_parameters['masksList'].setEnabled(True)


            if not save_only:
                #print("Not save only")
                #would be better to move this elsewhere
                self.parent().mask_worker = Worker(self.parent().extendMask)
                self.parent().create_progress_window("Loading", "Loading Mask")
                self.parent().mask_worker.signals.progress.connect(self.parent().progress)
                self.parent().mask_worker.signals.finished.connect(self.parent().DisplayMask)
                self.parent().threadpool.start(self.parent().mask_worker)
                self.parent().progress_window.setValue(10)
            
        if self.object == "pointcloud":
            filename = self.textbox.text() + ".roi"
            shutil.copyfile(os.path.join(tempfile.tempdir, "latest_pointcloud.roi"), os.path.join(tempfile.tempdir, filename))

            self.parent().pointcloud_parameters['loadButton'].setEnabled(True)
            self.parent().pointcloud_parameters['pointcloudList'].setEnabled(True)
            self.parent().pointcloud_parameters['pointcloudList'].addItem(filename)
            self.parent().pointCloud_details[filename] = self.parent().pointCloud_details['latest_pointcloud.roi']
            #print(self.parent().pointCloud_details)
            #self.parent().createPointCloud()
            if not save_only:
                self.parent().PointCloudWorker("create")
            

        self.close()

    def quit(self):
        if self.object == "mask":
            #would be better to move this elsewhere
            self.parent().mask_worker = Worker(self.parent().extendMask)
            self.parent().create_progress_window("Loading", "Loading Mask")
            self.parent().mask_worker.signals.progress.connect(self.parent().progress)
            self.parent().mask_worker.signals.finished.connect(self.parent().DisplayMask)
            self.parent().threadpool.start(self.parent().mask_worker)
            self.parent().progress_window.setValue(10)

        if self.object == "pointcloud":
            self.parent().PointCloudWorker("create")
            #self.parent().createPointCloud()

        self.close()
