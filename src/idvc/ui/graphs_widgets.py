from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from functools import partial
from scipy.stats import norm
from eqt.ui.NoBorderScrollArea import NoBorderScrollArea


class BaseResultsWidget(QWidget):
    '''
    Creates a widget which can be set in a QDockWidget. 
    '''
    def __init__(self, parent, result_data_frame):
        '''
        Creates the attributes, including a list of fontsizes and linewidth for the plots, and 
        a list of colour-blind friendly colours taken from matplotlib
        (https://matplotlib.org/stable/users/explain/colors/colors.html#colors-def).
        Initialises the Qwidget, adds a vertical layout to it. 
        Adds a grid layout containing information about the results to the vertical layout.
        Creates a figure to be added in a canvas. The canvas is added in a scrool bar wherby
        its size must be set to a minimum. The figure size and dpi are fixed
        for consistency among screens. The canvas size policy must be set to expandable
        to occupy all of the available space in both directions.
        A toolbar and the scroll bar are added to the vertical layout.
        
        Parameters
        ----------  
        parent : QWidget
        result_data_frame : pandas.DataFrame
                Data frame containing the results, with columns: 'subvol_size', 'subvol_points',
                'result', 'result_arrays', 'mean_array', 'std_array'.
        '''
        self.result_data_frame = result_data_frame
        single_result = result_data_frame.iloc[0]['result']
        self.run_name = single_result.run_name
        self.data_label = single_result.data_label
        self.subvol_sizes = result_data_frame['subvol_size'].unique().astype(str)
        self.subvol_points = result_data_frame['subvol_points'].unique().astype(str)
        self.color_list = [
            '#1f77b4',  # Blue
            '#ff7f0e',  # Orange
            '#2ca02c',  # Green
            '#d62728',  # Red
            '#9467bd',  # Purple
            '#8c564b',  # Brown
            '#e377c2',  # Pink
            '#7f7f7f',  # Gray
            '#bcbd22',  # Olive
            '#17becf'   # Cyan
            ]
        self.linewidth = 3 #pixels?
        self.fontsizes = {'figure_title':18, 'subplot_title':14, 'label':10}
        super().__init__(parent = parent)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.grid_layout = QGridLayout()
        self.grid_layout.setAlignment(Qt.AlignTop)
        self.layout.addLayout(self.grid_layout,0)
        self.addInfotoGridLayout(single_result)
        self.figsize = (8, 4)  # Size in inches
        self.dpi = 100
        self.fig = Figure(figsize=self.figsize, dpi=self.dpi)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setMinimumSize(800, 400) #needed for scrollbar
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.toolbar)
        scroll_area_widget = NoBorderScrollArea(self.canvas)
        self.layout.addWidget(scroll_area_widget,1)  
        
    def addInfotoGridLayout(self, result):
        '''Adds a QLabel widget containing information about the results to the grid layout.'''
        self.results_details_label = QLabel(self)
        self.results_details_label.setText("Subvolume Geometry: {subvol_geom}\n\
Maximum Displacement: {disp_max}\n\
Degrees of Freedom: {num_srch_dof}\n\
Objective Function: {obj_function}\n\
Interpolation Type: {interp_type}\n\
Rigid Body Offset: {rigid_trans}".format(subvol_geom=result.subvol_geom, \
        disp_max=result.disp_max, num_srch_dof=str(result.num_srch_dof), obj_function=result.obj_function, \
        interp_type=result.interp_type, rigid_trans=str(result.rigid_trans)))
        self.grid_layout.addWidget(self.results_details_label,0,0,5,1)
        self.results_details_label.setAlignment(Qt.AlignTop)        

    def addSubplotsToFigure(self):
        '''To be defined in the child classes.'''
        pass

    def addWidgetsToGridLayout(self):
        '''To be defined in the child classes.'''
        pass

    def _selectRow(self, result_data_frame, selected_subvol_points, selected_subvol_size):
        '''Given a dataframe, returns the whole row whose 'subvol_points' and 'subvol_size' columns
        are associated with the selected values.
        
        Parameters
        ----------
        result_data_frame : pandas.DataFrame
                Data frame containing the results. Includes the 'subvol_points' and 'subvol_size' columns.
        selected_subvol_points : int
                Selected points in subvolume.
        selected_subvol_size : int
                Selected subvolume size.
        '''
        df = result_data_frame
        if len(df) > 1: 
            df = df[(df['subvol_points'] == selected_subvol_points) & (df['subvol_size'] == selected_subvol_size)]
        elif len(df) == 1: 
            df = self.result_data_frame
        row = df.iloc[0]   
        return row     

    def _selectOneParameter(self, result_data_frame, parameter, selected_parameter):
        '''Given a dataframe, returns a filtered dataframe whose rows are associated with
        the selected value of a parameter.

        Parameters
        ----------
        result_data_frame : pandas.DataFrame
                Data frame containing the results. Includes the 'subvol_points' and 'subvol_size' columns.
        parameter : str
                'subvol_points' or 'subvol_size'
        selected_parameter : int
                Selected value of the parameter.
        '''
        df = result_data_frame
        df = df[(df[parameter] == selected_parameter)]  
        return df   

    def _addHistogramSubplot(self, subplot, array, xlabel, mean, std): 
        '''Given an array, calculates the relative counts by using the matplotlib
        histogram functionality. It clears the plot and plots the relative frequency histogram
        as a bar plot. Sets the x an y labels. Adds the mean and std values as vertical lines. 
        Plots the gaussian fit. Adds the legend to the plot.

        Parameters
        ----------
        subplot : matplotlib subplot of a figure
        array : numpyarray
        xlabel :  str
        mean : float
        std : float
        '''
        counts, bins = subplot.hist(array, bins=20)[0:2]
        relative_counts = counts*100/ len(array)
        subplot.cla()
        bin_widths = np.diff(bins)
        subplot.bar(bins[:-1], relative_counts, width=bin_widths, align='edge',color='lightgrey')
        subplot.set_ylabel("Relative frequency (% points in run)", fontsize=self.fontsizes['label'])
        subplot.set_xlabel(xlabel, fontsize=self.fontsizes['label'])
        subplot.axvline(mean, color=self.color_list[0], linestyle='--', linewidth=self.linewidth, label=f'mean = {mean:.3f}')
        subplot.axvline(mean-std, color=self.color_list[1], linestyle='--', linewidth=self.linewidth, label=f'std = {std:.3f}')
        subplot.axvline(mean+std, color=self.color_list[1], linestyle='--', linewidth=self.linewidth)
        x = np.linspace(min(array), max(array), 1000)
        gaussian = norm.pdf(x, mean, std) * (bins[1] - bins[0]) *100
        subplot.plot(x, gaussian, self.color_list[2],linestyle='--', linewidth=self.linewidth, label='gaussian fit')
        subplot.legend(loc='upper right')

    def _addStatisticalAnalysisPlot(self, subplot, xlabel, ylabel, xpoints, ypoints, color, label, linestyle):
        "Draws a line plot in 'subplot'. Adds labels and sets user-defined properties."
        subplot.plot(xpoints, ypoints, color=color, linestyle=linestyle, linewidth=self.linewidth, label=label)
        subplot.set_ylabel(ylabel + " (pixels)", fontsize=self.fontsizes['label'])
        subplot.set_xlabel(xlabel, fontsize=self.fontsizes['label'])


