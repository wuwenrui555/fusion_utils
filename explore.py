# %%
import json
from fusion_utils.generate_fusion_xpd import BaseInfo

# explore the id in the xpd file
with open("data/output/titration-rerun-150ms-C1.xpd", "r") as f:
    xpd = json.load(f)
base_info = BaseInfo.model_validate(xpd)

id_well = {}
id_marker = {}
id_channel = {}
for well in base_info.wells:
    for item in well.items:
        id_well[item.id] = id_well.get(item.id, {})
        id_well[item.id][well.wellName] = id_well[item.id].get(well.wellName, 0) + 1

        id_marker[item.id] = id_marker.get(item.id, {})
        id_marker[item.id][item.markerName] = (
            id_marker[item.id].get(item.markerName, 0) + 1
        )

        id_channel[item.id] = id_channel.get(item.id, {})
        id_channel[item.id][item.channel] = id_channel[item.id].get(item.channel, 0) + 1
