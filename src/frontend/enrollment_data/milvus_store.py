"""Default enrollment collection only. Never modify the blacklist collection."""
import json

from pymilvus import Collection, connections, utility
from . import config


class Faces:
    def __init__(self):
        self.alias = 'enrollment-maintenance'
        connections.connect(alias=self.alias, uri=config.MILVUS_URI, timeout=30)
        if not utility.has_collection('default', using=self.alias):
            raise ValueError('Default face collection is missing; start the face engine first.')
        self.collection = Collection('default', using=self.alias)
        schema = self.collection.schema
        fields = {f.name: f for f in schema.fields}
        if set(fields) != {'id','guid','vector','name','aadhaar'} or fields['vector'].params.get('dim') != 512 or not schema.auto_id:
            raise ValueError('Unsupported default face collection schema.')
        self.collection.load(timeout=60)

    def rows(self):
        iterator = self.collection.query_iterator(batch_size=500, expr='id >= 0',
            output_fields=['guid','vector','name','aadhaar'], consistency_level='Strong', timeout=60)
        try:
            while True:
                batch = iterator.next()
                if not batch:
                    break
                for r in batch:
                    yield {'guid': r['guid'], 'vector': [float(v) for v in r['vector']], 'name': r['name'], 'aadhaar': r['aadhaar']}
        finally:
            iterator.close()

    def empty(self):
        return not self.collection.query(expr='id >= 0', output_fields=['id'], limit=1, consistency_level='Strong', timeout=30)

    def delete_guids(self, guids):
        guids = list(guids)
        for start in range(0, len(guids), 200):
            self.collection.delete(expr='guid in ' + json.dumps(guids[start:start + 200]), timeout=60)

    def restore(self, rows, guids, progress):
        # Caller supplies only GUIDs owned by its committed import journal,
        # never every GUID in the uploaded package. Existing enrollments must
        # survive both initial loading and explicit recovery unchanged.
        if not self.empty():
            progress('Replacing partially restored facial vectors')
            self.delete_guids(guids)
        batch = []
        count = 0
        for row in rows:
            batch.append(row)
            if len(batch) == 200:
                self.collection.insert(batch, timeout=60)
                count += len(batch)
                progress(f'Loading facial vectors: {count}')
                batch = []
        if batch:
            self.collection.insert(batch, timeout=60)
        # Strong-consistency verification in service.py reads growing segments
        # too. Per-operation flushes needlessly seal tiny segments and can block
        # on Milvus compaction/indexing; accepted mutations are persisted by WAL.

    def close(self):
        connections.disconnect(self.alias)

    def restore_missing(self, rows, expected, progress):
        """Append missing vectors only, including after an interrupted repair."""
        from collections import Counter
        from .merge import face_index, face_fingerprint

        current = face_index(row for row in self.rows() if row['guid'] in expected)
        for guid, actual in current.items():
            if actual - Counter(expected[guid]):
                raise ValueError('Existing face data differs; repair will not replace it.')
        remaining = {guid: Counter(values) for guid, values in current.items()}
        batch = []
        count = 0
        for row in rows:
            existing = remaining.setdefault(row['guid'], Counter())
            fingerprint = face_fingerprint(row)
            if existing[fingerprint]:
                existing[fingerprint] -= 1
                continue
            batch.append(row)
            if len(batch) == 200:
                self.collection.insert(batch, timeout=60)
                count += len(batch)
                progress(f'Restoring missing facial vectors: {count}')
                batch = []
        if batch:
            self.collection.insert(batch, timeout=60)
