import math

from trame.app import TrameComponent
from trame.ui.html import DivLayout
from trame.widgets import paraview as pvw, vuetify3 as v3, client, html
from trame.decorators import controller

from trame_dataclass.core import StateDataModel

from paraview import simple

from e3sm_quickview.components import view as tview
from e3sm_quickview.utils.color import get_cached_colorbar_image, COLORBAR_CACHE
from e3sm_quickview.presets import COLOR_BLIND_SAFE


def auto_size_to_col(size):
    if size == 1:
        return 12

    if size >= 8 and size % 2 == 0:
        return 3

    if size % 3 == 0:
        return 4

    if size % 2 == 0:
        return 6

    return auto_size_to_col(size + 1)


COL_SIZE_LOOKUP = {
    0: auto_size_to_col,
    1: 12,
    2: 6,
    3: 4,
    4: 3,
    6: 2,
    12: 1,
    "flow": None,
}


def lut_name(element):
    return element.get("name").lower()


class ViewConfiguration(StateDataModel):
    variable: str
    preset: str = "Inferno (matplotlib)"
    preset_img: str
    invert: bool = False
    color_blind: bool = False
    use_log_scale: bool = False
    color_value_min: str = "0"
    color_value_max: str = "1"
    color_value_min_valid: bool = True
    color_value_max_valid: bool = True
    color_range: list[float] = (0, 1)
    override_range: bool = False
    order: int = 0
    size: int = 4
    offset: int = 0
    break_row: bool = False
    menu: bool = False
    swap_group: list[str]
    search: str | None


