# Deployment Profiles

Set `SITE_PROFILE` to one of `kupwara`, `ncpass`, `ganganagar` or `tangdhar`.

Suggested Compose profile combinations:

```text
Tangdhar:   visitor_vehicle
Kupwara:    visitor_vehicle,cameras_2_or_more
Ganganagar: visitor_vehicle,cameras_2_or_more,cameras_3_or_6,auto_close,reverse_proxy
NCPass:     visitor_vehicle,cameras_2_or_more,cameras_3_or_6,cameras_6,bundled_infra,top_report,reverse_proxy
```

Example:

```bash
SITE_PROFILE=ganganagar docker compose \
  --profile visitor_vehicle \
  --profile cameras_2_or_more \
  --profile cameras_3_or_6 \
  --profile auto_close \
  up -d
```

Secrets and deployment-specific values must be supplied through environment variables. Important values include `SECRET_KEY`, `DB_PASSWORD`, `ANPR_TOKEN`, `ANPR_LICENSE_KEY_1` through `ANPR_LICENSE_KEY_6`, `NGINX_SSL_DIR`, `IMAGE_SHARE_API_URL` and `IMAGE_SHARE_API_KEY`.

The reverse proxy defaults to host port `4443` to avoid conflicting with the directly exposed web service on `4001`. To expose Nginx on `4001`, set `PUBLIC_HTTPS_PORT=4001` and move the direct service using `WEBSERVICE_HOST_PORT=4002`.
