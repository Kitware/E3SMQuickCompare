from collections import defaultdict
import fnmatch
import json
import math
import os

import e3sm_quickview
from paraview import simple
from paraview.simple import (
    Contour,
    ExtractSurface,
    LegacyVTKReader,
    LoadPlugin,
    OutputPort,
    ProgrammableFilter,
)
from vtkmodules.vtkCommonCore import vtkLogger, vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkCommonTransforms import vtkTransform
from vtkmodules.vtkFiltersCore import (
    vtkAppendArcLength,
    vtkAssignAttribute,
    vtkExtractCells,
)
from vtkmodules.vtkFiltersGeometry import vtkGeometryFilter
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkDataSetMapper,
    vtkPolyDataMapper,
    vtkTexture,
)

from e3sm_compareview.comparison import (
    COMPARISON_TYPES,
    TWO_SIM_COLUMN_LABELS,
    COMPARISON_TYPE_TITLE_SUFFIXES,
)

COASTLINE_COLOR = (0.5, 0.5, 0.5)
COASTLINE_WIDTH = 0.5
GRIDLINE_COLOR = (0.0, 0.0, 0.0)
GRIDLINE_WIDTH = 0.5
GRIDLINE_DASH_PERIOD_RATIO = 0.02
# Grid spacing the dash period above was tuned against. Finer grids scale the
# period down proportionally so every cell keeps the same number of dashes,
# instead of dashes growing longer than the gap between neighbouring lines.
GRIDLINE_DASH_REFERENCE_INTERVAL = 30.0
# Floor the period so very fine grids degrade to a tight dotted line rather
# than a sub-pixel texture repeat, which reads as aliasing noise.
GRIDLINE_DASH_MIN_PERIOD_RATIO = 0.002
MAP_PERIMETER_WIDTH = 2.0


def range_to_trim(value_range, max_value):
    """Convert [-max, max] coordinate ranges into [left_trim, right_trim]."""
    min_value, max_range = value_range
    return [min_value + max_value, max_value - max_range]


def load_plugins():
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


class ErrorObserver:
    def __init__(self):
        self.error_occurred = False
        self.error_message = ""

    def __call__(self, obj, event):
        self.error_occurred = True

    def clear(self):
        self.error_occurred = False


class Continent:
    def __init__(self, projection="Robinson"):
        self._projection = projection
        self.clip_longitude = [-180.0, 180.0]
        self.clip_latitude = [-90.0, 90.0]

        globe_file = os.path.join(os.path.dirname(__file__), "data", "globe.vtk")
        self.reader = LegacyVTKReader(
            registrationName="ContReader",
            FileNames=[globe_file],
        )
        self.contour = Contour(registrationName="ContContour", Input=self.reader)
        self.contour.ContourBy = ["POINTS", "cstar"]
        self.contour.Isosurfaces = [0.5]
        self.contour.PointMergeMethod = "Uniform Binning"

        self.extract = EAMTransformAndExtract(  # noqa: F821
            registrationName="ContExtract",
            Input=self.contour,
        )
        self.extract.LongitudeRange = self.clip_longitude
        self.extract.LatitudeRange = self.clip_latitude

        self.proj = EAMProject(  # noqa: F821
            registrationName="ContProj",
            Input=OutputPort(self.extract, 0),
        )
        self.proj.Projection = projection
        self.proj.Translate = 0
        self.surface = ExtractSurface(registrationName="ContSurface", Input=self.proj)

        self.mapper = vtkPolyDataMapper()
        self.mapper.SetScalarVisibility(0)
        self.actor = vtkActor()
        self.actor.SetMapper(self.mapper)
        prop = self.actor.GetProperty()
        prop.SetRepresentationToWireframe()
        prop.SetRenderLinesAsTubes(1)
        prop.SetLineWidth(COASTLINE_WIDTH)
        prop.SetAmbientColor(*COASTLINE_COLOR)
        prop.SetDiffuseColor(*COASTLINE_COLOR)

    @property
    def projection(self):
        return self._projection

    @projection.setter
    def projection(self, value):
        self._projection = value
        self.proj.Projection = value

    @property
    def view_proxy(self):
        return OutputPort(self.proj, 0)

    @property
    def vtk_geometry(self):
        return self.surface.GetClientSideObject()

    def crop(self, longitude_min_max, latitude_min_max):
        self.clip_longitude = [float(longitude_min_max[0]), float(longitude_min_max[1])]
        self.clip_latitude = [float(latitude_min_max[0]), float(latitude_min_max[1])]
        self.extract.LongitudeRange = self.clip_longitude
        self.extract.LatitudeRange = self.clip_latitude

    def update(self, time=0.0):
        self.proj.UpdatePipeline(time)
        self.surface.UpdatePipeline(time)
        self.mapper.SetInputConnection(self.vtk_geometry.output_port)


