import inspect

tools = [
    ('list_directory', 'app.tools.file.list_directory'),
    ('search_files', 'app.tools.file.search_files'),
    ('grep_file_content', 'app.tools.file.grep_file_content'),
    ('copy_file', 'app.tools.file.copy_file'),
    ('move_file', 'app.tools.file.move_file'),
    ('delete_file', 'app.tools.file.delete_file'),
]

for tool_name, module_path in tools:
    try:
        module = __import__(module_path, fromlist=[tool_name])
        func = getattr(module, tool_name)
        sig = inspect.signature(func)
        params = list(sig.parameters.keys())
        print(f'{tool_name}: {params}')
    except Exception as e:
        print(f'{tool_name}: ERROR - {e}')