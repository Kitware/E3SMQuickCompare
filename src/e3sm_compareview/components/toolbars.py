import asyncio

from trame.app import asynchronous
from trame.decorators import change
from trame.widgets import client, html
from trame.widgets import vuetify3 as v3

from e3sm_compareview.comparison import COMPARISON_TYPES
from e3sm_quickview.utils import js

DENSITY = {
    "adjust-layout": "compact",
    "comparison-controls": "compact",
    "adjust-databounds": "default",
    "select-slice-time": "default",
    "animation-controls": "compact",
}

SIZES = {
    "adjust-layout": 49,
    "comparison-controls": 49,
    "adjust-databounds": 65,
    "select-slice-time": 70,
    "animation-controls": 49,
}

DEFAULT_STYLES = {
    "color": "white",
    "classes": "border-b-thin",
}


def to_kwargs(value):
    return {
        "v_show": js.is_active(value),
        "density": DENSITY[value],
        **DEFAULT_STYLES,
    }


class Layout(html.Div):
    def __init__(self, apply_size=None):
        style = to_kwargs("adjust-layout")
        style["style"] = "background: rgb(var(--v-theme-surface));"
        super().__init__(**style)

        with self:
            # First row - existing layout controls
            with v3.VToolbar(density="compact", color="white", classes="border-b-thin"):
                v3.VIcon("mdi-collage", classes="px-6 opacity-50")
                v3.VLabel("Viewport layout", classes="text-subtitle-2")
                v3.VSpacer()

                v3.VSlider(
                    v_model=("aspect_ratio", 2),
                    prepend_icon="mdi-aspect-ratio",
                    min=1,
                    max=2,
                    step=0.1,
                    density="compact",
                    hide_details=True,
                    style="max-width: 400px;",
                )
                v3.VSpacer()

                # ------------------------------------------------------------
                # Add tooltip for keyboard shortcut??
                # ------------------------------------------------------------
                # with v3.VTooltip(location="bottom"):
                #    with v3.Template(v_slot_activator="{ props }"):
                v3.VHotkey(keys="g", variant="contained", classes="mr-1")
                v3.VCheckbox(
                    # v_bind="props",
                    v_model=("layout_grouped", True),
                    label=("layout_grouped ? 'Grouped' : 'Uniform'",),
                    hide_details=True,
                    inset=True,
                    false_icon="mdi-apps",
                    true_icon="mdi-focus-field",
                    density="compact",
                )
                # with html.Span("Keyboard shortcut"):
                #     v3.VHotkey(theme="dark", keys="g", variant="contained", inline=True, classes="ml-2 mt-n2")
                # ------------------------------------------------------------

                with v3.VBtn(
                    "Size",
                    classes="text-none mx-4",
                    prepend_icon="mdi-view-module",
                    append_icon="mdi-menu-down",
                ):
                    with v3.VMenu(activator="parent"):
                        with v3.VList(density="compact"):
                            with v3.VListItem(
                                title="Auto flow",
                                click=(
                                    apply_size,
                                    "['flow']",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="=",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )
                            with v3.VListItem(
                                title="Auto",
                                click=(
                                    apply_size,
                                    "[0]",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="0",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )
                            with v3.VListItem(
                                title="Full Width",
                                click=(
                                    apply_size,
                                    "[1]",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="1",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )
                            with v3.VListItem(
                                title="2 Columns",
                                click=(
                                    apply_size,
                                    "[2]",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="2",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )
                            with v3.VListItem(
                                title="3 Columns",
                                click=(
                                    apply_size,
                                    "[3]",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="3",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )
                            with v3.VListItem(
                                title="4 Columns",
                                click=(
                                    apply_size,
                                    "[4]",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="4",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )
                            with v3.VListItem(
                                title="6 Columns",
                                click=(
                                    apply_size,
                                    "[6]",
                                ),
                            ):
                                with v3.Template(v_slot_append=True):
                                    v3.VHotkey(
                                        keys="6",
                                        variant="contained",
                                        inline=True,
                                        classes="ml-6 mt-n1",
                                    )

class Cropping(v3.VToolbar):
    def __init__(self):
        super().__init__(**to_kwargs("adjust-databounds"))

        with self:
            v3.VIcon("mdi-web", classes="pl-6 opacity-50")
            with v3.VRow(classes="ma-0 px-2 align-center"):
                with v3.VCol(cols=6):
                    with v3.VRow(classes="mx-2 my-0"):
                        v3.VLabel(
                            "Longitude",
                            classes="text-subtitle-2",
                        )
                        v3.VSpacer()
                        v3.VLabel(
                            "{{ crop_longitude }}",
                            classes="text-body-2",
                        )
                    v3.VRangeSlider(
                        v_model=("crop_longitude", [-180, 180]),
                        min=-180,
                        max=180,
                        step=1,
                        density="compact",
                        hide_details=True,
                    )
                with v3.VCol(cols=6):
                    with v3.VRow(classes="mx-2 my-0"):
                        v3.VLabel(
                            "Latitude",
                            classes="text-subtitle-2",
                        )
                        v3.VSpacer()
                        v3.VLabel(
                            "{{ crop_latitude }}",
                            classes="text-body-2",
                        )
                    v3.VRangeSlider(
                        v_model=("crop_latitude", [-90, 90]),
                        min=-90,
                        max=90,
                        step=1,
                        density="compact",
                        hide_details=True,
                    )


class ComparisonMode(v3.VToolbar):
    def __init__(self):
        super().__init__(**to_kwargs("comparison-controls"))

        with self:
            v3.VIcon("mdi-compare-horizontal", classes="pl-6 opacity-50")
            with v3.Template(v_if="comparison_mode === 'multi-sim'"):
                v3.VLabel("Comparison", classes="text-subtitle-2 px-4")
                for comparison_type in COMPARISON_TYPES:
                    v3.VBtn(
                        comparison_type.upper(),
                        size="small",
                        variant=(
                            f"comparison_type === '{comparison_type}' ? 'flat' : 'outlined'",
                        ),
                        color=(
                            f"comparison_type === '{comparison_type}' ? 'primary' : 'default'",
                        ),
                        classes="mx-1 text-none",
                        click=f"comparison_type = '{comparison_type}'",
                    )
                v3.VSpacer()
                html.Div(
                    "{{ Math.max(0, simulation_configs.filter(sim => sim.path !== control_simulation_file && sim.include).length) }} comparisons",
                    classes="text-caption mr-4",
                )

            with v3.Template(v_else=True):
                v3.VLabel("Columns", classes="text-subtitle-2 px-4")
                for comp_type in ["ctrl", "test", "diff", "comp1", "comp2"]:
                    v3.VBtn(
                        comp_type.upper(),
                        size="small",
                        variant=(
                            "selected_columns.includes('{0}') ? 'flat' : 'outlined'".format(
                                comp_type
                            ),
                        ),
                        color=(
                            "selected_columns.includes('{0}') ? 'primary' : 'default'".format(
                                comp_type
                            ),
                        ),
                        classes="mx-1 text-none",
                        click=(
                            f"selected_columns.includes('{comp_type}') ? "
                            f"selected_columns = selected_columns.filter(c => c !== '{comp_type}') : "
                            f"selected_columns = [...selected_columns, '{comp_type}']"
                        ),
                    )
                v3.VSpacer()
                v3.VBtn(
                    "Show all",
                    size="small",
                    variant="text",
                    classes="mr-2 text-none",
                    click="selected_columns = ['ctrl', 'test', 'diff', 'comp1', 'comp2']",
                )


class DataSelection(html.Div):
    def __init__(self):
        style = to_kwargs("select-slice-time")
        # Use style instead of d-flex class to avoid !important override of v-show
        # Add background color to match VToolbar appearance
        style["style"] = (
            "display: flex; align-items: center; background: rgb(var(--v-theme-surface));"
        )
        super().__init__(**style)

        with self:
            v3.VIcon("mdi-tune-variant", classes="ml-3 mr-2 opacity-50")

            with v3.VRow(classes="ma-0 pr-2 flex-wrap flex-grow-1", dense=True):
                # Debug: Show animation_tracks array
                # html.Div("Animation Tracks: {{ JSON.stringify(animation_tracks) }}", classes="col-12")
                # Each track gets a column (3 per row)
                with v3.VCol(
                    cols=4,
                    v_for="(track, idx) in animation_tracks",
                    key="idx",
                    classes="pa-2",
                ):
                    with client.Getter(name=("track.value",), value_name="t_values"):
                        with client.Getter(
                            name=("track.value + '_idx'",), value_name="t_idx"
                        ):
                            with v3.VRow(classes="ma-0 align-center", dense=True):
                                v3.VLabel(
                                    "{{track.title}}",
                                    classes="text-subtitle-2",
                                )
                                v3.VSpacer()
                                v3.VLabel(
                                    "{{ parseFloat(t_values[t_idx]).toFixed(2) }} hPa (k={{ t_idx }})",
                                    classes="text-body-2",
                                )
                            v3.VSlider(
                                model_value=("t_idx",),
                                update_modelValue=(
                                    self.on_update_slider,
                                    "[track.value, $event]",
                                ),
                                min=0,
                                # max=100,#("get(track.value).length - 1",),
                                max=("t_values.length - 1",),
                                step=1,
                                density="compact",
                                hide_details=True,
                            )

    def on_update_slider(self, dimension, index, *_, **__):
        with self.state:
            self.state[f"{dimension}_idx"] = index


class Animation(v3.VToolbar):
    def __init__(self):
        super().__init__(**to_kwargs("animation-controls"))

        with self:
            v3.VIcon(
                "mdi-video",
                classes="px-6 opacity-50",
            )
            with v3.VRow(classes="ma-0 px-2 align-center"):
                v3.VSelect(
                    v_model=("animation_track", "timestamps"),
                    items=("animation_tracks", []),
                    flat=True,
                    variant="plain",
                    hide_details=True,
                    density="compact",
                    style="max-width: 10rem;",
                )
                v3.VDivider(vertical=True, classes="mx-2")
                v3.VSlider(
                    v_model=("animation_step", 1),
                    min=0,
                    max=("amimation_step_max", 0),
                    step=1,
                    hide_details=True,
                    density="compact",
                    classes="mx-4",
                )
                v3.VDivider(vertical=True, classes="mx-2")
                v3.VIconBtn(
                    icon="mdi-page-first",
                    flat=True,
                    disabled=("animation_step === 0",),
                    click="animation_step = 0",
                )
                v3.VIconBtn(
                    icon="mdi-chevron-left",
                    flat=True,
                    disabled=("animation_step === 0",),
                    click="animation_step = Math.max(0, animation_step - 1)",
                )
                v3.VIconBtn(
                    icon="mdi-chevron-right",
                    flat=True,
                    disabled=("animation_step === amimation_step_max",),
                    click="animation_step = Math.min(amimation_step_max, animation_step + 1)",
                )
                v3.VIconBtn(
                    icon="mdi-page-last",
                    disabled=("animation_step === amimation_step_max",),
                    flat=True,
                    click="animation_step = amimation_step_max",
                )
                v3.VDivider(vertical=True, classes="mx-2")
                v3.VIconBtn(
                    icon=("animation_play ? 'mdi-stop' : 'mdi-play'",),
                    flat=True,
                    click="animation_play = !animation_play",
                )

    @change("animation_track")
    def _on_animation_track_change(self, animation_track, **_):
        self.state.animation_step = 0
        self.state.amimation_step_max = 0

        if animation_track:
            self.state.amimation_step_max = len(self.state[animation_track]) - 1

    @change("animation_step")
    def _on_animation_step(self, animation_track, animation_step, **_):
        if animation_track:
            self.state[f"{animation_track}_idx"] = animation_step

    @change("animation_play")
    def _on_animation_play(self, animation_play, **_):
        if animation_play:
            asynchronous.create_task(self._run_animation())

    async def _run_animation(self):
        with self.state as s:
            while s.animation_play:
                await asyncio.sleep(0.1)
                if s.animation_step < s.amimation_step_max:
                    with s:
                        s.animation_step += 1
                    await self.server.network_completion
                else:
                    s.animation_play = False
