from collections import OrderedDict


def __ordered_dict(data: dict) -> OrderedDict:
    if not isinstance(data, dict):
        return data
    result = OrderedDict()
    if 'ai' in data:
        ai_data = data['ai']
        ai_ordered = OrderedDict()
        if 'provider' in ai_data:
            ai_ordered['provider'] = ai_data['provider']
        if 'model' in ai_data:
            ai_ordered['model'] = ai_data['model']
        for key in sorted(ai_data.keys()):
            if key not in ('provider', 'model'):
                value = ai_data[key]
                if isinstance(value, dict):
                    ai_ordered[key] = _ordered_dict(value)
                else:
                    ai_ordered[key] = value
        result['ai'] = ai_ordered
    for key in sorted(data.keys()):
        if key != 'ai':
            value = data[key]
            if isinstance(value, dict):
                result[key] = _ordered_dict(value)
            else:
                result[key] = value
    return result
