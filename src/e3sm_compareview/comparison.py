import re
from pathlib import Path

COMPARISON_TYPES = ("diff", "comp1", "comp2")
COMPARISON_MODES = ("two-sim", "multi-sim")


def normalize_comparison_mode(mode):
    if mode in COMPARISON_MODES:
        return mode
    return "multi-sim"


def normalize_comparison_type(comparison_type):
    if comparison_type in COMPARISON_TYPES:
        return comparison_type
    return "diff"


def default_simulation_label(file_path):
    return Path(file_path).stem


def default_simulation_labels(simulation_files):
    labels = [Path(file_path).stem for file_path in simulation_files]
    fallback_labels = dict(zip(simulation_files, labels))
    if len(labels) < 2:
        return fallback_labels

    token_lists = [re.split(r"[._\-\s]+", label) for label in labels]
    shared_suffix_len = 0
    for suffix_group in zip(*(reversed(tokens) for tokens in token_lists)):
        if len(set(suffix_group)) != 1:
            break
        shared_suffix_len += 1

    if shared_suffix_len == 0:
        return fallback_labels

    stripped_labels = []
    for label in labels:
        parts = re.split(r"([._\-\s]+)", label)
        stripped = "".join(parts[: -(2 * shared_suffix_len)]).rstrip("._- ")
        if not stripped:
            return fallback_labels
        stripped_labels.append(stripped)

    if len(set(stripped_labels)) != len(stripped_labels):
        return fallback_labels

    return dict(zip(simulation_files, stripped_labels))


def build_simulation_configs(simulation_files, existing_configs, control_file):
    existing = {
        entry["path"]: entry for entry in (existing_configs or []) if entry.get("path")
    }
    existing_order = [
        entry["path"]
        for entry in (existing_configs or [])
        if entry.get("path") in simulation_files
    ]
    ordered_files = existing_order + [
        file_path for file_path in simulation_files if file_path not in existing
    ]
    labels = default_simulation_labels(simulation_files)
    configs = []
    for file_path in ordered_files:
        previous = existing.get(file_path, {})
        configs.append(
            {
                "path": file_path,
                "label": previous.get(
                    "label", labels.get(file_path, default_simulation_label(file_path))
                ),
                "include": previous.get("include", True),
            }
        )

    valid_paths = {entry["path"] for entry in configs}
    if control_file not in valid_paths:
        control_file = configs[0]["path"] if configs else ""

    return configs, control_file


def normalize_two_sim_target(configs, control_file, two_sim_target_file):
    configs = configs or []
    if not configs:
        return ""

    valid_paths = [entry.get("path") for entry in configs if entry.get("path")]
    if not valid_paths:
        return ""

    if two_sim_target_file in valid_paths and two_sim_target_file != control_file:
        return two_sim_target_file

    for path in valid_paths:
        if path != control_file:
            return path

    return control_file


def comparison_signature_for(
    configs, control_file, comparison_mode="multi-sim", two_sim_target_file=""
):
    comparison_mode = normalize_comparison_mode(comparison_mode)
    return (
        comparison_mode,
        control_file,
        normalize_two_sim_target(configs, control_file, two_sim_target_file),
        tuple(
            (entry.get("path"), bool(entry.get("include", True)))
            for entry in (configs or [])
        ),
    )


def label_signature_for(configs):
    return tuple(
        (entry.get("path"), entry.get("label", "")) for entry in (configs or [])
    )


def active_simulation_configs(
    configs, control_file, comparison_mode="multi-sim", two_sim_target_file=""
):
    comparison_mode = normalize_comparison_mode(comparison_mode)
    configs = configs or []
    if not configs:
        return []

    configs_by_path = {entry["path"]: entry for entry in configs}
    control_file = control_file or configs[0]["path"]
    control_config = configs_by_path.get(control_file, configs[0])
    control_index = next(
        (
            index
            for index, entry in enumerate(configs)
            if entry["path"] == control_config["path"]
        ),
        0,
    )

    active = [{**control_config, "role": "control", "source_index": control_index}]

    if comparison_mode == "two-sim":
        target_path = normalize_two_sim_target(
            configs, control_config["path"], two_sim_target_file
        )
        target_config = configs_by_path.get(target_path)
        if target_config and target_config["path"] != control_config["path"]:
            target_index = next(
                (
                    index
                    for index, entry in enumerate(configs)
                    if entry["path"] == target_config["path"]
                ),
                0,
            )
            active.append(
                {**target_config, "role": "comparison", "source_index": target_index}
            )
        return active

    active.extend(
        {**entry, "role": "comparison", "source_index": index}
        for index, entry in enumerate(configs)
        if entry["path"] != control_config["path"] and entry.get("include", True)
    )
    return active
