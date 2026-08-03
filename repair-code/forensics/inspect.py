import os, subprocess, glob

roots = [
 r"E:\recover-0802",
 r"E:\recovered_A001",
 r"E:\recovered_om001",
 r"E:\recovered_git\OmniAgentAs-desk",
 r"E:\test_dir\11.OmniAgentAs-desk",
 r"E:\tmp_rec\merged",
 r"E:\tmp_rec\final_backend_app",
 r"E:\tmp_rec\verify_proj",
 r"E:\tmp_rec\recover_res",
 r"E:\tmp_rec\missing_extract",
]

def count_files(d):
    if not d or not os.path.isdir(d): return 0
    c=0
    for _ in glob.glob(os.path.join(d,"**","*"), recursive=True): 
        pass
    for root,_,files in os.walk(d):
        c+=len(files)
    return c

for r in roots:
    print("===",r.replace("F:\\","") if r.startswith("F:") else r)
    app=os.path.join(r,"backend","app")
    ver=os.path.join(r,"version.txt")
    mp=os.path.join(app,"main.py")
    print("  app/main.py exists:", os.path.exists(mp))
    print("  version.txt exists:", os.path.exists(ver))
    if os.path.exists(ver):
        import datetime
        mt=datetime.datetime.fromtimestamp(os.path.getmtime(ver))
        with open(ver,encoding="utf-8",errors="replace") as f: first=f.readline().strip()
        print("  version.txt mtime:", mt.strftime("%Y-%m-%d %H:%M:%S"), "head:", first[:40])
    print("  backend/app file count:", count_files(app) if os.path.isdir(app) else "(app missing)")
    # spot check key 7.20-31 files
    for key in ["app/services/base_service.py","app/services/agent/shell_engine.py","app/tools/file/read_pdf.py","app/tools/system/desktop_tools.py","app/services/safety/tool_safety_checker.py"]:
        p=os.path.join(app,key)
        print("   ", key,":", "OK" if os.path.exists(p) else "-")
