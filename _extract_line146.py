# -*- coding: utf-8 -*-
import json
import re

path = r"C:\Users\mercury\.cursor\projects\c-Users-mercury-Desktop-tbank-mitm\agent-transcripts\3b3112d9-3df7-4362-88d6-a30da449767b\3b3112d9-3df7-4362-88d6-a30da449767b.jsonl"
out = r"C:\Users\mercury\Desktop\tbank-mitm\_extract_uq.txt"
meta = r"C:\Users\mercury\Desktop\tbank-mitm\_extract_meta.txt"

with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

info = []
info.append(f"total_lines={len(lines)}")

# Check messages after line 146 (1-indexed) - i.e. index >= 146
after = []
for i, line in enumerate(lines):
    if i < 146:
        continue
    try:
        obj = json.loads(line)
        role = obj.get("role")
        after.append(f"line {i+1} role={role}")
    except Exception as e:
        after.append(f"line {i+1} parse_error={e}")

info.append(f"lines_after_146={len(after)}")
info.extend(after)

# Also scan all user messages after index 145 for summary
user_after = []
for i, line in enumerate(lines):
    if i <= 145:
        continue
    try:
        obj = json.loads(line)
        if obj.get("role") != "user":
            continue
        content = obj.get("message", {}).get("content", [])
        texts = []
        for part in content:
            if part.get("type") == "text":
                t = part.get("text", "")
                m = re.search(r"<user_query>\n?(.*?)\n?</user_query>", t, re.S)
                texts.append(m.group(1) if m else t[:2000])
        user_after.append(f"--- line {i+1} ---\n" + "\n".join(texts)[:5000])
    except Exception as e:
        user_after.append(f"line {i+1} error {e}")

info.append(f"user_msgs_after_146={len(user_after)}")
info.extend(user_after)

obj = json.loads(lines[145])
info.append(f"line146_role={obj.get('role')}")
content = obj["message"]["content"]
info.append(f"content_parts={len(content)}")

uq = None
for i, part in enumerate(content):
    t = part.get("type")
    info.append(f"part{i}_type={t}")
    if t == "text":
        text = part["text"]
        info.append(f"text_len={len(text)}")
        # Remove any data URLs / base64 blobs
        cleaned = re.sub(r"data:image/[a-zA-Z0-9+.-]+;base64,[A-Za-z0-9+/=\s]+", "[IMAGE_BASE64_REMOVED]", text)
        m = re.search(r"<user_query>\n?(.*?)\n?</user_query>", cleaned, re.S)
        if m:
            uq = m.group(1)
            info.append(f"user_query_len={len(uq)}")
        else:
            # fallback: everything after <user_query>
            idx = cleaned.find("<user_query>")
            if idx >= 0:
                uq = cleaned[idx + len("<user_query>") :]
                end = uq.find("</user_query>")
                if end >= 0:
                    uq = uq[:end]
                info.append(f"user_query_fallback_len={len(uq)}")
            else:
                # write cleaned text without image_files preamble if possible
                uq = cleaned
                info.append("no_user_query_tag_using_full_text")
    elif t == "image":
        info.append(f"part{i}_image_keys={list(part.keys())}")

with open(meta, "w", encoding="utf-8") as wf:
    wf.write("\n".join(info))

with open(out, "w", encoding="utf-8") as wf:
    wf.write(uq or "")

print("done")
print("\n".join(info[:30]))
print("uq_chars", len(uq or ""))
