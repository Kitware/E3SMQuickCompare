import fnmatch
import json
import os

import e3sm_quickview


from paraview.simple import (
    FindSource,
    LoadPlugin,
    OutputPort,
    Contour,
    LegacyVTKReader,
)

from vtkmodules.vtkCommonCore import vtkLogger

from collections import defaultdict


# Define a VTK error observer
class ErrorObserver:
    def __init__(self):
        self.error_occurred = False
        self.error_message = ""

    def __call__(self, obj, event):
        self.error_occurred = True

    def clear(self):
        self.error_occurred = False


class EAMVisSource:
    def __init__(self):
        # flag to check if the pipeline is valid
        # this is set to true when the pipeline is updated
        # and the data is available
        self.valid = False

        self.ctrl_file = None
        self.test_file = None
        self.conn_file = None

        # List of all available variables
        self.varmeta = None
        self.dimmeta = None
        self.slicing = defaultdict(int)

        self.ctrl_data = None
        self.test_data = None
        self.globe = None
        self.projection = "Cyl. Equidistant"
        self.timestamps = []
        self.center = 0.0

        self.prog_filter = None
        self.atmos_extract = None
        self.atmos_proj = None
        self.cont_extract = None
        self.cont_proj = None
        self.grid_gen = None
        self.grid_proj = None

        self.extents = [-180.0, 180.0, -90.0, 90.0]
        self.moveextents = [-180.0, 180.0, -90.0, 90.0]

        self.views = {}
        self.vars = {"surface": [], "midpoint": [], "interface": []}

        self.observer = ErrorObserver()
        try:
            plugin_dir = os.path.join(
                os.path.dirname(e3sm_quickview.__file__),
                "plugins",
            )
            plugins = fnmatch.filter(os.listdir(path=plugin_dir), "*.py")
            for plugin in plugins:
                print("Loading plugin : ", plugin)
                plugpath = os.path.abspath(os.path.join(plugin_dir, plugin))
                if os.path.isfile(plugpath):
                    LoadPlugin(plugpath, ns=globals())

            vtkLogger.SetStderrVerbosity(vtkLogger.VERBOSITY_OFF)
        except Exception as e:
            print("Error loading plugin :", e)

    def ApplyClipping(self, cliplong, cliplat):
        if not self.valid:
            return

        atmos_extract = self.atmos_extract or FindSource("AtmosExtract")
        atmos_extract.LongitudeRange = cliplong
        atmos_extract.LatitudeRange = cliplat

        cont_extract = self.cont_extract or FindSource("ContExtract")
        cont_extract.LongitudeRange = cliplong
        cont_extract.LatitudeRange = cliplat

    def UpdateCenter(self, center):
        """
        if self.center != int(center):
            self.center = int(center)

            meridian = FindSource("CenterMeridian")
            meridian.CenterMeridian = self.center

            gmeridian = FindSource("GCMeridian")
            gmeridian.CenterMeridian = self.center
        """
        pass

    def UpdateProjection(self, proj):
        if not self.valid:
            return

        atmos_proj = self.atmos_proj or FindSource("AtmosProj")
        cont_proj = self.cont_proj or FindSource("ContProj")
        grid_proj = self.grid_proj or FindSource("GridProj")
        if self.projection != proj:
            self.projection = proj
            atmos_proj.Projection = proj
            cont_proj.Projection = proj
            grid_proj.Projection = proj

    def UpdateTimeStep(self, t_index):
        if not self.valid:
            return

    def UpdatePipeline(self, time=0.0):
        if not self.valid:
            return

        atmos_proj = self.atmos_proj or FindSource("AtmosProj")
        if atmos_proj:
            atmos_proj.UpdatePipeline(time)
        self.moveextents = atmos_proj.GetDataInformation().GetBounds()

        cont_proj = self.cont_proj or FindSource("ContProj")
        if cont_proj:
            cont_proj.UpdatePipeline(time)

        atmos_extract = self.atmos_extract or FindSource("AtmosExtract")
        bounds = atmos_extract.GetDataInformation().GetBounds()

        grid_gen = self.grid_gen or FindSource("GridGen")
        if grid_gen:
            grid_gen.LongitudeRange = [bounds[0], bounds[1]]
            grid_gen.LatitudeRange = [bounds[2], bounds[3]]
        grid_proj = self.grid_proj or FindSource("GridProj")
        if grid_proj:
            grid_proj.UpdatePipeline(time)

        self.views["atmosphere_data"] = OutputPort(atmos_proj, 0)
        self.views["continents"] = OutputPort(cont_proj, 0)
        self.views["grid_lines"] = OutputPort(grid_proj, 0)

    def UpdateSlicing(self, dimension, slice):
        if self.slicing.get(dimension) == slice:
            return
        else:
            self.slicing[dimension] = slice
            if self.ctrl_data is not None and self.test_data is not None:
                x = json.dumps(self.slicing)
                self.ctrl_data.Slicing = x
                self.test_data.Slicing = x

    def Update(self, ctrl_file, test_file, conn_file, variables=[], force_reload=False):
        # Check if we need to reload
        if (
            not force_reload
            and self.ctrl_file == ctrl_file
            and self.test_file == test_file
            and self.conn_file == conn_file
        ):
            return self.valid

        # Store the file paths
        self.ctrl_file = ctrl_file
        self.test_file = test_file
        self.conn_file = conn_file

        if self.ctrl_data is None or self.test_data is None:
            ctrl_data = EAMSliceDataReader(
                registrationName="AtmosReader",
                ConnectivityFile=self.conn_file,
                DataFile=self.ctrl_file,
            )
            self.ctrl_data = ctrl_data
            vtk_obj = ctrl_data.GetClientSideObject()
            vtk_obj.AddObserver("ErrorEvent", self.observer)
            vtk_obj.GetExecutive().AddObserver("ErrorEvent", self.observer)
            ctrl_varmeta = vtk_obj.GetVariables()
            # self.observer.clear()

            test_data = EAMSliceDataReader(
                registrationName="AtmosReader2",
                ConnectivityFile=self.conn_file,
                DataFile=self.test_file,
            )
            self.test_data = test_data
            vtk_obj = test_data.GetClientSideObject()
            vtk_obj.AddObserver("ErrorEvent", self.observer)
            vtk_obj.GetExecutive().AddObserver("ErrorEvent", self.observer)
            test_varmeta = vtk_obj.GetVariables()
            self.dimmeta = vtk_obj.GetDimensions()
            self.varmeta = {
                key: val
                for key, val in ctrl_varmeta.items()
                if key in test_varmeta
            }


            for dim in self.dimmeta.keys():
                self.slicing[dim] = 0

            self.observer.clear()

        else:
            self.ctrl_data.DataFile = self.ctrl_file
            self.ctrl_data.ConnectivityFile = self.conn_file
            # self.observer.clear()

            self.test_data.DataFile = self.test_file
            self.test_data.ConnectivityFile = self.conn_file
            self.observer.clear()


        try:
            # Update pipeline and force view refresh
            self.ctrl_data.UpdatePipeline(time=0.0)
            self.test_data.UpdatePipeline(time=0.0)
            if self.observer.error_occurred:
                raise RuntimeError(
                    "Error occurred in UpdatePipeline. "
                    "Please check if the data and connectivity files exist "
                    "and are compatible"
                )

            # Ensure TimestepValues is always a list
            timestep_values = self.ctrl_data.TimestepValues
            if isinstance(timestep_values, (list, tuple)):
                self.timestamps = list(timestep_values)
            elif hasattr(timestep_values, "__iter__") and not isinstance(
                timestep_values, str
            ):
                # Handle numpy arrays or other iterables
                self.timestamps = list(timestep_values)
            else:
                # Single value - wrap in a list
                self.timestamps = (
                    [timestep_values] if timestep_values is not None else []
                )

            print("Data pre-script", self.ctrl_data, self.test_data)

            script = f"vars = {variables}\n"
            script += """
for var in vars:
    ctrl = inputs[0].CellData[f"{var}"]
    test = inputs[1].CellData[f"{var}"]

    diff = test - ctrl
    comp1 = diff / ctrl
    comp2 = (2 * diff) / (test + ctrl)

    output.CellData.append(ctrl, f'{var}')
    output.CellData.append(ctrl, f'{var}_ctrl')
    output.CellData.append(test, f'{var}_test')
    output.CellData.append(diff, f'{var}_diff')
    output.CellData.append(comp1, f'{var}_comp1')
    output.CellData.append(comp2, f'{var}_comp2')

output.CellData.append(inputs[0].CellData["area"], 'area') # needed for utils.compute.extract_avgs
"""
            print("ProgrammableFilter script:\n", script, end='')
            self.prog_filter = ProgrammableFilter(registrationName='ProgrammableFilter', Input=[self.ctrl_data, self.test_data])
            self.prog_filter.Script = script
            self.prog_filter.RequestInformationScript = ''
            self.prog_filter.RequestUpdateExtentScript = ''
            self.prog_filter.PythonPath = ''


            # Step 1: Extract and transform atmospheric data
            self.atmos_extract = EAMTransformAndExtract(  # noqa: F821
                registrationName="AtmosExtract", Input=self.prog_filter
            )
            self.atmos_extract.LongitudeRange = [-180.0, 180.0]
            self.atmos_extract.LatitudeRange = [-90.0, 90.0]
            self.atmos_extract.UpdatePipeline()
            self.extents = self.atmos_extract.GetDataInformation().GetBounds()

            # Step 2: Apply map projection to atmospheric data
            self.atmos_proj = EAMProject(  # noqa: F821
                registrationName="AtmosProj", Input=OutputPort(self.atmos_extract, 0)
            )
            self.atmos_proj.Projection = self.projection
            self.atmos_proj.Translate = 0
            self.atmos_proj.UpdatePipeline()
            self.moveextents = self.atmos_proj.GetDataInformation().GetBounds()

            # Step 3: Load and process continent outlines
            if self.globe is None:
                globe_file = os.path.join(
                    os.path.dirname(__file__), "data", "globe.vtk"
                )
                globe_reader = LegacyVTKReader(
                    registrationName="ContReader", FileNames=[globe_file]
                )
                cont_contour = Contour(
                    registrationName="ContContour", Input=globe_reader
                )
                cont_contour.ContourBy = ["POINTS", "cstar"]
                cont_contour.Isosurfaces = [0.5]
                cont_contour.PointMergeMethod = "Uniform Binning"
                self.globe = cont_contour

            # Step 4: Extract and transform continent data
            self.cont_extract = EAMTransformAndExtract(  # noqa: F821
                registrationName="ContExtract", Input=self.globe
            )
            self.cont_extract.LongitudeRange = [-180.0, 180.0]
            self.cont_extract.LatitudeRange = [-90.0, 90.0]
            # Step 5: Apply map projection to continents
            self.cont_proj = EAMProject(  # noqa: F821
                registrationName="ContProj", Input=OutputPort(self.cont_extract, 0)
            )
            self.cont_proj.Projection = self.projection
            self.cont_proj.Translate = 0
            self.cont_proj.UpdatePipeline()

            # Step 6: Generate lat/lon grid lines
            self.grid_gen = EAMGridLines(registrationName="GridGen")  # noqa: F821
            self.grid_gen.UpdatePipeline()

            # Step 7: Apply map projection to grid lines
            self.grid_proj = EAMProject(  # noqa: F821
                registrationName="GridProj", Input=OutputPort(self.grid_gen, 0)
            )
            self.grid_proj.Projection = self.projection
            self.grid_proj.Translate = 0
            self.grid_proj.UpdatePipeline()

            # Step 8: Cache all projected views for rendering
            self.views["atmosphere_data"] = OutputPort(self.atmos_proj, 0)
            self.views["continents"] = OutputPort(self.cont_proj, 0)
            self.views["grid_lines"] = OutputPort(self.grid_proj, 0)

            self.valid = True
            self.observer.clear()
        except Exception as e:
            # print("Error in UpdatePipeline :", e)
            # traceback.print_stack()
            print(e)
            self.valid = False

        return self.valid

    def LoadVariables(self, vars):
        if not self.valid:
            return
        self.ctrl_data.Variables = vars
        self.test_data.Variables = vars


if __name__ == "__main__":
    e = EAMVisSource()
