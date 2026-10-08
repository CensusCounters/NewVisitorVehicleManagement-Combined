"""Copy the face collections between Milvus deployments through a JSON file.

Run inside the fr_engine container:
    python /app/milvus_migrate.py export /models/milvus_export.json   # against the old Milvus
    python /app/milvus_migrate.py import /models/milvus_export.json   # against the new Milvus, after fr_engine started

Primary keys are auto-generated, so imported faces get new ids; lookups use `guid`.
The export file contains names and Aadhaar numbers: delete it once the import is verified.
"""
import argparse
import json
import sys

from pymilvus import Collection, connections, utility

COLLECTIONS = ('default', 'blacklist')
FIELDS = ['guid', 'vector', 'aadhaar', 'name']
BATCH_SIZE = 500


def export_faces(path: str):
    data = {}
    for name in COLLECTIONS:
        if not utility.has_collection(name):
            print(f'{name}: collection not found, skipping')
            data[name] = []
            continue
        collection = Collection(name)
        collection.load()
        rows = []
        iterator = collection.query_iterator(batch_size=BATCH_SIZE, expr='id >= 0', output_fields=FIELDS)
        while True:
            batch = iterator.next()
            if not batch:
                break
            for row in batch:
                rows.append({
                    'guid': row['guid'],
                    'vector': [float(v) for v in row['vector']],
                    'aadhaar': row['aadhaar'],
                    'name': row['name'],
                })
        iterator.close()
        data[name] = rows
        print(f'{name}: exported {len(rows)} faces')

    with open(path, 'w') as fl:
        json.dump(data, fl)
    print(f'Written to {path}')


def import_faces(path: str, force: bool):
    with open(path) as fl:
        data = json.load(fl)

    for name in COLLECTIONS:
        if not utility.has_collection(name):
            sys.exit(f'{name}: collection not found. Start census_counters_fr_engine first, it creates the collections.')
        collection = Collection(name)
        collection.flush()
        if collection.num_entities and not force:
            sys.exit(f'{name}: already has {collection.num_entities} faces. Use --force to append anyway.')

    for name in COLLECTIONS:
        rows = data.get(name, [])
        collection = Collection(name)
        for start in range(0, len(rows), BATCH_SIZE):
            collection.insert(rows[start:start + BATCH_SIZE])
        collection.flush()
        print(f'{name}: imported {len(rows)} faces, collection now has {collection.num_entities}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('action', choices=['export', 'import'])
    parser.add_argument('path')
    parser.add_argument('--uri', default='http://census_counters_facedb:19530')
    parser.add_argument('--force', action='store_true', help='import into non-empty collections')
    args = parser.parse_args()

    connections.connect(uri=args.uri)
    if args.action == 'export':
        export_faces(args.path)
    else:
        import_faces(args.path, args.force)


if __name__ == '__main__':
    main()