class SingleRunResultsWidget(BaseResultsWidget):
    '''
    Creates a widget which can be set in a QDockWidget.
    This will display results from a single run of the DVC code.
    '''
    def __init__(self, parent, result_data_frame):
        '''
        Initialises the SingleRunResultsWidget.

        Parameters
        ----------
        parent : QWidget
            The parent widget.
        result_data_frame : pandas.DataFrame
                Dataframe containing the result data.
        '''
        super().__init__(parent, result_data_frame)
        if len(result_data_frame) > 1:
            self.addWidgetsToGridLayout()
        self.addSubplotsToFigure()
        
    def addWidgetsToGridLayout(self):
        """
        Initialises and adds the following widgets to the grid layout:
        - a QLabel and QComboBox for selecting points in a subvolume.
        - a QLabel and QComboBox for selecting the size of a subvolume.
        - a QPushButton for plotting histograms, which is connected to the `addSubplotsToFigure` method.
        """        
        widgetno=1

        self.subvol_points_label = QLabel(self)
        self.subvol_points_label.setText("Select points in subvolume: ")
        self.grid_layout.addWidget(self.subvol_points_label,widgetno,1)  
        
        self.subvol_points_widget = QComboBox(self)
        self.subvol_points_widget.addItems(self.subvol_points)
        self.subvol_points_widget.setCurrentIndex(0)
        self.grid_layout.addWidget(self.subvol_points_widget,widgetno,2)
        widgetno+=1

        self.subvol_size_label = QLabel(self)
        self.subvol_size_label.setText("Select subvolume size: ")
        self.grid_layout.addWidget(self.subvol_size_label,widgetno,1)  
        
        self.subvol_size_widget = QComboBox(self)
        self.subvol_size_widget.addItems(self.subvol_sizes)
        self.subvol_size_widget.setCurrentIndex(0)
        self.grid_layout.addWidget(self.subvol_size_widget,widgetno,2)
        widgetno+=1

        self.button = QPushButton("Plot histograms")
        self.button.clicked.connect(partial(self.addSubplotsToFigure))
        self.grid_layout.addWidget(self.button,widgetno,2)
        widgetno+=1

    def addSubplotsToFigure(self):
        '''
        Clears the current figure. Determines the number of rows and
        columns for the figure layout. Selects the appropriate row
        from the result dataframe based on the user selected subvolume points and size.
        Extracts result arrays, mean array, and standard deviation array from the selected row.
        Sets the figure title with details about the run and subvolume.
        Iterates over the result arrays to create histograms and adds them as subplots.
        Adjusts the figure layout and redraws the canvas.
        
        Attributes
        ----------
        result_data_frame : DataFrame
            Data frame containing the results.
        subvol_points_widget : QWidget
            Widget for selecting subvolume points.
        subvol_size_widget : QWidget
            Widget for selecting subvolume size.
        fig : Figure
            Matplotlib figure object.
        run_name : str
            Name of the current run.
        data_label : list
            List of labels for the result data.
        fontsizes : dict
            Dictionary containing font sizes for various elements.
        canvas : FigureCanvas
            Matplotlib canvas object for rendering the figure.
        '''
        self.fig.clf()
        numRows = 2
        numColumns = 2
        if len(self.result_data_frame) > 1:
            current_subvol_points = int(self.subvol_points_widget.currentText())
            current_subvol_size = int(self.subvol_size_widget.currentText())
            row = self._selectRow(self.result_data_frame, current_subvol_points, current_subvol_size)
        elif len(self.result_data_frame) == 1:
            row = self._selectRow(self.result_data_frame, None, None)
        result_arrays = row.result_arrays
        mean_array = row.mean_array
        std_array = row.std_array
        self.fig.suptitle(f"Run '{self.run_name}': points in subvolume {row.subvol_points}, subvolume size {row.subvol_size}",fontsize=self.fontsizes['figure_title'])
        for plotNum, array in enumerate(result_arrays):
            x_label = self.data_label[plotNum]
            if 0<plotNum<4:
                x_label = x_label + " (pixels)"   
            mean = mean_array[plotNum]
            std = std_array[plotNum]
            subplot = self.fig.add_subplot(numRows, numColumns, plotNum + 1)
            self._addHistogramSubplot(subplot, array, x_label, mean, std)
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])
        self.canvas.draw() 


