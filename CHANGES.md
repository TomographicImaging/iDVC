# ChangeLog


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
