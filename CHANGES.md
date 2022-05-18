# ChangeLog

## v22.x.x
* Make dockwidgets uncloseable, so that 3D viewer can't be lost.

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
