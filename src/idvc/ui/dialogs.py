import PySide2
from PySide2.QtWidgets import *
from PySide2.QtCore import *
from PySide2.QtGui import *
import multiprocessing
import vtk

from eqt.ui.FormDialog import FormDialog


class SettingsWindow(FormDialog):

    def __init__(self, parent, title="Settings"):

        super(SettingsWindow, self).__init__(parent, title)

        self.parent = parent


        self.fontsize_label = QLabel("Fontsize: ")
        self.fontsize_widget = QSpinBox()
        self.fontsize_widget.setMaximum(25)
        self.fontsize_widget.setMinimum(5)
        self.fontsize_widget.setSingleStep(1)
        self.fontsize_widget.setValue(12)
        self.addWidget(self.fontsize_widget, self.fontsize_label, 'fontsize')
        self.dark_checkbox = QCheckBox("Dark Mode")
        # populate from settings
        if self.parent.settings.value("dark_mode") is not None:
            if self.parent.settings.value("dark_mode") == "true":
                self.dark_checkbox.setChecked(True)
            else:
                self.dark_checkbox.setChecked(False)
        else:
            self.dark_checkbox.setChecked(True)

        self.addWidget(self.dark_checkbox, '', 'darkmode')

        self.copy_files_checkbox = QCheckBox("Allow a copy of the image files to be stored. ")
        self.addWidget(self.copy_files_checkbox, '', 'copy_file_checkbox')
        self.vis_size_label = QLabel("Maximum downsampled image size (GB): ")
        self.vis_size_entry = QDoubleSpinBox()
        self.vis_size_entry.setMaximum(64.0)
        self.vis_size_entry.setMinimum(0.01)
        self.vis_size_entry.setSingleStep(0.01)
        # populate from settings
        if self.parent.settings.value("vis_size") is not None:
            self.vis_size_entry.setValue(float(self.parent.settings.value("vis_size")))
        else:
            self.vis_size_entry.setValue(1.0)

        self.addWidget(self.vis_size_entry, self.vis_size_label, 'vis_size')

        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Raised)
        self.adv_settings_label = QLabel("Advanced")
        
        self.addSpanningWidget(separator,'separator')
        self.addSpanningWidget(self.adv_settings_label, 'advanced_label')


        self.gpu_label = QLabel("Please set the size of your GPU memory.")
        self.gpu_size_label = QLabel("GPU Memory (GB): ")
        self.gpu_size_entry = QDoubleSpinBox()

        self.addSpanningWidget(self.gpu_label, 'gpu_label')
        self.addWidget(self.gpu_size_entry, self.gpu_size_label, 'gpu_size')

        # populate from settings
        if self.parent.settings.value("gpu_size") is not None:
            self.gpu_size_entry.setValue(float(self.parent.settings.value("gpu_size")))
        else:
            self.gpu_size_entry.setValue(1.0)

        self.gpu_size_entry.setMaximum(64.0)
        self.gpu_size_entry.setMinimum(0.00)
        self.gpu_size_entry.setSingleStep(0.01)


        self.gpu_checkbox = QCheckBox("Use GPU for volume render. (Recommended) ")
        self.gpu_checkbox.setChecked(True) #gpu is default
        if self.parent.settings.value("volume_mapper") == "cpu":
            self.gpu_checkbox.setChecked(False)
        if hasattr(self.parent, 'copy_files'):
            self.copy_files_checkbox.setChecked(self.parent.copy_files)
        self.addWidget(self.gpu_checkbox, '', 'gpu_checkbox')


        self.omp_threads_entry = QSpinBox(self)
        # default OMP_THREADS based on the number of cores available
        n_cores = int(multiprocessing.cpu_count())
        if n_cores > 16:
            omp_threads = 16
        elif n_cores > 8:
            omp_threads = 8
        elif n_cores > 4:
            omp_threads = 4
        elif n_cores > 2:
            omp_threads = 2
        else:
            omp_threads = 1
        
        self.omp_threads_entry.setValue(omp_threads)
        self.omp_threads_entry.setRange(1, n_cores)
        self.omp_threads_entry.setSingleStep(1)
        self.omp_threads_label = QLabel("OMP Threads: ")

        self.addWidget(self.omp_threads_entry, self.omp_threads_label, 'use_omp')


    def onOk(self):
        font = PySide2.QtGui.QFont("Arial", self.fontsize_widget.value()) 
        PySide2.QtWidgets.QApplication.setFont(font)
        #self.parent.settings.setValue("settings_chosen", 1)
        if self.dark_checkbox.isChecked():
            self.parent.settings.setValue("dark_mode", True)
        else:
            self.parent.settings.setValue("dark_mode", False)
        self.parent.SetAppStyle()

        if self.copy_files_checkbox.isChecked():
            self.parent.copy_files = 1 # save for this session
            self.parent.settings.setValue("copy_files", 1) #save for next time we open app
        else:
            self.parent.copy_files = 0
            self.parent.settings.setValue("copy_files", 0)

        if self.gpu_checkbox.isChecked():
            self.parent.settings.setValue("volume_mapper", "gpu")
            self.parent.vis_widget_3D.volume_mapper = vtk.vtkSmartVolumeMapper()
        else:
            self.parent.settings.setValue("volume_mapper", "cpu")

        self.parent.settings.setValue("gpu_size", float(self.gpu_size_entry.value()))
        self.parent.settings.setValue("vis_size", float(self.vis_size_entry.value()))

        if self.parent.settings.value("first_app_load") != "False":
            self.parent.CreateSessionSelector("new window")
            self.parent.settings.setValue("first_app_load", "False")
            
        self.parent.settings.setValue("omp_threads", str(self.omp_threads_entry.value()))
        self.close()


        #print(self.parent.settings.value("copy_files"))
    def onCancel(self):
        if self.parent.settings.value("first_app_load") != "False":
            self.parent.CreateSessionSelector("new window")
            self.parent.settings.setValue("first_app_load", "False")
        self.close()