class VariableView(TrameComponent):
    def __init__(self, server, source, variable_name, variable_type):
        super().__init__(server)
        self.config = ViewConfiguration(server, variable=variable_name)
        self.source = source
        self.variable_name = variable_name
        self.variable_type = variable_type
        self.name = f"view_{self.variable_name}"
        self.view = simple.CreateRenderView()
        self.view.GetRenderWindow().SetOffScreenRendering(True)
        self.view.InteractionMode = "2D"
        self.view.OrientationAxesVisibility = 0
        self.view.UseColorPaletteForBackground = 0
        self.view.BackgroundColorMode = "Gradient"
        self.view.CameraParallelProjection = 1
        self.view.Size = 0  # make the interactive widget non responsive
        self.representation = simple.Show(
            proxy=source.views["atmosphere_data"],
            view=self.view,
        )

        # Lookup table color management
        simple.ColorBy(self.representation, ("CELLS", variable_name))
        self.lut = simple.GetColorTransferFunction(variable_name)
        self.lut.NanOpacity = 0.0

        self.view.ResetActiveCameraToNegativeZ()
        self.view.ResetCamera(True, 0.9)
        self.disable_render = False

        # Add annotation to the view
        # - continents
        globe = source.views["continents"]
        repG = simple.Show(globe, self.view)
        simple.ColorBy(repG, None)
        repG.SetRepresentationType("Wireframe")
        repG.RenderLinesAsTubes = 1
        repG.LineWidth = 1.0
        repG.AmbientColor = [0.67, 0.67, 0.67]
        repG.DiffuseColor = [0.67, 0.67, 0.67]
        self.rep_globe = repG
        # - gridlines
        annot = source.views["grid_lines"]
        repAn = simple.Show(annot, self.view)
        repAn.SetRepresentationType("Wireframe")
        repAn.AmbientColor = [0.67, 0.67, 0.67]
        repAn.DiffuseColor = [0.67, 0.67, 0.67]
        repAn.Opacity = 0.4
        self.rep_grid = repAn

        # Reactive behavior
        self.config.watch(
            ["color_value_min", "color_value_max"],
            self.color_range_str_to_float,
        )
        self.config.watch(
            ["override_range", "color_range"], self.update_color_range, eager=True
        )
        self.config.watch(
            ["preset", "invert", "use_log_scale"], self.update_color_preset, eager=True
        )

        # GUI
        self._build_ui()

    def render(self):
        if self.disable_render or not self.ctx.has(self.name):
            return
        self.ctx[self.name].update()

    def set_camera_modified(self, fn):
        self._observer = self.camera.AddObserver("ModifiedEvent", fn)

    @property
    def camera(self):
        return self.view.GetActiveCamera()

    def reset_camera(self):
        self.view.InteractionMode = "2D"
        self.view.ResetActiveCameraToNegativeZ()
        self.view.ResetCamera(True, 0.9)
        self.ctx[self.name].update()

    def update_color_preset(self, name, invert, log_scale):
        self.config.preset = name
        self.config.preset_img = get_cached_colorbar_image(
            self.config.preset,
            self.config.invert,
        )
        self.lut.ApplyPreset(self.config.preset, True)
        if invert:
            self.lut.InvertTransferFunction()
        if log_scale:
            self.lut.MapControlPointsToLogSpace()
            self.lut.UseLogScale = 1
        self.render()

    def color_range_str_to_float(self, color_value_min, color_value_max):
        try:
            min_value = float(color_value_min)
            self.config.color_value_min_valid = not math.isnan(min_value)
        except ValueError:
            self.config.color_value_min_valid = False

        try:
            max_value = float(color_value_max)
            self.config.color_value_max_valid = not math.isnan(max_value)
        except ValueError:
            self.config.color_value_max_valid = False

        if self.config.color_value_min_valid and self.config.color_value_max_valid:
            self.config.color_range = [min_value, max_value]

    def _parse_comparison(self):
        for comp_type in ("ctrl", "test", "diff", "comp1", "comp2"):
            suffix = f"_{comp_type}"
            if self.variable_name.endswith(suffix):
                return self.variable_name[: -len(suffix)], comp_type
        return self.variable_name, None

    def _ctrl_test_visible(self):
        selected_columns = getattr(self.state, "selected_columns", None)
        if not selected_columns:
            return False
        return "ctrl" in selected_columns and "test" in selected_columns

    def _get_ctrl_test_combined_range(self):
        base_name, comp_type = self._parse_comparison()
        if comp_type not in ("ctrl", "test"):
            return None
        if not self._ctrl_test_visible():
            return None

        data_info = self.source.views["atmosphere_data"].GetCellDataInformation()
        ctrl_array = data_info.GetArray(f"{base_name}_ctrl")
        test_array = data_info.GetArray(f"{base_name}_test")
        if not ctrl_array or not test_array:
            return None

        ctrl_range = ctrl_array.GetRange()
        test_range = test_array.GetRange()
        if (
            ctrl_range is None
            or test_range is None
            or math.isnan(ctrl_range[0])
            or math.isnan(ctrl_range[1])
            or math.isnan(test_range[0])
            or math.isnan(test_range[1])
        ):
            return None

        return [min(ctrl_range[0], test_range[0]), max(ctrl_range[1], test_range[1])]

    def update_color_range(self, *_):
        if self.config.override_range:
            skip_update = False
            if math.isnan(self.config.color_range[0]):
                skip_update = True
                self.config.color_value_min_valid = False

            if math.isnan(self.config.color_range[1]):
                skip_update = True
                self.config.color_value_max_valid = False

            if skip_update:
                return

            self.lut.RescaleTransferFunction(*self.config.color_range)
        else:
            data_range = self._get_ctrl_test_combined_range()
            if data_range is None:
                self.representation.RescaleTransferFunctionToDataRange(False, True)
                data_array = (
                    self.source.views["atmosphere_data"]
                    .GetCellDataInformation()
                    .GetArray(self.variable_name)
                )
                if data_array:
                    data_range = data_array.GetRange()

            if data_range is not None:
                self.config.color_range = data_range
                self.config.color_value_min = str(data_range[0])
                self.config.color_value_max = str(data_range[1])
                self.config.color_value_min_valid = True
                self.config.color_value_max_valid = True
                self.lut.RescaleTransferFunction(*data_range)
        self.render()

    def _build_ui(self):
        with DivLayout(
            self.server, template_name=self.name, connect_parent=False, classes="h-100"
        ) as self.ui:
            self.ui.root.classes = "h-100"
            with v3.VCard(
                variant="tonal",
                style=(
                    "active_layout !== 'auto_layout' ? `height: calc(100% - ${top_padding}px;` : 'overflow-hidden'",
                ),
                tile=("active_layout !== 'auto_layout'",),
            ):
                with v3.VRow(
                    dense=True,
                    classes="ma-0 pa-0 bg-black opacity-90 d-flex align-center",
                    style="flex-wrap: nowrap;",
                ):
                    tview.create_size_menu(self.name, self.config)
                    html.Div(
                        self.variable_name,
                        classes="text-subtitle-2 pr-2",
                        style="user-select: none; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; min-width: 0;",
                    )

                    v3.VIcon(
                        "mdi-lock-outline",
                        size="x-small",
                        v_show=("lock_views", False),
                        style="transform: scale(0.75);",
                    )

                    v3.VSpacer()
                    html.Div(
                        "t = {{ time_idx }}",
                        classes="text-caption px-1",
                        v_if="timestamps.length > 1",
                    )
                    if self.variable_type == "m":
                        html.Div(
                            "[k = {{ midpoint_idx }}]",
                            classes="text-caption px-1",
                            v_if="midpoints.length > 1",
                        )
                    if self.variable_type == "i":
                        html.Div(
                            "[k = {{ interface_idx }}]",
                            classes="text-caption px-1",
                            v_if="interfaces.length > 1",
                        )
                    # v3.VSpacer()
                    # html.Div(
                    #     "avg = {{"
                    #     f"fields_avgs['{self.variable_name}']?.toExponential(2) || 'N/A'"
                    #     "}}",
                    #     classes="text-caption px-1",
                    # )

                with html.Div(
                    style=(
                        """
                        {
                            aspectRatio: active_layout === 'auto_layout' ? aspect_ratio : null,
                            height: active_layout !== 'auto_layout' ? 'calc(100% - 2.4rem)' : null,
                            pointerEvents: lock_views ? 'none': null,
                        }
                        """,
                    ),
                ):
                    pvw.VtkRemoteView(
                        self.view, interactive_ratio=1, ctx_name=self.name
                    )

                tview.create_bottom_bar(self.config, self.update_color_preset)


