# Render static-site deployment

The public product concept at `https://refundsai.dontaiwilson.com` is a frontend-only
static export. The core services remain in the repository and are not deployed here.

## Render settings

Choose **New → Static Site**, connect `djwilson7/RefundsAI`, and enter:

| Setting | Value |
| --- | --- |
| Name | `refundsai` |
| Branch | `main` |
| Root directory | Leave blank (repository root) |
| Build command | `npm ci --workspace @refunds-ai/web && npm run web:build:static` |
| Publish directory | `apps/web/static-site/out` |
| Auto-deploy | On Commit |

The root `render.yaml` also defines these settings for Blueprint setup.
There is no Docker command, start command, port, or server process.

## Build environment

| Variable | Value |
| --- | --- |
| `NODE_VERSION` | `24.13.1` |
| `NEXT_TELEMETRY_DISABLED` | `1` |
| `SKIP_INSTALL_DEPS` | `true` |

Dependency installation is included in the build command, so disable Render's
automatic installation. No backend credentials or demo-mode variable are needed.
The static entry fixes demo mode at build time and contains no API route handlers.
Its pages use local identity, purchase, and audit generators. The browser updates
the reference date to the current UTC day after hydrating the exported snapshot.

## Unknown paths and headers

In Redirects/Rewrites, add:

| Source | Destination | Action |
| --- | --- | --- |
| `/*` | `/` | Redirect |

Render serves existing files before applying this rule, preserving the exported
pages and assets while redirecting missing paths and unknown record IDs to root.
Use Redirect rather than Rewrite so the address bar returns to `/`.
The exported 404 page also returns to root when JavaScript loads.

In Headers, add the following for path `/*` (also included in `render.yaml`):

```text
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; media-src 'self' blob:; frame-src 'none'; form-action 'self'; object-src 'none'; base-uri 'self'
```

Same-origin asset and page navigation requests are supported. The support preview
cannot submit requests, and there are no published service endpoints.

## Cloudflare DNS

1. Confirm the assigned `*.onrender.com` URL loads after the initial deployment.
2. In Render Settings → Custom Domains, add `refundsai.dontaiwilson.com`.
3. In Cloudflare, select `dontaiwilson.com` → DNS → Records → Add record:

   | Field | Value |
   | --- | --- |
   | Type | CNAME |
   | Name | `refundsai` |
   | Target | The site's exact assigned `*.onrender.com` hostname, without `https://` |
   | Proxy status | DNS only (gray cloud) |
   | TTL | Auto |

4. Preserve the existing portfolio/apex records. Resolve conflicting records only
   for `refundsai`, if any.
5. Return to Render, verify the domain, and wait for its HTTPS certificate.

Copy the target hostname from Render; the site name does not guarantee its address.
After the certificate is valid, Cloudflare proxying is optional. If enabled, use
Full or Full (strict) encryption; avoid changing zone-wide settings without checking
how they affect the existing portfolio.

## Verification

```bash
npm run test:demo --workspace @refunds-ai/web
npm run web:build:static
python -m http.server 3010 --bind 127.0.0.1 --directory apps/web/static-site/out
```

Check the landing page, perspective selection, client history and details, admin
history and details, and support preview. Direct detail URLs must work after reload.
The output contains HTML, browser assets, and navigation payloads, with no API
routes or Next.js server. No backend configuration is required.

Verify unknown-path redirects and the response header on Render after deployment;
the basic local file server does not implement Render's redirect/header rules.
Once the site exists with On Commit enabled, future pushes to `main` trigger builds
and deployments. A push does not create the site or configure DNS.

## References

* [Render Static Sites](https://render.com/docs/static-sites)
* [Redirects and rewrites](https://render.com/docs/redirects-rewrites)
* [Blueprint settings](https://render.com/docs/blueprint-spec)
* [Cloudflare DNS configuration](https://render.com/docs/configure-cloudflare-dns)
