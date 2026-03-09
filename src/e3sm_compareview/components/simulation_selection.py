from trame.widgets import html
from trame.widgets import vuetify3 as v3

from e3sm_compareview.components.drawer_utils import drawer_style
from e3sm_compareview.comparison import normalize_two_sim_target
from e3sm_quickview.utils import js

SIMULATION_DRAG_HANDLE_EVENTS = """
{
  dragstart: (event) => {
    dragged_simulation_path = entry.path;
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', entry.path);
  },
  dragend: () => {
    dragged_simulation_path = '';
  }
}
"""
SIMULATION_DROP_EVENTS = """
{
  dragover: (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  },
  drop: (event) => {
    event.preventDefault();
    const draggedPath = dragged_simulation_path || event.dataTransfer.getData('text/plain');
    if (!draggedPath || draggedPath === entry.path) {
      dragged_simulation_path = '';
      return;
    }

    const fromIndex = simulation_configs.findIndex((sim) => sim.path === draggedPath);
    const toIndex = simulation_configs.findIndex((sim) => sim.path === entry.path);
    if (fromIndex < 0 || toIndex < 0) {
      dragged_simulation_path = '';
      return;
    }

    const nextConfigs = [...simulation_configs];
    const [moved] = nextConfigs.splice(fromIndex, 1);
    nextConfigs.splice(toIndex, 0, moved);
    simulation_configs = nextConfigs;
    dragged_simulation_path = '';
  }
}
"""


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
                with html.Div(classes="px-3 py-2 border-b-thin"):
                    with v3.VBtnToggle(
                        v_model=("comparison_mode", "multi-sim"),
                        mandatory=True,
                        density="compact",
                        divided=True,
                    ):
                        v3.VBtn("Two Sim", value="two-sim", classes="text-none")
                        v3.VBtn("Multi Sim", value="multi-sim", classes="text-none")

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
                    with html.Div(
                        v_for="(entry, idx) in simulation_configs",
                        key="`${entry.path}-card`",
                        classes="pb-2 d-flex align-center",
                        v_on=SIMULATION_DROP_EVENTS,
                    ):
                        with html.Div(
                            draggable="true",
                            title="Drag to reorder",
                            style="cursor: grab; user-select: none;",
                            classes="d-flex align-center justify-center mr-1",
                            v_on=SIMULATION_DRAG_HANDLE_EVENTS,
                        ):
                            v3.VIcon(
                                "mdi-drag-vertical-variant",
                                size="small",
                                color="default",
                                classes="opacity-60",
                            )
                        with v3.VCard(
                            variant="outlined",
                            classes="flex-grow-1",
                        ):
                            with v3.VCardText(classes="pa-3"):
                                with v3.VRow(dense=True, classes="align-center"):
                                    with v3.VCol(cols=12, md=6):
                                        v3.VTextField(
                                            model_value=("entry.label",),
                                            update_modelValue="""
simulation_configs = simulation_configs.map((sim) =>
  sim.path === entry.path ? ({ ...sim, label: $event }) : sim
);
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
                                            click=(
                                                self._on_control_selected,
                                                "[entry.path]",
                                            ),
                                        )
                                    with v3.VCol(cols=6, md=3):
                                        with v3.Template(v_if="comparison_mode === 'multi-sim'"):
                                            v3.VCheckbox(
                                                model_value=(
                                                    "control_simulation_file === entry.path ? true : entry.include",
                                                ),
                                                update_modelValue="""
simulation_configs = simulation_configs.map((sim) =>
  sim.path === entry.path ? ({ ...sim, include: !!$event }) : sim
);
""",
                                                label="Include",
                                                density="compact",
                                                hide_details=True,
                                                disabled=(
                                                    "control_simulation_file === entry.path",
                                                ),
                                            )
                                        with v3.Template(v_else=True):
                                            v3.VBtn(
                                                text=(
                                                    "two_sim_test_simulation_file === entry.path ? 'Test' : 'Set test'",
                                                ),
                                                variant=(
                                                    "two_sim_test_simulation_file === entry.path ? 'flat' : 'outlined'",
                                                ),
                                                color=(
                                                    "two_sim_test_simulation_file === entry.path ? 'primary' : 'default'",
                                                ),
                                                classes="text-none w-100",
                                                style="min-width: 112px;",
                                                size="small",
                                                disabled=(
                                                    "control_simulation_file === entry.path",
                                                ),
                                                click="two_sim_test_simulation_file = entry.path",
                                            )
                                html.Div(
                                    "{{ entry.path }}",
                                    classes="text-caption text-medium-emphasis mt-2",
                                    style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left;",
                                    title=("entry.path",),
                                )

    def _on_control_selected(self, control_path, **_):
        self.state.control_simulation_file = control_path
        if self.state.comparison_mode != "two-sim":
            return

        self.state.two_sim_test_simulation_file = normalize_two_sim_target(
            self.state.simulation_configs,
            control_path,
            self.state.two_sim_test_simulation_file,
        )
