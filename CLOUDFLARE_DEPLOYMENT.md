# Cloudflare deployment

This site uses Workers Static Assets, with no server entry point or runtime backend.

Worker: refundsai
Public address: https://refundsai.dontaiwilson.com

## GitHub automatic deployments

GitHub Actions builds and deploys pushes to main using .github/workflows/deploy-cloudflare.yml. The workflow can also be run manually. Cloudflare native Builds is not connected, which avoids duplicate deployments.

Build command: `npm ci --workspace @refunds-ai/web && npm run web:build:static`
Deploy command: `npx --yes wrangler@4.156.0 deploy`
Published files: `apps/web/static-site/out/`

The workflow uses Node 24.13.1 and installs from the committed lockfile. Configure repository secret CLOUDFLARE_API_TOKEN and repository variable CLOUDFLARE_ACCOUNT_ID. The deployment token has Workers Scripts Edit for the hosting account and read-only Account Settings, User Details, and Memberships. It has no storage or zone-route permissions. It can deploy Workers across that account; it is not limited to this repository. Store it only in GitHub Actions secrets, never in source files. Runtime variables are not used by static assets.

Use only the separate static-site route tree, not the integrated standalone Next.js application. Demo mode is fixed true in that configuration. Never copy API, database, or model credentials into this build. The CSP is defined in apps/web/static-site/public/_headers. Cloudflare serves a real 404 for unknown paths; the existing browser fallback then returns to root. Do not copy Render's catch-all redirect into _redirects, because Cloudflare evaluates it before existing files.

The root wrangler.jsonc defines the asset directory and HTML routing. Custom domains are managed through the Cloudflare dashboard; omit route/routes keys so Git deployments preserve those domain attachments. Publish only the generated files, never the repository or .env files. Do not enable automatic framework conversion to a server runtime.

## Verification and rollback

Verify the GitHub-triggered build succeeds, HTTPS and direct nested paths load, missing pages have the intended status, and headers and SEO metadata match the exported files.

Retain the Render deployment for rollback. DNS rollback restores the recorded CNAME web targets; it does not require changing mail records. AssignmentAssistant is excluded from this migration.
