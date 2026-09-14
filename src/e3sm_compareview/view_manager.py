import asyncio
import math

from e3sm_compareview.comparison import MULTI_SIM_COMPARISON_LABELS
from paraview.modules.vtkPVVTKExtensionsInteractionStyle import (
    vtkPVInteractorStyle,
    vtkPVTrackballZoom,
    vtkTrackballPan,
)
from e3sm_quickview.utils import debounce
from trame.app import TrameComponent
from trame.decorators import controller
from trame.ui.html import DivLayout
from trame.widgets import client, colormaps, html, rca
from trame.widgets import vuetify3 as v3
from vtkmodules.vtkRenderingCore import (
    vtkCamera,
    vtkCellPicker,
    vtkRenderWindow,
    vtkRenderWindowInteractor,
)

from e3sm_compareview.view_panel import VariableView


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


MAX_PROBE_COLUMNS = 4


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


class ViewManager(TrameComponent):
    def __init__(self, server, source):
        super().__init__(server)
        self.use_image_stream = True
        self._camera = vtkCamera(parallel_projection=1)
        self._render_window = vtkRenderWindow()
        self._render_window.OffScreenRenderingOn()
        self._picker = vtkCellPicker(tolerance=0.0005)
        self._style = vtkPVInteractorStyle()
        self._style.AddManipulator(
            vtkPVTrackballZoom(
                button=3,
                shift=0,
                control=0,
            )
        )
        self._style.AddManipulator(
            vtkPVTrackballZoom(
                button=1,
                shift=1,
                control=0,
            )
        )
        self._style.AddManipulator(
            vtkTrackballPan(
                button=1,
                shift=0,
                control=0,
            )
        )
        self._render_window_interactor = vtkRenderWindowInteractor(
            interactor_style=self._style
        )
        self._render_window_interactor.SetRenderWindow(self._render_window)

        self.loop = asyncio.get_event_loop()
        self.layout_dirty = True
        self.pending_reset_camera = 1
        self.pending_render = False
        self.source = source
        self._var2view = {}
        self._last_vars = {}
        self._active_configs = {}
        self._group_orders = {}
        self._n_cols = None

        rca.initialize(self.server)
        colormaps.initialize(self.server)

        self.state.hover_info = None
        self.state.probe_table = None

        self.ctrl.on_server_ready.add(self._post_init)

    def refresh_ui(self, **_):
        for view in self._var2view.values():
            view._build_ui()

    def _post_init(self, *_, **__):
        self._render_window_interactor.AddObserver("ModifiedEvent", self._on_hover)

    @debounce.debounce(0.2)
    def _on_hover(self, *_):
        with self.state:
            self.state.probe_table = None

            hover_info = self.state.hover_info
            view = self._var2view.get(hover_info)
            if view is None:
                return

            x, y = self._render_window_interactor.GetEventPosition()
            self._picker.Pick(x, y, 0, view.renderer)
            if self._picker.cell_id < 0:
                return

            cell_id = self._picker.cell_id
            data_info = {}
            dataset = self._picker.GetDataSet()
            if dataset:
                cell_data = dataset.cell_data
                for index in range(cell_data.number_of_arrays):
                    array = cell_data.GetArray(index)
                    data_info[array.name] = array.GetTuple(cell_id)

            def picked_value(array_name):
                values = data_info.get(array_name)
                if not values:
                    return None
                value = values[0]
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    return str(value)
                if math.isnan(value):
                    return None
                return f"{value:.6g}"

            is_multi_sim = self.state.comparison_mode == "multi-sim"
            comparison_type = self.state.comparison_type
            show_source = is_multi_sim and comparison_type != "source"
            control_reads_zero = is_multi_sim and comparison_type in (
                "diff",
                "comp1",
                "comp2",
            )
            hovered_variable = view.base_variable

            columns = []
            for variable_name in self._probe_variables(hovered_variable):
                view_specs = self.get_view_specs(variable_name)
                if not view_specs:
                    continue

                source_by_path = {}
                if show_source:
                    source_by_path = {
                        spec.get("path"): spec
                        for spec in self.source.data_reader.get_view_specs(
                            variable_name,
                            "multi-sim",
                            "source",
                        )
                    }

                columns.append((variable_name, view_specs, source_by_path))

            if not columns:
                return

            _, row_specs, _ = columns[0]
            rows = []
            for index, row_spec in enumerate(row_specs):
                label = row_spec.get("label", row_spec["array_name"])
                if is_multi_sim:
                    label = label.rsplit(" (", 1)[0]
                    if row_spec.get("role") == "control":
                        label = f"{label} (ctrl)"

                cells = []
                for _, view_specs, source_by_path in columns:
                    spec = view_specs[index]
                    source_spec = source_by_path.get(spec.get("path"))
                    cells.append(
                        {
                            # A control row has diff of nothing with itself
                            "display": (
                                "0"
                                if control_reads_zero and spec.get("role") == "control"
                                else picked_value(spec["array_name"])
                            ),
                            "active": spec["array_name"] == hover_info,
                            "has_source": source_spec is not None,
                            "source_display": (
                                picked_value(source_spec["array_name"])
                                if source_spec
                                else None
                            ),
                        }
                    )

                rows.append(
                    {
                        "key": row_spec["array_name"],
                        "label": label,
                        "active": any(cell["active"] for cell in cells),
                        "cells": cells,
                    }
                )

            comparison_label = MULTI_SIM_COMPARISON_LABELS.get(
                comparison_type, comparison_type
            )
            self.state.probe_table = {
                "lat": data_info.get("lat", [None])[0],
                "lon": data_info.get("lon", [None])[0],
                "columns": [
                    {
                        "key": name,
                        "label": f"{name} {comparison_label}" if is_multi_sim else name,
                        "active": name == hovered_variable,
                    }
                    for name, _, _ in columns
                ],
                "rows": rows,
            }

    def _probe_variables(self, hovered_variable):
        """Leading variables in view order, plus the one being probed."""
        ordered_variables = self.get_group_order()
        leading_variables = ordered_variables[:MAX_PROBE_COLUMNS]
        if hovered_variable in leading_variables:
            return leading_variables

        return [*ordered_variables[: MAX_PROBE_COLUMNS - 1], hovered_variable]

    def _active_views(self):
        if self._active_configs:
            return [self._var2view[name] for name in self._active_configs]
        return list(self._var2view.values())

    def _resolve_view_spec(self, view_spec):
        if not isinstance(view_spec, str):
            return view_spec

        return (
            self.source.data_reader.get_array_metadata(view_spec)
            or next(
                iter(
                    self.source.data_reader.get_view_specs(
                        view_spec,
                        self.state.comparison_mode,
                        self.state.comparison_type,
                        self.state.selected_columns,
                    )
                ),
                None,
            )
            or {
                "array_name": view_spec,
                "base_variable": view_spec,
                "role": "control",
                "label": view_spec,
                "comparison_mode": self.state.comparison_mode,
            }
        )

    def camera_projection(self):
        """Look straight down -Z, the orientation every flat projection wants."""
        self._camera.focal_point = (0, 0, 0)
        self._camera.position = (0, 0, 1)
        self._camera.view_up = (0, 1, 0)
        self.reset_camera()

    def center_camera(self, lat, lon):
        """Point the shared camera at (lat, lon) on the unit sphere."""
        lat_rad = lat * math.pi / 180
        lon_rad = lon * math.pi / 180
        x = math.sin(lon_rad) * math.cos(lat_rad)
        y = math.sin(lat_rad)
        z = math.cos(lon_rad) * math.cos(lat_rad)
        self._camera.focal_point = (0, 0, 0)
        self._camera.position = (x, y, z)
        self._camera.view_up = (
            -math.sin(lon_rad),
            2,
            -math.cos(lon_rad),
        )
        self.reset_camera()

    def reset_camera(self, render=True):
        if self.layout_dirty or not self._last_vars:
            self.pending_reset_camera = 1
            return

        view_to_reset = None

        active_layout = self.state.active_layout or ""
        if active_layout.startswith("view_"):
            for view in self._var2view.values():
                if view.name == active_layout:
                    view_to_reset = view
                    break

        if not view_to_reset:
            for var_type, var_names in self._last_vars.items():
                for var_name in var_names:
                    for view_spec in self.get_view_specs(var_name):
                        view_to_reset = self.get_view(view_spec, var_type)
                        if view_to_reset:
                            break
                    if view_to_reset:
                        break

                if view_to_reset:
                    break

        if view_to_reset:
            view_to_reset.reset_camera()
            self.pending_reset_camera = 0
        else:
            self.pending_reset_camera = 1

        if render and view_to_reset:
            self.render()

    def guarded_zoom(self, factor):
        if (
            "adjust-layout" not in self.state.active_tools
            or not self.state.show_zoom_controls
        ):
            return
        self.zoom(factor)

    def zoom(self, factor):
        self._camera.SetParallelScale(self._camera.GetParallelScale() * factor)
        self.render()

    def get_zoom(self):
        return self._camera.GetParallelScale()

    def set_zoom(self, scale):
        if scale is None:
            return
        self._camera.SetParallelScale(scale)
        self.render()

    def guarded_pan(self, dx, dy):
        if (
            "adjust-layout" not in self.state.active_tools
            or not self.state.show_pan_controls
        ):
            return

        self.pan(dx, dy)

    def pan(self, dx, dy):
        cam = self._camera
        scale = cam.GetParallelScale()
        step = scale * 0.1
        pos = list(cam.GetPosition())
        foc = list(cam.GetFocalPoint())
        pos[0] += dx * step
        pos[1] += dy * step
        foc[0] += dx * step
        foc[1] += dy * step
        cam.SetPosition(*pos)
        cam.SetFocalPoint(*foc)
        self.render()

    def get_active_camera(self):
        if not self._var2view:
            return None
        camera = self._camera
        return {
            "position": camera.GetPosition(),
            "focal_point": camera.GetFocalPoint(),
            "view_up": camera.GetViewUp(),
            "parallel_projection": camera.GetParallelProjection(),
            "parallel_scale": camera.GetParallelScale(),
            "view_angle": camera.GetViewAngle(),
            "clipping_range": camera.GetClippingRange(),
        }

    @controller.set("size_update")
    def on_size_update(self):
        if not self.layout_dirty or not self.pending_render:
            self.pending_render = True
            self.loop.call_later(0.1, self.render)
        self.layout_dirty = True

    def render(self):
        if self.layout_dirty:
            self.compute_layout()

        if self.pending_reset_camera:
            self.reset_camera(False)

        if self.ctx.view:
            self.ctx.view.update()
            self.pending_render = False

    def update_color_range(self):
        for view in self._active_views():
            view.colormap.update_color_range()
        self.render()

    def refresh_pipeline_inputs(self):
        for view in self._var2view.values():
            view._connect_pipeline_input()

    def refresh_view_specs(self, variables=None):
        if variables is None:
            variables = self._last_vars

        for var_type, var_names in variables.items():
            for var_name in var_names:
                for view_spec in self.get_view_specs(var_name):
                    view = self._var2view.get(view_spec["array_name"])
                    if view is not None:
                        view.update_view_spec(view_spec)

    def reset_view_orders(self, variables=None):
        if variables is None:
            variables = self._last_vars
        if not variables:
            return

        for var_names in variables.values():
            for var_name in var_names:
                for view_spec in self.get_view_specs(var_name):
                    view = self._var2view.get(view_spec["array_name"])
                    if view is not None:
                        view.config.order = 0

    def get_group_order(self, variables=None):
        if variables is None:
            variables = self._last_vars
        if not variables:
            return []

        variable_names = []
        for var_names in variables.values():
            variable_names.extend(var_names)

        fallback_order = len(variable_names) + 1
        return sorted(
            variable_names,
            key=lambda var_name: self._group_orders.get(var_name, fallback_order),
        )

    def set_group_order(self, variable_names):
        self._group_orders = {
            var_name: index for index, var_name in enumerate(variable_names, start=1)
        }

    def get_view(self, view_spec, variable_type):
        view_spec = self._resolve_view_spec(view_spec)
        array_name = view_spec["array_name"]
        view = self._var2view.get(array_name)
        if view is None:
            current_size = None
            if self.state.comparison_mode == "multi-sim":
                for config in self._active_configs.values():
                    if config.size:
                        current_size = config.size
                        break
            view = self._var2view.setdefault(
                array_name,
                VariableView(
                    self.server,
                    self.source,
                    view_spec,
                    variable_type,
                    self._camera,
                ),
            )
            if current_size is not None:
                view.config.size = current_size
        else:
            view.update_view_spec(view_spec)

        return view

    def get_view_specs(self, variable_name):
        return self.source.data_reader.get_view_specs(
            variable_name,
            self.state.comparison_mode,
            self.state.comparison_type,
            self.state.selected_columns,
        )

    def compute_layout(self, variables=None):
        if variables is None:
            variables = self._last_vars

        if not variables:
            return

        self.layout_dirty = False

        views = []
        view_size = [0, 0]
        fullscreen_view = None
        fullscreen_view_name = self.state.active_layout or ""

        for var_type, var_names in variables.items():
            for var_name in var_names:
                for view_spec in self.get_view_specs(var_name):
                    view = self.get_view(view_spec, var_type)

                    if view.name == fullscreen_view_name:
                        fullscreen_view = view
                        break
                    if view.size[1]:
                        views.append(view)
                        view_size[0] = max(view_size[0], view.size[0])
                        view_size[1] = max(view_size[1], view.size[1])
                    else:
                        self.layout_dirty = True

                if fullscreen_view:
                    break

            if fullscreen_view:
                break

        if fullscreen_view:
            view_size = fullscreen_view.size
            views = [fullscreen_view]
        else:
            views = [
                view
                for index, view in sorted(
                    enumerate(views),
                    key=lambda item: (
                        item[1].config.order or len(views) + item[0],
                        item[0],
                    ),
                )
            ]

        size = len(views)
        if size == 0:
            return

        width_count = math.ceil(math.sqrt(size))
        height_count = math.ceil(size / width_count)
        full_size = [
            view_size[0] * width_count,
            view_size[1] * height_count,
        ]

        self._render_window.SetSize(*full_size)
        renderers = list(self._render_window.GetRenderers())
        for renderer in renderers:
            self._render_window.RemoveRenderer(renderer)

        dx = 1.0 / width_count
        dy = 1.0 / height_count
        for index, view in enumerate(views):
            x_index = index % width_count
            y_index = int(index / width_count)
            bounds = (
                x_index * dx,
                y_index * dy,
                (x_index + 1) * dx,
                (y_index + 1) * dy,
            )
            view.bounds = bounds
            self._render_window.AddRenderer(view.renderer)

    @controller.set("swap_variables")
    def swap_variable(self, variable_a, variable_b):
        if not variable_a or not variable_b or variable_a == variable_b:
            return

        def swap_pair(array_name_a, array_name_b):
            config_a = self._active_configs.get(array_name_a)
            config_b = self._active_configs.get(array_name_b)
            if config_a is None or config_b is None:
                return
            config_a.order, config_b.order = config_b.order, config_a.order
            config_a.size, config_b.size = config_b.size, config_a.size
            config_a.offset, config_b.offset = config_b.offset, config_a.offset
            config_a.break_row, config_b.break_row = (
                config_b.break_row,
                config_a.break_row,
            )

        metadata_a = self.source.data_reader.get_array_metadata(variable_a) or {}
        metadata_b = self.source.data_reader.get_array_metadata(variable_b) or {}
        if self.state.comparison_mode == "multi-sim":
            path_a = metadata_a.get("path")
            path_b = metadata_b.get("path")

            if path_a and path_b and path_a != path_b:
                simulation_configs = list(self.state.simulation_configs or [])
                index_a = None
                index_b = None
                for index, entry in enumerate(simulation_configs):
                    path = entry.get("path")
                    if path == path_a:
                        index_a = index
                    if path == path_b:
                        index_b = index

                if index_a is not None and index_b is not None and index_a != index_b:
                    simulation_configs[index_a], simulation_configs[index_b] = (
                        simulation_configs[index_b],
                        simulation_configs[index_a],
                    )
                    self.state.simulation_configs = simulation_configs
                    return

        base_variable_a = metadata_a.get("base_variable")
        base_variable_b = metadata_b.get("base_variable")
        slot_a = None
        slot_b = None

        if base_variable_a:
            for slot_index, view_spec in enumerate(
                self.get_view_specs(base_variable_a)
            ):
                if view_spec["array_name"] == variable_a:
                    slot_a = slot_index
                    break

        if base_variable_b:
            for slot_index, view_spec in enumerate(
                self.get_view_specs(base_variable_b)
            ):
                if view_spec["array_name"] == variable_b:
                    slot_b = slot_index
                    break

        if slot_a is None or slot_b is None or slot_a == slot_b:
            swap_pair(variable_a, variable_b)
            return

        for var_names in self._last_vars.values():
            for var_name in var_names:
                view_specs = self.get_view_specs(var_name)
                if slot_a >= len(view_specs) or slot_b >= len(view_specs):
                    continue

                swap_pair(
                    view_specs[slot_a]["array_name"],
                    view_specs[slot_b]["array_name"],
                )

    @controller.set("swap_variable_groups")
    def swap_variable_groups(self, variable_a, variable_b):
        if not variable_a or not variable_b or variable_a == variable_b:
            return

        if variable_a not in self._group_orders or variable_b not in self._group_orders:
            return

        self._group_orders[variable_a], self._group_orders[variable_b] = (
            self._group_orders[variable_b],
            self._group_orders[variable_a],
        )

        if self._last_vars:
            self.build_auto_layout(self._last_vars)
            self.render()

    def apply_size(self, n_cols):
        self._n_cols = n_cols
        if not self._last_vars:
            return

        self._apply_col_size(n_cols)

    def _apply_col_size(self, n_cols):
        if n_cols == 0:
            # Auto size views based on the number of comparison panels being shown.
            for var_type, var_names in self._last_vars.items():
                for var_name in var_names:
                    view_specs = self.get_view_specs(var_name)
                    if not view_specs:
                        continue
                    size = auto_size_to_col(len(view_specs))
                    for view_spec in view_specs:
                        self.get_view(view_spec, var_type).config.size = size
        else:
            # Apply a uniform size to all active views.
            for config in self._active_configs.values():
                config.size = COL_SIZE_LOOKUP[n_cols]

    def build_auto_layout(self, variables=None):
        if variables is None:
            variables = self._last_vars
        if not variables:
            self.state.animation_export_items = []
            return

        self._last_vars = variables
        self.compute_layout()

        # Create UI based on the selected variables.
        self.state.swap_groups = {}
        export_items = []
        # Build a lookup from variable type to the matching group border color.
        type_to_color = {vt["name"]: vt["color"] for vt in self.state.variable_types}
        flat_vars = []
        for var_type, var_names in variables.items():
            for var_name in var_names:
                view_specs = self.get_view_specs(var_name)
                if not view_specs:
                    continue
                flat_vars.append(
                    (var_type, var_name, view_specs, self._group_orders.get(var_name))
                )

        current_group_order = {
            var_name: saved for _, var_name, _, saved in flat_vars if saved is not None
        }
        next_group_order_idx = (
            (max(current_group_order.values()) + 1) if current_group_order else 1
        )
        for _, var_name, _, saved in flat_vars:
            if saved is None:
                current_group_order[var_name] = next_group_order_idx
                next_group_order_idx += 1

        self._group_orders = current_group_order

        grouped_entries = sorted(
            (
                (current_group_order[var_name], var_type, var_name, view_specs)
                for var_type, var_name, view_specs, _ in flat_vars
            ),
            key=lambda item: item[0],
        )

        with DivLayout(self.server, template_name="auto_layout") as self.ui:
            group_names = [var_name for _, _, var_name, _ in grouped_entries]

            with v3.VCol(classes="pa-1"):
                for _, var_type, var_name, view_specs in grouped_entries:
                    type_name = (
                        ", ".join(var_type)
                        if isinstance(var_type, (list, tuple))
                        else str(var_type)
                    )
                    border_color = type_to_color.get(type_name, "primary")
                    with v3.VAlert(
                        border="start",
                        classes="pr-1 py-1 pl-3 mb-6",
                        variant="flat",
                        border_color=border_color,
                        key=f"group-{var_name}",
                        raw_attrs=[f'data-variable-group="{var_name}"'],
                    ):
                        with html.Div(classes="d-flex align-center mb-1 ga-1"):
                            with html.Div(
                                var_name,
                                classes=(
                                    "text-subtitle-2 font-weight-medium d-inline-block"
                                ),
                                style="user-select: none; cursor: pointer;",
                            ):
                                with v3.VMenu(activator="parent"):
                                    with v3.VList(
                                        density="compact",
                                        style="max-height: 40vh;",
                                    ):
                                        for swap_name in group_names:
                                            if swap_name == var_name:
                                                continue
                                            v3.VListItem(
                                                title=swap_name,
                                                click=(
                                                    self.ctrl.swap_variable_groups,
                                                    f"['{var_name}', '{swap_name}']",
                                                ),
                                            )
                            v3.VIconBtn(
                                v_tooltip_bottom="'Capture group as png'",
                                icon="mdi-camera-outline",
                                size="small",
                                variant="plain",
                                click=f"utils.quickcompare.captureGroup('{var_name}')",
                                style="transform: scale(0.75);",
                            )
                        with v3.VRow(dense=True):
                            use_config_size = self.state.comparison_mode == "multi-sim"
                            if not use_config_size:
                                views_per_row = max(1, len(view_specs))
                                group_cols = max(1, math.floor(12 / views_per_row))
                            panel_options = [
                                {
                                    "name": vs["array_name"],
                                    "label": vs.get("label", vs["array_name"]),
                                }
                                for vs in view_specs
                            ]
                            for view_spec in view_specs:
                                view = self.get_view(view_spec, var_type)
                                export_items.append(
                                    {
                                        "title": view_spec.get(
                                            "label", view_spec["array_name"]
                                        ),
                                        "value": view_spec["array_name"],
                                    }
                                )
                                view.config.swap_group = sorted(
                                    [
                                        item
                                        for item in panel_options
                                        if item["name"] != view_spec["array_name"]
                                    ],
                                    key=lambda item: item["name"],
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
                                        )
                                        if use_config_size
                                        else ("config.offset * config.size",),
                                        cols=("config.size",)
                                        if use_config_size
                                        else group_cols,
                                        style=("`order: ${config.order};`",),
                                        key=view_spec["array_name"],
                                    ):
                                        client.ServerTemplate(name=view.name)

        self.state.animation_export_items = export_items

        self._active_configs = {}
        next_order_idx = 1
        for _, var_type, _, view_specs in grouped_entries:
            view_items = [
                (index, view_spec, self.get_view(view_spec, var_type))
                for index, view_spec in enumerate(view_specs)
            ]
            if self.state.comparison_mode != "multi-sim":
                view_items = sorted(
                    view_items,
                    key=lambda item: (
                        item[2].config.order or len(view_specs) + item[0],
                        item[0],
                    ),
                )

            for _, view_spec, view in view_items:
                config = view.config
                config.order = next_order_idx
                self._active_configs[view_spec["array_name"]] = config
                next_order_idx += 1

        if self._n_cols is not None:
            self._apply_col_size(self._n_cols)

        self.layout_dirty = True
        self.compute_layout()