class BulkRunResultsBaseWidget(BaseResultsWidget):
    '''
    Creates a baseclass widget with common functionality for displaying results from several results in a bulk run.
    '''
    def __init__(self, parent, result_data_frame, param_list, button_text = "Plot"):
        '''
        Initialises the BulkRunResultsBaseWidget.

        Parameters
        ----------
        parent : QWidget
            The parent widget.
        result_data_frame : pandas.DataFrame
                Data frame containing the results.
        param_list : list of str
            The text items for the QComboBox.
        button_text : str, optional
            The text to display on the QPushButton.
        '''
        super().__init__(parent, result_data_frame)
        self.addWidgetstoGridLayout(param_list, button_text)
        self.addSubplotsToFigure()
        
    def addWidgetstoGridLayout(self, param_list, button_text):
        """
        Adds the following widgets to the central and right column of the grid layout:
        - a QLabel and a QComboBox for selecting the result to plot.
        - a QLabel and a QComboBox for selecting the parameter to fix.
        - a QLabel and QComboBox for selecting points in subvolume.
        - a QLabel and QComboBox for selecting the size of the subvolume.
        - a QPushButton for plotting histograms, which is connected to the `addSubplotsToFigure` method.
        Hides the subvolume points widget and label by default.

        Parameters
        ----------
        param_list : list of str
                A list of parameters to populate the parameter_fix_widget.
        button_text : str
                The text to display on the button.
        """
        widgetno=0

        self.data_label_label = QLabel(self)
        self.data_label_label.setText("Select result to plot: ")
        self.grid_layout.addWidget(self.data_label_label,widgetno,1)

        self.data_label_widget = QComboBox(self)
        self.data_label_widget.addItems(self.data_label)
        self.grid_layout.addWidget(self.data_label_widget,widgetno,2)  
        
        widgetno+=1

        self.parameter_fix_label = QLabel(self)
        self.parameter_fix_label.setText("Select parameter to fix: ")
        self.grid_layout.addWidget(self.parameter_fix_label,widgetno,1)  
        
        self.parameter_fix_widget = QComboBox(self)
        self.parameter_fix_widget.addItems(param_list)
        self.grid_layout.addWidget(self.parameter_fix_widget,widgetno,2)
        
        widgetno+=1

        self.subvol_size_value_label = QLabel(self)
        self.subvol_size_value_label.setText("Subvolume size:")
        self.grid_layout.addWidget(self.subvol_size_value_label,widgetno,1)
        
        self.subvol_size_value_widget = QComboBox(self)
        self.subvol_size_value_widget.addItems(self.subvol_sizes)
        self.subvol_size_value_widget.setCurrentIndex(0)
        self.grid_layout.addWidget(self.subvol_size_value_widget,widgetno,2)

        self.subvol_points_value_label = QLabel(self)
        self.subvol_points_value_label.setText("Points in subvolume:")
        self.grid_layout.addWidget(self.subvol_points_value_label,widgetno,1)
        
        self.subvol_points_value_widget = QComboBox(self)
        self.subvol_points_value_widget.addItems(self.subvol_points)
        self.subvol_points_value_widget.setCurrentIndex(0)
        self.grid_layout.addWidget(self.subvol_points_value_widget,widgetno,2)
        
        self.showParameterValues()
        self.parameter_fix_widget.currentIndexChanged.connect(lambda: self.showParameterValues())

        widgetno+=1
        self.button = QPushButton(button_text)
        self.button.clicked.connect(partial(self.addSubplotsToFigure))
        self.grid_layout.addWidget(self.button,widgetno,2)

        self.parameter_value_widget_list = [self.subvol_size_value_widget, self.subvol_points_value_widget]

    def showParameterValues(self):
        """
        Adjusts the visibility of widgets based on the current index 
        of the parameter-to-fix widget.

        The widgets are removed and readded to maintain the spacing of the layout.
        """
        layout_row = 2
        index = self.parameter_fix_widget.currentIndex()

        if index == 0:
            self.subvol_points_value_label.hide()
            self.subvol_points_value_widget.hide()
            self.grid_layout.removeWidget(self.subvol_points_value_label)
            self.grid_layout.removeWidget(self.subvol_points_value_widget)
            self.grid_layout.addWidget(self.subvol_size_value_label, layout_row, 1)
            self.grid_layout.addWidget(self.subvol_size_value_widget, layout_row, 2)
            self.subvol_size_value_label.show()
            self.subvol_size_value_widget.show()

        elif index == 1:
            self.grid_layout.addWidget(self.subvol_points_value_label, layout_row,1)
            self.grid_layout.addWidget(self.subvol_points_value_widget, layout_row,2)
            self.subvol_points_value_label.show()
            self.subvol_points_value_widget.show() 
            self.subvol_size_value_label.hide()
            self.subvol_size_value_widget.hide()
            self.grid_layout.removeWidget(self.subvol_size_value_label)
            self.grid_layout.removeWidget(self.subvol_size_value_widget)
        
        elif index ==2:
            self.subvol_points_value_label.hide()
            self.subvol_points_value_widget.hide() 
            self.subvol_size_value_label.hide()
            self.subvol_size_value_widget.hide()
        

