from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtWidgets import QCheckBox, QLabel, QDoubleSpinBox, QFrame, QVBoxLayout,\
     QDialogButtonBox, QPushButton, QDialog, QLineEdit
from PySide2.QtCore import Qt
import vtk
from brem.ui import RemoteServerSettingDialog, RemoteFileDialog
from eqt.ui import UIFormFactory

import os, posixpath

class SettingsWindow(QDialog):

    def __init__(self, parent):
        super(SettingsWindow, self).__init__(parent)

        self.parent = parent

        self.setWindowTitle("Settings")

        self.dark_checkbox = QCheckBox("Dark Mode")

        self.copy_files_checkbox = QCheckBox("Allow a copy of the image files to be stored. ")
        self.vis_size_label = QLabel("Maximum downsampled image size (GB): ")
        self.vis_size_entry = QDoubleSpinBox()

        self.vis_size_entry.setMaximum(64.0)
        self.vis_size_entry.setMinimum(0.01)
        self.vis_size_entry.setSingleStep(0.01)

        if self.parent.settings.value("vis_size") is not None:
            self.vis_size_entry.setValue(float(self.parent.settings.value("vis_size")))

        else:
            self.vis_size_entry.setValue(1.0)


        if self.parent.settings.value("dark_mode") is not None:
            if self.parent.settings.value("dark_mode") == "true":
                self.dark_checkbox.setChecked(True)
            else:
                self.dark_checkbox.setChecked(False)
        else:
            self.dark_checkbox.setChecked(True)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Raised)
        self.adv_settings_label = QLabel("Advanced")


        self.gpu_label = QLabel("Please set the size of your GPU memory.")
        self.gpu_size_label = QLabel("GPU Memory (GB): ")
        self.gpu_size_entry = QDoubleSpinBox()


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

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.dark_checkbox)
        self.layout.addWidget(self.copy_files_checkbox)
        self.layout.addWidget(self.vis_size_label)
        self.layout.addWidget(self.vis_size_entry)
        self.layout.addWidget(separator)
        self.layout.addWidget(self.adv_settings_label)
        self.layout.addWidget(self.gpu_checkbox)
        self.layout.addWidget(self.gpu_label)
        self.layout.addWidget(self.gpu_size_label)
        self.layout.addWidget(self.gpu_size_entry)

        # configure remote server settings
        remote_separator = QFrame()
        remote_separator.setFrameShape(QFrame.HLine)
        remote_separator.setFrameShadow(QFrame.Raised)
        fw = UIFormFactory.getQWidget(parent=self)
        
        self.remote_button_entry = QPushButton(self)
        self.remote_button_entry.setText("Open Preferences")
        self.remote_button_entry.clicked.connect(self.openConfigRemote)
        fw.addWidget(self.remote_button_entry, 'Configure remote settings', 'remote_preferences')
        cb = QCheckBox(self)
        cb.setChecked(self.parent.connection_details is not None)
        fw.addWidget(cb, 'Connect to remote server', 'connect_to_remote')
        select_remote_workdir = QPushButton(self)
        select_remote_workdir.setText('Browse')
        select_remote_workdir.clicked.connect(self.browseRemote)
        fw.addWidget(select_remote_workdir, 'Select remote workdir', 'select_remote_workdir')
        remote_workdir = QLineEdit(self)
        fw.addWidget(remote_workdir, 'Remote workdir', 'remote_workdir')

        self.fw = fw
        for k,v in fw.widgets.items():
            print ("fw", k)
        # add to layout
        self.layout.addWidget(remote_separator)
        self.layout.addWidget(fw)

        self.buttons = QDialogButtonBox(
           QDialogButtonBox.Save | QDialogButtonBox.Cancel,
           Qt.Horizontal, self)
        self.layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.quit)

    def accept(self):
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
        
        # if remote is checked
        statusBar = self.parent.statusBar()
        if self.fw.widgets['connect_to_remote_field'].isChecked():
            self.parent.connection_details = self.connection_details
            statusBar.showMessage("Connected to {}@{}:{}".format(
                self.connection_details['username'], 
                self.connection_details['server_name'], 
                self.connection_details['server_port'])
                )
        else:
            statusBar.clearMessage()
            self.parent.connection_details = None
        self.close()


        #print(self.parent.settings.value("copy_files"))
    def quit(self):
        if self.parent.settings.value("first_app_load") != "False":
            self.parent.CreateSessionSelector("new window")
            self.parent.settings.setValue("first_app_load", "False")
        self.close()

    def openConfigRemote(self):

        dialog = RemoteServerSettingDialog(self,port=None,
                                    host=None,
                                    username=None,
                                    private_key=None)
        dialog.Ok.clicked.connect(lambda: self.getConnectionDetails(dialog))
        dialog.exec()

    def getConnectionDetails(self, dialog):
        for k,v in dialog.connection_details.items():
            print (k,v)
        self.connection_details = dialog.connection_details


    def browseRemote(self):     
        # start the RemoteFileBrowser
        logfile = os.path.join(os.getcwd(), '..','..',"RemoteFileDialog.log")
        # logfile = None
        dialog = RemoteFileDialog(self, logfile=logfile, port=self.connection_details['server_port'], 
                                  host=self.connection_details['server_name'], 
                                  username=self.connection_details['username'], 
                                  private_key=self.connection_details['private_key'],
                                  remote_os=self.connection_details['remote_os'])
        dialog.Ok.clicked.connect(
            lambda: self.getSelectedRemoteWorkdir(dialog)
            )
        if hasattr(self, 'files_to_get'):
            try:
                dialog.widgets['lineEdit'].setText(self.files_to_get[0][0])
            except:
                pass
        dialog.exec()


    def getSelectedRemoteWorkdir(self, dialog):
        if hasattr(dialog, 'selected'):
            print (type(dialog.selected))
            for el in dialog.selected:
                print ("Return from dialogue", el)
            self.files_to_get = list (dialog.selected)
            remote_workdir = posixpath.join(self.files_to_get[0][0], self.files_to_get[0][1])
            self.fw.widgets['remote_workdir_field'].setText(remote_workdir)
