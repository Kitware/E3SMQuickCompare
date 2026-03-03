from trame.widgets import html
from trame.widgets import vuetify3 as v3

from e3sm_compareview.assets import ASSETS
from e3sm_quickview.components.doc import (
    Bold,
    Link,
    Paragraph,
    Title,
    ToolAnimation,
    ToolCropping,
    ToolDataSelection,
    ToolFieldSelection,
    ToolFileLoading,
    ToolLayoutManagement,
    ToolMapProjection,
    ToolResetCamera,
    ToolStateImportExport,
)


class LandingPage(v3.VContainer):
    def __init__(self):
        super().__init__(classes="pa-6 pa-md-12")

        with self:
            html.P(
                "QuickCompare",
                classes="mt-2 text-h5 font-weight-bold text-sm-h4 text-medium-emphasis",
            )

            Paragraph(
                f"""
                {Bold("EAM QuickCompare")} is an open-source, interactive visualization
                tool designed for scientists working with the atmospheric component
                of the {Link("Energy Exascale Earth System Model (E3SM)", "https://e3sm.org/")},
                known as the E3SM Atmosphere Model (EAM).
                Its Python- and {Link("Trame", "https://www.kitware.com/trame/")}-based
                Graphical User Interface (GUI) provides intuitive access to {Link("ParaView's", "https://www.paraview.org/")} powerful analysis
                and visualization capabilities, without the steep learning curve.
            """
            )

            Paragraph(
                f"""
                {Bold("QuickCompare")} is an offshoot of {Link("QuickView", "https://github.com/Kitware/QuickView")}.
                Its focus is comparison between two or more simulations that use
                the same connectivity file.
            """
            )

            v3.VImg(classes="rounded-lg", src=ASSETS.banner)

            Title("Getting started")

            with v3.VRow():
                with v3.VCol(cols=6):
                    ToolFileLoading()
                    ToolFieldSelection()
                    ToolMapProjection()
                    ToolResetCamera()

                with v3.VCol(cols=6):
                    ToolLayoutManagement()
                    ToolCropping()
                    ToolDataSelection()
                    ToolAnimation()
                    ToolStateImportExport()

            Title("Keyboard shortcuts")

            with v3.VRow():
                with v3.VCol(cols=6):
                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle help")
                        v3.VSpacer()
                        v3.VHotkey(keys="h", variant="contained", inline=True)

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Auto zoom")
                        v3.VSpacer()
                        v3.VHotkey(keys="z", variant="contained", inline=True)

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle view interaction lock")
                        v3.VSpacer()
                        v3.VHotkey(keys="space", variant="contained", inline=True)

                    v3.VDivider(classes="mb-4")

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("File Open")
                        v3.VSpacer(classes="mt-2")
                        v3.VHotkey(keys="f", variant="contained", inline=True)

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Download state")
                        v3.VSpacer(classes="mt-2")
                        v3.VHotkey(keys="d", variant="contained", inline=True)

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Upload state")
                        v3.VSpacer(classes="mt-2")
                        v3.VHotkey(keys="u", variant="contained", inline=True)

                    v3.VDivider(classes="mb-4")

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle viewport layout toolbar")
                        v3.VSpacer(classes="mt-2")
                        v3.VHotkey(keys="p", variant="contained", inline=True)
                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle Lat/Long cropping toolbar")
                        v3.VSpacer()
                        v3.VHotkey(keys="l", variant="contained", inline=True)
                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle Slice selection toolbar")
                        v3.VSpacer()
                        v3.VHotkey(keys="s", variant="contained", inline=True)
                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle Animation controls toolbar")
                        v3.VSpacer()
                        v3.VHotkey(keys="a", variant="contained", inline=True)

                    v3.VDivider(classes="mb-4")

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle group layout")
                        v3.VSpacer()
                        v3.VHotkey(keys="g", variant="contained", inline=True)

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Toggle variable selection drawer")
                        v3.VSpacer()
                        v3.VHotkey(keys="v", variant="contained", inline=True)

                    v3.VDivider(classes="mb-4")

                    with v3.VRow(classes="ma-0 pb-4"):
                        v3.VLabel("Disable all toolbars and drawers")
                        v3.VSpacer()
                        v3.VHotkey(keys="esc", variant="contained", inline=True)

                with v3.VCol(cols=6):
                    with v3.VRow(classes="ma-0 pb-2"):
                        v3.VLabel("Projections")

                    with v3.VList(density="compact", classes="pa-0 ma-0"):
                        with v3.VListItem(subtitle="Cylindrical Equidistant"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="c", variant="contained", inline=True)
                        with v3.VListItem(subtitle="Robinson"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="r", variant="contained", inline=True)
                        with v3.VListItem(subtitle="Mollweide"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="m", variant="contained", inline=True)

                    v3.VDivider(classes="my-4")

                    with v3.VRow(classes="ma-0 pb-2"):
                        v3.VLabel("Apply size")

                    with v3.VList(density="compact", classes="pa-0 ma-0"):
                        with v3.VListItem(subtitle="Auto flow"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="=", variant="contained", inline=True)
                        with v3.VListItem(subtitle="Auto"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="0", variant="contained", inline=True)
                        with v3.VListItem(subtitle="1 column"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="1", variant="contained", inline=True)
                        with v3.VListItem(subtitle="2 columns"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="2", variant="contained", inline=True)
                        with v3.VListItem(subtitle="3 columns"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="3", variant="contained", inline=True)
                        with v3.VListItem(subtitle="4 columns"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="4", variant="contained", inline=True)
                        with v3.VListItem(subtitle="6 columns"):
                            with v3.Template(v_slot_append="True"):
                                v3.VHotkey(keys="6", variant="contained", inline=True)

            Title("Simulation Files")

            Paragraph(
                """
                QuickCompare has been developed using EAM's history output on
                the physics grids (pg2 grids) written by EAMv2, v3, and an
                intermediate version towards v4 (EAMxx).
                Those sample output files can be found on Zenodo.
                """
            )
            Paragraph(
                """
                Developers and users of EAM often use tools like NCO and CDO
                or write their own scripts to calculate time averages and/or
                select a subset of variables from the original model output.
                For those use cases, we clarify below the features of the data
                format that QuickCompare expects in order to properly read and
                visualize the simulation data.
                """
            )

            Title("Connectivity Files")

            Paragraph(
                """
                The horizontal grids used by EAM are cubed spheres.
                Since these are unstructed grids, QuickCompare needs
                to know how to map data to the globe. Therefore,
                for each simulation data file, a "connectivity file"
                needs to be provided.
                """
            )

            Paragraph(
                """
                In EAMv2, v3, and v4, most of the variables
                (physical quantities) are written out on a
                "physics grid" (also referred to as "physgrid",
                "FV grid", or "control volume mesh") described
                in Hannah et al. (2021). The naming convention
                for such grids is ne*pg2, with * being a number,
                e.g., 4, 30, 120, 256. Further details about EAM's
                cubed-sphere grids can be found in EAM's documention,
                for example in this overview and this description.
                """
            )
            Paragraph(
                """
                Future versions of QuickCompare will also support the
                cubed-sphere meshes used by EAM's dynamical core,
                i.e., the ne*np4 grids (also referred to as
                "native grids" or "GLL grids").
                """
            )

            Title("Project Background")

            Paragraph(
                """
                The lead developer of EAM QuickCompare is Abhishek Yenpure (abhi.yenpure@kitware.com)
                at Kitware, Inc.. Other key contributors at Kitware, Inc. include Berk Geveci and
                Sebastien Jourdain. Key contributors on the atmospheric science side are Hui Wan
                and Kai Zhang at Pacific Northwest National Laboratory.
                """
            )
