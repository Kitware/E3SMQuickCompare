import asyncio

from trame.app import asynchronous
from trame.decorators import change
from trame.widgets import html
from trame.widgets import vuetify3 as v3

from e3sm_compareview.comparison import (
    COMPARISON_TYPES,
    DEFAULT_TWO_SIM_COLUMNS,
    MULTI_SIM_COMPARISON_LABELS,
    TWO_SIM_COLUMN_LABELS,
)
from e3sm_quickview.components.toolbars import DataSelection as DataSelection
from e3sm_quickview.utils import js

DENSITY = {
    "adjust-layout": "compact",
    "simulation-controls": "compact",
    "adjust-databounds": "default",
    "select-slice-time": "default",
    "animation-controls": "compact",
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


def reload(m=None):
    if m:
        m.__loader__.exec_module(m)


class Layout(v3.VToolbar):
    def __init__(self, apply_size=None, zoom=None, pan=None, reset_camera=None):
        super().__init__(**to_kwargs("adjust-layout"))

        self.state.setdefault("show_zoom_controls", False)
        self.state.setdefault("show_pan_controls", False)
        self.state.setdefault("show_aspect_ratio", False)

        with self:
            v3.VIcon("mdi-view-module", classes="px-6 opacity-50")
            v3.VSpacer()
            with html.Div(classes="d-flex ga-2 align-center"):
                with v3.VSheet(
                    classes="d-flex align-center rounded px-1 ga-1 py-1",
                    color=("show_aspect_ratio ? 'grey-lighten-3' : 'transparent'",),
                ):
                    v3.VIconBtn(
                        v_tooltip_bottom="'Toggle aspect ratio'",
                        icon="mdi-arrow-expand-vertical",
                        flat=True,
                        click="show_aspect_ratio = !show_aspect_ratio",
                        color=("show_aspect_ratio ? 'primary' : ''",),
                        size=("show_aspect_ratio ? 'small' : 'default'",),
                        classes=("show_aspect_ratio ? 'ml-1' : 'rounded'",),
                    )
                    with (
                        v3.VExpandXTransition(),
                        html.Div(
                            v_if="show_aspect_ratio",
                            classes="d-flex align-center ga-1",
                        ),
                    ):
                        v3.VDivider(vertical=True, classes="mx-1")
                        v3.VSlider(
                            v_tooltip_bottom="'Reduce (left) / Increase (right) vertical aspect'",
                            v_model=("aspect_ratio", 0.5),
                            min=0,
                            max=4,
                            step=0.25,
                            show_ticks="always",
                            density="compact",
                            hide_details=True,
                            style="min-width: 200px; max-width: 300px;",
                        )

                with v3.VSheet(
                    classes="d-flex align-center rounded px-1 ga-1",
                    color=("show_zoom_controls ? 'grey-lighten-3' : 'transparent'",),
                ):
                    v3.VIconBtn(
                        v_tooltip_bottom="'Toggle zoom controls'",
                        icon="mdi-magnify-plus-cursor",
                        flat=True,
                        click="show_zoom_controls = !show_zoom_controls",
                        color=("show_zoom_controls ? 'primary' : ''",),
                        size=("show_zoom_controls ? 'small' : 'default'",),
                        classes=("show_zoom_controls ? 'ml-1' : 'rounded'",),
                    )
                    with (
                        v3.VExpandXTransition(),
                        html.Div(
                            v_if="show_zoom_controls",
                            classes="d-flex align-center ga-1",
                        ),
                    ):
                        v3.VDivider(vertical=True, classes="mx-1")
                        v3.VIconBtn(
                            v_tooltip_bottom="'Zoom in'",
                            icon="mdi-plus",
                            variant="plain",
                            click=(zoom, "[0.8333333]"),
                        )
                        v3.VIconBtn(
                            v_tooltip_bottom="'Zoom out'",
                            icon="mdi-minus",
                            variant="plain",
                            click=(zoom, "[1.2]"),
                        )

                with v3.VSheet(
                    classes="d-flex align-center rounded px-1 ga-1",
                    color=("show_pan_controls ? 'grey-lighten-3' : 'transparent'",),
                ):
                    v3.VIconBtn(
                        v_tooltip="'Toggle pan controls'",
                        icon="mdi-pan",
                        flat=True,
                        click="show_pan_controls = !show_pan_controls",
                        color=("show_pan_controls ? 'primary' : ''",),
                        size=("show_pan_controls ? 'small' : 'default'",),
                        classes=("show_pan_controls ? 'ml-1' : 'rounded'",),
                    )
                    with (
                        v3.VExpandXTransition(),
                        html.Div(
                            v_if="show_pan_controls",
                            classes="d-flex align-center ga-1",
                        ),
                    ):
                        v3.VDivider(vertical=True, classes="mx-1")
                        v3.VIconBtn(
                            v_tooltip_bottom="'Pan up'",
                            icon="mdi-arrow-up",
                            click=(pan, "[0, -1]"),
                            variant="plain",
                            classes="rounded",
                        )
                        v3.VIconBtn(
                            v_tooltip_bottom="'Pan down'",
                            icon="mdi-arrow-down",
                            flat=True,
                            click=(pan, "[0, 1]"),
                            variant="plain",
                        )
                        v3.VIconBtn(
                            v_tooltip_bottom="'Pan left'",
                            icon="mdi-arrow-left",
                            flat=True,
                            click=(pan, "[1, 0]"),
                            variant="plain",
                        )
                        v3.VIconBtn(
                            v_tooltip_bottom="'Pan right'",
                            icon="mdi-arrow-right",
                            flat=True,
                            click=(pan, "[-1, 0]"),
                            variant="plain",
                        )

                with v3.VBtn(
                    v_tooltip_bottom="'Auto zoom to fit'",
                    flat=True,
                    click=reset_camera,
                    density="compact",
                    icon=True,
                    classes="ml-2",
                ):
                    v3.VIcon("mdi-fit-to-page-outline")

                v3.VDivider(vertical=True, classes="mx-1")

                with v3.VBtn(
                    v_tooltip_bottom="'Column layout'",
                    flat=True,
                    icon=True,
                    density="compact",
                    classes="mr-4",
                ):
                    v3.VIcon("mdi-view-column")
                    with v3.VMenu(activator="parent"):
                        with v3.VList(density="compact"):
                            with v3.VListItem(
                                title="Full Width",
                                click=(apply_size, "[1]"),
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
                                click=(apply_size, "[2]"),
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
                                click=(apply_size, "[3]"),
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
                                click=(apply_size, "[4]"),
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
                                click=(apply_size, "[6]"),
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
            with v3.VTooltip(
                text=(
                    "crop_slider_edit ? 'Toggle to text edit' : 'Toggle to slider edit'",
                ),
            ):
                with v3.Template(v_slot_activator="{ props }"):
                    v3.VIcon(
                        "mdi-web",
                        v_bind="props",
                        classes="pl-6 opacity-50",
                        click="crop_slider_edit = !crop_slider_edit",
                    )
            with v3.VRow(
                classes="ma-0 px-2 align-center", v_if=("crop_slider_edit", True)
            ):
                with v3.VCol():
                    with v3.VRow(classes="mx-2 my-0"):
                        v3.VLabel(
                            "Longitude",
                            classes="text-subtitle-2",
                        )
                        v3.VSpacer()
                        v3.VLabel(
                            "[{{ crop_longitude[0] + spherical_center_lon }}, {{ crop_longitude[1] + spherical_center_lon }}]",
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
                # --- Spherical projection center ---
                with v3.VSheet(
                    classes="d-flex align-center rounded px-1 ga-1 py-1",
                    color=("show_longitude_center ? 'grey-lighten-3' : 'transparent'",),
                ):
                    v3.VIconBtn(
                        v_tooltip_bottom="'Toggle center location'",
                        icon="mdi-image-filter-center-focus-strong",
                        flat=True,
                        click="show_longitude_center = !show_longitude_center",
                        color=("show_longitude_center ? 'primary' : ''",),
                        size=("show_longitude_center ? 'small' : 'default'",),
                        classes=("show_longitude_center ? 'ml-1' : 'rounded'",),
                    )
                    with (
                        v3.VExpandXTransition(),
                        html.Div(
                            v_if=("show_longitude_center", True),
                            classes="d-flex align-center ga-1",
                        ),
                    ):
                        v3.VDivider(vertical=True, classes="mx-1")
                        v3.VNumberInput(
                            label="Longitude",
                            v_model=("spherical_center_lon", 0),
                            min=("-180",),
                            max=("180",),
                            step=("1",),
                            hide_details=True,
                            density="compact",
                            variant="plain",
                            flat=True,
                            control_variant="stacked",
                            inset=True,
                            style="min-width: 6rem;",
                        )
                        v3.VNumberInput(
                            label="Latitude",
                            v_model=("spherical_center_lat", 0),
                            min=("-90",),
                            max=("90",),
                            step=("1",),
                            hide_details=True,
                            density="compact",
                            style="min-width: 6rem;",
                            variant="plain",
                            flat=True,
                            control_variant="stacked",
                            inset=True,
                            disabled=("projection[0] !== 'Spherical'",),
                        )

                with v3.VCol():
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
            with v3.VRow(classes="ma-0 pl-6 pr-2 align-center ga-4", v_else=True):
                v3.VNumberInput(
                    label="Longitude (min)",
                    model_value=("crop_longitude[0] + longitude_origin + 180",),
                    update_modelValue=(
                        "$event != null"
                        " && $event - longitude_origin - 180 < crop_longitude[1]"
                        " && (crop_longitude ="
                        " [$event - longitude_origin - 180, crop_longitude[1]])"
                    ),
                    min=("longitude_origin",),
                    max=("crop_longitude[1] + longitude_origin + 180",),
                    step=[1],
                    hide_details=True,
                    density="comfortable",
                    variant="plain",
                    flat=True,
                    control_variant="stacked",
                )
                v3.VNumberInput(
                    label="Longitude (max)",
                    model_value=("crop_longitude[1] + longitude_origin + 180",),
                    update_modelValue=(
                        "$event != null"
                        " && $event - longitude_origin - 180 > crop_longitude[0]"
                        " && (crop_longitude ="
                        " [crop_longitude[0], $event - longitude_origin - 180])"
                    ),
                    min=("crop_longitude[0] + longitude_origin + 180",),
                    max=("longitude_origin + 360",),
                    step=[1],
                    hide_details=True,
                    density="comfortable",
                    variant="plain",
                    flat=True,
                    control_variant="stacked",
                    inset=True,
                )
                v3.VNumberInput(
                    label="Latitude (min)",
                    v_model=("crop_latitude_min", -90),
                    min=[-90],
                    max=("crop_latitude_max", 90),
                    step=[1],
                    hide_details=True,
                    density="comfortable",
                    variant="plain",
                    flat=True,
                    control_variant="stacked",
                    inset=True,
                )
                v3.VNumberInput(
                    label="Latitude (max)",
                    v_model=("crop_latitude_max", 90),
                    min=("crop_latitude_min", -90),
                    max=[90],
                    step=[1],
                    hide_details=True,
                    density="comfortable",
                    variant="plain",
                    flat=True,
                    control_variant="stacked",
                    inset=True,
                )
                v3.VNumberInput(
                    label="Longitude (center)",
                    v_model=("spherical_center_lon", 0),
                    min=("-180",),
                    max=("180",),
                    step=("1",),
                    hide_details=True,
                    density="comfortable",
                    variant="plain",
                    flat=True,
                    control_variant="stacked",
                    inset=True,
                )
                v3.VNumberInput(
                    label="Latitude (center)",
                    v_model=("spherical_center_lat", 0),
                    min=("-90",),
                    max=("90",),
                    step=("1",),
                    hide_details=True,
                    density="comfortable",
                    variant="plain",
                    flat=True,
                    control_variant="stacked",
                    inset=True,
                    disabled=("projection[0] !== 'Spherical'",),
                )

    @change("crop_latitude_min", "crop_latitude_max")
    def _on_crop_lat(self, crop_latitude_min, crop_latitude_max, **_):
        if crop_latitude_min is None or crop_latitude_max is None:
            return

        data_range = [float(crop_latitude_min), float(crop_latitude_max)]
        if data_range[0] < data_range[1]:
            self.state.crop_latitude = data_range

    @change("crop_latitude")
    def _sync_crop_lat_inputs(self, crop_latitude, **_):
        if not crop_latitude or len(crop_latitude) < 2:
            return

        self.state.crop_latitude_min = crop_latitude[0]
        self.state.crop_latitude_max = crop_latitude[1]


class SimulationControls(v3.VToolbar):
    def __init__(self):
        super().__init__(**to_kwargs("simulation-controls"))

        with self:
            v3.VIcon("mdi-database-cog-outline", classes="px-6 opacity-50")
            with v3.VBtnGroup(density="compact"):
                v3.VBtn(
                    "Two Sim",
                    variant="outlined",
                    size="small",
                    color="default",
                    click="comparison_mode = 'two-sim'",
                    style=(
                        "`border-width: ${comparison_mode === 'two-sim' ? '2px' : '1px'}; "
                        "border-style: solid; "
                        "border-color: ${comparison_mode === 'two-sim' ? 'rgb(var(--v-theme-primary))' : 'rgba(var(--v-border-color), var(--v-border-opacity))'}; "
                        "background-color: white; "
                        "color: ${comparison_mode === 'two-sim' ? '#000000' : 'rgba(var(--v-theme-on-surface), 0.7)'};`",
                    ),
                    classes=(
                        "`text-none ${comparison_mode === 'two-sim' ? 'font-weight-bold' : 'text-medium-emphasis'}`",
                    ),
                )
                v3.VBtn(
                    "Multi Sim",
                    variant="outlined",
                    size="small",
                    color="default",
                    click="comparison_mode = 'multi-sim'",
                    style=(
                        "`border-width: ${comparison_mode === 'multi-sim' ? '2px' : '1px'}; "
                        "border-style: solid; "
                        "border-color: ${comparison_mode === 'multi-sim' ? 'rgb(var(--v-theme-primary))' : 'rgba(var(--v-border-color), var(--v-border-opacity))'}; "
                        "background-color: white; "
                        "color: ${comparison_mode === 'multi-sim' ? '#000000' : 'rgba(var(--v-theme-on-surface), 0.7)'};`",
                    ),
                    classes=(
                        "`text-none ${comparison_mode === 'multi-sim' ? 'font-weight-bold' : 'text-medium-emphasis'}`",
                    ),
                )

            v3.VDivider(vertical=True, classes="mx-2")
            with v3.VSelect(
                v_if="comparison_mode === 'multi-sim'",
                v_model=("comparison_type", "diff"),
                items=(
                    [
                        {
                            "title": MULTI_SIM_COMPARISON_LABELS[comparison_type],
                            "value": comparison_type,
                        }
                        for comparison_type in COMPARISON_TYPES
                    ],
                ),
                item_title="title",
                item_value="value",
                density="compact",
                variant="flat",
                hide_details=True,
                style="width: 16rem;max-width: 16rem;",
            ):
                with v3.Template(v_slot_selection="{ item }"):
                    with html.Div("Comparison:", classes="ml-n3"):
                        v3.VChip(
                            "{{ item.raw.title }}",
                            size="small",
                            variant="outlined",
                            color="primary",
                        )
            with v3.VSelect(
                v_else=True,
                v_model=("selected_columns", DEFAULT_TWO_SIM_COLUMNS),
                items=(
                    [
                        {
                            "title": TWO_SIM_COLUMN_LABELS[column],
                            "value": column,
                        }
                        for column in ["ctrl", "test", "diff", "comp1", "comp2"]
                    ],
                ),
                item_title="title",
                item_value="value",
                label="Comparison columns",
                multiple=True,
                density="compact",
                variant="plain",
                hide_details=True,
                style="width: 21rem;max-width: 21rem;",
            ):
                with v3.Template(v_slot_selection="{ item, index }"):
                    v3.VChip(
                        "{{ item.raw.title }}",
                        size="small",
                        variant="outlined",
                        color="primary",
                        classes="",
                    )

            v3.VDivider(vertical=True, classes="mx-2")
            with v3.VSelect(
                v_model=("control_simulation_file", ""),
                items=("simulation_configs", []),
                item_title="label",
                item_value="path",
                density="compact",
                variant="flat",
                hide_details=True,
                disabled=("simulation_configs.length === 0",),
            ):
                with v3.Template(v_slot_selection="{ item }"):
                    with html.Div("Ctrl:", classes="ml-n3"):
                        v3.VChip(
                            "{{ item.raw.label || item.raw.path.split('/').pop() }}",
                            size="small",
                            variant="outlined",
                            color="primary",
                        )
            v3.VDivider(
                vertical=True, classes="mx-2", v_if="comparison_mode === 'two-sim'"
            )
            with v3.VSelect(
                v_if="comparison_mode === 'two-sim'",
                v_model=("two_sim_test_simulation_file", ""),
                items=(
                    "simulation_configs.filter(sim => sim.path !== control_simulation_file)",
                ),
                item_title="label",
                item_value="path",
                density="compact",
                variant="flat",
                hide_details=True,
                disabled=(
                    "simulation_configs.filter(sim => sim.path !== control_simulation_file).length === 0",
                ),
            ):
                with v3.Template(v_slot_selection="{ item }"):
                    with html.Div("Test:", classes="ml-n3"):
                        v3.VChip(
                            "{{ item.raw.label || item.raw.path.split('/').pop() }}",
                            size="small",
                            color="primary",
                            variant="outlined",
                        )
            v3.VBtn(
                "Organize simulation collection",
                v_if="comparison_mode === 'multi-sim'",
                size="small",
                variant="outlined",
                classes="text-none mx-1 mr-4",
                prepend_icon="mdi-pencil",
                click="simulation_controls_dialog = true",
            )

            with v3.VDialog(
                v_if="comparison_mode === 'multi-sim'",
                v_model=("simulation_controls_dialog", False),
                max_width=720,
                scrollable=True,
            ):
                with v3.VCard(style="max-height: 88vh;"):
                    with v3.VToolbar(
                        color="white",
                        density="compact",
                        classes="border-b-thin",
                    ):
                        v3.VIcon("mdi-database-cog-outline", classes="ml-4 mr-2")
                        v3.VLabel(
                            "Organize simulation collection", classes="text-subtitle-2"
                        )
                        v3.VSpacer()
                        with v3.VTooltip():
                            with v3.Template(v_slot_activator="{ props }"):
                                html.Div(
                                    "{{ simulation_configs.length }} loaded",
                                    v_bind="props",
                                    classes="text-caption mr-4",
                                )
                            html.Div(
                                "{{ utils.quickcompare.loadedSimulationsText(simulation_configs, control_simulation_file) }}",
                                style="white-space: pre-line;",
                            )
                        v3.VBtn(
                            icon="mdi-close",
                            variant="text",
                            size="small",
                            classes="mr-2",
                            click="simulation_controls_dialog = false",
                        )
                    with html.Div(
                        v_if="simulation_configs.length === 0", classes="pa-4"
                    ):
                        html.Div(
                            "Load simulation files first, then choose the control and comparison runs here.",
                            classes="text-body-2 text-medium-emphasis",
                        )

                    with html.Div(
                        v_else=True,
                        classes="pa-3",
                        style="max-height: calc(86vh - 64px); overflow-y: auto;",
                    ):
                        with html.Div(
                            v_for="(entry, idx) in simulation_configs",
                            key="`${entry.path}-card`",
                            classes="simulation-entry-row pb-2 d-flex align-center",
                        ):
                            with html.Div(
                                classes="d-flex flex-column align-center justify-space-between mr-2 ga-6",
                            ):
                                v3.VBtn(
                                    v_tooltip="'Move up'",
                                    icon="mdi-chevron-up",
                                    size="small",
                                    variant="outlined",
                                    density="comfortable",
                                    classes="rounded",
                                    disabled=("idx === 0",),
                                    click=(self._move_simulation, "[idx, -1]"),
                                )
                                v3.VBtn(
                                    v_tooltip="'Move down'",
                                    v_bind="props",
                                    icon="mdi-chevron-down",
                                    size="small",
                                    variant="outlined",
                                    density="comfortable",
                                    classes="rounded",
                                    disabled=("idx >= simulation_configs.length - 1",),
                                    click=(self._move_simulation, "[idx, 1]"),
                                )
                            with v3.VCard(
                                variant="outlined",
                                classes="flex-grow-1",
                            ):
                                with v3.VCardText(classes="pa-3"):
                                    with html.Div(classes="d-flex align-center ga-2"):
                                        v3.VTextField(
                                            model_value=("entry.label",),
                                            update_modelValue="utils.quickcompare.setSimulationLabel(entry.path, $event)",
                                            label="Label",
                                            density="compact",
                                            variant="outlined",
                                            hide_details=True,
                                        )
                                        v3.VBtn(
                                            v_tooltip_right="control_simulation_file === entry.path ? 'Current control simulation' : 'Set this simulation as control'",
                                            text=(
                                                "control_simulation_file === entry.path ? 'Control' : 'Set control'",
                                            ),
                                            variant="outlined",
                                            color=(
                                                "control_simulation_file === entry.path ? 'primary' : 'default'",
                                            ),
                                            classes=(
                                                "`text-none ${control_simulation_file === entry.path ? '' : 'text-medium-emphasis'}`",
                                            ),
                                            # style="min-width: 112px;",
                                            height="40px",
                                            width="120px",
                                            click=(
                                                self._on_control_selected,
                                                "[entry.path]",
                                            ),
                                        )
                                        v3.VSwitch(
                                            v_tooltip_right="'Toggle simulation inclusion'",
                                            model_value=(
                                                "control_simulation_file === entry.path ? true : entry.include",
                                            ),
                                            update_modelValue="utils.quickcompare.setSimulationInclude(entry.path, $event)",
                                            disabled=(
                                                "control_simulation_file === entry.path",
                                            ),
                                            hide_details=True,
                                            inset=True,
                                            false_icon="mdi-close",
                                            true_icon="mdi-check",
                                        )
                                    html.Div(
                                        "{{ entry.path }}",
                                        classes="text-caption text-medium-emphasis mt-2",
                                        style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: rtl; text-align: left;",
                                        title=("entry.path",),
                                    )

    def _on_control_selected(self, control_path, **_):
        self.state.control_simulation_file = control_path

    def _move_simulation(self, index, step, **_):
        configs = list(self.state.simulation_configs or [])
        next_index = index + step
        if index < 0 or next_index < 0 or next_index >= len(configs):
            return

        configs[index], configs[next_index] = configs[next_index], configs[index]
        self.state.simulation_configs = configs


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
                    v_model=("animation_track", None),
                    items=("available_animation_tracks", []),
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
                    max=("animation_step_max", 0),
                    step=1,
                    hide_details=True,
                    density="compact",
                    classes="mx-4",
                )
                v3.VDivider(vertical=True, classes="mx-2")
                v3.VIconBtn(
                    v_tooltip_bottom="'First step'",
                    icon="mdi-page-first",
                    flat=True,
                    disabled=("animation_step === 0",),
                    click="animation_step = 0",
                )
                v3.VIconBtn(
                    v_tooltip_bottom="'Previous step'",
                    icon="mdi-chevron-left",
                    flat=True,
                    disabled=("animation_step === 0",),
                    click="animation_step = Math.max(0, animation_step - 1)",
                )
                v3.VIconBtn(
                    v_tooltip_bottom="'Next step'",
                    icon="mdi-chevron-right",
                    flat=True,
                    disabled=("animation_step === animation_step_max",),
                    click="animation_step = Math.min(animation_step_max, animation_step + 1)",
                )
                v3.VIconBtn(
                    v_tooltip_bottom="'Last step'",
                    icon="mdi-page-last",
                    disabled=("animation_step === animation_step_max",),
                    flat=True,
                    click="animation_step = animation_step_max",
                )
                v3.VDivider(vertical=True, classes="mx-2")
                v3.VIconBtn(
                    v_tooltip_bottom="'Play reverse'",
                    icon=(
                        "animation_play && animation_direction === 'reverse' ? 'mdi-stop' : 'mdi-play'",
                    ),
                    flat=True,
                    click="if (animation_play && animation_direction === 'reverse') { animation_play = false } else { animation_direction = 'reverse'; animation_play = true }",
                    disabled=("animation_play && animation_direction === 'forward'",),
                    style="transform: scaleX(-1);",
                )
                v3.VIconBtn(
                    v_tooltip_bottom="'Play forward'",
                    icon=(
                        "animation_play && animation_direction === 'forward' ? 'mdi-stop' : 'mdi-play'",
                    ),
                    flat=True,
                    click="if (animation_play && animation_direction === 'forward') { animation_play = false } else { animation_direction = 'forward'; animation_play = true }",
                    disabled=("animation_play && animation_direction === 'reverse'",),
                )

    @change("animation_track")
    def _on_animation_track_change(self, animation_track, **_):
        self.state.animation_step = 0
        self.state.animation_step_max = 0

        if animation_track:
            values = None
            try:
                values = self.state[animation_track]
            except Exception:
                values = None

            if values:
                self.state.animation_step_max = len(values) - 1

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
                if s.animation_direction == "reverse":
                    if s.animation_step > 0:
                        with s:
                            s.animation_step -= 1
                        await self.server.network_completion
                    else:
                        with s:
                            s.animation_step = s.animation_step_max
                        await self.server.network_completion
                else:
                    if s.animation_step < s.animation_step_max:
                        with s:
                            s.animation_step += 1
                        await self.server.network_completion
                    else:
                        with s:
                            s.animation_step = 0
                        await self.server.network_completion
