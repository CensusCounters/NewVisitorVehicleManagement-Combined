from psycopg2 import sql
from psycopg2.extras import RealDictCursor

from . import jobs, package


def snapshot(conn):
    result = {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for table, fields in (('persons', package.PERSON_FIELDS), ('vehicles', package.VEHICLE_FIELDS)):
            cur.execute(sql.SQL('SELECT {} FROM {} ORDER BY id').format(
                sql.SQL(',').join(map(sql.Identifier, fields)), sql.Identifier(table)))
            result[table] = [dict(r) for r in cur.fetchall()]
    return result


def counts(conn):
    with conn.cursor() as cur:
        cur.execute('SELECT (SELECT count(*) FROM persons), (SELECT count(*) FROM vehicles), (SELECT count(*) FROM trips), (SELECT count(*) FROM passes)')
        p, v, t, a = cur.fetchone()
    return dict(persons=p, vehicles=v, trips=t, passes=a)


def check_empty(conn):
    if any(counts(conn).values()):
        raise ValueError('Reset verification failed: enrollment records or dependent history remain.')


def check_reset(conn):
    c = counts(conn)
    if c['trips'] or c['passes']:
        raise ValueError('Reset blocked: trips or passes reference enrollment data. History deletion is outside this feature.')
    return c


def restore(conn, plan, actor, job_id):
    # IDs are allocated locally. Journal their mappings and the checkpoint in
    # the same transaction as inserts, so a retry can never allocate twice.
    with conn:
        inserted = {'persons': [], 'vehicles': []}
        mapping = dict(plan['person_id_map'])
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for table in ('persons', 'vehicles'):
                for repair in plan.get('repairs', {}).get(table, []):
                    updates = repair['updates']
                    if not updates:
                        continue
                    if not set(updates) <= set(package.IMAGE_FIELDS[table]):
                        raise ValueError('Repair may only fill missing enrollment image references.')
                    cur.execute(sql.SQL('UPDATE {} SET {} WHERE id=%s RETURNING id').format(
                        sql.Identifier(table), sql.SQL(',').join(
                            sql.SQL('{}=%s').format(sql.Identifier(field)) for field in updates)),
                        [*updates.values(), repair['id']])
                    if cur.fetchone() is None:
                        raise ValueError('The enrollment selected for repair is missing.')
            for table, columns in (('persons', package.PERSON_FIELDS), ('vehicles', package.VEHICLE_FIELDS)):
                fields = [f for f in columns if f != 'id']
                stmt = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING {}').format(
                    sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, fields)),
                    sql.SQL(',').join(sql.Placeholder() for _ in fields),
                    sql.SQL(',').join(map(sql.Identifier, columns)))
                for source in plan[table]:
                    row = dict(source, created_by=actor)
                    if table == 'vehicles':
                        row['vehicle_owner_id'] = mapping[str(source['vehicle_owner_id'])]
                    cur.execute(stmt, [row[f] for f in fields])
                    local = dict(cur.fetchone())
                    inserted[table].append(local)
                    if table == 'persons':
                        mapping[str(source['id'])] = local['id']
            # JSON serialization is identical to the portable date/UUID encoding.
            import json
            plan['inserted'] = json.loads(json.dumps(inserted, default=str))
            plan['person_id_map'] = mapping
        jobs.save_plan(conn, job_id, plan, 'records_loaded')


def clear(conn, job_id):
    with conn:
        check_reset(conn)
        with conn.cursor() as cur:
            cur.execute('DELETE FROM vehicles')
            cur.execute('DELETE FROM persons')
            for table in ('vehicles','persons'):
                cur.execute("SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)", (table,))
        jobs.checkpoint(job_id, 'records_cleared', conn)


def ensure_schema(conn):
    with conn.cursor() as cur:
        for table, fields in (('persons', package.PERSON_FIELDS), ('vehicles', package.VEHICLE_FIELDS)):
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s", (table,))
            if {r[0] for r in cur.fetchall()} != set(fields):
                raise ValueError('Enrollment schema differs from the supported dataset format. Update the format mapping before proceeding.')
