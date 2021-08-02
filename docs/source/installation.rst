Installation
************

Currently the app is available to install on windows. Linux and MacOS versions are currently a work in progress.

Installing the App
==================
1.	Install miniconda: https://docs.conda.io/en/latest/miniconda.html 
2.	Open an anaconda prompt (miniconda) and type... 
3.	``conda create --name idvc idvc -c ccpi -c paskino -c conda-forge -c defaults --override-channels``
4.	``activate idvc``
5.	``idvc``

Please note that whenever you would like to open the app you need to carry out steps 2, 4 and 5 above.

Updating the App
================
If you have previously installed the app, to get an updated version:

1.	Open anaconda prompt (miniconda) and type…
2.	``activate idvc`` (note that when you created your environment, if you called it something else you need to replace dvc-gui with your environment name.)
3.	``conda install idvc=21.1.0 -c ccpi -c paskino -c conda-forge -c defaults --override-channels`` (or replace 21.1.0 with the latest version number)
4.	Then use: ``idvc`` to open up the app, as normal

Installing the DVC Executable Only
==================================
If you have followed the instructions to install the app above, you will have installed both the app and the dvc executable which can be called from the command line by typing ‘dvc’
Alternatively, if you would only like to install the dvc executable and not the gui, you may follow these instructions:

1.	Install miniconda<https://docs.conda.io/en/latest/miniconda.html>
2.	Open an anaconda prompt (miniconda) and type….
3.	``conda create --name dvc-core ccpi-dvc -c ccpi -c paskino -c conda-forge -c defaults --override-channels``
4.	``activate dvc-core``
5.	``dvc``

Please note that whenever you would like to run the executable in future, you need to carry out steps 2, 4 and 5 above.
