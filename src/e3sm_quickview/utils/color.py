import base64

from paraview import servermanager, simple
from vtkmodules.vtkCommonCore import vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOImage import vtkPNGWriter


def get_color_preset_names():
    presets = servermanager.vtkSMTransferFunctionPresets.GetInstance()
    return [
        presets.GetPresetName(index) for index in range(presets.GetNumberOfPresets())
    ]


def generate_colormaps():
    color_maps = {}
    samples = 255
    rgb = [0, 0, 0]
    names = get_color_preset_names()
    lut = simple.GetColorTransferFunction("to_generate_image")
    vtk_lut = lut.GetClientSideObject()
    colorArray = vtkUnsignedCharArray()
    colorArray.SetNumberOfComponents(3)
    colorArray.SetNumberOfTuples(samples)
    imgData = vtkImageData()
    imgData.SetDimensions(samples, 1, 1)
    imgData.GetPointData().SetScalars(colorArray)
    writer = vtkPNGWriter()
    writer.WriteToMemoryOn()
    writer.SetInputData(imgData)
    writer.SetCompressionLevel(1)

    for name in names:
        imgs = []
        for inverted in range(2):
            lut.ApplyPreset(name, True)
            if inverted:
                lut.InvertTransferFunction()

            v_min = lut.RGBPoints[0]
            v_max = lut.RGBPoints[-4]
            step = (v_max - v_min) / (samples - 1)

            for i in range(samples):
                value = v_min + step * float(i)
                vtk_lut.GetColor(value, rgb)
                r = int(round(rgb[0] * 255))
                g = int(round(rgb[1] * 255))
                b = int(round(rgb[2] * 255))
                colorArray.SetTuple3(i, r, g, b)

            writer.Write()
            img_bytes = writer.GetResult()

            base64_img = base64.standard_b64encode(img_bytes).decode("utf-8")
            imgs.append(f"data:image/png;base64,{base64_img}")

        color_maps[name] = imgs

    return {k: {"normal": v[0], "inverted": v[1]} for k, v in color_maps.items()}


COLORBAR_CACHE = generate_colormaps()


def get_cached_colorbar_image(colormap_name, inverted=False):
    """
    Get a cached colorbar image for a given colormap.

    Parameters:
    -----------
    colormap_name : str
        Name of the colormap (e.g., "Cool to Warm", "Rainbow Desaturated")
    inverted : bool
        Whether to get the inverted version

    Returns:
    --------
    str
        Base64-encoded PNG image as a data URI, or empty string if not found
    """
    if colormap_name in COLORBAR_CACHE:
        variant = "inverted" if inverted else "normal"
        return COLORBAR_CACHE[colormap_name].get(variant, "")

    return ""


def lut_to_img(lut_proxy):
    samples = 255
    rgb = [0, 0, 0]
    vtk_lut = lut_proxy.GetClientSideObject()
    colorArray = vtkUnsignedCharArray()
    colorArray.SetNumberOfComponents(3)
    colorArray.SetNumberOfTuples(samples)
    imgData = vtkImageData()
    imgData.SetDimensions(samples, 1, 1)
    imgData.GetPointData().SetScalars(colorArray)
    writer = vtkPNGWriter()
    writer.WriteToMemoryOn()
    writer.SetInputData(imgData)
    writer.SetCompressionLevel(1)

    v_min = lut_proxy.RGBPoints[0]
    v_max = lut_proxy.RGBPoints[-4]
    step = (v_max - v_min) / (samples - 1)

    for i in range(samples):
        value = v_min + step * float(i)
        vtk_lut.GetColor(value, rgb)
        r = int(round(rgb[0] * 255))
        g = int(round(rgb[1] * 255))
        b = int(round(rgb[2] * 255))
        colorArray.SetTuple3(i, r, g, b)

    writer.Write()
    base64_img = base64.standard_b64encode(writer.GetResult()).decode("utf-8")

    return f"data:image/png;base64,{base64_img}"