class GridLines:
    def __init__(self, projection="Robinson"):
        self._projection = projection
        self.clip_longitude = [-180.0, 180.0]
        self.clip_latitude = [-90.0, 90.0]

        self.grid_lines = EAMGridLines(registrationName="GridGen")  # noqa: F821
        self.grid_lines.LongitudeRange = self.clip_longitude
        self.grid_lines.LatitudeRange = self.clip_latitude

        self.proj = EAMProject(  # noqa: F821
            registrationName="GridProj",
            Input=OutputPort(self.grid_lines, 0),
        )
        self.proj.Projection = projection
        self.proj.Translate = 0
        self.surface = ExtractSurface(registrationName="GridSurface", Input=self.proj)

        geometry = self.vtk_geometry
        self.interior_extract = vtkExtractCells()
        self.interior_extract.SetInputConnection(geometry.output_port)
        self.interior_geometry = vtkGeometryFilter()
        self.interior_geometry.SetInputConnection(self.interior_extract.GetOutputPort())
        self.arc_length = vtkAppendArcLength()
        self.arc_length.SetInputConnection(self.interior_geometry.GetOutputPort())
        self.texture_coords = vtkAssignAttribute()
        self.texture_coords.SetInputConnection(self.arc_length.GetOutputPort())
        self.texture_coords.Assign("arc_length", "TCOORDS", "POINT_DATA")
        self.dash_transform = vtkTransform()

        self.mapper = vtkPolyDataMapper()
        self.mapper.SetScalarVisibility(0)
        self.mapper.SetInputConnection(self.texture_coords.GetOutputPort())
        self.actor = vtkActor()
        self.actor.SetMapper(self.mapper)
        dash_texture = self._create_dash_texture()
        dash_texture.SetTransform(self.dash_transform)
        self.actor.SetTexture(dash_texture)
        prop = self.actor.GetProperty()
        prop.SetLineWidth(GRIDLINE_WIDTH)
        prop.SetAmbientColor(*GRIDLINE_COLOR)
        prop.SetDiffuseColor(*GRIDLINE_COLOR)

        self.perimeter_extract = vtkExtractCells()
        self.perimeter_extract.SetInputConnection(geometry.output_port)
        self.perimeter_mapper = vtkDataSetMapper()
        self.perimeter_mapper.SetScalarVisibility(0)
        self.perimeter_mapper.SetInputConnection(self.perimeter_extract.GetOutputPort())
        self.perimeter_actor = vtkActor()
        self.perimeter_actor.SetMapper(self.perimeter_mapper)
        perimeter_prop = self.perimeter_actor.GetProperty()
        perimeter_prop.SetLineWidth(MAP_PERIMETER_WIDTH)
        perimeter_prop.SetAmbientColor(*GRIDLINE_COLOR)
        perimeter_prop.SetDiffuseColor(*GRIDLINE_COLOR)

    @property
    def projection(self):
        return self._projection

    @projection.setter
    def projection(self, value):
        self._projection = value
        self.proj.Projection = value

    @property
    def view_proxy(self):
        return OutputPort(self.proj, 0)

    @property
    def vtk_geometry(self):
        return self.surface.GetClientSideObject()

    def set_interval(self, interval):
        self.grid_lines.Interval = int(interval)

    def crop(self, longitude_min_max, latitude_min_max):
        self.clip_longitude = [float(longitude_min_max[0]), float(longitude_min_max[1])]
        self.clip_latitude = [float(latitude_min_max[0]), float(latitude_min_max[1])]
        self.grid_lines.LongitudeRange = self.clip_longitude
        self.grid_lines.LatitudeRange = self.clip_latitude

    def update(self, time=0.0):
        self.surface.UpdatePipeline(time)
        self._split_grid_cells()

    def _split_grid_cells(self):
        interval = int(self.grid_lines.Interval)
        longitude_count = self._axis_line_count(self.clip_longitude, interval)
        latitude_count = self._axis_line_count(self.clip_latitude, interval)
        cell_count = longitude_count + latitude_count

        perimeter_ids = {0, longitude_count - 1, longitude_count, cell_count - 1}
        interior_ids = [i for i in range(cell_count) if i not in perimeter_ids]

        self.interior_extract.SetCellIds(tuple(interior_ids), len(interior_ids))
        self.perimeter_extract.SetCellIds(tuple(perimeter_ids), len(perimeter_ids))
        self.interior_extract.Update()
        self.perimeter_extract.Update()
        self._update_dash_scale(interval)

    @staticmethod
    def _create_dash_texture():
        pixels = vtkUnsignedCharArray()
        pixels.SetNumberOfComponents(4)
        pixels.InsertNextTuple4(255, 255, 255, 255)
        pixels.InsertNextTuple4(255, 255, 255, 0)

        image = vtkImageData()
        image.SetDimensions(2, 1, 1)
        image.GetPointData().SetScalars(pixels)

        texture = vtkTexture()
        texture.SetInputData(image)
        texture.InterpolateOff()
        texture.RepeatOn()
        return texture

    @staticmethod
    def _axis_line_count(clip_range, interval):
        return (
            math.ceil(clip_range[1] / interval)
            - math.floor(clip_range[0] / interval)
            + 1
        )

    def _update_dash_scale(self, interval):
        interior = self.interior_extract.GetOutput()
        if not interior.GetNumberOfCells():
            return

        bounds = interior.GetBounds()
        map_span = math.hypot(bounds[1] - bounds[0], bounds[3] - bounds[2])
        period_ratio = max(
            GRIDLINE_DASH_PERIOD_RATIO * interval / GRIDLINE_DASH_REFERENCE_INTERVAL,
            GRIDLINE_DASH_MIN_PERIOD_RATIO,
        )
        dash_period = map_span * period_ratio
        if dash_period:
            self.dash_transform.Identity()
            self.dash_transform.Scale(1 / dash_period, 1, 1)


