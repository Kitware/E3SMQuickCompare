import math

import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
from trame.app import TrameComponent, dataclass
from trame.app.dataclass import watch
from trame.dataclasses.colormaps import ColormapConfig
from trame.ui.html import DivLayout
from trame.widgets import colormaps, html, rca
from trame.widgets import vuetify3 as v3
from vtkmodules.vtkRenderingCore import (
    vtkActor,
    vtkPolyDataMapper,
    vtkRenderer,
)


class ViewConfiguration(dataclass.StateDataModel):
    variable: str = dataclass.Sync(str)
    base_variable: str = dataclass.Sync(str, "")
    label: str = dataclass.Sync(str, "")
    order: int = dataclass.Sync(int, 0)
    size: int = dataclass.Sync(int, 4)
    offset: int = dataclass.Sync(int, 0)
    break_row: bool = dataclass.Sync(bool, False)
    swap_group: list[dict[str, str]] = dataclass.Sync(list[dict[str, str]], list)


class CompareColormapConfig(ColormapConfig):
    def __init__(self, *args, default_range_fn, **kwargs):
        self._default_range_fn = default_range_fn
        self._syncing_auto_abs_max = False
        self._diverging_manual_override = False
        super().__init__(*args, **kwargs)

    @property
    def saved_abs_max(self):
        """Hand-typed abs_max, or "" meaning "re-derive it from the data"."""
        return self.abs_max if self._diverging_manual_override else ""

    def _parse_abs_max(self):
        try:
            v = float(str(self.abs_max).strip())
        except (TypeError, ValueError):
            return None
        return None if (math.isnan(v) or v <= 0) else v

    def update_color_range(self):
        if self.diverging and self._diverging_manual_override:
            abs_max = self._parse_abs_max()
            if abs_max is None:
                self.abs_max_valid = False
                return
            self.abs_max_valid = True
            data_range = (-abs_max, abs_max)
        elif self.override_range and not self.diverging:
            nan_min = math.isnan(self.color_range[0])
            nan_max = math.isnan(self.color_range[1])
            if nan_min:
                self.color_value_min_valid = False
            if nan_max:
                self.color_value_max_valid = False
            if nan_min or nan_max:
                return
            data_range = self.color_range
        else:
            data_range = self._default_range_fn()
            if data_range is None:
                return
            if self.diverging:
                self._sync_abs_max_from_range(data_range)

        self.color_range = data_range
        self.color_value_min = str(data_range[0])
        self.color_value_max = str(data_range[1])
        self.color_value_min_valid = True
        self.color_value_max_valid = True

        self.update_color_preset(
            self.preset,
            self.invert,
            self.use_log_scale,
            self.discrete_log,
            self.n_discrete_colors,
            self.n_ticks,
        )

    @watch("diverging")
    def _on_diverging_change(self, diverging):
        if diverging:
            if self.use_log_scale == "log":
                self.use_log_scale = "linear"

        self._diverging_manual_override = False
        self.override_range = False
        self.update_color_range()

    def _sync_abs_max_from_range(self, data_range):
        if self._diverging_manual_override or data_range is None:
            return

        max_abs = max(abs(data_range[0]), abs(data_range[1]))
        self.abs_max_valid = True
        next_abs_max = str(max_abs)
        if self.abs_max == next_abs_max:
            return
        self._syncing_auto_abs_max = True
        self.abs_max = next_abs_max

    @watch("abs_max")
    def _on_abs_max_change(self, abs_max):
        if self._syncing_auto_abs_max:
            self._syncing_auto_abs_max = False
            return

        raw_value = str(abs_max).strip()

        if not self.diverging:
            return

        if raw_value == "":
            self.abs_max_valid = True
            self._diverging_manual_override = False
            self.override_range = False
            self.update_color_range()
            return

        abs_max_value = self._parse_abs_max()
        self.abs_max_valid = abs_max_value is not None
        if abs_max_value is None:
            return

        self._diverging_manual_override = True
        self.override_range = False
        self.update_color_range()


