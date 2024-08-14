import numpy as np
import numpy.testing as npt
import pytest
import json
import pathlib
import os
import logging
from src.wrappers.OsipiBase import OsipiBase
from utilities.data_simulation.GenerateData import GenerateData
logger = logging.getLogger(__name__)
#run using python -m pytest from the root folder

test_results = []


def signal_helper(signal):
    signal = np.asarray(signal)
    signal = np.abs(signal)
    signal /= signal[0]
    ratio = 1 / signal[0]
    return signal, ratio

def tolerances_helper(tolerances, ratio, noise):
    if "dynamic_rtol" in tolerances:
        dyn_rtol = tolerances["dynamic_rtol"]
        scale = dyn_rtol["offset"] + dyn_rtol["ratio"]*ratio + dyn_rtol["noise"]*noise + dyn_rtol["noiseCrossRatio"]*ratio*noise
        tolerances["rtol"] = {"f": scale*dyn_rtol["f"], "D": scale*dyn_rtol["D"], "Dp": scale*dyn_rtol["Dp"]}
    else:
        tolerances["rtol"] = tolerances.get("rtol", {"f": 5, "D": 5, "Dp": 25})
    if "dynamic_atol" in tolerances:
        dyn_atol = tolerances["dynamic_atol"]
        scale = dyn_atol["offset"] + dyn_atol["ratio"]*ratio + dyn_atol["noise"]*noise + dyn_atol["noiseCrossRatio"]*ratio*noise
        tolerances["atol"] = {"f": scale*dyn_atol["f"], "D": scale*dyn_atol["D"], "Dp": scale*dyn_atol["Dp"]}
    else:
        tolerances["atol"] = tolerances.get("atol", {"f": 1e-2, "D": 1e-2, "Dp": 1e-1})
    return tolerances

def data_ivim_fit_saved():
    # Find the algorithms from algorithms.json
    file = pathlib.Path(__file__)
    algorithm_path = file.with_name('algorithms.json')
    with algorithm_path.open() as f:
        algorithm_information = json.load(f)

    # Load generic test data generated from the included phantom: phantoms/MR_XCAT_qMRI
    generic = file.with_name('generic.json')
    with generic.open() as f:
        all_data = json.load(f)

    algorithms = algorithm_information["algorithms"]
    bvals = all_data.pop('config')
    bvals = bvals['bvalues']
    for name, data in all_data.items():
        for algorithm in algorithms:
            algorithm_dict = algorithm_information.get(algorithm, {})
            xfail = {"xfail": name in algorithm_dict.get("xfail_names", {}),
                "strict": algorithm_dict.get("xfail_names", {}).get(name, True)}
            kwargs = algorithm_dict.get("options", {})
            tolerances = algorithm_dict.get("tolerances", {})
            yield name, bvals, data, algorithm, xfail, kwargs, tolerances


@pytest.mark.parametrize("name, bvals, data, algorithm, xfail, kwargs, tolerances", data_ivim_fit_saved())
def test_ivim_fit_saved(name, bvals, data, algorithm, xfail, kwargs, tolerances, request):
    global test_results
    if xfail["xfail"]:
        mark = pytest.mark.xfail(reason="xfail", strict=xfail["strict"])
        request.node.add_marker(mark)
    fit = OsipiBase(algorithm=algorithm, **kwargs)
    signal, ratio = signal_helper(data["data"])
    
    tolerances = tolerances_helper(tolerances, ratio, data["noise"])
    [f_fit, Dp_fit, D_fit] = fit.osipi_fit(signal, bvals)
    def to_list_if_needed(value):
        return value.tolist() if isinstance(value, np.ndarray) else value
    test_result = {
        "name": name,
        "algorithm": algorithm,
        "f_fit": to_list_if_needed(f_fit),
        "Dp_fit": to_list_if_needed(Dp_fit),
        "D_fit": to_list_if_needed(D_fit),
        "f": to_list_if_needed(data['f']),
        "Dp": to_list_if_needed(data['Dp']),
        "D": to_list_if_needed(data['D']),
        "status": "PASSED"
    }
    if xfail["xfail"]:
        test_result['status'] = "XFAILED"

    test_results.append(test_result)
    with open('test_results_report.json', 'w') as f:
            json.dump({"results": test_results, "rtol": tolerances["rtol"],
        "atol": tolerances["atol"], }, f, indent=4)
    npt.assert_allclose(data['f'], f_fit, rtol=tolerances["rtol"]["f"], atol=tolerances["atol"]["f"])
    npt.assert_allclose(data['D'], D_fit, rtol=tolerances["rtol"]["D"], atol=tolerances["atol"]["D"])
    npt.assert_allclose(data['Dp'], Dp_fit, rtol=tolerances["rtol"]["Dp"], atol=tolerances["atol"]["Dp"])
