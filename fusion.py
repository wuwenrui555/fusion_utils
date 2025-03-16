# %%
import itertools
import numpy as np
import re
import json
import uuid
from pathlib import Path
from typing import OrderedDict, Union

import pandas as pd
from pydantic import BaseModel


class MarkerPanel(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    excel_f: Union[str, Path]
    channel_1: str = "ATTO550"
    channel_2: str = "CY5"
    start_well: str = "A1"
    marker_channel: pd.DataFrame = None
    well_name_dict: OrderedDict = None
    blank_uuid: str = None

    def __init__(self, **data):
        super().__init__(**data)
        self.parse_codex_panel()
        self.get_well_names()
        self.get_marker_uuids()

    def parse_codex_panel(self) -> None:
        """Parse the CODEX panel Excel file into a DataFrame."""
        marker_channel = pd.read_excel(self.excel_f)
        marker_channel.columns = [
            column.removesuffix(".1").strip().lower()
            for column in marker_channel.columns
        ]

        # Process channel 1
        marker_channel_1 = marker_channel.iloc[:, 0:9].assign(channel=self.channel_1)
        marker_channel_1 = marker_channel_1.rename(
            columns={marker_channel_1.columns[1]: "marker_name"}
        )

        # Process channel 2
        marker_channel_2 = marker_channel.iloc[:, [0] + list(range(10, 18))].assign(
            channel=self.channel_2
        )
        marker_channel_2 = marker_channel_2.rename(
            columns={marker_channel_2.columns[1]: "marker_name"}
        )

        # Combine and filter
        marker_channel = (
            pd.concat([marker_channel_1, marker_channel_2])[
                ["cycle", "channel", "marker_name", "oligo", "cid", "clone", "msec"]
            ]
            .fillna("None")
            .astype(
                {
                    "cycle": int,
                    "channel": str,
                    "marker_name": str,
                    "oligo": str,
                    "cid": str,
                    "clone": str,
                    "msec": int,
                }
            )
        )
        marker_idx = [
            re.search("blank", marker, re.IGNORECASE) is None
            for marker in marker_channel["marker_name"]
        ]
        self.marker_channel = marker_channel.loc[marker_idx, :].reset_index(drop=True)

    def get_well_names(self) -> None:
        """Generate well names based on cycles."""
        if self.marker_channel is None:
            raise ValueError("Marker channel data not initialized")

        cycles = sorted(self.marker_channel["cycle"].unique().tolist())
        well_names = pd.DataFrame(
            itertools.product(["A", "B", "C", "D", "E", "F", "G"], range(1, 13)),
            columns=["row", "col"],
        ).assign(well_name=lambda x: x["row"] + x["col"].astype(str))

        start_idx = well_names["well_name"] == self.start_well
        if not start_idx.any():
            raise ValueError(f"Start well {self.start_well} not found")
        if start_idx.sum() > 1:
            raise ValueError("Multiple start wells found")

        start_idx = start_idx.idxmax()
        end_idx = start_idx + len(cycles)
        if end_idx > len(well_names):
            raise ValueError("Not enough wells for all cycles")

        self.well_name_dict = OrderedDict(
            zip(cycles, well_names.iloc[start_idx:end_idx, :]["well_name"])
        )

    def get_marker_uuids(self) -> None:
        """Generate UUIDs for each marker."""
        n_uuids = len(self.marker_channel) + 1
        uuids = []
        while np.unique(uuids).size < n_uuids:
            uuids.append(str(uuid.uuid4()))
        self.marker_channel["uuid"] = uuids[1:n_uuids]
        self.blank_uuid = uuids[0]


class MarkerItem(BaseModel):
    id: str = "00000000-0000-0000-0000-000000000000"
    inventoryItemType: str = "Marker"
    markerName: str = "--"
    barcode: str = "None"  # CID
    reporter: str = "None"  # Oligo
    clone: str = "None"  # Clone
    channel: str = "None"
    dye: str = "None"
    exposure: int = None  # msec
    panel: str = "None"


class WellItem(BaseModel):
    wellName: str
    items: list[MarkerItem] = [
        MarkerItem(channel="DAPI", dye="DAPI"),
        MarkerItem(channel="AF750", dye="AF750"),
        MarkerItem(channel="ATTO550", dye="ATTO550"),
        MarkerItem(channel="CY5", dye="CY5"),
    ]


class BaseInfo(BaseModel):
    formatVersion: str = "2"
    formatType: str = "Protein"
    name: str
    tissueType: str = "HumanFFPE"
    tissueInfo: str = ""
    resolution: float = 0.5
    channels: list[dict] = [
        {"name": "DAPI", "defaultExposure": 10},
        {"name": "ATTO550", "defaultExposure": 150},
        {"name": "CY5", "defaultExposure": 150},
        {"name": "AF750", "defaultExposure": 1},
    ]
    wells: list[WellItem] = []
    unusedItems: list[dict[str, str]] = []

    def _well_exists(self, well_name: str) -> bool:
        return any(well.wellName == well_name for well in self.wells)

    def add_well_blank(self, well_name: str, uuid: str, blank_exposure: dict[str:int]):
        if self._well_exists(well_name):
            print(f"Well {well_name} already exists.")
            return
        exposure_dict = OrderedDict(
            {channel["name"]: channel["defaultExposure"] for channel in self.channels}
        )
        exposure_dict.update(blank_exposure)
        well_item = WellItem(
            wellName=well_name,
            items=[
                MarkerItem(
                    id=uuid,
                    markerName="DAPI" if channel == "DAPI" else "--",
                    channel=channel,
                    dye=channel,
                    exposure=exposure,
                )
                for channel, exposure in exposure_dict.items()
            ],
        )
        self.wells.append(well_item)

    def add_well_default(self, well_name: str):
        if self._well_exists(well_name):
            print(f"Well {well_name} already exists.")
            return
        default_exposure = OrderedDict(
            {channel["name"]: channel["defaultExposure"] for channel in self.channels}
        )
        well_item = WellItem(
            wellName=well_name,
            items=[
                MarkerItem(
                    markerName="DAPI" if channel == "DAPI" else "--",
                    channel=channel,
                    dye=channel,
                    exposure=exposure,
                    panel="Inventoried" if channel == "DAPI" else "None",
                )
                for channel, exposure in default_exposure.items()
            ],
        )
        self.wells.append(well_item)

    def update_well(self, well_name: str, channel: str, marker_item: MarkerItem):
        well_idx = [well.wellName == well_name for well in self.wells].index(True)
        channel_idx = [
            item.channel == channel for item in self.wells[well_idx].items
        ].index(True)
        self.wells[well_idx].items[channel_idx] = marker_item


# %%

excel_f = "data/codex_marker.xlsx"
project_name = "titration-rerun-150ms-C1"
start_well = "C1"
channel_1 = "ATTO550"
channel_2 = "CY5"
blank_wells = ["H3", "H4"]
blank_exposures = {
    "H3": {channel_1: 150, channel_2: 150},
    "H4": {channel_1: 150, channel_2: 150},
}

# Parse the marker panel
marker_panel = MarkerPanel(
    excel_f=excel_f,
    channel_1=channel_1,
    channel_2=channel_2,
    start_well=start_well,
)

# Initialize the base info
base_info = BaseInfo(name=project_name)

# Add wells for blank DAPI
for well_name in blank_wells:
    base_info.add_well_blank(
        well_name=well_name,
        uuid=marker_panel.blank_uuid,
        blank_exposure=blank_exposures[well_name],
    )

# Add wells for default markers
for cycle, well_name in marker_panel.well_name_dict.items():
    base_info.add_well_default(well_name)

# Update wells with marker information
for _, row in marker_panel.marker_channel.iterrows():
    well_name = marker_panel.well_name_dict[row["cycle"]]
    marker_item = MarkerItem(
        id=row["uuid"],
        markerName=row["marker_name"],
        barcode=row["cid"],
        reporter=row["oligo"],
        clone=row["clone"],
        channel=row["channel"],
        dye=row["channel"],
        exposure=row["msec"],
    )
    base_info.update_well(well_name, row["channel"], marker_item)

# Sort wells
well_order = (
    blank_wells[:1] + list(marker_panel.well_name_dict.values()) + blank_wells[1:]
)
base_info.wells = sorted(base_info.wells, key=lambda x: well_order.index(x.wellName))

# Print the JSON
with open("data/titration-rerun-150ms-C1.xpd", "w") as f:
    f.write(base_info.model_dump_json(indent=2))
# %%
# explore the id in the xpd file
with open("data/titration-rerun-150ms-C1.xpd", "r") as f:
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
# %%
