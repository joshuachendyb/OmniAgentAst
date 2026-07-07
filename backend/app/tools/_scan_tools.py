import os, re

base = r'G:\OmniAgentAs-desk\backend\app\tools'
categories = ['fundamental', 'file', 'shell', 'network', 'document', 'system']

def extract_call(text, func_name, start_pos):
    """Extract a full function call starting at start_pos."""
    paren_pos = text.find('(', start_pos)
    if paren_pos == -1:
        return text[start_pos:start_pos+300]
    depth = 0
    i = paren_pos
    while i < len(text):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return text[start_pos:i+1]
        i += 1
    return text[start_pos:start_pos+300]

for cat in categories:
    cat_dir = os.path.join(base, cat)
    if not os.path.isdir(cat_dir):
        continue
    py_files = sorted([f for f in os.listdir(cat_dir) 
                       if f.endswith('.py') and f != '__init__.py' 
                       and not f.startswith('_')])
    
    # Also include register files
    register_files = sorted([f for f in os.listdir(cat_dir) 
                              if f.endswith('_register.py')])
    
    all_files = py_files + register_files
    
    print(f'\n{"="*60}')
    print(f'  Category: {cat} - {len(py_files)} tool files, {len(register_files)} register files')
    print(f'{"="*60}')
    
    for fname in all_files:
        filepath = os.path.join(cat_dir, fname)
        with open(filepath, 'r', encoding='utf-8') as fh:
            content = fh.read()
        
        funcs = re.findall(r'^(?:async\s+)?def\s+(\w+)\s*\(', content, re.MULTILINE)
        
        success_calls = []
        for m in re.finditer(r'build_success\(', content):
            call = extract_call(content, 'build_success(', m.start())
            success_calls.append(call)
        
        error_calls = []
        for m in re.finditer(r'build_error\(', content):
            call = extract_call(content, 'build_error(', m.start())
            error_calls.append(call)
        
        has_any = len(funcs) > 0 or len(success_calls) > 0 or len(error_calls) > 0
        
        if has_any:
            print(f'\n--- {fname} ---')
            if funcs:
                print(f'  Functions: {", ".join(funcs)}')
            if success_calls:
                print(f'  build_success calls ({len(success_calls)}):')
                for i, c in enumerate(success_calls):
                    shortened = c[:250].replace('\n', '\\n')
                    print(f'    [{i+1}] {shortened}')
            if error_calls:
                print(f'  build_error calls ({len(error_calls)}):')
                for i, c in enumerate(error_calls):
                    shortened = c[:250].replace('\n', '\\n')
                    print(f'    [{i+1}] {shortened}')
            if not success_calls and not error_calls:
                print('  (no build_success/build_error calls)')
