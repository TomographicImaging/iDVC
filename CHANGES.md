# ChangeLog

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
