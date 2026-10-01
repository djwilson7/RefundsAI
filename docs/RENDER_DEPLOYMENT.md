# Render deployment

This deployment serves the frontend product concept at
`https://refundsai.dontaiwilson.com`. The core API and database are not deployed here.

## Service type

Use a **Web Service** with the **Docker** runtime. The current Next.js application
uses server-rendered routes and `output: "standalone"`, so it is not a static export.
Render Static Sites require an exported `out` directory instead.

## Create the service

GitHub is already connected to Render. Choose one of these setup paths:

* **Blueprint:** New → Blueprint → select `djwilson7/RefundsAI`, branch `main`, and
  apply the root `render.yaml`. Review the free service plan before deploying.
* **Manual:** New → Web Service → select the same repository and use the settings below.

| Setting | Value |
| --- | --- |
| Name | `refundsai` |
| Branch | `main` |
| Runtime / Language | Docker |
| Root directory | Leave blank: repository root |
| Dockerfile path | `./apps/web/Dockerfile` |
| Docker build context | `.` |
| Docker command | Leave blank to use the image's `CMD` |
| Image startup command | `node apps/web/server.js` |
| Health check path | `/` |
| Auto-deploy | On Commit |

Render builds the Dockerfile directly. Do not supply a Docker Compose command,
`docker run`, or the development-stage command. The final `runner` stage contains
the production Next.js standalone server and static assets.

## Environment

Set these values before the first deployment:

| Variable | Value |
| --- | --- |
| `REFUNDS_AI_DEMO_MODE` | `true` |
| `NEXT_TELEMETRY_DISABLED` | `1` |
| `HOSTNAME` | `0.0.0.0` |
| `PORT` | `10000` |

Render passes Docker service environment variables as build arguments and runtime
variables. The Dockerfile's `REFUNDS_AI_DEMO_MODE` build argument selects the demo
branch for both server and browser code. Rebuild after changing this value.

Do not attach a backend environment group or configure `REFUNDS_AI_API_BASE_URL`,
`SUPABASE_DB_URL`, or `OPENAI_API_KEY` for this service. The demo uses local fixtures;
its API proxies and live readers remain blocked. Local environment files are excluded
from the Docker build context.

## Custom domain

1. After deployment, confirm the assigned `*.onrender.com` URL loads the landing page.
2. In Settings → Custom Domains, add `refundsai.dontaiwilson.com` if the Blueprint
   has not already added it.
3. In Cloudflare, select `dontaiwilson.com` → DNS → Records → Add record:

   | Field | Value |
   | --- | --- |
   | Type | CNAME |
   | Name | `refundsai` |
   | Target | The service's exact assigned `*.onrender.com` hostname, without `https://` |
   | Proxy status | DNS only (gray cloud) during verification |
   | TTL | Auto |

4. Leave the portfolio root domain's records unchanged. Remove conflicting records
   only for the `refundsai` hostname, if present.
5. Return to Render and verify the custom domain. Render provisions HTTPS after
   verification; check the custom URL once DNS and routing have propagated.

Keep DNS only while Render verifies the hostname and issues its certificate. After
the certificate is valid, Cloudflare proxying is optional. If enabled, use Full
or Full (strict) encryption, not Flexible; confirm this is compatible with the
portfolio's existing zone settings before changing a zone-wide SSL/TLS setting.

The service's assigned hostname must be copied from Render; the service name does
not guarantee a particular `onrender.com` address.

## Deployment verification

* Landing page, perspective selection, Client purchases, and Admin audits load.
* Unknown page paths and missing purchase/session detail records redirect to `/`.
* Both perspectives show local examples with no backend credentials configured.
* Demo pages select fixture data before reaching API readers. Support submission,
  live refresh, pagination, and SSE subscription paths return before any network call.
* The support preview is visible and its composer is disabled.
* `POST /api/chat` returns `404` with error code `DEMO_SERVICE_DISABLED`.
* A service proxy such as `/api/admin/audit/sessions` returns the same blocked result.
* Response headers include the demo Content Security Policy with `connect-src 'self'`.

`npm run test:demo --workspace @refunds-ai/web` removes all three backend connection
variables and replaces fetch/EventSource with spies that throw on any attempt.
It verifies zero calls from page reads, support submission, service proxies, and
accidental live-component mounts. Proxy rejection is an additional boundary,
not the mechanism the UI relies on to avoid requests.

For the same image locally:

```bash
docker build -f apps/web/Dockerfile --build-arg REFUNDS_AI_DEMO_MODE=true -t refundsai-demo .
docker run --rm -p 3010:10000 -e PORT=10000 -e HOSTNAME=0.0.0.0 -e REFUNDS_AI_DEMO_MODE=true refundsai-demo
```

## Redeployments

Once this service is created with the connected GitHub repository, `main` branch,
and On Commit auto-deploy, pushes to `main` trigger image rebuilds and redeployments.
A repository push alone does not create the service or configure DNS.

## References

* [Next.js on Render](https://render.com/docs/deploy-nextjs-app)
* [Docker on Render](https://render.com/docs/docker)
* [Blueprint settings](https://render.com/docs/blueprint-spec)
* [Automatic deployments](https://render.com/docs/deploys)
* [Custom domains](https://render.com/docs/custom-domains)
* [Subdomain DNS configuration](https://render.com/docs/configure-other-dns)
* [Cloudflare configuration](https://render.com/docs/configure-cloudflare-dns)
