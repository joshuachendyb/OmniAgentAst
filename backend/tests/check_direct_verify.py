# -*- coding: utf-8 -*-
"""直接对比Pydantic模型字段 vs 函数签名（不依赖注册表） - 小健 2026-05-06"""
import inspect, sys
sys.path.insert(0, '.')

checks = []

# reg模块
from app.services.tools.system.reg_schema import RegReadInput, RegWriteInput, RegDeleteInput
from app.services.tools.system.reg_tools import reg_read, reg_write, reg_delete
checks.extend([
    ("reg_read", reg_read, RegReadInput),
    ("reg_write", reg_write, RegWriteInput),
    ("reg_delete", reg_delete, RegDeleteInput),
])

# system模块
from app.services.tools.system.system_schema import (
    ListProcessesInput, ServiceListInput, ServiceStartInput, ServiceStopInput,
    TaskListInput, TaskCreateInput, TaskDeleteInput,
)
from app.services.tools.system.system_tools import (
    list_processes, service_list, service_start, service_stop,
    task_list, task_create, task_delete,
)
checks.extend([
    ("list_processes", list_processes, ListProcessesInput),
    ("service_list", service_list, ServiceListInput),
    ("service_start", service_start, ServiceStartInput),
    ("service_stop", service_stop, ServiceStopInput),
    ("task_list", task_list, TaskListInput),
    ("task_create", task_create, TaskCreateInput),
    ("task_delete", task_delete, TaskDeleteInput),
])

# time模块
from app.services.tools.time.time_schema import TimeAddInput
from app.services.tools.time.time_tools import time_add
checks.append(("time_add", time_add, TimeAddInput))

issues = []
for name, func, schema_cls in checks:
    sig = inspect.signature(func)
    func_params = {}
    for pname, param in sig.parameters.items():
        if pname in ('self', 'cls', 'kwargs', 'args'):
            continue
        func_params[pname] = param.default == inspect.Parameter.empty

    schema_fields = set(schema_cls.model_fields.keys())
    func_names = set(func_params.keys())
    
    missing_schema = func_names - schema_fields
    missing_func = schema_fields - func_names
    if missing_schema:
        issues.append(f'[{name}] 函数有参数但Schema缺少: {missing_schema}')
    if missing_func:
        issues.append(f'[{name}] Schema有字段但函数缺少: {missing_func}')
    
    for pname in func_names & schema_fields:
        f_req = func_params[pname]
        s_req = schema_cls.model_fields[pname].is_required()
        if f_req != s_req:
            issues.append(f'[{name}] "{pname}" required不一致: 函数={f_req}, Schema={s_req}')

if issues:
    print(f'发现 {len(issues)} 个不一致:')
    for i in issues:
        print(f'  ❌ {i}')
else:
    print('✅ 所有修改的模块函数参数与Schema完全一致!')
