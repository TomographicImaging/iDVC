# ChangeLog

## v24.0.0
New features:
* Edit DVC-Results tab #231
* Add scrolling widget in the help text #260
* Allow csv, xlxs and inp formats in point-cloud file & add error dialog #262 #269 #284
* Set registration-box-size default and help text #259
* Make dimensionality 3D the default #256
* Enable loading of TIFF files with non integer pixel values. Data will be rescaled to uint16 #228
* Edit registration-tab name from "Manual" to "Initial" #241
* Add automatic registration functionality #304
* Added argument parser to idvc command. This allows the user to specify the debugging level #218
* Add setting to set the number of OpenMP threads to use during DVC analysis #194
* Renames input files with names reference and correlate for the relative images, if data are copied in the session #186
* More efficient pointcloud creation by not shifting the pointcloud to the make such that point0 is one point of the 
  created cloud. Point0 is simply added as first point of the cloud even if it does not lie on the regular grid #163
* Improves progress reporting when loading a saved session, including displaying file names as they are loaded #195
* Make splash screen appear instantly when app is opened #198
* Restructure to create:
  * ui/dialogs.py
  * ui/widgets.py
  * ui/windows.py
  * utils.py
  * idvc.py - which launches the app #198
  
Bug fixes:
* Make 3D viewer dock widget floatable, add minimum height. Add scroll area to point-cloud tab #289
* Disables buttons in Select-Image tab after first registration #293
* Scales the displacement vectors keeping the color bar with the displacement values. Adds title to color bar #270
* Edit "degrees of freedom" widget to be "optimisation parameters" #254
* Set empty pop-up menus for the main windows #217
* Set Tabified widgets not to move or close #226 #217
* Set QDockWidgets flag to NoDockWidgetFeatures to prevent them being moved or lost #226 #217
* Consume events 'w' and 's' in viewers to avoid render changes between wireframe and surface respectively #218
* Add workaround for box clipping due to VTK behaviour change from 9.1 #216
* Use os.path.join to create all filepaths, previously in some cases we were forcing "\" or "/" to be in some paths #175
* Updates progress bar for setting up a DVC run configuration - previously this was hanging #195
  
CI:
* Upgrade CILviewer to 24.0.0 #279
* Fix vtk version #291
* Add `openpyxl` to recipe files #262
* Fix some missing pip dependencies & update workflows & fix tests #233
* Add build directory to gitignore #216
* Revert to v1.4.4 of conda build action #202

Documentation:
* Edit point 0/registration/mask/point-cloud/results tooltips, help text and documentation #257 #264 #268 #286 #287
* Edit README.md to include Prof. Bay citations and ref to DVC executable #255

## v22.3.0
* Fix bug with size of 'overlap' spinboxes expanding in the vertical direction
* Create environment file for development of iDVC
* On load/creation of pointcloud display points only by default
* Makes a few GUI bugfixes, such as fix number of points in the pointcloud displayed wrongly here and there.
* Catches exceptions on load of files and opens message boxes
* Fix load of TIFF files
* Added button to start tracing
* Added estimated time to completion of DVC analysis
* Do not allow registration box to extend over the edge of the image (previously this caused the app to crash)
* Added more granular progress update from pointcloud creation step, and bugfixes
* fix the build script for Windows
* Update documentation to be consistent with this version.
* Add environment file for installing iDVC : recipe/idvc_environment.yml

## v22.2.0
* Update DVC executable version to v22.0.0
* Adds GUI elements to control the range of the displacement vectors displayed
* Adds splash screen
* Add basic color bar when visualising the vectors in both 2D and 3D
* Pass max number of points to be processed to dvc executable
* Pass point 0 location to dvc executable
* Add button to set the number of points in the run to all points in the pointcloud.
* Use v2.0.0 of conda build action

