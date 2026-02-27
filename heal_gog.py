import re, os
key = os.environ.get("GEMINI_KEY")
with open("ea/app/gog.py", "r", encoding="utf-8") as f: code = f.read()

# Strip out old broken injections
code = re.sub(r'("-e",\s*"GEMINI_API_KEY=[^"]+",\s*)', '', code)
code = re.sub(r'("-e",\s*"LITELLM_API_KEY=[^"]+",\s*)', '', code)
code = re.sub(r'("-e",\s*"LLM_MODEL=[^"]+",\s*)', '', code)
code = re.sub(r'-e\s+GEMINI_API_KEY=[^\s]+\s+', '', code)
code = re.sub(r'-e\s+LITELLM_API_KEY=[^\s]+\s+', '', code)
code = re.sub(r'-e\s+LLM_MODEL=[^\s]+\s+', '', code)
code = code.replace(', ,', ',')
code = code.replace('[,', '[')

# Carefully inject fresh keys
code = re.sub(r'\[\s*["\']docker["\']\s*,\s*["\']exec["\']\s*,', f'["docker", "exec", "-e", "GEMINI_API_KEY={key}", "-e", "LITELLM_API_KEY={key}", "-e", "LLM_MODEL=gemini/gemini-2.5-flash", ', code)
code = re.sub(r'(["\'])docker\s+exec\s+', f'\\1docker exec -e GEMINI_API_KEY={key} -e LITELLM_API_KEY={key} -e LLM_MODEL=gemini/gemini-2.5-flash ', code)

with open("ea/app/gog.py", "w", encoding="utf-8") as f: f.write(code)
print("✅ gog.py patched.")
