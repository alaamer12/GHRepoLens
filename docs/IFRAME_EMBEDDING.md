# Iframe Embedding for Charts

GHRepoLens now supports embedding generated HTML charts into external websites (e.g., Notion, documentation, dashboards) via `<iframe>` by hosting them on a public HTTPS URL using [Vercel](https://vercel.com/).

## Overview

This feature allows you to:

1. Deploy your charts to Vercel 
2. Embed them in any website that supports iframes
3. Share interactive visualizations with others

## Configuration Options

The iframe embedding feature is controlled by the `IFRAME_EMBEDDING` configuration option:

- **"disabled"** _(default)_: No iframe embedding or deployment.
    
- **"partial"**: Deploy only key chart HTML files for embedding.
    
- **"full"**: Deploy **all** HTML files, including the full `visual_report.html` dashboard.

## Required Configuration

To use iframe embedding, you must provide:

1. `VERCEL_TOKEN`: A personal access token from Vercel
2. `VERCEL_PROJECT_NAME`: A unique name for your project on Vercel

## HTML Files Deployed

### Partial Mode (Key Charts)

- `active_inactive_age.html`
- `commit_activity_heatmap.html`
- `documentation_quality.html`
- `infrastructure_metrics.html`
- `quality_heatmap.html`
- `repo_creation_timeline.html`
- `repo_types_distribution.html`
- `repository_timeline.html`
- `stars_vs_issues.html`
- `top_repos_metrics.html`

### Full Mode

All of the above **plus**:
- `visual_report.html` (main dashboard)

## Setup Instructions

### 1. Create a Vercel Account

If you don't have one already, create an account at [vercel.com](https://vercel.com/).

### 2. Get a Vercel Token

1. Log in to your Vercel account
2. Go to Settings → Tokens
3. Create a new token with a descriptive name (e.g., "GHRepoLens")
4. Copy the token value

### 3. Configure GHRepoLens

#### Using Environment Variables

Add to your `.env` file:
```
IFRAME_EMBEDDING=partial
VERCEL_TOKEN=your_token_here
VERCEL_PROJECT_NAME=ghrepolens-yourname
```

#### Using Config File

In your `config.ini`:
```ini
[iframe]
iframe_embedding = partial
vercel_token = your_token_here
vercel_project_name = ghrepolens-yourname
```

#### Using Command Line

```bash
python main.py --iframe partial
```
(You will be prompted for your Vercel token and project name)

## Example Usage

After deploying your charts, you can embed them in any HTML page like this:

```html
<iframe 
  src="https://your-project-name.vercel.app/stars_vs_issues.html" 
  width="100%" 
  height="600px" 
  frameborder="0">
</iframe>
```

## Troubleshooting

### Deployment Fails

- Verify your Vercel token is valid and has the correct permissions
- Check that your project name is unique
- Ensure your internet connection is stable
- Try running `vercel` from the command line to see if it works

### Charts Display Issues

- Make sure to include the full URL with `https://`
- Check if the chart loads correctly in a browser first
- Some websites have CSP restrictions that block iframe embedding

## Security Considerations

- Your Vercel token gives access to deploy to your account - keep it secure
- Deployed charts are public - don't include sensitive information
- When you're done sharing, you can delete the project from your Vercel dashboard 