class BulkRunResultsWidget(BulkRunResultsBaseWidget):
    '''
    Creates a class widget to plot histograms from several results in a bulk run.
    '''
    def __init__(self, parent, result_data_frame):
        '''
        Initialises the class. Includes the option 'None' to
        the parameter list and tailors the text of the button.
        '''
        param_list = ["Subvolume size", "Sampling points in subvolume", "None"]
        super().__init__(parent, result_data_frame, param_list, "Plot histograms")
        
    def addSubplotsToFigure(self):
        '''
        Clears the current figure, retrieves the selected data label and parameter index.
        Constructs the plot title based on the parameter index. 
        It iterates over the result data frame to create subplots for each result,
        adjusting the figure and subplot titles accordingly. The canvas size is adjusted
        based on the parameter index and ensures that the subplots are properly spaced and titled.

        The method handles three cases for the parameter index:
        - 0: Plots the subplots for all values of the number of points in the subvolume
            and fixed value of the subvolume size.
        - 1: Plots the subplots for all values of the the subvolume size and fixed number of points in the subvolume.
        - 2: Plots the subplots for all values of the subvolume size and number of points in the subvolume.
        
        Adjusts the figure layout and redraws the canvas.
        
        Attributes
        ----------
            self.fig : matplotlib.figure.Figure
                The figure object to which subplots are added.
            self.data_label_widget : QComboBox)
                Widget to select the data label.
            self.parameter_fix_widget : QComboBox
                Widget to select the parameter to fix.
            self.parameter_value_widget_list : list of QComboBox
                List of widgets to select parameter values.
            self.run_name : str
                Name of the current run.
            self.fontsizes : dict
                Dictionary containing font sizes for various plot elements.
            self.subvol_sizes : list
                List of subvolume sizes.
            self.subvol_points : list
                List of points in subvolumes.
            self.result_data_frame : pandas.DataFrame
                Data frame containing the results.
            self.canvas : matplotlib.backends.backend_qt5agg.FigureCanvasQTAgg
                Canvas to draw the figure on.
        '''
        self.fig.clf()
        data_label = self.data_label_widget.currentText()
        param_index = self.parameter_fix_widget.currentIndex()

        if param_index == 2:
            plot_title = f"Bulk run '{self.run_name}': {data_label.lower()} distribution for all parameters"
        else:
            value_widget = self.parameter_value_widget_list[param_index]
            parameter_value = int(value_widget.currentText())
            param_text = self.parameter_fix_widget.currentText().lower()
            plot_title = f"Bulk run '{self.run_name}': {data_label.lower()} distribution for {param_text} = {parameter_value}"
        self.fig.suptitle(plot_title,fontsize=self.fontsizes['figure_title'])
        
        numRows = len(self.subvol_sizes)
        numColumns = len(self.subvol_points)
        plotNum = 0
        
        for row in self.result_data_frame.itertuples():
            result = row.result
            
            if param_index == 0: 
                numRows = 1
                self.canvas.setMinimumSize(300*numColumns, 400)
                subplot_title = f"Points in subvolume = {result.subvol_points}"
                if result.subvol_size != parameter_value:
                    continue
            elif param_index == 1:
                numColumns = 1
                self.canvas.setMinimumSize(800, 400*numRows) #needed for scrollbar
                subplot_title = f"Subvolume size = {result.subvol_size}"
                if result.subvol_points != parameter_value:
                    continue
            elif param_index == 2:
                subplot_title = f"Points in subvolume = {result.subvol_points}, subvolume size = {result.subvol_size}"
                self.canvas.setMinimumSize(300*numColumns, 400*numRows)
            data_index = self.data_label_widget.currentIndex()
            x_label = data_label
            if 0<data_index<4:
                x_label = x_label + " (pixels)"  
            mean = row.mean_array[data_index]
            std = row.std_array[data_index]
            plotNum = plotNum + 1
            subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
            self._addHistogramSubplot(subplot, row.result_arrays[data_index], x_label, mean, std)
            subplot.set_title(subplot_title, pad=20, fontsize=self.fontsizes['subplot_title'])
            self.fig.subplots_adjust(hspace=2,wspace=0.5)

        self.fig.tight_layout(rect=[0, 0, 1, 0.95])
        self.canvas.draw()


