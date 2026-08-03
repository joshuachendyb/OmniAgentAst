import os, re
base = r"E:\tmp_rec\verify_proj/backend/app"
p = os.path.join(base, "tools/win_registry/registry_write.py")
t = open(p, encoding="utf-8", errors="replace").read()
print("=== registry_write.py: unsigned/DWORD/overflow lines ===")
for i, line in enumerate(t.splitlines()):
    if "unsigned" in line.lower() or "REG_DWORD" in line or "REG_QWORD" in line or "overflow" in line.lower():
        print(f"[{i}] {line.strip()[:120]}")

print("\n=== safety_checker confirm/bypass lines ===")
for root, _, fs in os.walk(base):
    for f in fs:
        if "safety" in f.lower() and f.endswith(".py"):
            tp = os.path.join(root, f)
            txt = open(tp, encoding="utf-8", errors="replace").read()
            for i, line in enumerate(txt.splitlines()):
                if "bypass" in line.lower() or "security.enabled" in line.lower() or "auto_confirm" in line.lower():
                    print(f"[{os.path.relpath(tp, base)}:{i}] {line.strip()[:110]}")
