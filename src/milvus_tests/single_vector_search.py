import json
from pymilvus import MilvusClient, MilvusClient, DataType
CLUSTER_ENDPOINT = "http://census_counters_facedb:19530"

# 1. Set up a Milvus client
client = MilvusClient(
    uri=CLUSTER_ENDPOINT
)

res = client.search(
    collection_name="quick_setup", # Replace with the actual name of your collection
    # Replace with your query vector
    data=[[0.3580376395471989, -0.6023495712049978, 0.18414012509913835, -0.26286205330961354, 0.9029438446296592]],
    limit=5, # Max. number of search results to return
    search_params={"metric_type": "IP", "params": {}} # Search parameters
)

result = json.dumps(res, indent=4)
print(result)
