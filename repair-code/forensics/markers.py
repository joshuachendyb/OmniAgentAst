import os
base = r"E:\tmp_rec\verify_proj/backend/app"
txts = {}
for root, _, files in os.walk(base):
    for f in files:
        if f.endswith(".py"):
            try:
                txts[os.path.join(root, f)] = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            except Exception:
                pass
blob = "\n".join(txts.values())
print("total .py joined size:", len(blob), "files:", len(txts))
want = [
 "finish_reason", "_extract_finish_reason", "exponential", "ShellPoolManager",
 "_finalize_cycle", "reasoning_content", "_process_page", "transcode_url",
 "_to_unsigned", "registry_path_checker", "auto_confirm", "bypass",
 "EXIT_CODE_MEANING", "jina", "Jina", "truncate_summary", "compress hint",
 "validation", "_strip_sql_comments_and_strings", "ShellPoolManager",
]
for w in want:
    print(f"  {w!r:32} present={w in blob}")