class VariableView(TrameComponent):
    def __init__(self, server, source, view_spec, variable_type, camera):
        super().__init__(server)
        self.source = source
        self.view_spec = view_spec
        self.array_name = view_spec["array_name"]
        self.base_variable = view_spec["base_variable"]
        self.role = view_spec["role"]
        self.comparison_mode = view_spec.get("comparison_mode", "multi-sim")
        self.comparison_type = view_spec.get("comparison_type", "diff")
        self.display_label = view_spec["label"]
        self.variable_type = variable_type
        self.config = ViewConfiguration(server, variable=self.array_name)
        self.config.base_variable = self.base_variable
        self.config.label = self.display_label
        self.name = f"view_{self.array_name}"
        self._bounds_key = f"{self.name}_bounds"
        self._size = (0, 0)

        self.disable_render = False

        self.renderer = vtkRenderer()
        self.renderer.SetActiveCamera(camera)
        self.renderer.SetBackground(1, 1, 1)
        self._camera = camera
        self.mapper = vtkPolyDataMapper()
        self.actor = vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.ForceOpaqueOn()
        self.renderer.AddActor(self.actor)

        # Lookup table color management
        self.colormap = CompareColormapConfig(
            server,
            mapper=self.mapper,
            data_array_fn=lambda: self._get_data_array(self.array_name),
            default_range_fn=self._get_default_range,
        ).set_data_array(
            self.array_name, lambda: self._get_data_array(self.array_name), "cell"
        )

        if self.role in ("control", "test", "source"):
            self.colormap.preset = "Rainbow Desaturated"

        if self.role == "diff":
            self.colormap.preset = "Cool to Warm (Extended)"

        if self.role in ("comp1", "comp2"):
            self.colormap.preset = "Blue Orange (divergent)"

        self._sync_diverging_mode()
        self.colormap.watch(["mapper_change"], lambda *_: self.render())

        self._connect_pipeline_input()

        # Add shared annotation actors
        continents_actor = source.continent.actor
        if continents_actor is not None:
            self.renderer.AddActor(continents_actor)
        grid_lines_actor = source.grid_lines.actor
        if grid_lines_actor is not None:
            self.renderer.AddActor(grid_lines_actor)
        perimeter_actor = source.grid_lines.perimeter_actor
        if perimeter_actor is not None:
            self.renderer.AddActor(perimeter_actor)

        # GUI
        self._build_ui()

    def _connect_pipeline_input(self):
        atmosphere_data = self.source.data_reader.vtk_geometry
        if atmosphere_data is not None:
            self.mapper.SetInputConnection(atmosphere_data.output_port)

    def update_view_spec(self, view_spec):
        self.view_spec = view_spec
        self.base_variable = view_spec["base_variable"]
        self.role = view_spec["role"]
        self.comparison_mode = view_spec.get("comparison_mode", "multi-sim")
        self.comparison_type = view_spec.get("comparison_type", "diff")
        self.display_label = view_spec["label"]
        self.config.base_variable = self.base_variable
        self.config.label = self.display_label
        self._sync_diverging_mode()
        self._connect_pipeline_input()

    def _sync_diverging_mode(self):
        is_diverging = self.role in ("diff", "comp1", "comp2")
        self.colormap.diverging = is_diverging
        if is_diverging:
            self.colormap.override_range = False

    @property
    def bounds(self):
        return self.state[self._bounds_key]

    @bounds.setter
    def bounds(self, value):
        self.renderer.SetViewport(*value)
        with self.state as state:
            state[self._bounds_key] = value

    def update_size(self, size):
        new_size = (int(size["w"] * size["p"]), int(size["h"] * size["p"]))
        if self._size != new_size:
            self._size = new_size
            self.ctrl.size_update()

    @property
    def size(self):
        return self._size

    def render(self):
        if self.disable_render or not self.ctx.view:
            return
        self.ctx.view.update()

    @property
    def camera(self):
        return self._camera

    def edit_colormap(self):
        self.ctrl.edit_lookup_table(
            self.colormap._id,
            self.array_name,
            f"{self.base_variable} — {self.display_label}",
        )

    def reset_camera(self):
        self.renderer.ResetCameraScreenSpace(0.9)
        self.renderer.ResetCameraClippingRange()
        self.render()

    @staticmethod
    def _is_finite_range(data_range):
        if data_range is None or len(data_range) < 2:
            return False
        return math.isfinite(data_range[0]) and math.isfinite(data_range[1])

    @staticmethod
    def _max_abs_from_ranges(ranges):
        max_abs = None
        for data_range in ranges:
            if data_range is None:
                continue
            candidate = max(abs(data_range[0]), abs(data_range[1]))
            max_abs = candidate if max_abs is None else max(max_abs, candidate)
        if max_abs is None:
            return None
        return (-max_abs, max_abs)

    def _get_data_array(self, array_name):
        return self.source.data_reader.get_cell_data_array(array_name)

    def _get_data_array_range(self, array_name):
        data_array = self._get_data_array(array_name)
        if data_array is None:
            return None
        data_range = data_array.GetRange()
        if self._is_finite_range(data_range):
            return data_range
        return None

    def _get_multi_sim_default_range(self):
        view_specs = self.source.data_reader.get_view_specs(
            self.base_variable,
            "multi-sim",
            self.comparison_type,
        )

        if self.comparison_type == "source":
            range_min = None
            range_max = None
            for view_spec in view_specs:
                data_range = self._get_data_array_range(view_spec["array_name"])
                if data_range is None:
                    continue
                range_min = (
                    data_range[0]
                    if range_min is None
                    else min(range_min, data_range[0])
                )
                range_max = (
                    data_range[1]
                    if range_max is None
                    else max(range_max, data_range[1])
                )

            if range_min is not None and range_max is not None:
                return (range_min, range_max)

        if (
            self.comparison_type in ("diff", "comp1", "comp2")
            and self.role != "control"
        ):
            comparison_ranges = []
            for view_spec in view_specs:
                if view_spec["role"] == "control":
                    continue
                data_range = self._get_data_array_range(view_spec["array_name"])
                if data_range is not None:
                    comparison_ranges.append(data_range)

            centered = self._max_abs_from_ranges(comparison_ranges)
            if centered is not None:
                return centered

        data_range = self._get_data_array_range(self.array_name)
        if self.role in ("diff", "comp1", "comp2"):
            return self._max_abs_from_ranges([data_range])
        return data_range

    def _get_two_sim_default_range(self):
        two_sim_specs = self.source.data_reader.get_view_specs(
            self.base_variable,
            "two-sim",
            self.comparison_type,
            ["ctrl", "test", "diff", "comp1", "comp2"],
        )
        spec_by_role = {spec["role"]: spec for spec in two_sim_specs}

        if self.role in ("control", "test"):
            ctrl_spec = spec_by_role.get("control")
            test_spec = spec_by_role.get("test")
            if ctrl_spec and test_spec:
                ctrl_range = self._get_data_array_range(ctrl_spec["array_name"])
                test_range = self._get_data_array_range(test_spec["array_name"])
                if ctrl_range is not None and test_range is not None:
                    return (
                        min(ctrl_range[0], test_range[0]),
                        max(ctrl_range[1], test_range[1]),
                    )

        if self.role == "diff":
            diff_spec = spec_by_role.get("diff")
            if diff_spec:
                diff_range = self._get_data_array_range(diff_spec["array_name"])
                if diff_range is not None:
                    return self._max_abs_from_ranges([diff_range])

        if self.role in ("comp1", "comp2"):
            comp_ranges = []
            for role in ("comp1", "comp2"):
                comp_spec = spec_by_role.get(role)
                if not comp_spec:
                    continue
                comp_range = self._get_data_array_range(comp_spec["array_name"])
                if comp_range is not None:
                    comp_ranges.append(comp_range)

            centered = self._max_abs_from_ranges(comp_ranges)
            if centered is not None:
                return centered

        return self._get_data_array_range(self.array_name)

    def _get_default_range(self):
        if self.comparison_mode == "two-sim":
            return self._get_two_sim_default_range()
        return self._get_multi_sim_default_range()

    def _build_ui(self):
        with DivLayout(
            self.server, template_name=self.name, connect_parent=False, classes="h-100"
        ) as self.ui:
            self.ui.root.classes = "h-100"
            with v3.VCard(
                variant="tonal",
                style=(
                    "active_layout !== 'auto_layout' ? `height: calc(100% - ${toolbar_size?.size?.height || 0}px;` : 'overflow-hidden'",
                ),
                tile=("active_layout !== 'auto_layout'",),
                raw_attrs=[f'data-field-name="{self.array_name}"'],
                v_on_mouseenter=f"hover_info = '{self.array_name}'",
                v_on_mouseleave="hover_info = null; probe_table = null",
            ):
                with v3.VRow(
                    dense=True,
                    classes="ma-0 pa-0 bg-white text-black d-flex align-center border-b-thin",
                    style="flex-wrap: nowrap;",
                ):
                    with self.config.provide_as("config"):
                        with html.Div(
                            "{{ config.label }}",
                            classes="text-subtitle-2 px-2 text-truncate",
                            style="user-select: none; min-width: 0;",
                            title=("config.label",),
                        ):
                            with v3.VMenu(activator="parent"):
                                with v3.VList(
                                    density="compact", style="max-height: 40vh;"
                                ):
                                    with self.config.provide_as("config"):
                                        v3.VListItem(
                                            title=("swap.label || swap.name",),
                                            v_for="swap, idx in config.swap_group",
                                            key="swap.name",
                                            click=(
                                                self.ctrl.swap_variables,
                                                "[config.variable, swap.name]",
                                            ),
                                        )

                    v3.VIcon(
                        "mdi-lock-outline",
                        size="x-small",
                        v_show=("lock_views", False),
                        style="transform: scale(0.75);",
                    )
                    v3.VIconBtn(
                        v_tooltip_bottom="'Capture as png'",
                        icon="mdi-camera-outline",
                        size="small",
                        variant="plain",
                        click=f"utils.quickview.capturePanel('{self.array_name}')",
                        style="transform: scale(0.75);",
                    )
                    self.state.setdefault("picking_mode", None)
                    v3.VIconBtn(
                        v_tooltip_bottom="'Extract information on click'",
                        icon="mdi-cursor-default-click-outline",
                        size="small",
                        base_variant="plain",
                        active_variant="tonal",
                        click="picking_mode = (picking_mode === 'click' ? null : 'click')",
                        active=("picking_mode === 'click'",),
                        active_color="primary",
                        hide_overlay=True,
                        rounded=False,
                    )
                    v3.VIconBtn(
                        v_tooltip_bottom="'Extract information on hover'",
                        icon="mdi-cursor-default-gesture-outline",
                        size="small",
                        base_variant="plain",
                        active_variant="tonal",
                        click="picking_mode = (picking_mode === 'hover' ? null : 'hover')",
                        active=("picking_mode === 'hover'",),
                        active_color="primary",
                        hide_overlay=True,
                        rounded=False,
                    )

                    v3.VSpacer()
                    html.Div(
                        "t = {{ time_idx }}",
                        classes="text-caption px-1 text-no-wrap",
                        v_if="timestamps.length > 1",
                    )
                    if self.variable_type == "m":
                        html.Div(
                            "[k = {{ midpoint_idx }}]",
                            classes="text-caption px-1 text-no-wrap",
                            v_if="midpoints.length > 1",
                        )
                    if self.variable_type == "i":
                        html.Div(
                            "[k = {{ interface_idx }}]",
                            classes="text-caption px-1 text-no-wrap",
                            v_if="interfaces.length > 1",
                        )
                    v3.VSpacer()
                    with self.config.provide_as("config"):
                        html.Div(
                            "avg = {{"
                            "fields_avgs[config.variable]?.toExponential(2)"
                            " || fields_avgs[config.base_variable]?.toExponential(2)"
                            " || 'N/A'"
                            "}}",
                            classes="text-caption px-1 text-no-wrap",
                        )

                with v3.VTooltip(
                    classes="tooltip-no-padding",
                    disabled=(f"!picking_mode || hover_info !== '{self.array_name}'",),
                    open_on_hover=False,
                    model_value=(
                        f"picking_mode && !!probe_table && hover_info === '{self.array_name}'",
                    ),
                ):
                    with v3.Template(v_slot_activator="{props}"):
                        with html.Div(
                            v_bind="props",
                            style=(
                                """
                                {
                                    aspectRatio: active_layout === 'auto_layout' ? 1/aspect_ratio : null,
                                    height: active_layout !== 'auto_layout' ? 'calc(100% - 2.4rem)' : null,
                                }
                                """,
                            ),
                        ):
                            rca.ImageRegion(
                                enable_interaction=False,
                                bounds=(self._bounds_key, (0, 0, 1, 1)),
                                size=(self.update_size, "[$event]"),
                                send_mouse_click=(
                                    f"picking_mode === 'click' && hover_info === '{self.array_name}'",
                                ),
                                send_mouse_move=(
                                    f"picking_mode === 'hover' && hover_info === '{self.array_name}'",
                                ),
                                v_on_wheel="window.scrollBy(0, $event.deltaY)",
                            )

                    with html.Div(
                        v_if="picking_mode && !!probe_table",
                        classes="px-3 pt-2 pb-1 d-flex align-center text-caption",
                    ):
                        v3.VIcon("mdi-target", size="small", classes="mr-2")
                        html.Div(
                            "lat: {{ probe_table.lat == null ? 'N/A' : probe_table.lat.toFixed(4) }}",
                            classes="pr-4",
                        )
                        html.Div(
                            "lon: {{ probe_table.lon == null ? 'N/A' : probe_table.lon.toFixed(4) }}",
                        )

                    with html.Div(
                        v_if="picking_mode && !!probe_table",
                        style="max-width: 72vw; overflow-x: auto;",
                    ):
                        with v3.VTable(
                            density="compact",
                            theme="dark",
                            classes="text-no-wrap",
                        ):
                            with html.Tbody():
                                with html.Tr():
                                    html.Td("", classes="font-weight-bold")
                                    html.Td(
                                        "{{ column.label }}",
                                        v_for="column in probe_table.columns",
                                        key="column.key",
                                        classes="font-weight-bold",
                                        style=(
                                            """
                                            {
                                                color: column.active ? '#90caf9' : null,
                                            }
                                            """,
                                        ),
                                    )

                                with html.Tr(
                                    v_for="row in probe_table.rows",
                                    key="row.key",
                                ):
                                    html.Td(
                                        "{{ row.label }}",
                                        style=(
                                            """
                                            {
                                                fontWeight: row.active ? 700 : null,
                                                color: row.active ? '#90caf9' : null,
                                            }
                                            """,
                                        ),
                                    )
                                    with html.Td(
                                        v_for="(cell, index) in row.cells",
                                        key="index",
                                        style=(
                                            """
                                            {
                                                backgroundColor: cell.active ? '#1e3a8a' : null,
                                                border: cell.active ? '1px solid #90caf9' : null,
                                            }
                                            """,
                                        ),
                                    ):
                                        html.Div(
                                            "{{ cell.display || 'N/A' }}",
                                            style=(
                                                """
                                                {
                                                    fontWeight: cell.active ? 700 : null,
                                                    color: cell.active ? '#ffffff' : null,
                                                }
                                                """,
                                            ),
                                        )
                                        html.Div(
                                            "(value: {{ cell.source_display || 'N/A' }})",
                                            v_if="cell.has_source",
                                            classes="text-caption text-medium-emphasis",
                                        )

                with self.colormap.provide_as(self.name):
                    colormaps.HorizontalScalarBar(
                        self.name,
                        has_menu=False,
                        click=self.edit_colormap,
                    )
