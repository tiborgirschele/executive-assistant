with open("ea/app/poll_listener.py", "r", encoding="utf-8") as f:
    code = f.read()

# Surgically repair the broken string literal by escaping the newline
code = code.replace('Alert:</b>\nYour previous task', 'Alert:</b>\\nYour previous task')

with open("ea/app/poll_listener.py", "w", encoding="utf-8") as f:
    f.write(code)

print("✅ Syntax error patched!")
