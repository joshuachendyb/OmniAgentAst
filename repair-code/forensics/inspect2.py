import os
base = r"E:\recovered_git\OmniAgentAs-desk\backend/app".replace("backend/app","backend/app")
base=r"E:\recovered_git\OmniAgentAs-desk\backend/app"
checks = [
 ("services/llm/base_service.py","base_service","exponential","finish_reason"),
 ("services/agent/shell_engine.py","shell_engine","ShellPoolManager","session_id"),
 ("tools/file/read_pdf.py","read_pdf","_process_page","BUG-001"),
 ("tools/system/win_registry/win_registry_tools.py","win_registry","_to_unsigned","registry_write"),
 ("services/react_sse_wrapper/run_sse_stream.py","sse","step"),
 ("tools/network/http_request.py","http_request","transcode_url","Header"),
]
for rel,nice,a,b in checks:
    p=os.path.join(base,rel)
    print(nice, "EXISTS" if os.path.exists(p) else "MISSING")
    if os.path.exists(p):
        txt=open(p,encoding='utf-8',errors='replace').read()
        print("   ", a, "->", a in txt, "|", b, "->", b in txt)