class ViewManager(TrameComponent):
    def __init__(self, server, source):
        super().__init__(server)
        self.source = source
        self._var2view = {}
        self._camera_sync_in_progress = False
        self._last_vars = {}
        self._active_configs = {}

        pvw.initialize(self.server)

        self.state.luts_normal = [
            {"name": k, "url": v["normal"], "safe": k in COLOR_BLIND_SAFE}
            for k, v in COLORBAR_CACHE.items()
        ]
        self.state.luts_inverted = [
            {"name": k, "url": v["inverted"], "safe": k in COLOR_BLIND_SAFE}
            for k, v in COLORBAR_CACHE.items()
        ]

        # Sort lists
        self.state.luts_normal.sort(key=lut_name)
        self.state.luts_inverted.sort(key=lut_name)

    def refresh_ui(self, **_):
        for view in self._var2view.values():
            view._build_ui()

    def reset_camera(self):
        views = list(self._var2view.values())
        for view in views:
            view.disable_render = True

        for view in views:
            view.reset_camera()

        for view in views:
            view.disable_render = False

    def render(self):
        for view in list(self._var2view.values()):
            view.render()

    def update_color_range(self):
        for view in list(self._var2view.values()):
            view.update_color_range()

    def get_view(self, variable_name, variable_type):
        view = self._var2view.get(variable_name)
        if view is None:
            view = self._var2view.setdefault(
                variable_name,
                VariableView(self.server, self.source, variable_name, variable_type),
            )
            view.set_camera_modified(self.sync_camera)

        return view

    def sync_camera(self, camera, *_):
        if self._camera_sync_in_progress:
            return
        self._camera_sync_in_progress = True

        for var_view in self._var2view.values():
            cam = var_view.camera
            if cam is camera:
                continue
            cam.DeepCopy(camera)
            var_view.render()

        self._camera_sync_in_progress = False

    @controller.set("swap_variables")
    def swap_variable(self, variable_a, variable_b):
        config_a = self._active_configs[variable_a]
        config_b = self._active_configs[variable_b]
        config_a.order, config_b.order = config_b.order, config_a.order
        config_a.size, config_b.size = config_b.size, config_a.size
        config_a.offset, config_b.offset = config_b.offset, config_a.offset
        config_a.break_row, config_b.break_row = config_b.break_row, config_a.break_row

    def apply_size(self, n_cols):
        if not self._last_vars:
            return

        if n_cols == 0:
            # Auto based on group size
            if self.state.layout_grouped:
                for var_type in "smi":
                    var_names = self._last_vars[var_type]
                    total_size = len(var_names)

                    if total_size == 0:
                        continue

                    size = auto_size_to_col(total_size)
                    for name in var_names:
                        config = self.get_view(name, var_type).config
                        config.size = size

            else:
                size = auto_size_to_col(len(self._active_configs))
                for config in self._active_configs.values():
                    config.size = size
        else:
            # uniform size
            for config in self._active_configs.values():
                config.size = COL_SIZE_LOOKUP[n_cols]

    def build_auto_layout(self, variables=None):
        if variables is None:
            variables = self._last_vars

        self._last_vars = variables

        # Create UI based on variables
        self.state.swap_groups = {}
        # Build a lookup from type name to color from state.variable_types
        type_to_color = {vt["name"]: vt["color"] for vt in self.state.variable_types}
        with DivLayout(self.server, template_name="auto_layout") as self.ui:
            if self.state.layout_grouped:
                with v3.VCol(classes="pa-1"):
                    for var_type in variables.keys():
                        var_names = variables[var_type]
                        total_size = len(var_names)
                        print(total_size, var_names, var_type)

                        if total_size == 0:
                            continue

                        for var_name in var_names:
                            # Define all possible comparison types
                            all_comp_types = ["ctrl", "test", "diff", "comp1", "comp2"]
                            # Build the full list of comparisons
                            var_comps = [f"{var_name}_{comp_type}" for comp_type in all_comp_types]

                            # Look up color from variable_types to match chip colors
                            border_color = type_to_color.get(str(var_type), "primary")
                            with v3.VAlert(
                                border="start",
                                classes="pr-1 py-1 pl-3 mb-1",
                                variant="flat",
                                border_color=border_color,
                            ):
                                with v3.VRow(dense=True):
                                    for comp_type, name in zip(all_comp_types, var_comps):
                                        print("Creating view for", name)
                                        view = self.get_view(name, var_type)
                                        view.config.swap_group = sorted(
                                            [n for n in var_comps if n != name]
                                        )
                                        with view.config.provide_as("config"):
                                            # Only show column if it's in selected_columns
                                            with v3.Template(v_if=f"selected_columns.includes('{comp_type}')"):
                                                v3.VCol(
                                                    v_if="config.break_row",
                                                    cols=12,
                                                    classes="pa-0",
                                                    style=("`order: ${config.order};`",),
                                                )
                                                # For flow handling
                                                with v3.Template(v_if="!config.size"):
                                                    v3.VCol(
                                                        v_for="i in config.offset",
                                                        key="i",
                                                        style=("{ order: config.order }",),
                                                    )
                                                with v3.VCol(
                                                    offset=("config.offset * config.size",),
                                                    cols=("Math.floor(12 / selected_columns.length)",),
                                                    # cols=("config.size",),
                                                    style=("`order: ${config.order};`",),
                                                ):
                                                    client.ServerTemplate(name=view.name)
            else:
                all_names = [name for names in variables.values() for name in names]
                with v3.VRow(dense=True, classes="pa-2"):
                    for var_type in variables.keys():
                        var_names = variables[var_type]
                        for name in var_names:
                            view = self.get_view(name, var_type)
                            view.config.swap_group = sorted(
                                [n for n in all_names if n != name]
                            )
                            with view.config.provide_as("config"):
                                v3.VCol(
                                    v_if="config.break_row",
                                    cols=12,
                                    classes="pa-0",
                                    style=("`order: ${config.order};`",),
                                )

                                # For flow handling
                                with v3.Template(v_if="!config.size"):
                                    v3.VCol(
                                        v_for="i in config.offset",
                                        key="i",
                                        style=("{ order: config.order }",),
                                    )
                                with v3.VCol(
                                    offset=(
                                        "config.size ? config.offset * config.size : 0",
                                    ),
                                    cols=("config.size",),
                                    style=("`order: ${config.order};`",),
                                ):
                                    client.ServerTemplate(name=view.name)

        # Assign any missing order
        self._active_configs = {}
        existed_order = set()
        order_max = 0
        orders_to_update = []
        for var_type in variables.keys():
            var_names = variables[var_type]
            for var_name in var_names:
                # Define all possible comparison types
                all_comp_types = ["ctrl", "test", "diff", "comp1", "comp2"]
                # Build the full list of comparisons
                var_comps = [f"{var_name}_{comp_type}" for comp_type in all_comp_types]

                for name in var_comps:
                    config = self.get_view(name, var_type).config
                    self._active_configs[name] = config
                    if config.order:
                        order_max = max(order_max, config.order)
                        assert config.order not in existed_order, "Order already assigned"
                        existed_order.add(config.order)
                    else:
                        orders_to_update.append(config)

        next_order = order_max + 1
        for config in orders_to_update:
            config.order = next_order
            next_order += 1
