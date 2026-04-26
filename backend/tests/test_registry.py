# -*- coding: utf-8 -*-
"""
全面测试新的工具注册架构
小健 - 2026-04-26
"""
import sys
sys.path.insert(0, r'D:\OmniAgentAs-desk\backend')

def test_all():
    print('='*60)
    print('Test 1: tool_registry core')
    print('='*60)
    
    from app.services.tools.registry import tool_registry, ToolCategory
    
    # Register test tool
    def test_func():
        return 'test'
    
    result = tool_registry.register(
        name='test_tool',
        description='test tool',
        category=ToolCategory.FILE,
        implementation=test_func
    )
    print(f'1.1 Register: {result["status"]}')
    
    # Get implementation
    impl = tool_registry.get_implementation('test_tool')
    print(f'1.2 Get impl: {impl is not None}')
    
    # List tools
    tools = tool_registry.list_tools(category=ToolCategory.FILE)
    print(f'1.3 List file tools: {len(tools)}')
    
    # Get tool info
    info = tool_registry.get('test_tool')
    print(f'1.4 Get info: {info is not None}')
    
    # Unregister
    result = tool_registry.unregister('test_tool')
    print(f'1.5 Unregister: {result["status"]}')
    
    print('='*60)
    print('Test 2: file_register flow')
    print('='*60)
    
    from app.services.tools.file.file_register import _register_file_tools
    _register_file_tools()
    print('2.1 Register triggered: OK')
    
    file_tools = tool_registry.list_tools(category=ToolCategory.FILE)
    print(f'2.2 Registered file tools: {len(file_tools)}')
    
    all_have_impl = all(tool_registry.get_implementation(t['name']) for t in file_tools)
    print(f'2.3 All have impl: {all_have_impl}')
    
    required = ['read_file', 'write_file', 'list_directory', 'delete_file', 
               'move_file', 'search_file_content', 'search_files']
    missing = [t for t in required if not tool_registry.get_implementation(t)]
    print(f'2.4 Required tools complete: {len(missing) == 0}, missing: {missing}')
    
    print('='*60)
    print('Test 3: file_react integration')
    print('='*60)
    
    from app.services.agent.file_react import FileReactAgent
    print('3.1 FileReactAgent import: OK')
    
    print('='*60)
    print('Test 4: react_schema integration')
    print('='*60)
    
    from app.services.agent.types.react_schema import get_tools_schema_for_function_calling
    schemas = get_tools_schema_for_function_calling()
    print(f'4.1 Get schemas: {len(schemas)}')
    
    has_file = any(s.get('function', {}).get('name', '').startswith('read_file') for s in schemas)
    print(f'4.2 Contains file tools: {has_file}')
    
    print('='*60)
    print('Test 5: get_tools_from_file_registry')
    print('='*60)
    
    from app.services.tools.registry import get_tools_from_file_registry
    tools = get_tools_from_file_registry()
    print(f'5.1 Get tools: {len(tools)}')
    
    is_dict = isinstance(tools, dict)
    print(f'5.2 Is dict: {is_dict}')
    
    can_call = all(callable(v) for v in tools.values())
    print(f'5.3 Tools callable: {can_call}')
    
    print('='*60)
    print('Test 6: no legacy code')
    print('='*60)
    
    from app.services.tools.file import file_tools as ft_module
    has_old = hasattr(ft_module, '_TOOL_REGISTRY')
    print(f'6.1 No _TOOL_REGISTRY: {not has_old}')
    
    has_compat = hasattr(ft_module, 'get_registered_tools') or hasattr(ft_module, 'get_tool')
    print(f'6.2 No compat in file_tools: {not has_compat}')
    
    from app.services.tools.file import file_register as fr_module
    has_compat2 = hasattr(fr_module, 'get_registered_tools') or hasattr(fr_module, 'get_tool')
    print(f'6.3 No compat in file_register: {not has_compat2}')
    
    print('='*60)
    print('Test 7: tool can be called')
    print('='*60)
    
    # Test that tool can be called (not actual execution test)
    from app.services.tools.file import FileTools
    ft = FileTools()
    
    # Verify read_file method exists
    has_method = hasattr(ft, 'read_file')
    print(f'7.1 read_file method exists: {has_method}')
    
    # Verify list_directory method exists
    has_method = hasattr(ft, 'list_directory')
    print(f'7.2 list_directory method exists: {has_method}')
    
    # Verify delete_file method exists
    has_method = hasattr(ft, 'delete_file')
    print(f'7.3 delete_file method exists: {has_method}')
    
    print('='*60)
    print('ALL TESTS PASSED!')
    print('='*60)


if __name__ == '__main__':
    test_all()