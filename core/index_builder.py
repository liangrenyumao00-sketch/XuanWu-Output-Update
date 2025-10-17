# core/index_builder.py
import os, json
from core.config import SCREENSHOT_DIR, LOG_DIR

def build_log_index():
    entries = []
    for fn in sorted(os.listdir(LOG_DIR)):
        if fn.endswith(".txt"):
            base = os.path.splitext(fn)[0]
            png = f"{base}.png"
            img_full = os.path.join(SCREENSHOT_DIR, png)
            if not os.path.exists(img_full):
                continue
            entries.append({
                "timestamp": base.split("_")[-1],
                "keywords": base.rsplit("_", 1)[0],
                "log": fn,
                "image": os.path.relpath(img_full, LOG_DIR).replace("\\", "/")
            })

    with open(os.path.join(LOG_DIR, "log_index.json"), "w", encoding="utf-8") as jf:
        json.dump(entries, jf, ensure_ascii=False, indent=2)

    with open(os.path.join(LOG_DIR, "index.html"), "w", encoding="utf-8") as hf:
        hf.write(
            "<html><meta charset='utf-8'><meta http-equiv='Cache-Control' content='no-cache'>"
            "<title>识别索引</title><body><h1>识别记录</h1><ul>"
        )
        for e in entries:
            hf.write(
                f"<li><b>{e['keywords']}</b> [{e['timestamp']}] – "
                f"<a href='{e['log']}' target='_blank'>日志</a> | "
                f"<a href='{e['image']}' target='_blank'>截图</a></li>"
            )
        hf.write("</ul></body></html>")
