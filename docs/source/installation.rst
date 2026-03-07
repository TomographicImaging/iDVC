Installation
************

Binary installation of iDVC can be achieved with conda. Currently we only tested the app on Windows.

Installing the App
==================
1.	Install miniconda: https://docs.conda.io/en/latest/miniconda.html 
2.	Open an anaconda prompt (miniconda).
3.  Create a new environment and install the software by typing ``conda create --name idvc_environment -c conda-forge -c ccpi idvc=25.0.0`` (or replace ``25.0.0`` with the latest version number).
4.	Activate the environment by typing ``activate idvc_environment``.
5.	Run the app by typing ``idvc``.

Please note that whenever you would like to open the app you need to carry out steps 2, 4 and 5 above.
Alternatively, use miniforge (https://github.com/conda-forge/miniforge) instead of miniconda. 

Updating the App
================
If you have previously installed the app, to get an updated version:

1.	Open anaconda prompt (miniconda).
2.	Type ``activate idvc_environment`` (note that when you created your environment, if you called it something else you need to replace ``idvc`` with your environment name.)
3.	Type ``conda install idvc=25.0.0 -c ccpi -c conda-forge`` (or replace ``25.0.0`` with the latest version number)
4.	Type ``idvc`` to open up the app, as normal.

Installing the DVC Executable Only
==================================
If you have followed the instructions to install the app above, you will have installed both the app and the dvc executable which can be called from the command line by typing ‘dvc’
Alternatively, if you would only like to install the dvc executable and not the gui, you may follow these instructions:

1.	Install miniconda<https://docs.conda.io/en/latest/miniconda.html>
2.	Open an anaconda prompt (miniconda) and type….
3.	``conda create --name dvc-core ccpi-dvc -c ccpi -c conda-forge``
4.	``activate dvc-core``
5.	``dvc``

Please note that whenever you would like to run the executable in future, you need to carry out steps 2, 4 and 5 above.
