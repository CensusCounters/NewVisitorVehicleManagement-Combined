import json
from pymilvus import MilvusClient, MilvusClient, DataType
CLUSTER_ENDPOINT = "http://census_counters_facedb:19530"

# 1. Set up a Milvus client
client = MilvusClient(
    uri=CLUSTER_ENDPOINT
)

res = client.search(
    collection_name="quick_setup", # Replace with the actual name of your collection
    data=[
        [0.19886812562848388, 0.06023560599112088, 0.6976963061752597, 0.2614474506242501, 0.838729485096104],
        [0.3172005263489739, 0.9719044792798428, -0.36981146090600725, -0.4860894583077995, 0.95791889146345]
    ], # Replace with your query vectors
    limit=5, # Max. number of search results to return
    search_params={"metric_type": "IP", "params": {}} # Search parameters
)

result = json.dumps(res, indent=4)
print(result)

