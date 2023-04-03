from eqt.ui import UIFormFactory
from PySide2.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QLabel, QPushButton)

class StrainFactory(object):

    @staticmethod
    def getStrainQDockWidget(parent):
        dock =  UIFormFactory.getQDockWidget(parent)
        
        dock.setWindowTitle('7 - Strain Calculation')

        # update help widget
        # dock.visibilityChanged.connect(partial(self.displayHelp, panel_no = 5))

        label = QLabel()
        label.setText("Select a run:")
        
        widget = QComboBox()
        dock.addWidget(widget, label, 'run')

        return dock
