from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XY
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_XZ
from ccpi.viewer.CILViewer2D import SLICE_ORIENTATION_YZ

from ccpi.viewer.utils import cilClipPolyDataBetweenPlanes

from vtk import vtkPolyData, vtkAlgorithmOutput


class cilPlaneClipper(object):


    def __init__(self, interactor, data_list_to_clip = {}):
        self.SetInteractor(interactor)
        self.SetDataListToClip(data_list_to_clip)

    def SetDataListToClip(self, data_list_to_clip):
        self.DataListToClip = {}
        for key, data_to_clip in data_list_to_clip:
             self.AddDataToClip(key, data_to_clip)

    def AddDataToClip(self, key, data_to_clip):
        self.DataListToClip[str(key)] = self.MakeClippableData(data_to_clip)
        self.UpdateClippingPlanes()

    def RemoveDataToClip(self, key):
        if key in self.DataListToClip.keys():
            self.DataListToClip.pop(key)

    def MakeClippableData(self, data_to_clip):
        clippable_data = cilClipPolyDataBetweenPlanes()
        print("Type", type(data_to_clip))
        if isinstance(data_to_clip, vtkPolyData):
            print("Polydata output")
            clippable_data.SetInputDataObject(data_to_clip)
        elif isinstance(data_to_clip, vtkAlgorithmOutput):
            print("Algorithm output")
            clippable_data.SetInputConnection(data_to_clip)
        return clippable_data

    def GetDataListToClip(self):
        return self.DataListToClip

    def GetClippedData(self, key):
        return self.DataListToClip[key]
    
    def SetInteractor(self, interactor):
         self.Interactor = interactor

    def GetInteractor(self):
         return self.Interactor

    def UpdateClippingPlanes(self, interactor = None, event = "ClipData"):
        try:
            if len(self.DataListToClip) > 0:
                if interactor is None:
                    interactor = self.Interactor
                print("Update Clipping Planes", self.DataListToClip)
                
                print("Orientation", interactor.GetSliceOrientation())
                #print("Interactor", interactor)
                normal = [0, 0, 0]
                origin = [0, 0, 0]
                norm = 1

                orientation = interactor.GetSliceOrientation()

                beta = 0
                print("Current active slice", interactor.GetActiveSlice()+beta)

                spac = interactor.GetInputData().GetSpacing()
                orig = interactor.GetInputData().GetOrigin()
                slice_thickness = spac[orientation]

                rounding = True

                if rounding == True:
                    beta_up = 0.5 - 1e-9
                    beta_down = 0.5
                else:
                    beta_up = 1 - 1e-9
                    beta_down = 0

                normal[orientation] = norm
                origin [orientation] = (interactor.GetActiveSlice() + beta_up) * slice_thickness - orig[orientation]

                # update the  plane below
                slice_below = interactor.GetActiveSlice() - beta_down

                # if slice_below < 0:
                #     slice_below = 0

                origin_below = [i for i in origin]
                origin_below[orientation] = ( slice_below ) * slice_thickness - orig[orientation]

                for data_to_clip in self.DataListToClip.values():
                    data_to_clip.SetPlaneOriginAbove(origin)
                    data_to_clip.SetPlaneNormalAbove(normal)
                    data_to_clip.SetPlaneOriginBelow(origin_below)
                    data_to_clip.SetPlaneNormalBelow((-normal[0], -normal[1], -normal[2]))
                    data_to_clip.Update()
                
                interactor.UpdatePipeline()

                
        except AttributeError as ae:
            print (ae)
            print ("No data to clip.")