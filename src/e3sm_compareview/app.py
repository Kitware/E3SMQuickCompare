import asyncio
import datetime
import json
import os
import time
from pathlib import Path

from e3sm_compareview import module as qc_module
from e3sm_quickview import module as qv_module
from e3sm_quickview.components import css
from e3sm_quickview.components import dialogs as qv_dialogs
from e3sm_quickview.utils import cli, compute
from e3sm_quickview.utils.colors import get_type_color
from trame.app import TrameApp, asynchronous, file_upload
from trame.decorators import change, controller, life_cycle, trigger
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import client, dataclass, html, rca, tauri
from trame.widgets import trame as tw
from trame.widgets import vuetify3 as v3

from e3sm_compareview.assets import ASSETS
from e3sm_compareview.comparison import (
    active_simulation_configs,
    build_simulation_configs,
    comparison_signature_for,
    DEFAULT_TWO_SIM_COLUMNS,
    label_signature_for,
    normalize_comparison_mode,
    normalize_comparison_type,
    normalize_two_sim_target,
)
from e3sm_compareview.components import (
    dialogs,
    doc,
    drawers,
    file_browser,
    toolbars,
)
from e3sm_compareview.components import (
    tools as nav_tools,
)
from e3sm_compareview.pipeline import EAMVisSource
from e3sm_compareview.view_manager import ViewManager

v3.enable_lab()

EXCLUSIVE_DRAWERS = {"select-fields", "select-simulations"}


