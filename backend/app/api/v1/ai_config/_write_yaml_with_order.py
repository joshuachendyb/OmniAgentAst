import yaml
from collections import OrderedDict
from ._ordered_dict import __ordered_dict as _ordered_dict


def _write_yaml_with_order(file_path: str, data: dict):
    """使用OrderedDict写入YAML，保持特定顺序"""
    ordered_data = _ordered_dict(data)
    def represent_ordereddict(dumper, data):
        return dumper.represent_dict(data.items())
    yaml.add_representer(OrderedDict, represent_ordereddict)
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(ordered_data, f, allow_unicode=True, default_flow_style=False)
