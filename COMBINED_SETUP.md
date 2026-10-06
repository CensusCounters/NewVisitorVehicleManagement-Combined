## Run BaseContainers 

Run BaseContainers repository to supply with required baseline like databases/etc

## Load ddl into the database

**One time run only to create postrgesql database):** 

```bash
docker cp DB_Files/table_schema_May172025.sql census_counters_postgres_db:/table_schema_May172025.sql
docker exec census_counters_postgres_db psql -U postgres -d postgres_visitor_vehicle -f /table_schema_May172025.sql
```

## Select configuration

Define `SITE_PROFILE` in the docker-compose file 

- `kupwara`
- `ncpass`
- `ganganagar`
- `tangdhar`

The default is `kupwara`. An unknown profile stops application startup with a clear error.

## Logo note

The repository contains the NCPass and Ganganagar logo files. The configured Kupwara and Tangdhar logo filenames were referenced by their branches but
were not present in the supplied repositories. The common layout therefore falls back to `images/census-logo.png` if either deployment-specific logo is missing. Add the real files at:

```text
src/frontend/finalfrsproject/static/images/vajr-28-div-logo.jpeg
src/frontend/finalfrsproject/static/images/shakti-vijay-logo.jpeg
```

#TODO:review this
## Cache busting

Templates call:

```jinja2
{{ asset_url('css/style.css') }}
```

which renders like:

```text
/static/css/style.css?v=combined-1
```

Increment `ASSET_URL_VERSION` when static files change.
