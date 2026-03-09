import fnmatch
import json
import os

import e3sm_quickview
from paraview import simple

from e3sm_compareview.comparison import COMPARISON_TYPES

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

        self.conn_file = None
        self.simulation_files = []
        self.simulation_configs = []

        # List of all available variables
        self.varmeta = None
        self.dimmeta = None
        self.slicing = defaultdict(int)

        self.data_readers = []
        self.globe = None
        self.projection = "Cyl. Equidistant"
        self.timestamps = []
        self.center = 0.0
        self.variable_view_specs = {}
        self.array_metadata = {}
        self.loaded_variables = []

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
        self.slicing[dimension] = slice
        if self.data_readers:
            slicing_state = json.dumps(self.slicing)
            for reader in self.data_readers:
                reader.Slicing = slicing_state

    def _clear_readers(self):
        for reader in self.data_readers:
            try:
                simple.Delete(reader)
            except Exception:
                pass
        self.data_readers = []

    def _clear_derived_state(self):
        # Clear metadata and derived ParaView outputs tied to the current inputs.
        self.valid = False
        self.timestamps = []
        self.variable_view_specs = {}
        self.array_metadata = {}
        self.views = {}

    def _create_reader(self, index, file_path):
        reader = EAMSliceDataReader(
            registrationName=f"AtmosReader{index}",
            ConnectivityFile=self.conn_file,
            DataFile=file_path,
        )
        vtk_obj = reader.GetClientSideObject()
        vtk_obj.AddObserver("ErrorEvent", self.observer)
        vtk_obj.GetExecutive().AddObserver("ErrorEvent", self.observer)
        return reader

    def _configure_readers(self):
        slicing_state = json.dumps(self.slicing)
        for reader in self.data_readers:
            reader.Slicing = slicing_state
            reader.Variables = self.loaded_variables

    def _update_varmeta(self):
        reader_varmeta = []
        for index, reader in enumerate(self.data_readers):
            vtk_obj = reader.GetClientSideObject()
            if index == 0:
                self.dimmeta = vtk_obj.GetDimensions()
            reader_varmeta.append(vtk_obj.GetVariables())

        if not reader_varmeta:
            self.varmeta = {}
            return

        common_keys = set(reader_varmeta[0])
        for metadata in reader_varmeta[1:]:
            common_keys &= set(metadata)

        self.varmeta = {
            key: reader_varmeta[0][key]
            for key in reader_varmeta[0]
            if key in common_keys
        }

        for dim in self.dimmeta.keys():
            self.slicing.setdefault(dim, 0)

    @staticmethod
    def control_array_name(var_name):
        return f"{var_name}__control"

    @staticmethod
    def comparison_array_name(var_name, comparison_type, index):
        return f"{var_name}__{comparison_type}__{index}"

    @staticmethod
    def _normalize_timestamps(timestep_values):
        if isinstance(timestep_values, (list, tuple)):
            return list(timestep_values)
        if hasattr(timestep_values, "__iter__") and not isinstance(timestep_values, str):
            return list(timestep_values)
        return [timestep_values] if timestep_values is not None else []

    def _build_programmable_filter_script(self):
        # Emit the control array plus one comparison array per selected simulation.
        return f"""vars = {self.loaded_variables}
for var in vars:
    ctrl = inputs[0].CellData[f"{{var}}"]

    output.CellData.append(ctrl, f'{{var}}')
    output.CellData.append(ctrl, f'{{var}}__control')
    for sim_index, sim_input in enumerate(inputs[1:], start=1):
        sim = sim_input.CellData[f"{{var}}"]
        output.CellData.append(sim, f'{{var}}__test__{{sim_index}}')
        diff = sim - ctrl
        comp1 = diff / ctrl
        comp2 = (2 * diff) / (sim + ctrl)
        output.CellData.append(diff, f'{{var}}__diff__{{sim_index}}')
        output.CellData.append(comp1, f'{{var}}__comp1__{{sim_index}}')
        output.CellData.append(comp2, f'{{var}}__comp2__{{sim_index}}')

output.CellData.append(inputs[0].CellData["area"], 'area') # needed for utils.compute.extract_avgs
"""

    def _build_view_specs(self, variables):
        self.variable_view_specs = {}
        self.array_metadata = {}
        if not self.simulation_configs:
            return

        control = self.simulation_configs[0]
        for var_name in variables:
            per_type_specs = {}
            control_array_name = self.control_array_name(var_name)
            control_metadata = {
                "array_name": control_array_name,
                "base_variable": var_name,
                "role": "control",
                "metric": "raw",
                "label": f'{control["label"]} (control)',
                "path": control["path"],
                "index": 0,
                "source_index": control.get("source_index", 0),
            }
            self.array_metadata[control_array_name] = control_metadata

            two_sim_specs = {
                "ctrl": {
                    **control_metadata,
                    "comparison_mode": "two-sim",
                    "label": f"{var_name}_ctrl",
                }
            }
            for comparison_type in COMPARISON_TYPES:
                specs = [
                    {
                        **control_metadata,
                        "comparison_mode": "multi-sim",
                        "comparison_type": comparison_type,
                    }
                ]

                for index, simulation in enumerate(self.simulation_configs[1:], start=1):
                    comparison_spec = {
                        "array_name": self.comparison_array_name(
                            var_name, comparison_type, index
                        ),
                        "base_variable": var_name,
                        "role": comparison_type,
                        "metric": comparison_type,
                        "comparison_mode": "multi-sim",
                        "comparison_type": comparison_type,
                        "label": simulation["label"],
                        "path": simulation["path"],
                        "index": index,
                        "source_index": simulation.get("source_index", index),
                    }
                    specs.append(comparison_spec)
                    self.array_metadata[comparison_spec["array_name"]] = comparison_spec

                per_type_specs[comparison_type] = sorted(
                    specs,
                    key=lambda spec: spec.get("source_index", 0),
                )

            if len(self.simulation_configs) > 1:
                two_sim_target = self.simulation_configs[1]
                test_spec = {
                    "array_name": f"{var_name}__test__1",
                    "base_variable": var_name,
                    "role": "test",
                    "metric": "raw",
                    "label": f"{var_name}_test",
                    "path": two_sim_target["path"],
                    "index": 1,
                    "source_index": two_sim_target.get("source_index", 1),
                    "comparison_mode": "two-sim",
                }
                two_sim_specs["test"] = test_spec
                self.array_metadata[test_spec["array_name"]] = test_spec

                for comparison_type in COMPARISON_TYPES:
                    two_sim_specs[comparison_type] = {
                        "array_name": self.comparison_array_name(
                            var_name, comparison_type, 1
                        ),
                        "base_variable": var_name,
                        "role": comparison_type,
                        "metric": comparison_type,
                        "comparison_mode": "two-sim",
                        "comparison_type": comparison_type,
                        "label": f"{var_name}_{comparison_type}",
                        "path": two_sim_target["path"],
                        "index": 1,
                        "source_index": two_sim_target.get("source_index", 1),
                    }
                    self.array_metadata[two_sim_specs[comparison_type]["array_name"]] = (
                        two_sim_specs[comparison_type]
                    )

            self.variable_view_specs[var_name] = {
                "multi-sim": per_type_specs,
                "two-sim": two_sim_specs,
            }

    def get_view_specs(
        self,
        variable_name,
        comparison_mode="multi-sim",
        comparison_type="diff",
        selected_columns=None,
    ):
        entry = self.variable_view_specs.get(variable_name, {})
        if comparison_mode == "two-sim":
            two_sim_specs = entry.get("two-sim", {})
            column_order = ["ctrl", "test", "diff", "comp1", "comp2"]
            selected = selected_columns or column_order
            selected_set = set(selected)
            return [
                two_sim_specs[column]
                for column in column_order
                if column in selected_set
                if column in two_sim_specs
            ]
        return entry.get("multi-sim", {}).get(comparison_type, [])

    def get_array_metadata(self, array_name):
        return self.array_metadata.get(array_name)

    def RefreshViewSpecs(self, simulation_configs=None):
        if simulation_configs is not None:
            self.simulation_configs = simulation_configs
        self._build_view_specs(self.loaded_variables)

    def Update(self, simulation_configs, conn_file, variables=None, force_reload=False):
        next_loaded_variables = (
            self.loaded_variables if variables is None else list(variables)
        )
        simulation_files = [entry["path"] for entry in simulation_configs]
        if not simulation_files:
            self.loaded_variables = next_loaded_variables
            self.simulation_files = []
            self.simulation_configs = []
            self.conn_file = conn_file
            self._clear_derived_state()
            return self.valid

        # Check if we need to rebuild the ParaView pipeline at all.
        if (
            not force_reload
            and self.simulation_files == simulation_files
            and self.conn_file == conn_file
            and self.loaded_variables == next_loaded_variables
        ):
            self.simulation_configs = simulation_configs
            self._build_view_specs(self.loaded_variables)
            return self.valid

        # Store the active simulation set before (re)configuring readers.
        self.loaded_variables = next_loaded_variables
        self.simulation_files = simulation_files
        self.simulation_configs = simulation_configs
        self.conn_file = conn_file

        if len(self.data_readers) != len(simulation_files):
            self._clear_readers()
            self.data_readers = [
                self._create_reader(index, file_path)
                for index, file_path in enumerate(simulation_files)
            ]
        else:
            for reader, file_path in zip(self.data_readers, simulation_files):
                reader.DataFile = file_path
                reader.ConnectivityFile = self.conn_file

        self._update_varmeta()
        self._configure_readers()
        self.observer.clear()

        try:
            # Update the raw readers before rebuilding derived filters and views.
            for reader in self.data_readers:
                reader.UpdatePipeline(time=0.0)
            if self.observer.error_occurred:
                raise RuntimeError(
                    "Error occurred in UpdatePipeline. "
                    "Please check if the data and connectivity files exist "
                    "and are compatible"
                )

            # Ensure TimestepValues is always a plain Python list.
            timestep_values = self.data_readers[0].TimestepValues
            self.timestamps = self._normalize_timestamps(timestep_values)

            self._build_view_specs(self.loaded_variables)

            script = self._build_programmable_filter_script()
            self.prog_filter = ProgrammableFilter(
                registrationName="ProgrammableFilter",
                Input=self.data_readers,
            )
            self.prog_filter.Script = script
            self.prog_filter.RequestInformationScript = ""
            self.prog_filter.RequestUpdateExtentScript = ""
            self.prog_filter.PythonPath = ""


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
            self._clear_derived_state()

        return self.valid

    def LoadVariables(self, vars):
        if not self.valid:
            return
        self.loaded_variables = list(vars)
        for reader in self.data_readers:
            reader.Variables = vars


if __name__ == "__main__":
    e = EAMVisSource()