class EAMApp(TrameApp):
    def __init__(self, server=None):
        super().__init__(server)

        # Pre-load deferred widgets
        dataclass.initialize(self.server)
        self.server.enable_module(qc_module)
        self.server.enable_module(qv_module)

        # CLI
        args = cli.configure_and_parse(self.server.cli)

        # Initial UI state
        self.state.update(
            {
                "trame__title": "QuickCompare",
                "trame__favicon": ASSETS.icon,
                "download_name": "quickcompare-state.json",
                "is_tauri": False,
                "animation_play": False,
                "animation_direction": "forward",
                "animation_export": False,
                "animation_export_fields": [],
                "animation_export_items": [],
                "capture_recording": False,
                "show_animation_export_menu": False,
                # All available variables
                "variables_listing": [],
                # Selected variables to load
                "variables_selected": [],
                # Control 'Load Variables' button availability
                "variables_loaded": False,
                # Loading feedback
                "loading": False,
                "loading_time": 0,
                # Slicing / animation track state
                "animation_tracks": [],
                "available_animation_tracks": [],
                "dim_units": {},
                "crop_slider_edit": True,
                "slice_slider_edit": True,
                # Dynamic type-color mapping (populated when data loads)
                "variable_types": [],
                # Dimension arrays (will be populated dynamically)
                "midpoints": [],
                "interfaces": [],
                "timestamps": [],
                # Fields summaries
                "fields_avgs": {},
                # Simulation comparison selection
                "simulation_configs": [],
                "control_simulation_file": "",
                "two_sim_test_simulation_file": "",
                "comparison_mode": "multi-sim",
                "comparison_type": "diff",
                "selected_columns": DEFAULT_TWO_SIM_COLUMNS,
                "projection": ["Robinson"],
                "grid_interval": 30,
                "spherical_center_lat": 0,
                "spherical_center_lon": 0,
                "dragged_simulation_path": "",
            }
        )

        # Data input
        self.source = EAMVisSource()

        # Helpers
        self.view_manager = ViewManager(self.server, self.source)
        self.file_browser = file_browser.ParaViewFileBrowser(
            self.server,
            prefix="pv_files",
            home=None if args.user_home else args.workdir,  # can use current=
            group="",
        )
        self._comparison_signature = ()
        self._simulation_label_signature = ()

        # Process CLI to pre-load data
        if args.state is not None:
            state_content = json.loads(Path(args.state).read_text())

            async def wait_for_import(**_):
                await self.import_state(state_content)

            self.ctrl.on_server_ready.add_task(wait_for_import)
        elif args.data and args.conn:
            self.file_browser.set_data_simulation(args.data)
            self.file_browser.set_data_connectivity(args.conn)
            self.ctrl.on_server_ready.add(self.file_browser.load_data_files)

        # Development setup
        if self.server.hot_reload:
            self.ctrl.on_server_reload.add(self._build_ui)
            self.ctrl.on_server_reload.add(self.view_manager.refresh_ui)

        # GUI
        self._build_ui()

    # -------------------------------------------------------------------------
    # Tauri adapter
    # -------------------------------------------------------------------------

    @life_cycle.server_ready
    def _tauri_ready(self, **_):
        jupyter_url_prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        jupyter_url_api = os.environ.get("JUPYTERHUB_API_URL")
        if jupyter_url_prefix:
            base_url = "https://jupyter.nersc.gov"
            if jupyter_url_api:
                base_url = jupyter_url_api[:-8]

            os.write(
                1,
                "\nUse URL below to connect to the application:\n\n  => "
                f"{base_url}{jupyter_url_prefix}proxy/{self.server.port}"
                "/index.html?ui=main&reconnect=auto\n\n".encode(),
            )
        else:
            base_url = "http://localhost"
            os.write(1, f"tauri-server-port={self.server.port}\n".encode())
            os.write(
                1,
                "\nUse URL below to connect to the application:\n\n  => "
                f"{base_url}:{self.server.port}/\n\n".encode(),
            )

    @life_cycle.client_connected
    def _tauri_show(self, **_):
        jupyter_url_prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        if not jupyter_url_prefix:
            os.write(1, "tauri-client-ready\n".encode())

    # -------------------------------------------------------------------------
    # UI definition
    # -------------------------------------------------------------------------

    def _build_ui(self, **_):
        if self.server.hot_reload:
            toolbars.reload(toolbars)

        with VAppLayout(self.server, fill_height=True) as self.ui:
            # Keyboard shortcut
            with tw.MouseTrap(
                ResetCamera=self.view_manager.reset_camera,
                Size1=(self.view_manager.apply_size, "[1]"),
                Size2=(self.view_manager.apply_size, "[2]"),
                Size3=(self.view_manager.apply_size, "[3]"),
                Size4=(self.view_manager.apply_size, "[4]"),
                Size6=(self.view_manager.apply_size, "[6]"),
                ToolbarLayout=(self.toggle_toolbar, "['adjust-layout']"),
                ToolbarCrop=(self.toggle_toolbar, "['adjust-databounds']"),
                ToolbarSelect=(self.toggle_toolbar, "['select-slice-time']"),
                ToolbarAnimation=(self.toggle_toolbar, "['animation-controls']"),
                ToolbarComparison=(self.toggle_toolbar, "['simulation-controls']"),
                ToggleVariableSelection=(self.toggle_toolbar, "['select-fields']"),
                RemoveAllToolbars=(self.toggle_toolbar),
                ProjectionEquidistant="projection = ['Cyl. Equidistant']",
                ProjectionRobinson="projection = ['Robinson']",
                ProjectionMollweide="projection = ['Mollweide']",
                ProjectionSpherical="projection = ['Spherical']",
                FileOpen=(self.toggle_toolbar, "['load-data']"),
                SaveState="trigger('download_state_dialog')",
                UploadState="utils.get('document').querySelector('#fileUpload').click()",
                ToggleHelp="compact_drawer = !compact_drawer",
                PanLeft=(self.view_manager.guarded_pan, "[1, 0]"),
                PanRight=(self.view_manager.guarded_pan, "[-1, 0]"),
                PanUp=(self.view_manager.guarded_pan, "[0, -1]"),
                PanDown=(self.view_manager.guarded_pan, "[0, 1]"),
                ZoomIn=(self.view_manager.guarded_zoom, "[0.83]"),
                ZoomOut=(self.view_manager.guarded_zoom, "[1.2]"),
            ) as mt:
                mt.bind(["z"], "ResetCamera")
                mt.bind(["alt+1", "1"], "Size1")
                mt.bind(["alt+2", "2"], "Size2")
                mt.bind(["alt+3", "3"], "Size3")
                mt.bind(["alt+4", "4"], "Size4")
                mt.bind(["alt+6", "6"], "Size6")

                mt.bind("c", "ProjectionEquidistant")
                mt.bind("r", "ProjectionRobinson")
                mt.bind("m", "ProjectionMollweide")
                mt.bind("n", "ProjectionSpherical")

                mt.bind("f", "FileOpen")
                mt.bind("e", "SaveState")
                mt.bind("i", "UploadState")
                mt.bind("h", "ToggleHelp")

                mt.bind("p", "ToolbarLayout")
                mt.bind("l", "ToolbarCrop")
                mt.bind("s", "ToolbarSelect")
                mt.bind("a", "ToolbarAnimation")
                mt.bind("v", "ToggleVariableSelection")

                mt.bind("space", "ToolbarComparison", stop_propagation=True)

                mt.bind("esc", "RemoveAllToolbars")

                mt.bind("left", "PanLeft", stop_propagation=True)
                mt.bind("right", "PanRight", stop_propagation=True)
                mt.bind("up", "PanUp", stop_propagation=True)
                mt.bind("down", "PanDown", stop_propagation=True)

                mt.bind("shift+up", "ZoomIn", stop_propagation=True)
                mt.bind("shift+down", "ZoomOut", stop_propagation=True)

            # Native Dialogs
            client.ClientTriggers(mounted="is_tauri = !!window.__TAURI__")
            with tauri.Dialog() as dialog:
                self.ctrl.save = dialog.save

            with v3.VLayout():
                nav_tools.Tools(
                    reset_camera=self.view_manager.reset_camera,
                    toggle_toolbar=self.toggle_toolbar,
                )

                with v3.VMain():
                    dialogs.FileOpen(self.file_browser)
                    dialogs.StateDownload()
                    drawers.FieldSelection(load_variables=self.data_load_variables)

                    with v3.VContainer(classes="h-100 pa-0", fluid=True):
                        with client.SizeObserver("main_size"):
                            # Sticky overlay for toolbars
                            with html.Div(style=css.TOOLBARS_FIXED_OVERLAY):
                                client.SizeObserver(
                                    "toolbar_size",
                                    style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;",
                                )
                                toolbars.Layout(
                                    apply_size=self.view_manager.apply_size,
                                    zoom=self.view_manager.zoom,
                                    pan=self.view_manager.pan,
                                    reset_camera=self.view_manager.reset_camera,
                                )
                                toolbars.SimulationControls()
                                toolbars.Cropping()
                                toolbars.DataSelection()
                                toolbars.Animation()

                            # View of all the variables
                            with rca.ImageStream(
                                self.view_manager._render_window,
                                encoder="turbo-jpeg",
                                ctx_name="view",
                            ):
                                qv_dialogs.ColorMapEditor()
                                with html.Div(
                                    classes="all-variables",
                                    v_if="variables_selected.length",
                                ):
                                    client.ServerTemplate(
                                        name=("active_layout", "auto_layout"),
                                    )

                            # Show documentation when no variable selected
                            with html.Div(v_if="!variables_selected.length"):
                                doc.LandingPage()

    # -------------------------------------------------------------------------
    # Derived properties
    # -------------------------------------------------------------------------

    @property
    def selected_variables(self):
        from collections import defaultdict

        vars_per_type = defaultdict(list)
        varmeta = self.source.data_reader.varmeta or {}
        for var in self.state.variables_selected:
            metadata = varmeta.get(var)
            if metadata is None:
                continue
            vars_per_type[metadata.dimensions].append(var)

        return dict(vars_per_type)

    @property
    def active_simulation_configs(self):
        return active_simulation_configs(
            self.state.simulation_configs,
            self.state.control_simulation_file,
            self.state.comparison_mode,
            self.state.two_sim_test_simulation_file,
        )

    @staticmethod
    def _projection_name(projection):
        if isinstance(projection, (list, tuple)):
            if projection:
                return projection[0]
            return "Robinson"
        if isinstance(projection, str):
            return projection
        return "Robinson"

    def _ensure_two_sim_target(self):
        if self.state.comparison_mode != "two-sim":
            return

        target_path = normalize_two_sim_target(
            self.state.simulation_configs,
            self.state.control_simulation_file,
            self.state.two_sim_test_simulation_file,
        )
        if target_path != self.state.two_sim_test_simulation_file:
            self.state.two_sim_test_simulation_file = target_path

    def _sim_mode(self, count):
        if count == 2:
            return "two-sim"
        if count > 2:
            return "multi-sim"
        return self.state.comparison_mode

    def _selected_variables_to_show(self):
        vars_to_show = self.selected_variables
        return vars_to_show if any(vars_to_show.values()) else None

    def _update_variable_listing(self):
        self.state.variables_filter = ""
        self.state.variables_listing = [
            {
                "name": var.name,
                "type": ", ".join(var.dimensions),
                "id": f"{var.name}",
            }
            for _, var in self.source.data_reader.varmeta.items()
        ]

        # Build dynamic type-color mapping.
        dim_types = sorted(
            set(
                ", ".join(var.dimensions)
                for var in self.source.data_reader.varmeta.values()
            )
        )
        self.state.variable_types = [
            {"name": dim_type, "color": get_type_color(index)}
            for index, dim_type in enumerate(dim_types)
        ]

    def _rebuild_active_layout(self, update_color=False):
        vars_to_show = self._selected_variables_to_show()
        if not vars_to_show:
            return False

        self.view_manager.build_auto_layout(vars_to_show)
        if update_color:
            self.view_manager.update_color_range()
            self.view_manager.render()
        return True

    def _update_field_avgs(self):
        vtk_data = self.source.data_reader.get_output_dataset()
        if vtk_data is None:
            self.state.fields_avgs = {}
            return

        array_names = list(self.source.data_reader.array_metadata)
        if not array_names:
            self.state.fields_avgs = {}
            return

        self.state.fields_avgs = compute.extract_avgs(vtk_data, array_names)

    def _refresh_source_simulations(self):
        if not self.source.data_reader.conn_file:
            return

        self.source.Update(
            simulation_configs=self.active_simulation_configs,
            conn_file=self.source.data_reader.conn_file,
        )
        if (
            self.source.data_reader.valid
            and self.source.data_reader.varmeta is not None
        ):
            self._update_variable_listing()
            valid_variables = set(self.source.data_reader.varmeta)
            self.state.variables_selected = [
                var for var in self.state.variables_selected if var in valid_variables
            ]
            self._update_field_avgs()

    # -------------------------------------------------------------------------
    # Methods connected to UI
    # -------------------------------------------------------------------------

    @trigger("download_state_dialog")
    @controller.set("download_state_dialog")
    @trigger("download_state")
    @controller.set("download_state")
    def download_state(self):
        active_variables = self.selected_variables
        state_content = {}
        state_content["origin"] = {
            "user": os.environ.get("USER", os.environ.get("USERNAME")),
            "created": f"{datetime.datetime.now()}",
            "comment": self.state.export_comment,
        }
        state_content["files"] = {
            "simulation": str(Path(self.file_browser.get("data_simulation")).resolve()),
            "simulations": [
                entry["path"] for entry in (self.state.simulation_configs or [])
            ]
            or list(self.file_browser.get("data_simulation_files") or []),
            "connectivity": str(
                Path(self.file_browser.get("data_connectivity")).resolve()
            ),
        }
        state_content["comparisons"] = {
            "control": self.state.control_simulation_file,
            "target": self.state.two_sim_test_simulation_file,
            "mode": self.state.comparison_mode,
            "type": self.state.comparison_type,
            "columns": self.state.selected_columns,
            "simulations": self.state.simulation_configs,
        }
        state_content["variables-selection"] = self.state.variables_selected
        layout = {
            "aspect-ratio": self.state.aspect_ratio,
            "active": self.state.active_layout,
            "tools": self.state.active_tools,
            "help": not self.state.compact_drawer,
            "variable-order": self.view_manager.get_group_order(active_variables),
        }
        state_content["layout"] = layout
        data_selection = {
            k: self.state[k]
            for k in [
                "time_idx",
                "midpoint_idx",
                "interface_idx",
                "crop_longitude",
                "crop_latitude",
                "projection",
                "grid_interval",
                "crop_slider_edit",
                "slice_slider_edit",
                "animation_track",
            ]
        }
        for dim_name in self.state.available_animation_tracks:
            idx_key = f"{dim_name}_idx"
            data_selection[idx_key] = self.state[idx_key]
        state_content["data-selection"] = data_selection

        saved_views = state_content["views"] = []
        for view_type, var_names in active_variables.items():
            for var_name in var_names:
                for view_spec in self.source.data_reader.get_view_specs(
                    var_name,
                    self.state.comparison_mode,
                    self.state.comparison_type,
                    self.state.selected_columns,
                ):
                    view = self.view_manager.get_view(view_spec, view_type)
                    config = view.config
                    cmap = view.colormap
                    saved_views.append(
                        {
                            "type": view_type,
                            "name": var_name,
                            "array_name": view_spec["array_name"],
                            "config": {
                                # layout
                                "order": config.order,
                                "size": config.size,
                                "offset": config.offset,
                                "break_row": config.break_row,
                            },
                            "colormap": {
                                "preset": cmap.preset,
                                "invert": cmap.invert,
                                "color_blind": cmap.color_blind,
                                "use_log_scale": cmap.use_log_scale,
                                "discrete_log": cmap.discrete_log,
                                "n_discrete_colors": cmap.n_discrete_colors,
                                "override_range": cmap.override_range,
                                "color_range": cmap.color_range,
                                "color_value_min": cmap.color_value_min,
                                "color_value_max": cmap.color_value_max,
                                "diverging": cmap.diverging,
                                "abs_max": cmap.saved_abs_max,
                                "epsilon": cmap.epsilon,
                                "cut_outside_range": cmap.cut_outside_range,
                            },
                        }
                    )

        return json.dumps(state_content, indent=2)

    @change("upload_state_file")
    def _on_import_state(self, upload_state_file, **_):
        if upload_state_file is None:
            return

        file_proxy = file_upload.ClientFile(upload_state_file)
        state_content = json.loads(file_proxy.content)
        self.import_state(state_content)

    @controller.set("import_state")
    def import_state(self, state_content):
        asynchronous.create_task(self._import_state(state_content))

    async def _import_state(self, state_content):
        # Files
        simulation_files = state_content["files"].get("simulations")
        if simulation_files is None:
            simulation_file = state_content["files"]["simulation"]
            simulation_files = [simulation_file] if simulation_file else []

        self.file_browser.set("data_simulation_files", simulation_files)
        if simulation_files:
            self.file_browser.set("data_simulation", simulation_files[-1])
        self.file_browser.set_data_connectivity(state_content["files"]["connectivity"])
        await self.data_loading_open(
            simulation_files,
            self.file_browser.get("data_connectivity"),
        )

        layout = state_content.get("layout", {})
        saved_views = state_content.get("views", [])
        comparisons = state_content.get("comparisons", {})
        if comparisons:
            self.state.simulation_configs = comparisons.get(
                "simulations", self.state.simulation_configs
            )
            self.state.control_simulation_file = comparisons.get(
                "control", self.state.control_simulation_file
            )
            self.state.two_sim_test_simulation_file = comparisons.get(
                "target", self.state.two_sim_test_simulation_file
            )
            self.state.comparison_mode = normalize_comparison_mode(
                comparisons.get(
                    "mode", comparisons.get("strategy", self.state.comparison_mode)
                )
            )
            raw_type = comparisons.get("type", comparisons.get("mode"))
            self.state.comparison_type = normalize_comparison_type(raw_type)
            self.state.selected_columns = comparisons.get(
                "columns", self.state.selected_columns
            )
            self._ensure_two_sim_target()
            self._refresh_source_simulations()

        # Load variables
        saved_variables = state_content.get("variables-selection", [])
        valid_variables = set(self.source.data_reader.varmeta or {})
        self.state.variables_selected = [
            var for var in saved_variables if var in valid_variables
        ]
        variable_order = list(layout.get("variable-order") or [])
        if not variable_order:
            seen_variables = set()
            for view_state in sorted(
                saved_views,
                key=lambda view_state: view_state.get("config", {}).get("order", 0),
            ):
                var_name = view_state["name"]
                if var_name in seen_variables:
                    continue
                seen_variables.add(var_name)
                variable_order.append(var_name)

        variable_order = [
            var_name
            for var_name in variable_order
            if var_name in self.state.variables_selected
        ]
        variable_order.extend(
            var_name
            for var_name in self.state.variables_selected
            if var_name not in variable_order
        )
        self.view_manager.set_group_order(variable_order)

        data_selection = state_content.get("data-selection", {})
        for key in (
            "crop_longitude",
            "crop_latitude",
            "projection",
            "grid_interval",
            "crop_slider_edit",
            "slice_slider_edit",
        ):
            if key in data_selection:
                self.state[key] = data_selection[key]
        self.state.projection = [self._projection_name(self.state.projection)]
        await self._data_load_variables()
        self.state.variables_loaded = True

        with self.state:
            for key in ("time_idx", "midpoint_idx", "interface_idx"):
                if key in data_selection:
                    self.state[key] = data_selection[key]
            for track in self.state.available_animation_tracks:
                idx_key = f"{track}_idx"
                if idx_key in data_selection:
                    self.state[idx_key] = data_selection[idx_key]
            if (
                data_selection.get("animation_track")
                in self.state.available_animation_tracks
            ):
                self.state.animation_track = data_selection["animation_track"]

        self.source.ApplyClipping(
            self.state.crop_longitude,
            self.state.crop_latitude,
        )
        self.source.UpdateProjection(self._projection_name(self.state.projection))
        self.source.UpdatePipeline()
        self.view_manager.refresh_pipeline_inputs()
        self.view_manager.reset_camera()
        self.view_manager.update_color_range()
        self.view_manager.render()
        self._update_field_avgs()

        # Update view states
        for view_state in saved_views:
            view_type = view_state["type"]
            var_name = view_state["name"]
            array_name = view_state.get("array_name", var_name)

            view_spec = next(
                (
                    c
                    for c in self.view_manager.get_view_specs(var_name)
                    if c["array_name"] == array_name
                ),
                None,
            )
            view = self.view_manager.get_view(view_spec or array_name, view_type)

            # Extract state
            cfg = view_state["config"]
            cmap_cfg = view_state["colormap"]
            cmap_cfg["color_range"] = tuple(cmap_cfg["color_range"])

            # Apply state
            view.config.update(**cfg)
            view.colormap.update(**cmap_cfg)

        # Update layout
        self.state.aspect_ratio = layout["aspect-ratio"]
        self.state.active_layout = layout["active"]
        self.state.active_tools = [
            tool for tool in layout["tools"] if tool != "comparison-controls"
        ]
        self.state.compact_drawer = not layout["help"]

        # Update filebrowser state
        with self.state:
            self.file_browser.set("state_loading", False)

    @controller.add_task("file_selection_load")
    async def data_loading_open(self, simulation_files, connectivity):
        # Reset state
        self.state.variables_selected = []
        self.state.variables_loaded = False
        self.state.animation_track = None
        self.state.available_animation_tracks = []
        self.state.animation_export_items = []
        self.state.midpoint_idx = 0
        self.state.midpoints = []
        self.state.interface_idx = 0
        self.state.interfaces = []
        self.state.time_idx = 0
        self.state.timestamps = []

        # Initialize simulation selection using the current files and saved labels.
        simulation_configs, control_file = build_simulation_configs(
            simulation_files,
            self.state.simulation_configs,
            self.state.control_simulation_file,
        )
        self.state.simulation_configs = simulation_configs
        self.state.control_simulation_file = control_file
        self.state.comparison_mode = self._sim_mode(len(simulation_configs))
        self._ensure_two_sim_target()

        await asyncio.sleep(0.1)
        # Use the selected simulations from the UI state.
        active_simulations = self.active_simulation_configs
        self.source.Update(
            simulation_configs=active_simulations,
            conn_file=connectivity,
        )

        self.file_browser.loading_completed(self.source.data_reader.valid)

        if self.source.data_reader.valid:
            with self.state as s:
                next_tools = [
                    "select-fields",
                    *(
                        tool
                        for tool in s.active_tools
                        if tool
                        not in {
                            "load-data",
                            "select-simulations",
                            "comparison-controls",
                        }
                    ),
                ]
                s.active_tools = list(dict.fromkeys(next_tools))

                self._update_variable_listing()

                # Update Layer/Time values and ui layout
                n_cols = 0
                available_tracks = []
                dim_units = {}
                for name, dim in self.source.data_reader.dimmeta.items():
                    values = dim.data
                    dim_size = getattr(dim, "size", None)
                    # Convert to list for JSON serialization
                    if values is not None:
                        self.state[name] = (
                            values.tolist()
                            if hasattr(values, "tolist")
                            else list(values)
                        )
                    else:
                        self.state[name] = list(range(dim_size or 0))

                    if dim_size is None:
                        dim_size = len(self.state[name])

                    if dim_size > 1:
                        n_cols += 1
                        available_tracks.append(name)
                        units = getattr(dim, "units", None)
                        if units:
                            dim_units[name] = units

                self.state.dim_units = dim_units
                self.state.animation_tracks = available_tracks
                self.state.available_animation_tracks = available_tracks
                self.state.animation_track = (
                    self.state.available_animation_tracks[0]
                    if self.state.available_animation_tracks
                    else None
                )

                from functools import partial

                # Initialize dynamic index variables for each dimension
                for dim_name in available_tracks:
                    index_var = f"{dim_name}_idx"
                    if "time" in index_var:
                        self.state[index_var] = 50
                    else:
                        self.state[index_var] = 0
                    self.state.change(index_var)(
                        partial(self._on_slicing_change, dim_name, index_var)
                    )

    @controller.set("file_selection_cancel")
    def data_loading_hide(self):
        self.state.active_tools = [
            tool for tool in self.state.active_tools if tool != "load-data"
        ]

    def data_load_variables(self):
        self.state.loading = True
        asynchronous.create_task(self._data_load_variables())

    async def _data_load_variables(self):
        """Called at 'Load Variables' button click"""
        t0 = time.perf_counter()
        try:
            # Give room for UI loading state to render
            await asyncio.sleep(0.1)
            vars_to_show = self.selected_variables

            # Flatten the list of lists
            flattened_vars = [
                var for var_list in vars_to_show.values() for var in var_list
            ]

            # Keep only tracks present in currently selected variables.
            used_dims = set()
            for dims in vars_to_show.keys():
                used_dims.update(dims)
            self.state.available_animation_tracks = [
                track for track in self.state.animation_tracks if track in used_dims
            ]
            self.state.animation_track = (
                self.state.available_animation_tracks[0]
                if self.state.available_animation_tracks
                else None
            )

            self.source.data_reader.load_variables(flattened_vars)

            # Trigger source update + compute avg
            with self.state:
                self.state.variables_loaded = True
            await self.server.network_completion

            await asyncio.sleep(0.1)
            active_simulations = self.active_simulation_configs
            self.source.Update(
                simulation_configs=active_simulations,
                conn_file=self.source.data_reader.conn_file,
                variables=flattened_vars,
                force_reload=True,
            )
            self._update_field_avgs()

            if self.state.comparison_mode == "two-sim":
                self.view_manager.reset_view_orders(vars_to_show)

            # Update views in layout
            with self.state:
                self.view_manager.build_auto_layout(vars_to_show)
            await self.server.network_completion

            # Reset camera after yield
            await asyncio.sleep(0.1)
            self.view_manager.reset_camera()
        finally:
            t1 = time.perf_counter()
            with self.state:
                self.state.loading = False
                self.state.loading_time = t1 - t0

    @change("comparison_type")
    def _on_comparison_type_change(self, **_):
        if self.state.comparison_mode != "multi-sim" or not self.state.variables_loaded:
            return

        self.view_manager.reset_view_orders(self.selected_variables)
        self._rebuild_active_layout(update_color=True)

    @change("comparison_mode")
    def _on_comparison_mode_change(self, comparison_mode, **_):
        normalized = normalize_comparison_mode(comparison_mode)
        if normalized != comparison_mode:
            self.state.comparison_mode = normalized

    @change("selected_columns")
    def _on_selected_columns_change(self, **_):
        if self.state.comparison_mode != "two-sim" or not self.state.variables_loaded:
            return
        self.view_manager.reset_view_orders(self.selected_variables)
        self._rebuild_active_layout(update_color=True)

    @change(
        "simulation_configs",
        "control_simulation_file",
        "comparison_mode",
        "two_sim_test_simulation_file",
    )
    def _on_simulation_selection_change(self, simulation_configs, **_):
        if simulation_configs:
            valid_paths = {entry["path"] for entry in simulation_configs}
            if self.state.control_simulation_file not in valid_paths:
                self.state.control_simulation_file = simulation_configs[0]["path"]
            self._ensure_two_sim_target()
        comparison_signature = comparison_signature_for(
            simulation_configs,
            self.state.control_simulation_file,
            self.state.comparison_mode,
            self.state.two_sim_test_simulation_file,
        )
        label_signature = label_signature_for(simulation_configs)

        comparison_changed = comparison_signature != self._comparison_signature
        labels_changed = label_signature != self._simulation_label_signature

        self._comparison_signature = comparison_signature
        self._simulation_label_signature = label_signature

        if comparison_changed:
            self._refresh_source_simulations()
            self.view_manager.reset_view_orders(self.selected_variables)
            if self.state.variables_loaded and self._rebuild_active_layout(
                update_color=True
            ):
                return
            self.state.variables_loaded = False
            self.state.animation_export_items = []
            return

        if (
            labels_changed
            and self.state.variables_selected
            and self.source.data_reader.varmeta
        ):
            self.source.data_reader.refresh_view_specs(self.active_simulation_configs)
            self.view_manager.refresh_view_specs(self.selected_variables)

    @change("projection")
    async def _on_projection(self, projection, **_):
        proj_str = self._projection_name(projection)
        self.source.UpdateProjection(proj_str)
        self.source.UpdatePipeline()
        self.view_manager.refresh_pipeline_inputs()
        self.view_manager.reset_camera()

    @change("grid_interval")
    def _on_grid_interval(self, grid_interval, **_):
        if grid_interval is None:
            return

        self.source.UpdateGridInterval(grid_interval)
        self.view_manager.render()

    @change("spherical_center_lat", "spherical_center_lon", "projection")
    def _on_center(self, spherical_center_lat, spherical_center_lon, projection, **_):
        if self._projection_name(projection) != "Spherical":
            self.view_manager.camera_projection()
            return

        if spherical_center_lat is None or spherical_center_lon is None:
            return

        self.view_manager.center_camera(
            float(spherical_center_lat), float(spherical_center_lon)
        )

    def _on_slicing_change(self, var, ind_var, **_):
        self.source.UpdateSlicing(var, self.state[ind_var])
        self.source.UpdatePipeline()
        self.view_manager.refresh_pipeline_inputs()

        self.view_manager.update_color_range()
        self.view_manager.render()
        self._update_field_avgs()

    @change(
        "crop_longitude",
        "crop_latitude",
    )
    def _on_downstream_change(
        self,
        crop_longitude,
        crop_latitude,
        **_,
    ):
        if not self.state.variables_loaded:
            return

        self.source.ApplyClipping(crop_longitude, crop_latitude)
        self.source.UpdateProjection(self._projection_name(self.state.projection))
        self.source.UpdatePipeline()
        self.view_manager.refresh_pipeline_inputs()
        self.view_manager.reset_camera()

        self.view_manager.update_color_range()
        self.view_manager.render()
        self._update_field_avgs()

    def toggle_toolbar(self, toolbar_name=None):
        if toolbar_name is None:
            self.state.compact_drawer = True
            self.state.active_tools = []
            return

        active_tools = list(self.state.active_tools)
        if toolbar_name in self.state.active_tools:
            self.state.active_tools = [
                n for n in self.state.active_tools if n != toolbar_name
            ]
        else:
            if toolbar_name in EXCLUSIVE_DRAWERS:
                active_tools = [n for n in active_tools if n not in EXCLUSIVE_DRAWERS]
            active_tools.append(toolbar_name)
            self.state.active_tools = active_tools
            self.state.dirty("active_tools")


# -------------------------------------------------------------------------
# Standalone execution
# -------------------------------------------------------------------------
def main():
    app = EAMApp()
    app.server.start(show_connection_info=False, open_browser=False)


if __name__ == "__main__":
    main()
