import asyncio
import datetime
import json
import os
from pathlib import Path

from trame.app import TrameApp, asynchronous, file_upload
from trame.decorators import change, controller, life_cycle, trigger
from trame.ui.vuetify3 import VAppLayout
from trame.widgets import client, dataclass, html, tauri
from trame.widgets import trame as tw
from trame.widgets import vuetify3 as v3

from e3sm_compareview.assets import ASSETS
from e3sm_compareview.comparison import (
    active_simulation_configs,
    build_simulation_configs,
    comparison_signature_for,
    label_signature_for,
)
from e3sm_compareview.components import doc, drawers, file_browser, toolbars
from e3sm_compareview.pipeline import EAMVisSource
from e3sm_compareview.view_manager import ViewManager
from e3sm_quickview.components import css, dialogs
from e3sm_quickview import module as qv_module
from e3sm_quickview.utils import cli, compute

v3.enable_lab()

EXCLUSIVE_DRAWERS = {"select-fields", "select-simulations"}


class EAMApp(TrameApp):
    def __init__(self, server=None):
        super().__init__(server)

        # Pre-load deferred widgets
        dataclass.initialize(self.server)
        self.server.enable_module(qv_module)

        # CLI
        args = cli.configure_and_parse(self.server.cli)

        # Initial UI state
        self.state.update(
            {
                "trame__title": "QuickCompare",
                "trame__favicon": ASSETS.icon,
                "is_tauri": False,
                "animation_play": False,
                # All available variables
                "variables_listing": [],
                # Selected variables to load
                "variables_selected": [],
                # Control 'Load Variables' button availability
                "variables_loaded": False,
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
                "comparison_mode": "diff",
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
            os.write(1, f"tauri-server-port={self.server.port}\n".encode())

    @life_cycle.client_connected
    def _tauri_show(self, **_):
        jupyter_url_prefix = os.environ.get("JUPYTERHUB_SERVICE_PREFIX")
        if not jupyter_url_prefix:
            os.write(1, "tauri-client-ready\n".encode())
    # -------------------------------------------------------------------------
    # UI definition
    # -------------------------------------------------------------------------

    def _build_ui(self, **_):
        with VAppLayout(self.server, fill_height=True) as self.ui:
            # Keyboard shortcut
            with tw.MouseTrap(
                ResetCamera=self.view_manager.reset_camera,
                SizeAuto=(self.view_manager.apply_size, "[0]"),
                Size1=(self.view_manager.apply_size, "[1]"),
                Size2=(self.view_manager.apply_size, "[2]"),
                Size3=(self.view_manager.apply_size, "[3]"),
                Size4=(self.view_manager.apply_size, "[4]"),
                Size6=(self.view_manager.apply_size, "[6]"),
                SizeFlow=(self.view_manager.apply_size, "['flow']"),
                ToolbarLayout=(self.toggle_toolbar, "['adjust-layout']"),
                ToolbarCrop=(self.toggle_toolbar, "['adjust-databounds']"),
                ToolbarSelect=(self.toggle_toolbar, "['select-slice-time']"),
                ToolbarAnimation=(self.toggle_toolbar, "['animation-controls']"),
                ToggleVariableSelection=(self.toggle_toolbar, "['select-fields']"),
                RemoveAllToolbars=(self.toggle_toolbar),
                ToggleGroups="layout_grouped = !layout_grouped",
                ProjectionEquidistant="projection = ['Cyl. Equidistant']",
                ProjectionRobinson="projection = ['Robinson']",
                ProjectionMollweide="projection = ['Mollweide']",
                ToggleViewLock="lock_views = !lock_views",
                FileOpen=(self.toggle_toolbar, "['load-data']"),
                SaveState="trigger('download_state')",
                UploadState="utils.get('document').querySelector('#fileUpload').click()",
                ToggleHelp="compact_drawer = !compact_drawer",
            ) as mt:
                mt.bind(["z"], "ResetCamera")
                mt.bind(["alt+0", "0"], "SizeAuto")
                mt.bind(["alt+1", "1"], "Size1")
                mt.bind(["alt+2", "2"], "Size2")
                mt.bind(["alt+3", "3"], "Size3")
                mt.bind(["alt+4", "4"], "Size4")
                mt.bind(["alt+6", "6"], "Size6")
                mt.bind(["="], "SizeFlow")

                mt.bind("c", "ProjectionEquidistant")
                mt.bind("r", "ProjectionRobinson")
                mt.bind("m", "ProjectionMollweide")

                mt.bind("f", "FileOpen")
                mt.bind("d", "SaveState")
                mt.bind("u", "UploadState")
                mt.bind("h", "ToggleHelp")

                mt.bind("p", "ToolbarLayout")
                mt.bind("l", "ToolbarCrop")
                mt.bind("s", "ToolbarSelect")
                mt.bind("a", "ToolbarAnimation")
                mt.bind("g", "ToggleGroups")

                mt.bind("v", "ToggleVariableSelection")

                mt.bind("space", "ToggleViewLock", stop_propagation=True)

                mt.bind("esc", "RemoveAllToolbars")

            # Native Dialogs
            client.ClientTriggers(mounted="is_tauri = !!window.__TAURI__")
            with tauri.Dialog() as dialog:
                self.ctrl.save = dialog.save

            with v3.VLayout():
                drawers.Tools(
                    reset_camera=self.view_manager.reset_camera,
                    toggle_toolbar=self.toggle_toolbar,
                )

                with v3.VMain():
                    dialogs.FileOpen(self.file_browser)
                    dialogs.StateDownload()
                    drawers.SimulationSelection()
                    drawers.FieldSelection(load_variables=self.data_load_variables)

                    with v3.VContainer(classes="h-100 pa-0", fluid=True):
                        with client.SizeObserver("main_size"):
                            # Take space to push content below the fixed overlay
                            html.Div(style=("`height: ${top_padding}px`",))

                            # Fixed overlay for toolbars
                            with html.Div(style=css.TOOLBARS_FIXED_OVERLAY):
                                toolbars.Layout(apply_size=self.view_manager.apply_size)
                                toolbars.ComparisonMode()
                                toolbars.Cropping()
                                toolbars.DataSelection()
                                toolbars.Animation()

                            # View of all the variables
                            client.ServerTemplate(
                                name=("active_layout", "auto_layout"),
                                v_if="variables_selected.length",
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
        for var in self.state.variables_selected:
            type = self.source.varmeta[var].dimensions
            vars_per_type[type].append(var)

        return dict(vars_per_type)

    @property
    def selected_variable_names(self):
        # Remove var type (first char)
        return [var for var in self.state.variables_selected]

    @property
    def active_simulation_configs(self):
        return active_simulation_configs(
            self.state.simulation_configs, self.state.control_simulation_file
        )

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
            for _, var in self.source.varmeta.items()
        ]

        from e3sm_quickview.utils.colors import get_type_color

        # Build dynamic type-color mapping.
        dim_types = sorted(
            set(", ".join(var.dimensions) for var in self.source.varmeta.values())
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

    def _refresh_source_simulations(self):
        if not self.source.conn_file:
            return

        self.source.Update(
            simulation_configs=self.active_simulation_configs,
            conn_file=self.source.conn_file,
        )
        if self.source.valid and self.source.varmeta is not None:
            self._update_variable_listing()
            valid_variables = set(self.source.varmeta)
            self.state.variables_selected = [
                var for var in self.state.variables_selected if var in valid_variables
            ]

    # -------------------------------------------------------------------------
    # Methods connected to UI
    # -------------------------------------------------------------------------

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
            "mode": self.state.comparison_mode,
            "simulations": self.state.simulation_configs,
        }
        state_content["variables-selection"] = self.state.variables_selected
        state_content["layout"] = {
            "aspect-ratio": self.state.aspect_ratio,
            "grouped": self.state.layout_grouped,
            "active": self.state.active_layout,
            "tools": self.state.active_tools,
            "help": not self.state.compact_drawer,
        }
        state_content["data-selection"] = {
            k: self.state[k]
            for k in [
                "time_idx",
                "midpoint_idx",
                "interface_idx",
                "crop_longitude",
                "crop_latitude",
                "projection",
            ]
        }
        views_to_export = state_content["views"] = []
        for view_type, var_names in active_variables.items():
            for var_name in var_names:
                for view_spec in self.source.get_view_specs(
                    var_name, self.state.comparison_mode
                ):
                    config = self.view_manager.get_view(view_spec, view_type).config
                    views_to_export.append(
                        {
                            "type": view_type,
                            "name": var_name,
                            "array_name": view_spec["array_name"],
                            "config": {
                                # lut
                                "preset": config.preset,
                                "invert": config.invert,
                                "use_log_scale": config.use_log_scale,
                                # layout
                                "order": config.order,
                                "size": config.size,
                                "offset": config.offset,
                                "break_row": config.break_row,
                                # color range
                                "override_range": config.override_range,
                                "color_range": config.color_range,
                                "color_value_min": config.color_value_min,
                                "color_value_max": config.color_value_max,
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

        comparisons = state_content.get("comparisons", {})
        if comparisons:
            self.state.simulation_configs = comparisons.get(
                "simulations", self.state.simulation_configs
            )
            self.state.control_simulation_file = comparisons.get(
                "control", self.state.control_simulation_file
            )
            self.state.comparison_mode = comparisons.get("mode", "diff")

        # Load variables
        self.state.variables_selected = state_content["variables-selection"]
        self.state.update(state_content["data-selection"])
        await self._data_load_variables()
        self.state.variables_loaded = True

        # Update view states
        for view_state in state_content["views"]:
            view_type = view_state["type"]
            array_name = view_state.get("array_name", view_state["name"])
            config = self.view_manager.get_view(array_name, view_type).config
            config.update(**view_state["config"])

        # Update layout
        self.state.aspect_ratio = state_content["layout"]["aspect-ratio"]
        self.state.layout_grouped = state_content["layout"]["grouped"]
        self.state.active_layout = state_content["layout"]["active"]
        self.state.active_tools = state_content["layout"]["tools"]
        self.state.compact_drawer = not state_content["layout"]["help"]

        # Update filebrowser state
        with self.state:
            self.file_browser.set("state_loading", False)

    @controller.add_task("file_selection_load")
    async def data_loading_open(self, simulation_files, connectivity):
        # Reset state
        self.state.variables_selected = []
        self.state.variables_loaded = False
        self.state.midpoint_idx = 0
        self.state.midpoints = []
        self.state.interface_idx = 0
        self.state.interfaces = []
        self.state.time_idx = 0
        self.state.timestamps = []

        self.state.data_files = simulation_files
        # Initialize simulation selection using the current files and saved labels.
        simulation_configs, control_file = build_simulation_configs(
            simulation_files,
            self.state.simulation_configs,
            self.state.control_simulation_file,
        )
        self.state.simulation_configs = simulation_configs
        self.state.control_simulation_file = control_file

        await asyncio.sleep(0.1)
        # Use the selected simulations from the UI state.
        active_simulations = self.active_simulation_configs
        self.source.Update(
            simulation_configs=active_simulations,
            conn_file=connectivity,
        )

        self.file_browser.loading_completed(self.source.valid)

        if self.source.valid:
            with self.state as s:
                s.active_tools = list(
                    set(
                        (
                            "select-simulations",
                            *(tool for tool in s.active_tools if tool != "load-data"),
                        )
                    )
                )

                self._update_variable_listing()

                # Update Layer/Time values and ui layout
                n_cols = 0
                available_tracks = []
                for name, dim in self.source.dimmeta.items():
                    values = dim.data
                    # Convert to list for JSON serialization
                    self.state[name] = (
                        values.tolist()
                        if hasattr(values, "tolist")
                        else list(values)
                        if values is not None
                        else []
                    )
                    if values is not None and len(values) > 1:
                        n_cols += 1
                        available_tracks.append({"title": name, "value": name})
                self.state.toolbar_slider_cols = 12 / n_cols if n_cols else 12
                self.state.animation_tracks = available_tracks
                self.state.animation_track = (
                    self.state.animation_tracks[0]["value"]
                    if available_tracks
                    else None
                )

                from functools import partial

                # Initialize dynamic index variables for each dimension
                for track in available_tracks:
                    dim_name = track["value"]
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
        asynchronous.create_task(self._data_load_variables())

    async def _data_load_variables(self):
        """Called at 'Load Variables' button click"""
        vars_to_show = self.selected_variables

        # Flatten the list of lists
        flattened_vars = [var for var_list in vars_to_show.values() for var in var_list]

        self.source.LoadVariables(flattened_vars)

        # Trigger source update + compute avg
        with self.state:
            self.state.variables_loaded = True
        await self.server.network_completion

        await asyncio.sleep(0.1)
        active_simulations = self.active_simulation_configs
        self.source.Update(
            simulation_configs=active_simulations,
            conn_file=self.source.conn_file,
            variables=flattened_vars,
            force_reload=True,
        )

        # Update views in layout
        with self.state:
            self.view_manager.build_auto_layout(vars_to_show)
        await self.server.network_completion

        # Reset camera after yield
        await asyncio.sleep(0.1)
        self.view_manager.reset_camera()

    @change("layout_grouped")
    def _on_layout_change(self, **_):
        self._rebuild_active_layout()

    @change("comparison_mode")
    def _on_comparison_mode_change(self, **_):
        if not self.state.variables_loaded:
            return

        self._rebuild_active_layout(update_color=True)

    @change("simulation_configs", "control_simulation_file")
    def _on_simulation_selection_change(self, simulation_configs, **_):
        if simulation_configs:
            valid_paths = {entry["path"] for entry in simulation_configs}
            if self.state.control_simulation_file not in valid_paths:
                self.state.control_simulation_file = simulation_configs[0]["path"]
        comparison_signature = comparison_signature_for(
            simulation_configs, self.state.control_simulation_file
        )
        label_signature = label_signature_for(simulation_configs)

        comparison_changed = comparison_signature != self._comparison_signature
        labels_changed = label_signature != self._simulation_label_signature

        self._comparison_signature = comparison_signature
        self._simulation_label_signature = label_signature

        if comparison_changed:
            self._refresh_source_simulations()
            if self.state.variables_loaded and self._rebuild_active_layout(update_color=True):
                return
            self.state.variables_loaded = False
            return

        if labels_changed and self.state.variables_selected and self.source.varmeta:
            self.source.RefreshViewSpecs(self.active_simulation_configs)
            self.view_manager.refresh_view_specs(self.selected_variables)

    @change("projection")
    async def _on_projection(self, projection, **_):
        proj_str = projection[0]
        self.source.UpdateProjection(proj_str)
        self.source.UpdatePipeline()
        self.view_manager.reset_camera()

        # Hack to force reset_camera for "cyl mode"
        # => may not be needed if we switch to rca
        if " " in proj_str:
            for _ in range(2):
                await asyncio.sleep(0.1)
                self.view_manager.reset_camera()

    @change("active_tools", "animation_tracks")
    def _on_toolbar_change(self, active_tools, **_):
        top_padding = 0
        for name in active_tools:
            if name == "select-slice-time":
                track_count = len(self.state.animation_tracks or [])
                rows_needed = max([1, (track_count + 2) // 3])  # 3 sliders per row
                top_padding += 70 * rows_needed
            else:
                top_padding += toolbars.SIZES.get(name, 0)

        self.state.top_padding = top_padding

    def _on_slicing_change(self, var, ind_var, **_):
        self.source.UpdateSlicing(var, self.state[ind_var])
        self.source.UpdatePipeline()

        self.view_manager.update_color_range()
        self.view_manager.render()

        # Update avg computation
        # Get area variable to calculate weighted average
        data = self.source.views["atmosphere_data"]
        self.state.fields_avgs = compute.extract_avgs(
            data, self.selected_variable_names
        )

    @change(
        # "variables_loaded",
        "crop_longitude",
        "crop_latitude",
        "projection",
    )
    def _on_downstream_change(
        self,
        # variables_loaded,
        crop_longitude,
        crop_latitude,
        projection,
        **_,
    ):
        if not self.state.variables_loaded:
            return

        self.source.ApplyClipping(crop_longitude, crop_latitude)
        self.source.UpdateProjection(projection[0])
        self.source.UpdatePipeline()

        self.view_manager.update_color_range()
        self.view_manager.render()

        # Update avg computation
        # Get area variable to calculate weighted average
        data = self.source.views["atmosphere_data"]
        self.state.fields_avgs = compute.extract_avgs(
            data, self.selected_variable_names
        )

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
