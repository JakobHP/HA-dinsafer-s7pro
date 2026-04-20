# How to Upload to GitHub

## Prerequisites
- Git installed on your computer
- GitHub account created
- New repository created on GitHub (e.g., `homeassistant-dinsafer`)

## Steps

### 1. Open Terminal/Command Prompt

Navigate to the `github-repo` folder:
```bash
cd /path/to/github-repo
```

### 2. Initialize Git Repository

```bash
git init
git add .
git commit -m "Initial commit: DinSafer S7pro Home Assistant integration"
```

### 3. Connect to GitHub

Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repository name:

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

### 4. Enter Credentials

When prompted, enter your GitHub username and password (or personal access token).

## Alternative: GitHub Desktop

1. Download and install GitHub Desktop: https://desktop.github.com/
2. Open GitHub Desktop
3. Click "Add" → "Add Existing Repository"
4. Select the `github-repo` folder
5. Click "Publish repository"
6. Choose your repository name and settings
7. Click "Publish repository"

## Verification

After uploading, visit your repository on GitHub. You should see:
- README.md displayed on the main page
- `custom_components/dinsafer/` folder with all integration files
- .gitignore file

## Next Steps

1. Add a LICENSE file (MIT recommended)
2. Create releases/tags for versioning
3. (Optional) Submit to HACS for easier installation
4. Share the repository URL with others!

## Troubleshooting

### "Permission denied" error
- Make sure you're using the correct GitHub credentials
- Consider using a Personal Access Token instead of password
- Generate token at: https://github.com/settings/tokens

### "Repository not found" error
- Double-check the repository URL
- Make sure the repository exists on GitHub
- Verify you have write access to the repository