## v22.1.0
* Allows loading of TIFF stacks to run DVC code
* Requires CILViewer >= 22.2.0 and VTK = 8.1.2
* Correctly scales total displacement vectors 
* Correctly aligned help text
* Make dockwidgets uncloseable, so that 3D viewer can't be lost.
* Add idvc entrypoint to the setup.py
* Fix issue with importing qApp from PySide2
* Fix bug with viewer windows appearing outside of GUI on Linux

## v22.0.1
* Requires >=v22.0.1 and <v22.1 of the CILViewer due to backwards incompatibility of reader restructuring, and requirement of vtk 8.1.2 in iDVC.

## v22.0.0
* Fixes bug with incorrect bit depth being passed to dvc code if a int16 raw file is used.
* Moved io.py from CILViewer to this package
* Generate version.py from setup.py
* Changed the directory structure for the configuration files for a single or bulk run which are now saved as same level subdirectories as Result/<run_name>/dvc_result_<run_number>. The Bulk run will launch a DVC execution consequently for each directory.
* use pip install instead of setup.py install in recipes

## v21.1.2
* Only use relative filepaths to session files
* This allows session folders to be transferred between computers
* Display results graphs without hard-coding expected columns in .disp file
* This fixes a bug with graphs not displaying after the update to ccp-dvc v21.1.0
* Increases ccpi-viewer version requirement to 21.1.1

## v21.1.1
* Increases ccpi-dvc version requirement to 21.1.0.
* This fixes issue of missing DLLs when running DVC exe on windows

## v21.1.0
* the package renamed to idvc
* version string from git describe
* introduced unit test infrastructure

## v21.0.1
* improvements to saving and closing app
* check for platform, and adjust call to dvc core code
* Update orienatation in manual registration, in line with v21.0.1 of the CILViewer
* Rearrange X, Y, Z entry boxes to be horizontal
* Fix reading dvc progress updates on linux

## v21.0.0
* change backend to PySide2
* add dependency on eqt (package with some Qt threading and UI templates)

## v20.07.6
* Fixed location of registration viewer on interface
* shows subvolume size for externally loaded pointclouds
* updates minimal version of viewer

## v20.07.5
* Changed default location of viewers on interface
* refactored process launching for DVC analysis with DVC_runner class
* added output of dvc command to progress dialog

## v20.07.4
* Rearranged viewers on interface
* Changed subvolume radius setting to subvolume size
* Added preview of subvolume at position of point 0
* Allow manual setting of translation for registration
* Allow displacement vectors to be scaled up/down
* Added more info about run configuration to results summary panel

## v20.07.3
*  Fixed problem with image translation on the z axis causing a DVC run error.
*  Fixed pointcloud rotation so it works for all pointclouds generated on any axis.
*  Minor interface updates to prevent errors when clicking in unexpected order.
*  Scale maximum registration box size according to maximum downsampling level.

## v20.07.2
*  Downsampling of large image files based on gpu size and max. downsampling size input by user. Can switch between coordinates of downsampled or original image.
*  Displacement vectors are displayed correctly in 2D and 3D, and can show total or relative displacement.
*  Improvements to progress bar and error reporting for running the DVC code.
*  Improvements to image registration – can scroll through slices in registration box and switch orientation without error.
*  Fixed mask erosion, with ability to adjust level of erosion.
*  Added user help when hovering over labels.
*  Improvements to viewer including correct linkage between 2D and 3D for slice scrolling and window level

## v20.07.1
*  Endianness is set and input to DVC code. This allows uint16 images to be worked with.

## v20.07.0
* Fixed problem with image header length automatically being set instead of being read from the image file - this caused the dvc run to fail.
* mha/mhd files can be used. In this case, a copy of the file is converted to numpy format and saved in the session folder. 


## v20.06.2
* added error messages when pointcloud contains no points or maximum > minimum in bulk run settings. Made sure run is cancelled if these errors occur in a bulk run setup, so that the interface does not crash.
* fixed problem with "New Session" not clearing previous session files.
* fixed issue with location of pointcloud file not being saved correctly in certain cases 

## v20.06.1

* enable read of files with white-spaces in path

## v20.06.0

* initial release for Windows
