# Data

QuickView has been developed using EAM's history output on the physics grids
(`pg2` grids) written by EAMv2, v3, and an intermediate version towards v4
(EAMxx). Those sample output files can be found on
[Zenodo](https://zenodo.org/records/16922607).

Developers and users of EAM often use tools like NCO and CDO or write their own
scripts to calculate time averages and/or select a subset of variables from the
original model output. For those use cases, we clarify below the features of the
data format that QuickView expects in order to properly read and visualize the
simulation data.

::: tip Tip: Consistency Between Simulation File and Connecitivity File One of
the repeatedly encountered causes of error when loading files in QuickView is
that the grid described by the connecitivity file does not match the grid in the
simulation data file.
:::

::: warning Caution: Newer EAMxx Output Files The EAMxx output file that
QuickView has been tested for was generated in late 2024. As EAMxx further
evolves and its output format changes, QuickView might need to be updated
accordingly. If the user encounters such a case, we recommend reaching out to
our developers or using the
[Issue tab on GitHub](https://github.com/Kitware/QuickView/issues) to start a
discussion.
:::

## Overview

The ParaView Reader behind the QuickView GUI detects and categorizes variables
based on their dimensions. Variables with dimensions not matching the expected
patterns are ignored.

## 2D variables

QuickView recognizes variables with—and only with—the **dimensions `time` and
`ncol`** as 2D variables, i.e., physical quantities varying with latitude and
longitude but without a vertical dimension. These are referred to as "surface
variables" in the control panel. For these variables, the only required
^^coordinate variable^^ is ^^`time`^^. Grid information, including latitude and
longitude, are obtained from the connecitivity file.

If an `area` variable with the dimension `ncol` is also present, this variable
is used for calculating the area-weighted horizontal averages displayed in the
viewport. If the `area` variable is not present, then an arithmetic average is
calculated and displayed.

## 3D variables

If a variables has not only `time` and `ncol` but also a vertical dimension,
QuickView expects the dimension to be named **`lev`** for variables defined at
layer midpoints and **`ilev`** for variables defined at layer interfaces.

For variables defined at layer midpoints, in order for the `Slice Selection`
section of the control panel to work properly, the simulation data file needs to
contain a 1D coordinate variable named `lev`, the values of which are
interpreted as pressure in hPa. If `lev` is not present, QuickView attempts to
find two 1D variables, `hyam` and `hybm`, of that dimension size, from which
QuickView calculates `lev` using

```
lev = (hyam * P0) + (hybm * PS0)
```

where PS0 = 1000 hPa; P0 is read from the data file and set to 1000 hPa if not
found.

Similarly, for variables defined at layer interfaces, QuickView looks for either
`ilev` or `hyai` and `hybi` for parsing the vertical dimension.

## Variable with more dimensions

QuickView currently only visualizes the variables types discussed above. For
variables that have extra dimensions in addition to `time`, `ncol`, and `lev` or
`ilev`, for example aggregated tracer arrays or
[COSP](https://climatedataguide.ucar.edu/climate-data/cosp-cloud-feedback-model-intercomparison-project-cfmip-observation-simulator-package)-related
variables, support can be provided if there is sufficient interest from the
users.

## Missing values

If a variable has an attribute named `missing_value` or `_FillValue`, the value
is converted to NaN and ignored in the calculation of global averages and for
the visualization.

# Connectivity files

::: tip Tip: Connecitivity File Download A collection of connectivity files can
be found on [Zenodo](https://doi.org/10.5281/zenodo.16908566). The archive is
continually updated as more users inform us about the grids their data files
use.
:::

The horizontal grids used by EAM are cubed spheres. Since these are unstructed
grids, QuickView needs to know how to map data to the globe. Therefore, for each
simulation data file, a "connectivity file" needs to be provided.

In EAMv2, v3, and v4, most of the variables (physical quantities) are written
out on a "physics grid" (also referred to as "physgrid", "FV grid", or "control
volume mesh") described in
[Hannah et al. (2021)](https://doi.org/10.1029/2020MS002419). The naming
convention for such grids is `ne*pg2`, with `*` being a number, e.g., 4, 30,
120, 256. Further details about EAM's cubed-sphere grids can be found in EAM's
documentation, for example in
[this overview](https://e3sm.atlassian.net/wiki/spaces/DOC/pages/34113147/SE+Atmosphere+Grid+Overview+EAM+CAM)
and
[this description](https://e3sm.atlassian.net/wiki/spaces/DOC/pages/872579110/Running+E3SM+on+New+Atmosphere+Grids).

Future versions of QuickView will also support the cubed-sphere meshes used by
EAM's dynamical core, i.e., the `ne*np4` grids (also referred to as "native
grids" or "GLL grids").

## Generate connectivity files

Users can generate connectivity files with
[`TempestRemap`](https://github.com/ClimateGlobalChange/tempestremap)
([Ullrich and Taylor, 2015](https://doi.org/10.1175/MWR-D-14-00343.1);
[Ullrich et al., 2016](https://doi.org/10.1175/MWR-D-15-0301.1)) using
[this script](https://github.com/mt5555/remap-ncl/blob/master/makeSE.sh) shared
by Mark A. Taylor at Sandia National Laboratories. (`TempestRemap` is available
as a part of the [`E3SM-Unified`](https://github.com/E3SM-Project/e3sm-unified)
conda environment. It can also be installed following the instructions provided
in its [repo](https://github.com/ClimateGlobalChange/tempestremap).)

For example, using Mark's script, the command

```
./makeSE.sh 30
```

will generate several different files for the `ne30pg2` grid, including, e.g.,

- `TEMEPST_NE30pg2.g` (Exodus format),
- `TEMPEST_ne30pg2.scrip.nc` (SCRIP format).

EAM QuickView uses the **SCRIP** format.