class StatisticsResultsWidget(BulkRunResultsBaseWidget):
    '''
    Creates a class widget to plot statistical analysis from several results in a bulk run.
    '''
    def __init__(self, parent, result_data_frame):
        '''
        Defines the parameter list and linestyles. 
        Initialises the class. Adds the option `All` to the
        subvolume size and subvolume points widgets.
        '''
        param_list = ["Subvolume size", "Sampling points in subvolume"]
        self.linestyles = ['-','--','-.', ':']
        super().__init__(parent, result_data_frame, param_list)
        self.subvol_points_value_widget.addItem("All")
        self.subvol_size_value_widget.addItem("All")

    def addWidgetstoGridLayout(self, param_list, button_text):
        """
        Redefines the superclass method to add widgets to the grid layout.
        Adds "All" to the data label widget.
        Inserts a checkbox labeled "Collapse plots" into the grid layout and hides it.
        Moves the button one row down in the grid layout.
        Connects various signals to the `hideShowAllItemInValueWidget` and
        `hideShowCollapseCheckbox` methods.

        Parameters
        ----------
        param_list : list of str
                A list of parameters to populate the parameter_fix_widget.
        button_text : str
                The text to display on the button.
        """
        super().addWidgetstoGridLayout(param_list, button_text)
        self.data_label_widget.addItem("All")
        widgetno = self.grid_layout.rowCount() - 2
        self.collapse_checkbox = QCheckBox("Collapse plots", self)
        self.collapse_checkbox.setChecked(False)
        self.grid_layout.addWidget(self.collapse_checkbox,widgetno,2)
        self.grid_layout.addWidget(self.button,widgetno+1,2)
        self.data_label_widget.currentIndexChanged.connect(lambda: self.hideShowAllItemInValueWidget())
        self.subvol_points_value_widget.currentIndexChanged.connect(lambda: self.hideShowCollapseCheckbox())
        self.subvol_size_value_widget.currentIndexChanged.connect(lambda: self.hideShowCollapseCheckbox())
        self.parameter_fix_widget.currentIndexChanged.connect(lambda: self.hideShowCollapseCheckbox())
        self.collapse_checkbox.hide()

    def _meanStdPlots(self, subplot_mean, subplot_std, result_data_frame, data_index, data_label, parameter, selected_parameter, x_parameter, x_label, color_mean='#1f77b4', color_std='#ff7f0e', label_mean="Mean", label_std="Std", linestyle='-'):
        """
        Plots mean and standard deviation data on given subplots.

        Parameters
        ----------
        subplot_mean : matplotlib subplot of a figure
            Subplot for mean values.
        subplot_std : matplotlib subplot of a figure
            Subplot for std values.
        result_data_frame : pandas.DataFrame
                Data frame containing the results.
        data_index : int
            Index of the data.
        data_label : str
            Label for the data.
        parameter : str
            Parameter to filter the data frame.
        selected_parameter : int
            Value of the parameter to filter.
        x_parameter : str
            Column name for x-axis values.
        x_label : str
            Label for the x-axis.
        color_mean : str, optional
            Color for mean plot line.
        color_std : str, optional
            Color for std plot line.
        label_mean : str, optional
            Label for mean plot line.
        label_std : str, optional
            Label for std plot line.
        linestyle : str, optional
            Line style for plot lines.
        """
        df_sz = self._selectOneParameter(result_data_frame, parameter, selected_parameter)
        xpoints = df_sz[x_parameter]
        ypoints = df_sz['mean_array'].apply(lambda array: array[data_index])
        self._addStatisticalAnalysisPlot(subplot_mean, x_label, data_label+"mean",xpoints,ypoints, color_mean, label_mean, linestyle)       
        ypoints = df_sz['std_array'].apply(lambda array: array[data_index])
        self._addStatisticalAnalysisPlot(subplot_std, x_label, data_label+"std", xpoints,ypoints, color_std, label_std, linestyle)

    def hideShowAllItemInValueWidget(self):
        """
        Toggles the visibility of the "All" item in the subvolume-size-value widget and
        subvolume-points-value widget based on the current text of the data-label widget.
        """
        index_ss = self.subvol_size_value_widget.findText("All")
        index_sp = self.subvol_points_value_widget.findText("All")
        if self.data_label_widget.currentText() == "All":
            self.subvol_size_value_widget.removeItem(index_ss)
            self.subvol_points_value_widget.removeItem(index_sp)
        else:
            if index_ss == -1:
                self.subvol_size_value_widget.addItem("All")
            if index_sp == -1:
                self.subvol_points_value_widget.addItem("All")

    def hideShowCollapseCheckbox(self):
        """
        Shows or hides the collapse checkbox based on the
        selection of the fixed parameter.
        """
        param_index = self.parameter_fix_widget.currentIndex()
        if param_index == 0: 
            widget = self.subvol_size_value_widget
        elif param_index == 1: 
            widget = self.subvol_points_value_widget 
        if widget.currentText() == "All":
            self.collapse_checkbox.show()
        else:
            self.collapse_checkbox.hide()


    def addSubplotsToFigure(self):
        """
        Clears the figure and sets a minimum size for the canvas. 
        Generates subplots for mean and standard deviation of the selected data
        and parameter values. It supports different configurations based on user selections.
        The subplots are arranged in a grid layout, where the figure title and subplot titles
        are dynamically generated based on the selected options. The figure layout is adjusted
        and the canvas is redrawn.

        The method handles the following cases:
        - Plotting all data labels with fixed parameter values.
        - Plotting a specific data label with fixed parameter values.
        - Plotting a specific data label with all parameter values. An option to
            collapse the subplots in the same row is available.
        """
        self.fig.clf()
        self.canvas.setMinimumSize(800, 400)
        df = self.result_data_frame

        param_index = self.parameter_fix_widget.currentIndex()
        param_text = self.parameter_fix_widget.currentText().lower()
        x_label = self.parameter_fix_widget.itemText(1 - param_index)
        value_widget = self.parameter_value_widget_list[param_index]

        self.value_list = [self.subvol_sizes, self.subvol_points]
        label_list = ['subvol_size','subvol_points']

        numColumns = 2
        plotNum = 1
        if self.data_label_widget.currentText() == "All":
            for data_index in range(4):
                data_label = f"{self.data_label_widget.itemText(data_index)}"
                numRows = 2
                numColumns = 2
                subplot = self.fig.add_subplot(numRows, numColumns, plotNum)
                subplot.set_title(f"{data_label}", pad=20, fontsize=self.fontsizes['subplot_title']) 
                value = int(value_widget.currentText())
                plot_title = f"Bulk run '{self.run_name}': mean and standard deviation for {param_text} = {value}"
                twin = subplot.twinx()
                self._meanStdPlots(subplot, twin, df, data_index, "", label_list[param_index], value, label_list[1-param_index], x_label)
                lines1, labels1 = subplot.get_legend_handles_labels()
                lines2, labels2 = twin.get_legend_handles_labels()
                lines = lines1 + lines2
                labels = labels1 + labels2
                subplot.legend(lines, labels, loc='upper right')
                plotNum += 1
        else:
            data_index = self.data_label_widget.currentIndex()
            data_label = f"{self.data_label_widget.currentText()}"
            
            if value_widget.currentText() == "All":
                plot_title = f"Bulk run '{self.run_name}': {data_label.lower()} mean and standard deviation for fixed {param_text}"
                if not self.collapse_checkbox.isChecked():
                    numRows = len(self.value_list[param_index])
                    self.canvas.setMinimumSize(800, 400*numRows)
                    for value in self.value_list[param_index]:
                        subplot_mean = self.fig.add_subplot(numRows, numColumns, plotNum)
                        subplot_mean.set_title(f"Mean for {param_text} = {value}", fontsize=self.fontsizes['subplot_title'], pad=20) 
                        subplot_std = self.fig.add_subplot(numRows, numColumns, plotNum +1)
                        subplot_std.set_title(f"Standard deviation for {param_text} = {value}", fontsize=self.fontsizes['subplot_title'], pad=20)
                        label = f"{param_text} = {value}"
                        self._meanStdPlots(subplot_mean, subplot_std, df, data_index, data_label+" ", label_list[param_index], int(value), label_list[1-param_index], x_label, label_mean = label, label_std = label)
                        plotNum = plotNum + 2
                elif self.collapse_checkbox.isChecked():
                    numRows = 1
                    subplot_mean = self.fig.add_subplot(numRows, numColumns, plotNum)
                    subplot_mean.set_title("Mean", fontsize=self.fontsizes['subplot_title'], pad=20) 
                    subplot_std = self.fig.add_subplot(numRows, numColumns, plotNum +1)
                    subplot_std.set_title("Standard deviation", fontsize=self.fontsizes['subplot_title'], pad=20)

                    for i, value in enumerate(self.value_list[param_index]):
                        linestyle = self.linestyles[i // len(self.color_list) % len(self.linestyles)]
                        if len(self.result_data_frame) <= len(self.color_list) * len(self.linestyles):
                            color = self.color_list[i % len(self.color_list)]
                        else:
                            color = np.random.rand(3,)
                        label = f"{param_text} = {value}"
                        self._meanStdPlots(subplot_mean, subplot_std, df, data_index, data_label+" ", label_list[param_index], int(value), label_list[1-param_index], x_label, color, color, label, label, linestyle = linestyle)
                    subplot_mean.legend(loc='upper right')
                    subplot_std.legend(loc='upper right')
            else:
                numRows = 1
                subplot_mean = self.fig.add_subplot(numRows, numColumns, plotNum)
                subplot_mean.set_title("Mean", fontsize=self.fontsizes['subplot_title'], pad=20) 
                subplot_std = self.fig.add_subplot(numRows, numColumns, plotNum+1)
                subplot_std.set_title("Standard deviation", fontsize=self.fontsizes['subplot_title'], pad=20)
                value = int(value_widget.currentText())
                plot_title = f"Bulk run '{self.run_name}': {data_label.lower()} mean and standard deviation for {param_text} = {value}"
                self._meanStdPlots(subplot_mean, subplot_std, df, data_index, data_label+" ", label_list[param_index], value, label_list[1-param_index], x_label)
            
        self.fig.suptitle(plot_title,fontsize=self.fontsizes['figure_title'])
        self.fig.tight_layout(rect=[0, 0, 1, 0.95])        
        self.canvas.draw() 


