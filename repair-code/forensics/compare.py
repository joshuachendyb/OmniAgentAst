import os, glob, datetime

cands = {
 "recovered_git": r"E:\recovered_git\OmniAgentAs-desk",
 "verify_proj":   r"E:\tmp_rec\verify_proj",
 "recover-0802":  r"E:\recover-0802",
 "recovered_om001": r"E:\recovered_om001",
 "final_backend_app": r"E:\tmp_rec\final_backend_app",
}
def mt(p):
    try: return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%m-%d %H:%M")
    except: return "-"
def find(base, name):
    hits = glob.glob(os.path.join(base,"**",name), recursive=True)
    return hits[0] if hits else None
for label,base in cands.items():
    print("\n###",label, base)
    ver=os.path.join(base,"version.txt")
    print("  version.txt:", os.path.exists(ver), "head:"+(""+open(ver,encoding="utf-8",errors="replace").readline().strip())[:30] if os.path.exists(ver) else "-")
    app=os.path.join(base,"backend/app")
    if not os.path.isdir(app):
        # maybe flattened
        app=base
        print("  (backend/app missing; using project root)")
    print("  app mtime:", mt(app))
    # structure
    for sub in ["services","tools","api"]:
        d=os.path.join(app,sub)
        if os.path.isdir(d):
            n=sum(len(f) for _,_,f in os.walk(d))
            print(f"  {sub}/ exists, files={n}")
    # markers
    for fname,marker in [("base_service.py","finish_reason"),("shell_engine.py","ShellPoolManager"),
                         ("read_pdf.py","_process_page"),("win_registry_tools.py","_to_unsigned"),
                         ("http_request.py","transcode_url"),("message_builder.py","reasoning")]:
        p=find(app,fname)
        if p:
            txt=open(p,encoding="utf-8",errors="replace").read()
            print(f"  FIND {fname}: mtime={mt(p)} marker[{marker}]={marker in txt} size={len(txt)}")
        else:
            print(f"  FIND {fname}: MISSING")
