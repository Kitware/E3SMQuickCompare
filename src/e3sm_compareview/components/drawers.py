from trame.decorators import change
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from e3sm_compareview import __version__ as app_version
from e3sm_compareview.assets import ASSETS
from e3sm_quickview.components import css, tools
from e3sm_quickview.utils import constants, js

DRAWER_TRANSITION_STYLE = "transition: none !important;"


def drawer_style(tool_name):
    return (
        f"{js.is_active(tool_name)} ? "
        f"'transform: none; {DRAWER_TRANSITION_STYLE}' : "
        f"'{DRAWER_TRANSITION_STYLE}'"
    )


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


class SimulationSelectionTool(v3.VTooltip):
    def __init__(self, click=None, compact="compact_drawer"):
        super().__init__(
            text="Simulation selection",
            disabled=(f"!{compact}",),
        )
        with self:
            with v3.Template(v_slot_activator="{ props }"):
                v3.VListItem(
                    v_bind="props",
                    active=(js.is_active("select-simulations"),),
                    prepend_icon="mdi-database-cog-outline",
                    title=(f"{compact} ? null : 'Simulation selection'",),
                    click=click,
                    disabled=("simulation_configs.length === 0",),
                )


class FieldSelectionTool(v3.VTooltip):
    def __init__(self, click=None, compact="compact_drawer"):
        super().__init__(
            text="Variable selection",
            disabled=(f"!{compact}",),
        )
        with self:
            with v3.Template(v_slot_activator="{ props }"):
                with v3.VListItem(
                    v_bind="props",
                    active=(js.is_active("select-fields"),),
                    prepend_icon="mdi-list-status",
                    title=(f"{compact} ? null : 'Variable selection'",),
                    click=click,
                    disabled=("variables_listing.length === 0",),
                ):
                    with v3.Template(v_slot_append=True):
                        v3.VHotkey(
                            keys="v",
                            variant="contained",
                            inline=True,
                            classes="mt-n2",
                        )


class Tools(v3.VNavigationDrawer):
    def __init__(self, reset_camera=None, toggle_toolbar=None):
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
                    SimulationSelectionTool(
                        click=(toggle_toolbar, "['select-simulations']")
                    )

                    v3.VDivider(classes="my-1")  # ---------------------

                    FieldSelectionTool(click=(toggle_toolbar, "['select-fields']"))
                    tools.DataSelection()
                    tools.Animation()
                    tools.ToggleButton(
                        compact="compact_drawer",
                        title="Comparison mode",
                        icon="mdi-compare-horizontal",
                        value="comparison-controls",
                    )

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
            style=(drawer_style("select-fields"),),
        )

        with self:
            with html.Div(style="position:fixed;top:0;width: 500px;"):
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


class SimulationSelection(v3.VNavigationDrawer):
    def __init__(self):
        super().__init__(
            model_value=(js.is_active("select-simulations"),),
            width=500,
            permanent=True,
            style=(drawer_style("select-simulations"),),
        )

        with self:
            with html.Div(style="position:fixed;top:0;width: 500px;"):
                with v3.VToolbar(
                    color="white",
                    density="compact",
                    classes="border-b-thin",
                ):
                    v3.VIcon("mdi-database-cog-outline", classes="ml-4 mr-2")
                    v3.VLabel("Simulation selection", classes="text-subtitle-2")
                    v3.VSpacer()
                    html.Div(
                        "{{ simulation_configs.length }} loaded",
                        classes="text-caption mr-4",
                    )

                with html.Div(v_if="simulation_configs.length === 0", classes="pa-4"):
                    html.Div(
                        "Load simulation files first, then choose the control and comparison runs here.",
                        classes="text-body-2 text-medium-emphasis",
                    )

                with html.Div(
                    v_else=True,
                    classes="pa-2",
                    style="max-height: calc(100vh - 48px); overflow-y: auto;",
                ):
                    with v3.VCard(
                        v_for="(entry, idx) in simulation_configs",
                        key="`${entry.path}-card`",
                        variant="outlined",
                        classes="mb-2",
                    ):
                        with v3.VCardText(classes="pa-3"):
                            with v3.VRow(dense=True, classes="align-center"):
                                with v3.VCol(cols=12, md=6):
                                    v3.VTextField(
                                        model_value=("entry.label",),
                                        update_modelValue="""
simulation_configs = simulation_configs.map((sim) =>
  sim.path === entry.path ? ({ ...sim, label: $event }) : sim
)
""",
                                        label="Label",
                                        density="compact",
                                        variant="outlined",
                                        hide_details=True,
                                    )
                                with v3.VCol(cols=6, md=3):
                                    v3.VBtn(
                                        text=(
                                            "control_simulation_file === entry.path ? 'Control' : 'Set control'",
                                        ),
                                        variant=(
                                            "control_simulation_file === entry.path ? 'flat' : 'outlined'",
                                        ),
                                        color=(
                                            "control_simulation_file === entry.path ? 'primary' : 'default'",
                                        ),
                                        classes="text-none w-100",
                                        style="min-width: 112px;",
                                        size="small",
                                        click="control_simulation_file = entry.path",
                                    )
                                with v3.VCol(cols=6, md=3):
                                    v3.VCheckbox(
                                        model_value=(
                                            "control_simulation_file === entry.path ? true : entry.include",
                                        ),
                                        update_modelValue="""
simulation_configs = simulation_configs.map((sim) =>
  sim.path === entry.path ? ({ ...sim, include: !!$event }) : sim
)
""",
                                        label="Include",
                                        density="compact",
                                        hide_details=True,
                                        disabled=("control_simulation_file === entry.path",),
                                    )
                            html.Div(
                                "{{ entry.path }}",
                                classes="text-caption text-medium-emphasis mt-2",
                                style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left;",
                                title=("entry.path",),
                            )
