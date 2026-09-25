import random
from pymilvus import MilvusClient, MilvusClient, DataType
CLUSTER_ENDPOINT = "http://census_counters_facedb:19530"

# 1. Set up a Milvus client
client = MilvusClient(
    uri=CLUSTER_ENDPOINT
)

# 2. Create a collection in quick setup mode
# client.create_collection(
#     collection_name="quick_setup",
#     dimension=5
# )



client.create_collection(
    collection_name="quick_setup",
    dimension=5,
    metric_type="IP"
)

res = client.get_load_state(
    collection_name="quick_setup"
)

print(res)

colors = ["green", "blue", "yellow", "red", "black", "white", "purple", "pink", "orange", "brown", "grey"]
data = []

for i in range(1000):
    current_color = random.choice(colors)
    data.append({
        "id": i,
        "vector": [ random.uniform(-1, 1) for _ in range(5) ],
        "color": current_color,
        "color_tag": f"{current_color}_{str(random.randint(1000, 9999))}"
    })

res = client.insert(
    collection_name="quick_setup",
    data=data
)

print(res)


client.create_partition(
    collection_name="quick_setup",
    partition_name="red"
)

client.create_partition(
    collection_name="quick_setup",
    partition_name="blue"
)

red_data = [ {"id": i, "vector": [ random.uniform(-1, 1) for _ in range(5) ], "color": "red", "color_tag": f"red_{str(random.randint(1000, 9999))}" } for i in range(500) ]
blue_data = [ {"id": i, "vector": [ random.uniform(-1, 1) for _ in range(5) ], "color": "blue", "color_tag": f"blue_{str(random.randint(1000, 9999))}" } for i in range(500) ]

res = client.insert(
    collection_name="quick_setup",
    data=red_data,
    partition_name="red"
)

print(res)


res = client.insert(
    collection_name="quick_setup",
    data=blue_data,
    partition_name="blue"
)

print(res)

