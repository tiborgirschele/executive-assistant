#!/bin/bash

echo "========================================="
echo "        IONOS MOUNT SMOKE TESTS          "
echo "========================================="

# 1. Find the relevant container running rclone
echo -e "\n[1] Finding Container with rclone..."
CONTAINER_NAME=$(docker ps --format '{{.Names}}' | grep -iE "filemanager|ionos|rclone|plex" | head -n 1)

if [ -z "$CONTAINER_NAME" ]; then
    echo "⚠️ WARNING: Could not find a running container matching filemanager/ionos/rclone/plex."
    echo "    Will try to run tests on the host system directly."
    EXEC_CMD=""
else
    echo "✅ PASS: Testing inside container: $CONTAINER_NAME"
    EXEC_CMD="docker exec $CONTAINER_NAME"
fi

# 2. Check Rclone Process
echo -e "\n[2] Checking Rclone Process..."
if $EXEC_CMD pgrep -af 'rclone mount' >/dev/null 2>&1 || pgrep -af 'rclone mount' >/dev/null 2>&1; then
    echo "✅ PASS: rclone mount process is running."
    if [ -n "$EXEC_CMD" ]; then
        $EXEC_CMD pgrep -af 'rclone mount' | sed 's/^/    > /'
    else
        pgrep -af 'rclone mount' | sed 's/^/    > /'
    fi
else
    echo "❌ FAIL: No rclone mount process found."
    echo "    💡 Did your cloud-mounter script execute successfully?"
fi

# 3. Check Mount Registration
echo -e "\n[3] Checking Mount Registration (/proc/mounts)..."
if [ -n "$EXEC_CMD" ]; then
    MOUNT_LINE=$($EXEC_CMD grep -iE 'rclone|webdav|ionos' /proc/mounts 2>/dev/null)
else
    MOUNT_LINE=$(grep -iE 'rclone|webdav|ionos' /proc/mounts 2>/dev/null)
fi

if [ -n "$MOUNT_LINE" ]; then
    echo "✅ PASS: Rclone mount is actively registered in /proc/mounts."
    echo "$MOUNT_LINE" | sed 's/^/    > /'
    ACTUAL_MOUNT=$(echo "$MOUNT_LINE" | awk '{print $2}' | head -n 1)
else
    echo "❌ FAIL: No rclone mount found in /proc/mounts."
    ACTUAL_MOUNT="/media/ionos"
fi

# 4. Testing Mount Responsiveness (FUSE Hang Test)
echo -e "\n[4] Testing Mount Responsiveness (Anti-Freeze Check)..."
if [ -n "$EXEC_CMD" ]; then
    CMD_PREFIX="$EXEC_CMD "
else
    CMD_PREFIX=""
fi

if $CMD_PREFIX sh -c "command -v timeout >/dev/null 2>&1"; then
    TIMEOUT_CMD="timeout 8"
else
    TIMEOUT_CMD=""
fi

# We use a timeout. If the FUSE mount is completely broken, 'ls' will hang forever.
if $CMD_PREFIX sh -c "$TIMEOUT_CMD ls -1A \"$ACTUAL_MOUNT\" >/dev/null 2>&1"; then
    echo "✅ PASS: Mount point ($ACTUAL_MOUNT) is readable and responsive."
else
    echo "❌ FAIL: Mount point ($ACTUAL_MOUNT) timed out or does not exist."
    echo "    💡 The FUSE layer might be stuck. You may need to forcefully unmount it:"
    echo "       sudo fusermount -uz $ACTUAL_MOUNT"
fi

# 5. Checking Rclone Logs
echo -e "\n[5] Checking Rclone Logs for IONOS Errors..."
LOG_FILE="/config/rclone/mount.log" 
if $CMD_PREFIX sh -c "[ -f \"$LOG_FILE\" ]"; then
    ERRORS=$($CMD_PREFIX sh -c "tail -n 100 \"$LOG_FILE\" | grep -iE 'error|fatal|unauthorized|401|403|bad password'")
    if [ -z "$ERRORS" ]; then
        echo "✅ PASS: No obvious authentication or connection errors in the last 100 lines of $LOG_FILE."
    else
        echo "❌ FAIL: Found connection/auth errors in the log:"
        echo "$ERRORS" | tail -n 5 | sed 's/^/    > /'
    fi
else
    echo "⚠️ SKIP: Log file not found at $LOG_FILE inside the container."
    echo "    (If the log path is different, update LOG_FILE in this script)."
fi

echo -e "\n========================================="
echo "               TESTS COMPLETE              "
echo "========================================="