class DataReader:
    def __init__(self, projection="Robinson"):
        self.valid = False
        self.conn_file = None
        self.simulation_files = []
        self.simulation_configs = []
        self.varmeta = None
        self.dimmeta = None
        self.slicing = defaultdict(int)
        self.data_readers = []
        self._projection = projection
        self.timestamps = []
        self.variable_view_specs = {}
        self.array_metadata = {}
        self.loaded_variables = []
        self.prog_filter = None
        self.atmos_center = None
        self.atmos_extract = None
        self.atmos_proj = None
        self.atmos_surface = None
        self.extents = [-180.0, 180.0, -90.0, 90.0]
        self.moveextents = [-180.0, 180.0, -90.0, 90.0]
        self.clip_longitude = [-180.0, 180.0]
        self.clip_latitude = [-90.0, 90.0]
        self.observer = ErrorObserver()

    @property
    def projection(self):
        return self._projection

    @projection.setter
    def projection(self, value):
        self._projection = value
        if self.atmos_proj is not None:
            self.atmos_proj.Projection = value

    @property
    def view_proxy(self):
        if self.atmos_surface is None:
            return None
        return OutputPort(self.atmos_surface, 0)

    @property
    def vtk_geometry(self):
        if self.atmos_surface is None:
            return None
        return self.atmos_surface.GetClientSideObject()

    def crop(self, longitude_min_max, latitude_min_max):
        self.clip_longitude = [float(longitude_min_max[0]), float(longitude_min_max[1])]
        self.clip_latitude = [float(latitude_min_max[0]), float(latitude_min_max[1])]
        if self.atmos_extract is None:
            return
        self._apply_clip_to_extract()

    def _apply_clip_to_extract(self):
        self.atmos_extract.LongitudeRange = self.clip_longitude
        self.atmos_extract.LatitudeRange = self.clip_latitude

    def update(self, time=0.0):
        if not self.valid or self.atmos_proj is None:
            return

        self.atmos_proj.UpdatePipeline(time)
        self.moveextents = self.atmos_proj.GetDataInformation().GetBounds()
        if self.atmos_surface is not None:
            self.atmos_surface.UpdatePipeline(time)

    def update_slicing(self, dimension, slice_index):
        if self.slicing.get(dimension) == slice_index:
            return
        self.slicing[dimension] = slice_index
        if self.data_readers:
            slicing_state = json.dumps(self.slicing)
            for reader in self.data_readers:
                reader.Slicing = slicing_state

    def clear_readers(self):
        for reader in self.data_readers:
            try:
                simple.Delete(reader)
            except Exception:
                pass
        self.data_readers = []

    def clear_derived_state(self):
        self.valid = False
        self.timestamps = []
        self.variable_view_specs = {}
        self.array_metadata = {}
        self.prog_filter = None
        self.atmos_center = None
        self.atmos_extract = None
        self.atmos_proj = None
        self.atmos_surface = None

    def _create_reader(self, index, file_path):
        reader = EAMSliceDataReader(  # noqa: F821
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
            reader.Variables = list(set([*self.loaded_variables, "lat", "lon"]))

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
        if hasattr(timestep_values, "__iter__") and not isinstance(
            timestep_values, str
        ):
            return list(timestep_values)
        return [timestep_values] if timestep_values is not None else []

    def _build_programmable_filter_script(self):
        # Emit control/source arrays and derived comparison arrays per simulation.
        return f"""import numpy as np

def _to_float_array(values, shape=None):
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError):
        return None if shape is None else np.full(shape, np.nan, dtype=np.float64)
    if shape is not None and array.shape != shape:
        return np.full(shape, np.nan, dtype=np.float64)
    return array

vars = {self.loaded_variables}
for var in vars:
    ctrl_np = _to_float_array(inputs[0].CellData[f"{{var}}"])
    if ctrl_np is None:
        continue

    output.CellData.append(ctrl_np, f'{{var}}')
    output.CellData.append(ctrl_np, f'{{var}}__control')
    for sim_index, sim_input in enumerate(inputs[1:], start=1):
        sim_np = _to_float_array(sim_input.CellData[f"{{var}}"], ctrl_np.shape)
        output.CellData.append(sim_np, f'{{var}}__test__{{sim_index}}')
        output.CellData.append(sim_np, f'{{var}}__source__{{sim_index}}')

        # Use guarded division to avoid runtime warnings for zero-valued slices.
        diff = sim_np - ctrl_np
        comp1 = np.full(ctrl_np.shape, np.nan, dtype=np.float64)
        comp2 = np.full(ctrl_np.shape, np.nan, dtype=np.float64)
        denom_ctrl = ctrl_np
        denom_sum = sim_np + ctrl_np
        np.divide(diff, denom_ctrl, out=comp1, where=(denom_ctrl != 0))
        np.divide(2.0 * diff, denom_sum, out=comp2, where=(denom_sum != 0))

        output.CellData.append(diff, f'{{var}}__diff__{{sim_index}}')
        output.CellData.append(comp1, f'{{var}}__comp1__{{sim_index}}')
        output.CellData.append(comp2, f'{{var}}__comp2__{{sim_index}}')

area_np = _to_float_array(inputs[0].CellData["area"])
if area_np is not None:
    output.CellData.append(area_np, 'area') # needed for utils.compute.extract_avgs

lat_np = _to_float_array(inputs[0].CellData["lat"])
if lat_np is not None:
    output.CellData.append(lat_np, "lat")

lon_np = _to_float_array(inputs[0].CellData["lon"])
if lon_np is not None:
    output.CellData.append(lon_np, "lon")
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
                "label": f"{control['label']} (ctrl)",
                "path": control["path"],
                "index": 0,
                "source_index": control.get("source_index", 0),
            }
            self.array_metadata[control_array_name] = control_metadata

            two_sim_specs = {
                "ctrl": {
                    **control_metadata,
                    "comparison_mode": "two-sim",
                    "label": TWO_SIM_COLUMN_LABELS["ctrl"],
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

                for index, simulation in enumerate(
                    self.simulation_configs[1:], start=1
                ):
                    is_source = comparison_type == "source"
                    comparison_spec = {
                        "array_name": self.comparison_array_name(
                            var_name, comparison_type, index
                        ),
                        "base_variable": var_name,
                        "role": "source" if is_source else comparison_type,
                        "metric": "raw" if is_source else comparison_type,
                        "comparison_mode": "multi-sim",
                        "comparison_type": comparison_type,
                        "label": (
                            f"{simulation['label']} "
                            f"({COMPARISON_TYPE_TITLE_SUFFIXES[comparison_type]})"
                        ),
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
                    "label": TWO_SIM_COLUMN_LABELS["test"],
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
                        "label": TWO_SIM_COLUMN_LABELS[comparison_type],
                        "path": two_sim_target["path"],
                        "index": 1,
                        "source_index": two_sim_target.get("source_index", 1),
                    }
                    self.array_metadata[
                        two_sim_specs[comparison_type]["array_name"]
                    ] = two_sim_specs[comparison_type]

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

    def refresh_view_specs(self, simulation_configs=None):
        if simulation_configs is not None:
            self.simulation_configs = simulation_configs
        self._build_view_specs(self.loaded_variables)

    def _build_atmosphere_pipeline(self):
        script = self._build_programmable_filter_script()
        self.prog_filter = ProgrammableFilter(
            registrationName="ProgrammableFilter",
            Input=self.data_readers,
        )
        self.prog_filter.Script = script
        self.prog_filter.RequestInformationScript = ""
        self.prog_filter.RequestUpdateExtentScript = ""
        self.prog_filter.PythonPath = ""

        has_trim_extract = (
            "EAMCenterMeridian" in globals() and "EAMExtract" in globals()
        )
        has_range_extract = "EAMTransformAndExtract" in globals()

        if has_trim_extract:
            self.atmos_center = EAMCenterMeridian(  # noqa: F821
                registrationName="AtmosCenter",
                Input=self.prog_filter,
            )
            self.atmos_extract = EAMExtract(  # noqa: F821
                registrationName="AtmosExtract",
                Input=self.atmos_center,
            )
        elif has_range_extract:
            self.atmos_center = None
            self.atmos_extract = EAMTransformAndExtract(  # noqa: F821
                registrationName="AtmosExtract",
                Input=self.prog_filter,
            )
        else:
            raise RuntimeError(
                "No compatible atmospheric extract filter is available "
                "(expected EAMCenterMeridian+EAMExtract or EAMTransformAndExtract)"
            )

        self._apply_clip_to_extract()
        self.atmos_extract.UpdatePipeline()
        self.extents = self.atmos_extract.GetDataInformation().GetBounds()

        self.atmos_proj = EAMProject(  # noqa: F821
            registrationName="AtmosProj",
            Input=OutputPort(self.atmos_extract, 0),
        )
        self.atmos_proj.Projection = self.projection
        self.atmos_proj.Translate = 0
        self.atmos_proj.UpdatePipeline()

        self.atmos_surface = ExtractSurface(
            registrationName="AtmosSurface",
            Input=self.atmos_proj,
        )
        self.atmos_surface.UpdatePipeline()
        self.moveextents = self.atmos_proj.GetDataInformation().GetBounds()

    def load(self, simulation_configs, conn_file, variables=None, force_reload=False):
        next_loaded_variables = (
            self.loaded_variables if variables is None else list(variables)
        )
        simulation_files = [entry["path"] for entry in simulation_configs]
        if not simulation_files:
            self.loaded_variables = next_loaded_variables
            self.simulation_files = []
            self.simulation_configs = []
            self.conn_file = conn_file
            self.clear_readers()
            self.clear_derived_state()
            return self.valid

        if (
            not force_reload
            and self.simulation_files == simulation_files
            and self.conn_file == conn_file
            and self.loaded_variables == next_loaded_variables
        ):
            self.simulation_configs = simulation_configs
            self._build_view_specs(self.loaded_variables)
            return self.valid

        self.loaded_variables = next_loaded_variables
        self.simulation_files = simulation_files
        self.simulation_configs = simulation_configs
        self.conn_file = conn_file

        if len(self.data_readers) != len(simulation_files):
            self.clear_readers()
            self.data_readers = [
                self._create_reader(index, file_path)
                for index, file_path in enumerate(simulation_files)
            ]
        else:
            for reader, file_path in zip(self.data_readers, simulation_files):
                reader.DataFile = file_path
                reader.ConnectivityFile = self.conn_file

        self._update_varmeta()
        if self.varmeta is None:
            self.loaded_variables = []
        else:
            valid_variables = set(self.varmeta)
            self.loaded_variables = [
                var_name
                for var_name in self.loaded_variables
                if var_name in valid_variables
            ]
        self._configure_readers()
        self.observer.clear()

        try:
            for reader in self.data_readers:
                reader.UpdatePipeline(time=0.0)
            if self.observer.error_occurred:
                raise RuntimeError(
                    "Error occurred in UpdatePipeline. "
                    "Please check if the data and connectivity files exist "
                    "and are compatible"
                )

            self.timestamps = self._normalize_timestamps(
                self.data_readers[0].TimestepValues
            )
            self._build_view_specs(self.loaded_variables)
            self._build_atmosphere_pipeline()
            self.valid = True
            self.observer.clear()
        except Exception as e:
            print(e)
            self.clear_derived_state()

        return self.valid

    def load_variables(self, variables):
        if not self.valid:
            return
        self.loaded_variables = list(variables)
        for reader in self.data_readers:
            reader.Variables = list(set([*variables, "lat", "lon"]))

    def get_output_dataset(self):
        vtk_geometry = self.vtk_geometry
        if vtk_geometry is None:
            return None
        vtk_geometry.Update()
        return vtk_geometry.GetOutput()

    def get_cell_data_array(self, array_name):
        dataset = self.get_output_dataset()
        if dataset is None:
            return None
        cell_data = dataset.GetCellData()
        if cell_data is None:
            return None
        return cell_data.GetArray(array_name)


class EAMVisSource:
    def __init__(self):
        self.projection = "Robinson"
        load_plugins()
        self.data_reader = DataReader(self.projection)
        self.continent = Continent(self.projection)
        self.grid_lines = GridLines(self.projection)

    def update(self, time=0.0):
        self.data_reader.update(time=time)
        self.continent.update(time=time)
        self.grid_lines.update(time=time)

    def ApplyClipping(self, cliplong, cliplat):
        if not self.data_reader.valid:
            return
        self.data_reader.crop(cliplong, cliplat)
        self.continent.crop(cliplong, cliplat)
        self.grid_lines.crop(cliplong, cliplat)

    def UpdateGridInterval(self, interval):
        # Changing the spacing changes how many cells the generator emits, so the
        # interior/perimeter split has to be recomputed against the new geometry.
        self.grid_lines.set_interval(interval)
        self.grid_lines.update()

    def UpdateProjection(self, proj):
        if not self.data_reader.valid:
            return

        if self.projection != proj:
            self.projection = proj
            self.data_reader.projection = proj
            self.continent.projection = proj
            self.grid_lines.projection = proj

    def UpdatePipeline(self, time=0.0):
        if not self.data_reader.valid:
            return
        self.update(time=time)

    def UpdateSlicing(self, dimension, slice):
        self.data_reader.update_slicing(dimension, slice)

    def Update(self, simulation_configs, conn_file, variables=None, force_reload=False):
        valid = self.data_reader.load(
            simulation_configs,
            conn_file,
            variables=variables,
            force_reload=force_reload,
        )
        if valid:
            self.update()
        return valid


if __name__ == "__main__":
    e = EAMVisSource()
