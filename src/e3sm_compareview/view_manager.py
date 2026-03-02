import math

from trame.app import TrameComponent
from trame.ui.html import DivLayout
from trame.widgets import paraview as pvw, vuetify3 as v3, client, html
from trame.decorators import controller

from trame_dataclass.core import StateDataModel

from paraview import simple

from e3sm_compareview.components import view as tview
from e3sm_quickview.presets import COLOR_BLIND_SAFE
from e3sm_quickview.utils.color import COLORBAR_CACHE, get_cached_colorbar_image


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
    label: str = ""
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
    def __init__(self, server, source, view_spec, variable_type):
        super().__init__(server)
        self.source = source
        self.view_spec = view_spec
        self.array_name = view_spec["array_name"]
        self.base_variable = view_spec["base_variable"]
        self.role = view_spec["role"]
        self.comparison_mode = view_spec.get("comparison_mode", "diff")
        self.display_label = view_spec["label"]
        self.variable_type = variable_type
        self.config = ViewConfiguration(server, variable=self.array_name)
        self.config.label = self.display_label
        self.name = f"view_{self.array_name}"

        if self.role == "control":
            self.config.preset = "navia"
        elif self.role == "diff":
            self.config.preset = "Cool to Warm (Extended)"
        elif self.role in ("comp1", "comp2"):
            self.config.preset = "bam"
            self.config.invert = True

        self.view = simple.CreateRenderView()
        self.view.GetRenderWindow().SetOffScreenRendering(True)
        self.view.InteractionMode = "2D"
        self.view.OrientationAxesVisibility = 0
        self.view.UseColorPaletteForBackground = 0
        self.view.BackgroundColorMode = "Single Color"
        self.view.Background = [1, 1, 1]
        self.view.Background2 = [1, 1, 1]
        self.view.CameraParallelProjection = 1
        self.view.Size = 0  # make the interactive widget non responsive
        self.representation = simple.Show(
            proxy=source.views["atmosphere_data"],
            view=self.view,
        )

        # Lookup table color management
        simple.ColorBy(self.representation, ("CELLS", self.array_name))
        self.lut = simple.GetColorTransferFunction(self.array_name)
        self.lut.NanOpacity = 0.0

        self.view.ResetActiveCameraToNegativeZ()
        self.view.ResetCamera(True, 0.9)
        self.disable_render = False

        # Add annotations to the view
        # - continents
        globe = source.views["continents"]
        rep_globe = simple.Show(globe, self.view)
        simple.ColorBy(rep_globe, None)
        rep_globe.SetRepresentationType("Wireframe")
        rep_globe.RenderLinesAsTubes = 1
        rep_globe.LineWidth = 1.0
        rep_globe.AmbientColor = [0.67, 0.67, 0.67]
        rep_globe.DiffuseColor = [0.67, 0.67, 0.67]
        self.rep_globe = rep_globe

        # - gridlines
        grid_lines = source.views["grid_lines"]
        rep_grid = simple.Show(grid_lines, self.view)
        rep_grid.SetRepresentationType("Wireframe")
        rep_grid.AmbientColor = [0.67, 0.67, 0.67]
        rep_grid.DiffuseColor = [0.67, 0.67, 0.67]
        rep_grid.Opacity = 0.4
        self.rep_grid = rep_grid

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

    def update_view_spec(self, view_spec):
        self.view_spec = view_spec
        self.base_variable = view_spec["base_variable"]
        self.role = view_spec["role"]
        self.comparison_mode = view_spec.get("comparison_mode", "diff")
        self.display_label = view_spec["label"]
        self.config.label = self.display_label

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

    @staticmethod
    def _is_finite_range(data_range):
        if data_range is None or len(data_range) < 2:
            return False
        return math.isfinite(data_range[0]) and math.isfinite(data_range[1])

    def _get_default_range(self):
        data_info = self.source.views["atmosphere_data"].GetCellDataInformation()
        if self.role != "control":
            max_abs = None
            for view_spec in self.source.get_view_specs(
                self.base_variable, self.comparison_mode
            ):
                if view_spec["role"] == "control":
                    continue
                data_array = data_info.GetArray(view_spec["array_name"])
                if not data_array:
                    continue
                data_range = data_array.GetRange()
                if not self._is_finite_range(data_range):
                    continue
                candidate = max(abs(data_range[0]), abs(data_range[1]))
                max_abs = candidate if max_abs is None else max(max_abs, candidate)
            if max_abs is not None:
                return [-max_abs, max_abs]
            return None

        data_array = data_info.GetArray(self.array_name)
        if not data_array:
            return None

        data_range = data_array.GetRange()
        if self._is_finite_range(data_range):
            return list(data_range)
        return None

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
            data_range = self._get_default_range()
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
                    classes="ma-0 pa-0 bg-white text-black d-flex align-center border-b-thin",
                    style="flex-wrap: nowrap;",
                ):
                    tview.create_size_menu(self.name, self.config)
                    with self.config.provide_as("config"):
                        html.Div(
                            "{{ config.label }}",
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

    def _active_views(self):
        if self._active_configs:
            return [self._var2view[name] for name in self._active_configs]
        return list(self._var2view.values())

    def _resolve_view_spec(self, view_spec):
        if not isinstance(view_spec, str):
            return view_spec

        return (
            self.source.get_array_metadata(view_spec)
            or next(
                iter(self.source.get_view_specs(view_spec, self.state.comparison_mode)),
                None,
            )
            or {
                "array_name": view_spec,
                "base_variable": view_spec,
                "role": "control",
                "label": view_spec,
            }
        )

    def reset_camera(self):
        views = self._active_views()
        for view in views:
            view.disable_render = True

        for view in views:
            view.reset_camera()

        for view in views:
            view.disable_render = False

    def render(self):
        for view in self._active_views():
            view.render()

    def update_color_range(self):
        for view in self._active_views():
            view.update_color_range()

    def refresh_view_specs(self, variables=None):
        if variables is None:
            variables = self._last_vars

        for var_type, var_names in variables.items():
            for var_name in var_names:
                for view_spec in self.get_view_specs(var_name):
                    view = self._var2view.get(view_spec["array_name"])
                    if view is not None:
                        view.update_view_spec(view_spec)

    def get_view(self, view_spec, variable_type):
        view_spec = self._resolve_view_spec(view_spec)
        array_name = view_spec["array_name"]
        view = self._var2view.get(array_name)
        if view is None:
            view = self._var2view.setdefault(
                array_name,
                VariableView(self.server, self.source, view_spec, variable_type),
            )
            view.set_camera_modified(self.sync_camera)
        else:
            view.update_view_spec(view_spec)

        return view

    def get_view_specs(self, variable_name):
        return self.source.get_view_specs(variable_name, self.state.comparison_mode)

    def sync_camera(self, camera, *_):
        if self._camera_sync_in_progress:
            return
        self._camera_sync_in_progress = True

        for var_view in self._active_views():
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
            # Auto size views based on the number of comparison panels being shown.
            if self.state.layout_grouped:
                for var_type, var_names in self._last_vars.items():
                    for var_name in var_names:
                        view_specs = self.get_view_specs(var_name)
                        if not view_specs:
                            continue
                        size = auto_size_to_col(len(view_specs))
                        for view_spec in view_specs:
                            self.get_view(view_spec, var_type).config.size = size
            else:
                size = auto_size_to_col(len(self._active_configs))
                for config in self._active_configs.values():
                    config.size = size
        else:
            # Apply a uniform size to all active views.
            for config in self._active_configs.values():
                config.size = COL_SIZE_LOOKUP[n_cols]

    def build_auto_layout(self, variables=None):
        if variables is None:
            variables = self._last_vars

        self._last_vars = variables

        # Create UI based on the selected variables.
        self.state.swap_groups = {}
        # Build a lookup from variable type to the matching group border color.
        type_to_color = {vt["name"]: vt["color"] for vt in self.state.variable_types}
        with DivLayout(self.server, template_name="auto_layout") as self.ui:
            if self.state.layout_grouped:
                with v3.VCol(classes="pa-1"):
                    for var_type, var_names in variables.items():
                        for var_name in var_names:
                            view_specs = self.get_view_specs(var_name)
                            if not view_specs:
                                continue

                            border_color = type_to_color.get(str(var_type), "primary")
                            with v3.VAlert(
                                border="start",
                                classes="pr-1 py-1 pl-3 mb-1",
                                variant="flat",
                                border_color=border_color,
                            ):
                                html.Div(
                                    var_name,
                                    classes="text-subtitle-2 font-weight-medium mb-1",
                                )
                                with v3.VRow(dense=True):
                                    views_per_row = min(len(view_specs), 3)
                                    group_cols = max(1, math.floor(12 / views_per_row))
                                    group_names = [
                                        view_spec["array_name"] for view_spec in view_specs
                                    ]
                                    for order, view_spec in enumerate(view_specs, start=1):
                                        view = self.get_view(view_spec, var_type)
                                        view.config.order = order
                                        view.config.swap_group = sorted(
                                            [
                                                name
                                                for name in group_names
                                                if name != view_spec["array_name"]
                                            ]
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
                                                offset=("config.offset * config.size",),
                                                cols=group_cols,
                                                style=("`order: ${config.order};`",),
                                            ):
                                                client.ServerTemplate(name=view.name)
            else:
                all_names = []
                for var_name_list in variables.values():
                    for var_name in var_name_list:
                        all_names.extend(
                            [
                                view_spec["array_name"]
                                for view_spec in self.get_view_specs(var_name)
                            ]
                        )
                with v3.VRow(dense=True, classes="pa-2"):
                    for var_type, var_names in variables.items():
                        for name in var_names:
                            for view_spec in self.get_view_specs(name):
                                view = self.get_view(view_spec, var_type)
                                view.config.swap_group = sorted(
                                    [
                                        array_name
                                        for array_name in all_names
                                        if array_name != view_spec["array_name"]
                                    ]
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

        # Assign any missing order.
        self._active_configs = {}
        existed_order = set()
        order_max = 0
        orders_to_update = []
        for var_type, var_names in variables.items():
            for var_name in var_names:
                for view_spec in self.get_view_specs(var_name):
                    config = self.get_view(view_spec, var_type).config
                    name = view_spec["array_name"]
                    self._active_configs[name] = config
                    if config.order:
                        order_max = max(order_max, config.order)
                        assert (
                            config.order not in existed_order
                        ), "Order already assigned"
                        existed_order.add(config.order)
                    else:
                        orders_to_update.append(config)

        next_order = order_max + 1
        for config in orders_to_update:
            config.order = next_order
            next_order += 1
