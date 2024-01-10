from eqt.ui import FormDockWidget
from PySide2 import QtCore, QtGui, QtWidgets
from PySide2.QtWidgets import (QCheckBox, QComboBox,
                               QDoubleSpinBox,  QFormLayout,
                               QFrame, QLabel, QLineEdit,
                               QPushButton, QHBoxLayout, QSizePolicy,
                               QWidget)

from functools import partial

class PointCloudPanel(FormDockWidget):

    def __init__(self, parent=None, title=None):
        super(PointCloudPanel, self).__init__(parent, title)
        self.parent = parent
        self.setupUi()

    @property
    def pc(self, key):
        return self.getWidget(key)

    def setupUi(self):
        
        self.setWindowTitle('4 - Point Cloud')
        self.setObjectName("PointCloudPanel")
        self.visibilityChanged.connect(partial(self.displayHelp, panel_no = 3))


        # Create validation rule for text entry
        validator = QtGui.QDoubleValidator()
        validator.setDecimals(2)
        validatorint = QtGui.QIntValidator()

        #dockWidget.visibilityChanged.connect(lambda: self.showRangesConfigurator.setEnabled(True)) #SHOULD BE IN

        pc = {}
        self.pointcloud_parameters = pc
     
        # Add ISO Value field
        label = QLabel(self.groupBox)
        label.setText("Subvolume size")
        label.setToolTip("Defines the diameter or side length of the subvolumes created around each search point. This is in units of voxels on the original image.")
        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, label)
        entry= QLineEdit(self.groupBox)
        entry.setValidator(validatorint)
        entry.setText('30')
        entry.setToolTip("Defines the diameter or side length of the subvolumes created around each search point. This is in units of voxels on the original image.")
        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.isoValueEntry)
        entry.textChanged.connect(self.displaySubvolumePreview)

        self.addWidget(entry, label, 'pointcloud_size_entry')

        
        pc['subvolume_preview_check']
        entry = QCheckBox(self.groupBox)
        entry.setText("Display Subvolume Preview")
        entry.setChecked(True)
        entry.stateChanged.connect( partial(self.showHideActor,actor_name='subvol_preview_actor') )
        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['subvolume_preview_check'])
        # widgetno += 1
        self.addWidget(entry, '', 'subvolume_preview_check')

        # Add collapse priority field
        label = QLabel(self.groupBox)
        label.setText("Subvolume shape")
        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.subvolumeShapeLabel)
        entry = QComboBox(self.groupBox)
        entry.addItem("Cube")
        entry.addItem("Sphere")
        entry.setCurrentIndex(0)
        # TODO probably this connection needs to go in the main window
        entry.currentTextChanged.connect(self.parent.displaySubvolumePreview)

        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.subvolumeShapeValue)
        # widgetno += 1
        # pc['pointcloud_volume_shape_entry'] = self.subvolumeShapeValue

        # Add horizonal seperator
        # Generate panel
        separator = QFrame(self.groupBox)
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Raised)
        self.addSpanningWidget(separator, layout='vertical')

        # Load point cloud section 
        # add a separator and title
        label = QLabel("Generate Pointcloud", self.groupBox)
        self.addWidget(label, '', 'separator_label')


        # Add collapse priority field
        label = QLabel(self.groupBox)
        label.setText("Dimensionality")
        label.setToolTip("A 2D pointcloud is created only on the currently viewed plane.\n\
A 3D pointcloud is created within the full extent of the mask.")
        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.dimensionalityLabel)
        entry = QComboBox(self.groupBox)
        entry.addItems(["3D","2D"])
        entry.setCurrentIndex(1)
        # TODO: connect in the main window
        entry.currentIndexChanged.connect(self.parent.updatePointCloudPanel)
        entry.setToolTip("A 2D pointcloud is created only on the currently viewed plane.\n\
A 3D pointcloud is created within the full extent of the mask.")
        self.addWidget(entry, label, 'pointcloud_dimensionality_entry')


        v = self.parent.vis_widget_2D.frame.viewer
        orientation = v.getSliceOrientation()

        # Add Log Tree field
        overlap_tooltip_text = "Overlap as a fraction of the subvolume size."
        # Add Overlap X

        label = QLabel("Overlap", self.groupBox)
        label.setToolTip(overlap_tooltip_text)
        # self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.overlapLabel)
        self.addWidget()

        overlap_layout = QHBoxLayout()
        overlap_layout.setContentsMargins(0,0,0,0)

        self.overlapXLabel = QLabel(self.graphParamsGroupBox)
        self.overlapXLabel.setText("X: ")
        overlap_layout.addWidget(self.overlapXLabel)
        self.overlapXLabel.setToolTip(overlap_tooltip_text)
        self.overlapXValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapXLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.overlapXValueEntry.setValue(0.20)
        self.overlapXValueEntry.setMaximum(0.99)
        self.overlapXValueEntry.setMinimum(0.00)
        self.overlapXValueEntry.setSingleStep(0.01)
        self.overlapXValueEntry.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.overlapXValueEntry.valueChanged.connect(self.displaySubvolumePreview)
        self.overlapXValueEntry.setToolTip(overlap_tooltip_text)
        if orientation == 0:
            self.overlapXValueEntry.setEnabled(False)

        overlap_layout.addWidget(self.overlapXValueEntry)
        pc['pointcloud_overlap_x_entry'] = self.overlapXValueEntry
        # Add Overlap Y
        self.overlapYLabel = QLabel(self.graphParamsGroupBox)
        self.overlapYLabel.setText("Y: ")
        self.overlapYLabel.setToolTip(overlap_tooltip_text)
        self.overlapYLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        overlap_layout.addWidget(self.overlapYLabel)
        self.overlapYValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapYValueEntry.setValue(0.20)
        self.overlapYValueEntry.setMaximum(0.99)
        self.overlapYValueEntry.setMinimum(0.00)
        self.overlapYValueEntry.setSingleStep(0.01)
        self.overlapYValueEntry.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.overlapYValueEntry.valueChanged.connect(self.displaySubvolumePreview)
        self.overlapYValueEntry.setToolTip(overlap_tooltip_text)
        if orientation == 1:
            self.overlapYValueEntry.setEnabled(False)

        overlap_layout.addWidget(self.overlapYValueEntry)
        pc['pointcloud_overlap_y_entry'] = self.overlapYValueEntry
        # Add Overlap Z
        self.overlapZLabel = QLabel(self.graphParamsGroupBox)
        self.overlapZLabel.setText("Z: ")
        self.overlapZLabel.setToolTip(overlap_tooltip_text)
        self.overlapZLabel.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        overlap_layout.addWidget(self.overlapZLabel)
        self.overlapZValueEntry = QDoubleSpinBox(self.graphParamsGroupBox)
        self.overlapZValueEntry.setValue(0.20)
        self.overlapZValueEntry.setMaximum(0.99)
        self.overlapZValueEntry.setMinimum(0.00)
        self.overlapZValueEntry.setSingleStep(0.01)
        self.overlapZValueEntry.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.MinimumExpanding)
        self.overlapZValueEntry.valueChanged.connect(self.displaySubvolumePreview)
        self.overlapZValueEntry.setToolTip(overlap_tooltip_text)
        if orientation == 2:
            self.overlapZValueEntry.setEnabled(False)

        overlap_layout.addWidget(self.overlapZValueEntry)
        overlap_layout.update()
        pc['pointcloud_overlap_z_entry'] = self.overlapZValueEntry

        overlap_widget = QWidget()
        overlap_widget.setLayout(overlap_layout)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, overlap_widget)
        widgetno+=1

        rotation_tooltip_text = "Rotation of the pointcloud in degrees."

        rotation_layout = QHBoxLayout()
        rotation_layout.setContentsMargins(0,0,0,0)

        self.rotationLabel = QLabel("Rotation Angle", self.graphParamsGroupBox)
        self.rotationLabel.setToolTip(rotation_tooltip_text)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.rotationLabel)

        # Add Rotation X
        self.rotateXLabel = QLabel(self.graphParamsGroupBox)
        self.rotateXLabel.setText("X: ")
        self.rotateXLabel.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateXLabel)
        self.rotateXValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateXValueEntry.setValidator(validator)
        self.rotateXValueEntry.setText("0.00")
        self.rotateXValueEntry.textChanged.connect(self.displaySubvolumePreview)
        self.rotateXValueEntry.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateXValueEntry)
        pc['pointcloud_rotation_x_entry'] = self.rotateXValueEntry

        # Add Overlap Y
        self.rotateYLabel = QLabel(self.graphParamsGroupBox)
        self.rotateYLabel.setText("Y: ")
        self.rotateYLabel.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateYLabel)
        self.rotateYValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateYValueEntry.setValidator(validator)
        self.rotateYValueEntry.setText("0.00")
        self.rotateYValueEntry.setToolTip(rotation_tooltip_text)
        self.rotateYValueEntry.textChanged.connect(self.displaySubvolumePreview)

        rotation_layout.addWidget(self.rotateYValueEntry)
        pc['pointcloud_rotation_y_entry'] = self.rotateYValueEntry

        # Add Overlap Z
        self.rotateZLabel = QLabel(self.graphParamsGroupBox)
        self.rotateZLabel.setText("Z: ")
        self.rotateZLabel.setToolTip(rotation_tooltip_text)
        rotation_layout.addWidget(self.rotateZLabel)
        self.rotateZValueEntry = QLineEdit(self.graphParamsGroupBox)
        self.rotateZValueEntry.setValidator(validator)
        self.rotateZValueEntry.setText("0.00")
        self.rotateZValueEntry.setToolTip(rotation_tooltip_text)
        self.rotateZValueEntry.textChanged.connect(self.displaySubvolumePreview)

        rotation_layout.addWidget(self.rotateZValueEntry)

        pc['pointcloud_rotation_z_entry'] = self.rotateZValueEntry

        rotation_widget = QWidget()
        rotation_widget.setLayout(rotation_layout)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, rotation_widget)
        widgetno+=1

        # Add should extend checkbox
        self.erodeCheck = QCheckBox(self.graphParamsGroupBox)
        self.erodeCheck.setText("Erode mask")
        self.erodeCheck.setToolTip("Mask erosion ensures the entirety of the subvolume regions are within the mask.")
        self.erodeCheck.setEnabled(True)
        self.erodeCheck.setChecked(False)
        
        self.erodeCheck.stateChanged.connect(lambda: 
            self.warningDialog('Erosion of mask may take long time!', 
                                window_title='WARNING', 
                                detailed_text='You may better leave this unchecked while experimenting with the point clouds' ) \
                                if self.erodeCheck.isChecked() else (lambda: True) )
        
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.erodeCheck)
        widgetno += 1
        pc['pointcloud_erode_entry'] = self.erodeCheck
        
        self.erodeRatioLabel =  QLabel(self.graphParamsGroupBox)
        self.erodeRatioLabel.setText("Erosion Multiplier")
        self.erodeRatioLabel.setToolTip("Adjust the level of mask erosion.")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, self.erodeRatioLabel)
        self.erodeRatioSpinBox = QDoubleSpinBox(self.graphParamsGroupBox)
        self.erodeRatioSpinBox.setEnabled(False)
        self.erodeRatioSpinBox.setSingleStep(0.1)
        self.erodeRatioSpinBox.setMaximum(1.50)
        self.erodeRatioSpinBox.setMinimum(0.1)
        self.erodeRatioSpinBox.setValue(1.00)
        self.erodeRatioSpinBox.setToolTip("Adjust the level of mask erosion.")
        self.erodeCheck.stateChanged.connect(lambda: self.erodeRatioSpinBox.setEnabled(True) if self.erodeCheck.isChecked() else  self.erodeRatioSpinBox.setEnabled(False))
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.erodeRatioSpinBox)
        widgetno += 1
        

        # Add submit button
        self.graphParamsSubmitButton = QPushButton(self.graphParamsGroupBox)
        self.graphParamsSubmitButton.setText("Generate Point Cloud")
        self.graphParamsSubmitButton.clicked.connect(lambda: self.createSavePointCloudWindow(save_only=False))
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, self.graphParamsSubmitButton)
        widgetno += 1
        # Add elements to layout
        self.graphWidgetVL.addWidget(self.graphParamsGroupBox)
        self.graphDockVL.addWidget(self.dockWidget)
        self.pointCloudDockWidget.setWidget(self.pointCloudDockWidgetContents)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.pointCloudDockWidget)
        widgetno += 1

        # Load point cloud section 
        # add a separator and title
        seperator = QFrame(self.graphParamsGroupBox)
        seperator.setFrameShape(QFrame.HLine)
        seperator.setFrameShadow(QFrame.Raised)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.SpanningRole, seperator)
        widgetno += 1
        generatePointCloudLabel = QLabel("Load Pointcloud", self.graphParamsGroupBox)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, generatePointCloudLabel)
        widgetno += 1

        pc['pointcloudList'] = QComboBox(self.graphParamsGroupBox)
        pc['pointcloudList'].setEnabled(False)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['pointcloudList'])
        widgetno += 1

        pc['loadButton'] = QPushButton(self.graphParamsGroupBox)
        pc['loadButton'].setText("Load Saved Point Cloud")
        pc['loadButton'].clicked.connect(lambda: self.PointCloudWorker("load selection"))
        pc['loadButton'].setEnabled(False)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['loadButton'])
        widgetno += 1

        pc['roi_browse'] = QPushButton(self.graphParamsGroupBox)
        pc['roi_browse'].setText("Load Pointcloud from File")
        pc['roi_browse'].setToolTip("Specify the file containing data for all measurement points in the Region of Interest (ROI).\n\
The ROI is defined as a cloud of points that fill a geometric region within the reference volume.\n\
Point cloud size, shape, and density are completely flexible, as long as all points fall within the image volumes.\n\
Dense point clouds that accurately reflect sample geometry and reflect measurement objectives yield the best results.\n\
Each line in the tab delimited file contains an integer point label followed by the x,y,z point location, e.g. \n\
1   300   750.2  208\n\
2   300   750.2  209\n\
etc.\n\
Non-integer voxel locations are admitted, with reference volume interpolation used as needed.\n\
The first point is significant, as it is used as a global starting point and reference for the rigid_trans variable.")
        pc['roi_browse'].clicked.connect(self.select_pointcloud)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['roi_browse'])
        widgetno += 1

        # Display point cloud section 
        # add a separator and title
        seperator = QFrame(self.graphParamsGroupBox)
        seperator.setFrameShape(QFrame.HLine)
        seperator.setFrameShadow(QFrame.Raised)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.SpanningRole, seperator)
        widgetno += 1
        generatePointCloudLabel = QLabel("Display Pointcloud", self.graphParamsGroupBox)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, generatePointCloudLabel)
        widgetno += 1

        pc['clear_button'] = QPushButton(self.graphParamsGroupBox)
        pc['clear_button'].setText("Clear Point Cloud")
        pc['clear_button'].clicked.connect(self.clearPointCloud)
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['clear_button'])
        widgetno += 1

        pc['subvolumes_check'] = QCheckBox(self.graphParamsGroupBox)
        pc['subvolumes_check'].setText("Display Subvolume Regions")
        pc['subvolumes_check'].setChecked(False)
        pc['subvolumes_check'].stateChanged.connect( partial(self.showHideActor,actor_name='subvol_actor') )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['subvolumes_check'])
        widgetno += 1

        pc['reg_box_check'] = QCheckBox(self.graphParamsGroupBox)
        pc['reg_box_check'].setText("Display Registration Region")
        pc['reg_box_check'].setChecked(True)
        pc['reg_box_check'].stateChanged.connect( partial(self.showHideActor,actor_name='registration_box_actor') )
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['reg_box_check'])
        widgetno += 1

        #Pointcloud points label
        pc['pc_points_label'] = QLabel("Points in current pointcloud:")
        self.graphWidgetFL.setWidget(widgetno, QFormLayout.LabelRole, pc['pc_points_label'])
        pc['pc_points_value'] = QLabel("0")

        self.graphWidgetFL.setWidget(widgetno, QFormLayout.FieldRole, pc['pc_points_value'])