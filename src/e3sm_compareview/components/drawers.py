from trame.decorators import change
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from e3sm_compareview import __version__ as app_version
from e3sm_compareview.assets import ASSETS
from e3sm_quickview.components import css, tools
from e3sm_quickview.utils import constants, js


class AppLogo(v3.VTooltip):
    def __init__(self, compact="compact_drawer"):
        super().__init__(
            text=f"CompareView {app_version}",
            disabled=(f"!{compact}",),
        )
        with self:
            with v3.Template(v_slot_activator="{ props }"):
                with v3.VListItem(
                    v_bind="props",
                    click=f"{compact} = !{compact}",
                ):
                    with html.Div(classes="d-flex align-center flex-grow-1"):
                        html.Img(
                            src=ASSETS.icon,
                            v_if=compact,
                            style="width: 24px; height: 24px; object-fit: contain;",
                        )
                        html.Img(
                            src=ASSETS.logo,
                            v_else=True,
                            style="height: 28px; max-width: 160px; object-fit: contain;",
                        )
                    v3.VProgressCircular(
                        color="primary",
                        indeterminate=True,
                        v_show="trame__busy",
                        v_if=compact,
                        style="position: absolute !important;left: 50%;top: 50%; transform: translate(-50%, -50%);",
                    )
                    v3.VProgressLinear(
                        v_else=True,
                        color="primary",
                        indeterminate=True,
                        v_show="trame__busy",
                        absolute=True,
                        style="top:90%;width:100%;",
                    )


class Tools(v3.VNavigationDrawer):
    def __init__(self, reset_camera=None):
        super().__init__(
            permanent=True,
            rail=("compact_drawer", True),
            width=253,
            style="transform: none;",
        )

        with self:
            with html.Div(style=css.NAV_BAR_TOP):
                with v3.VList(
                    density="compact",
                    nav=True,
                    select_strategy="independent",
                    v_model_selected=("active_tools", ["load-data"]),
                ):
                    AppLogo()
                    tools.ResetCamera(click=reset_camera)

                    v3.VDivider(classes="my-1")  # ---------------------

                    tools.StateImportExport()
                    tools.OpenFile()

                    v3.VDivider(classes="my-1")  # ---------------------

                    tools.FieldSelection()
                    tools.DataSelection()
                    tools.Animation()

                    v3.VDivider(classes="my-1")  # ---------------------

                    tools.LayoutManagement()
                    tools.MapProjection()
                    tools.Cropping()

                    # dev add-on ui reload
                    if self.server.hot_reload:
                        v3.VDivider(classes="my-1")  # ---------------------
                        tools.ActionButton(
                            compact="compact_drawer",
                            title="Refresh UI",
                            icon="mdi-database-refresh-outline",
                            click=self.ctrl.on_server_reload,
                        )

            with html.Div(style=css.NAV_BAR_BOTTOM):
                v3.VDivider()
                v3.VLabel(
                    f"{app_version}",
                    classes="text-center text-caption d-block text-wrap",
                )


class FieldSelection(v3.VNavigationDrawer):
    def __init__(self, load_variables=None):
        super().__init__(
            model_value=(js.is_active("select-fields"),),
            width=500,
            permanent=True,
            style=(f"{js.is_active('select-fields')} ? 'transform: none;' : ''",),
        )

        with self:
            with html.Div(style="position:fixed;top:0;width: 500px;"):
                # Simulation file selection dropdowns
                with v3.VRow(classes="mx-2 my-2", dense=True, v_if="pv_files_data_simulation_files.length > 1"):
                    with v3.VCol(cols=6):
                        v3.VSelect(
                            v_model=("ctrl_simulation_file", "pv_files_data_simulation_files[0]"),
                            items=("pv_files_data_simulation_files", []),
                            label="Control Simulation",
                            density="compact",
                            variant="outlined",
                            hide_details=True,
                        )
                    with v3.VCol(cols=6):
                        v3.VSelect(
                            v_model=("test_simulation_file", "pv_files_data_simulation_files[1] || pv_files_data_simulation_files[0]"),
                            items=("pv_files_data_simulation_files", []),
                            label="Test Simulation",
                            density="compact",
                            variant="outlined",
                            hide_details=True,
                        )

                with v3.VCardActions(classes="px-2", style="min-height: 0;"):
                    v3.VBtn(
                        classes="text-none",
                        color="primary",
                        prepend_icon="mdi-database",
                        text=(
                            "`Load ${variables_selected.length} variable${variables_selected.length > 1 ? 's' :''}`",
                        ),
                        variant="flat",
                        block=True,
                        disabled=(
                            "variables_selected.length === 0 || variables_loaded",
                        ),
                        click=load_variables,
                    )
                with v3.VCardActions(
                    classes="flex-wrap py-1",
                    style="overflow-y: auto; max-height: 100px; min-height: 42px;",
                ):
                    v3.VChip(
                        "{{ variables_selected.filter(id => variables_listing.find(v => v.id === id)?.type === vtype.name).length }} {{ vtype.name }}",
                        v_for="(vtype, idx) in variable_types",
                        key="idx",
                        color=("vtype.color",),
                        v_show=(
                            "variables_selected.filter(id => variables_listing.find(v => v.id === id)?.type === vtype.name).length",
                        ),
                        size="small",
                        closable=True,
                        click_close=(
                            "variables_selected = variables_selected.filter(id => variables_listing.find(v => v.id === id)?.type !== vtype.name)"
                        ),
                        classes="ma-1",
                    )

                v3.VTextField(
                    v_model=("variables_filter", ""),
                    hide_details=True,
                    color="primary",
                    placeholder="Filter",
                    density="compact",
                    variant="outlined",
                    classes="mx-2",
                    prepend_inner_icon="mdi-magnify",
                    clearable=True,
                )
                with html.Div(style="margin:1px;"):
                    v3.VDataTable(
                        v_model=("variables_selected", []),
                        show_select=True,
                        item_value="id",
                        density="compact",
                        fixed_header=True,
                        headers=(
                            "variables_headers",
                            constants.VAR_HEADERS,
                        ),
                        items=("variables_listing", []),
                        height="calc(100vh - 6rem)",
                        style="user-select: none; cursor: pointer;",
                        hover=True,
                        search=("variables_filter", ""),
                        items_per_page=-1,
                        hide_default_footer=True,
                    )

    @change("variables_selected")
    def _on_dirty_variable_selection(self, **_):
        self.state.variables_loaded = False

    @change("ctrl_simulation_file", "test_simulation_file")
    def _on_dirty_simulation_selection(self, **_):
        self.state.variables_loaded = False
