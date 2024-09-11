import numpy as np
from idvc.pointcloud_conversion import PointCloudConverter

def extractDataFromDispResultFile(result, displ_wrt_point0):    
    """
    Gets the filepath of the disp file via `result.disp_file`.
    Extracts the data in the numpy format by using the converter, does not load the label row.
    This imports the whole row, so the displacement vector is given by indices 6, 7, 8. Index 5 is the objective func minimum.
    'plot_data' is a list of array, where each array is a column of data: objmin, u, v, w.
    """
    print("result.disp_file is ", result.disp_file)
    data = np.asarray(
    PointCloudConverter.loadPointCloudFromCSV(result.disp_file,'\t')[:]
    )
    data_shape = data.shape
    index_objmin = 5
    index_disp = [6,9]
    no_points = data_shape[0]
    if displ_wrt_point0:
        point0_disp_array = data[0,index_disp[0]:index_disp[1]]
        data[:,index_disp[0]:index_disp[1]] = data[:,index_disp[0]:index_disp[1]] - point0_disp_array
    result_arrays = np.transpose(data[:,index_objmin:data_shape[1]])
    return data, no_points, result_arrays