#!/bin/bash
echo "--- Starting Morning Briefings: $(date) ---"
# Only trigger the actual keys defined in your YAML
for tenant in tibor liz; do
  echo "Triggering $tenant..."
  curl -s -X POST "http://localhost:8090/trigger/briefing/$tenant" -d '{}' -H "Content-Type: application/json"
  sleep 2
done
