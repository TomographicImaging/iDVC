import numpy as np
import pandas as pd
from idvc.pointcloud_conversion import PointCloudConverter
from idvc.utilities import RunResults
import glob, os

def _extractDataFromDispResultFile(result, displ_wrt_point0):
    """
    Extracts objective minimum and displacement vectors from a result file in a numpy 2D array.
    Optionally, adjusts the displacement vectors relative to the displacement of the first point.

    The objective function minimum is located at index 5. 
    The displacement vector is extracted from columns indexed 6 to 8 (inclusive).
    If `displ_wrt_point0` is True, the displacement values will be adjusted by
    subtracting the displacement of the first point.

    Parameters
    ----------
    result : RunResults
        An object containing the filepath to the displacement result file (`result.disp_file`).
        The displacement result file is expected to be tab-delimited and have a header row that will be skipped.
    displ_wrt_point0 : bool
        If True, the displacement vectors will be adjusted relative to the displacement vector of the first point
        (point zero).

    Returns
    -------
    numpy.ndarray
        2D array where each row corresponds to a column of data from the file,
        including the objective function minimum and displacement vectors.
    """
    data = np.genfromtxt(result.disp_file, delimiter='\t', skip_header=1, ndmin=2)
    data_shape = data.shape
    index_objmin = 5
    index_disp = [6, 9]
    if displ_wrt_point0:
        point0_disp_array = data[0, index_disp[0]:index_disp[1]]
        data[:, index_disp[0]:index_disp[1]] -= point0_disp_array
    result_arrays = np.transpose(data[:, index_objmin:data_shape[1]])
    return result_arrays

def createResultsDataFrame(results_folder, displ_wrt_point0):
    """
    Creates a pandas DataFrame containing results from DVC result files.
    The folder is scanned for subfolders matching the pattern
    "dvc_result_*". The data for a result is extracted from each result file, and compiles
    the data into a pandas DataFrame.

    Parameters
    ----------
    results_folder : str
        The path to the folder containing the DVC result subfolders.
    displ_wrt_point0 :bool
        A flag indicating whether to extract displacement data with respect to point 0.
    
    Returns
    -------
    pd.DataFrame: A DataFrame with the following columns:
            - 'subvol_size': List of subvolume sizes as int.
            - 'subvol_points': List of subvolume points as int.
            - 'result': List of RunResults objects.
            - 'result_arrays': List of 4 arrays containing extracted data.
    """
    subvol_size_list = []
    subvol_points_list = []
    result_list = []
    result_arrays_list = []

    for folder in glob.glob(os.path.join(results_folder, "dvc_result_*")):
        result = RunResults(folder)
        result_arrays = _extractDataFromDispResultFile(result, displ_wrt_point0)
        subvol_size_list.append(int(result.subvol_size))
        subvol_points_list.append(int(result.subvol_points))
        result_list.append(result)

        result_arrays_list.append(result_arrays)
    result_data_frame = pd.DataFrame({
'subvol_size': subvol_size_list,
'subvol_points': subvol_points_list,
'result': result_list,
'result_arrays': result_arrays_list})
    result_data_frame = result_data_frame.sort_values(by=['subvol_size', 'subvol_points'], ascending=[True, True]).reset_index(drop=True)
    return result_data_frame

def addMeanAndStdToResultDataFrame(result_data_frame):
    """
    Adds mean and standard deviation arrays to the result DataFrame.

    In particular, iterates over each row in the DataFrame, calculates the mean and 
    standard deviation for each array in the 'result_arrays' column, and appends
    the new columns 'mean_array' and 'std_array'.

    Parameters
    ----------
    result_data_frame : pd.DataFrame
        A pandas DataFrame.

    Returns
    -------
    pd.DataFrame: The modified DataFrame with additional columns 'mean_array' and 'std_array'.
    """
    mean_array_list = []
    std_array_list = []
    for row in result_data_frame.itertuples():
        mean_array = []
        std_array = []
        for array in row.result_arrays:
            mean_array.append(array.mean())
            std_array.append(array.std())
        mean_array_list.append(mean_array)
        std_array_list.append(std_array)
    result_data_frame['mean_array'] = mean_array_list
    result_data_frame['std_array'] = std_array_list
    return result_data_frame