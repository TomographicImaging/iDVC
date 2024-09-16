import numpy as np
import pandas as pd
from idvc.pointcloud_conversion import PointCloudConverter
from idvc.utilities import RunResults
import glob, os

def extractDataFromDispResultFile(result, displ_wrt_point0):    
    """
    Gets the filepath of the disp file via `result.disp_file`.
    Extracts the data in the numpy format by using the converter, does not load the label row.
    This imports the whole row, so the displacement vector is given by indices 6, 7, 8. Index 5 is the objective func minimum.
    'plot_data' is a list of array, where each array is a column of data: objmin, u, v, w.
    """
    data = np.asarray(
    PointCloudConverter.loadPointCloudFromCSV(result.disp_file,'\t')[:]
    )
    data_shape = data.shape
    index_objmin = 5
    index_disp = [6,9]
    if displ_wrt_point0:
        point0_disp_array = data[0,index_disp[0]:index_disp[1]]
        data[:,index_disp[0]:index_disp[1]] = data[:,index_disp[0]:index_disp[1]] - point0_disp_array
    result_arrays = np.transpose(data[:,index_objmin:data_shape[1]])
    return result_arrays

def createResultsDataFrame(results_folder, displ_wrt_point0):
    subvol_size_list = []
    subvol_points_list = []
    result_list = []
    result_arrays_list = []

    for folder in glob.glob(os.path.join(results_folder, "dvc_result_*")):
        result = RunResults(folder)
        result_arrays = extractDataFromDispResultFile(result, displ_wrt_point0)
        subvol_size_list.append(str(result.subvol_size))
        subvol_points_list.append(str(result.subvol_points))
        result_list.append(result)

        result_arrays_list.append(result_arrays)
    result_data_frame = pd.DataFrame({
'subvol_size': subvol_size_list,
'subvol_points': subvol_points_list,
'result': result_list,
'result_arrays': result_arrays_list})
    return result_data_frame