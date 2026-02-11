# Run this script to commit and push the new documentation files

cd c:\repos\sentinel-activity-maps

# Add the new files
git add LOCAL_DEVELOPMENT.md
git add QUICKSTART.md
git add api/test_local.py

# Commit with message
git commit -m "Add local development guides and test script"

# Push to GitHub
git push origin main

Write-Host "`n✅ Files pushed to GitHub!" -ForegroundColor Green
