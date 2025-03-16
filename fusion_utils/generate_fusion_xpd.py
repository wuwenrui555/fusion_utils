#! /usr/bin/env python3
"""
Generate an xpd file for the CODEX panel based.

Usage
-----
python generate_fusion_xpd.py --param data/raw/input_param.json
"""

# %%
import argparse
import itertools
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
        marker_channel_1 = (
            marker_channel.iloc[:, 0:9]
            .assign(channel=self.channel_1)
            .rename(columns={marker_channel.columns[1]: "marker_name"})
        )

        # Process channel 2
        marker_channel_2 = (
            marker_channel.iloc[:, [0] + list(range(10, 18))]
            .assign(channel=self.channel_2)
            .rename(columns={marker_channel.columns[10]: "marker_name"})
        )

        # Combine channel 1 and channel 2
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

        # Filter out blank markers
        self.marker_channel = marker_channel[
            ~marker_channel["marker_name"].str.contains("blank", case=False)
        ].reset_index(drop=True)

    def get_well_names(self) -> None:
        """Generate well names based on cycles."""
        # All cycles
        cycles = sorted(self.marker_channel["cycle"].unique().tolist())

        # All well names
        rows = list("ABCDEFG")
        cols = list(range(1, 13))
        well_names = pd.DataFrame(
            itertools.product(rows, cols), columns=["row", "col"]
        ).assign(well_name=lambda x: x["row"] + x["col"].astype(str))

        # Find start well
        start_idx = well_names.index[well_names["well_name"] == self.start_well]
        if len(start_idx) == 0:
            raise ValueError(f"Start well {self.start_well} not found")
        elif len(start_idx) > 1:
            raise ValueError("Multiple start wells found")
        start_idx = start_idx[0]
        end_idx = start_idx + len(cycles)
        if end_idx > len(well_names):
            raise ValueError("Not enough wells for all cycles")

        # Generate well name dictionary
        self.well_name_dict = OrderedDict(
            zip(cycles, well_names.iloc[start_idx:end_idx, :]["well_name"])
        )

    def get_marker_uuids(self) -> None:
        """Generate UUIDs for each marker."""
        # All markers + 1 for blank
        n_uuids = len(self.marker_channel) + 1

        # Generate unique UUIDs
        uuids = []
        while len(set(uuids)) < n_uuids:
            uuids.extend([str(uuid.uuid4()) for _ in range(n_uuids - len(set(uuids)))])
            uuids = list(set(uuids))

        self.marker_channel["uuid"] = uuids[: n_uuids - 1]
        self.blank_uuid = uuids[n_uuids - 1]


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
    unusedItems: list = []

    def _well_exists(self, well_name: str) -> bool:
        """Check if a well exists in the base info."""
        return any(well.wellName == well_name for well in self.wells)

    def add_well_blank(self, well_name: str, uuid: str, blank_exposure: dict[str:int]):
        """Add a blank well to the base info."""
        if self._well_exists(well_name):
            print(f"Well {well_name} already exists.")
            return

        # Update the blank exposure with default exposures
        exposure_dict = OrderedDict(
            {channel["name"]: channel["defaultExposure"] for channel in self.channels}
        )
        exposure_dict.update(blank_exposure)

        # Add the blank well
        items = [
            MarkerItem(
                id=uuid,
                markerName="DAPI" if channel == "DAPI" else "--",
                channel=channel,
                dye=channel,
                exposure=exposure,
            )
            for channel, exposure in exposure_dict.items()
        ]
        self.wells.append(WellItem(wellName=well_name, items=items))

    def add_well_default(self, well_name: str):
        """Add a default well to the base info."""
        if self._well_exists(well_name):
            print(f"Well {well_name} already exists.")
            return

        # Default exposures for all channels
        default_exposure = OrderedDict(
            {channel["name"]: channel["defaultExposure"] for channel in self.channels}
        )

        # Add the default well
        items = [
            MarkerItem(
                markerName="DAPI" if channel == "DAPI" else "--",
                channel=channel,
                dye=channel,
                exposure=exposure,
                panel="Inventoried" if channel == "DAPI" else "None",
            )
            for channel, exposure in default_exposure.items()
        ]
        self.wells.append(WellItem(wellName=well_name, items=items))

    def update_well(self, well_name: str, channel: str, marker_item: MarkerItem):
        """Update a well with a marker item."""
        try:
            well_idx = next(
                i for i, well in enumerate(self.wells) if well.wellName == well_name
            )
        except StopIteration:
            print(f"Well {well_name} not found.")

        try:
            channel_idx = next(
                i
                for i, item in enumerate(self.wells[well_idx].items)
                if item.channel == channel
            )
        except StopIteration:
            print(f"Channel {channel} not found in well {well_name}.")

        self.wells[well_idx].items[channel_idx] = marker_item


class InputParameter(BaseModel):
    excel_f: Union[str, Path]
    output_f: Union[str, Path]
    project_name: str
    start_well: str = "A1"
    channel_1: str = "ATTO550"
    channel_2: str = "CY5"
    blank_wells: list[str] = ["H1", "H2"]
    blank_exposures: dict[str, dict[str, int]] = {
        "H1": {"DAPI": 10, "ATTO550": 150, "CY5": 150, "AF750": 1},
        "H2": {"DAPI": 10, "ATTO550": 150, "CY5": 150, "AF750": 1},
    }
    default_exposures: dict[str, int] = {
        "DAPI": 10,
        "ATTO550": 150,
        "CY5": 150,
        "AF750": 1,
    }


def generate_fusion_xpd(param_f=Union[str, Path]) -> None:
    """Generate an xpd file for Fusion based on the input parameters."""
    # Load the input parameters
    with open(param_f, "r") as f:
        input_param = InputParameter.model_validate(json.load(f))

    # Parse the marker panel
    marker_panel = MarkerPanel(
        excel_f=input_param.excel_f,
        channel_1=input_param.channel_1,
        channel_2=input_param.channel_2,
        start_well=input_param.start_well,
    )

    # Initialize the base info
    base_info = BaseInfo(
        name=input_param.project_name,
        channels=[
            {"name": channel, "defaultExposure": input_param.default_exposures[channel]}
            for channel in ["DAPI", "ATTO550", "CY5", "AF750"]
        ],
    )

    # Add wells for blank DAPI
    for well_name in input_param.blank_wells:
        base_info.add_well_blank(
            well_name=well_name,
            uuid=marker_panel.blank_uuid,
            blank_exposure=input_param.blank_exposures[well_name],
        )

    # Add wells for default markers
    for _, well_name in marker_panel.well_name_dict.items():
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

    # Sort wells: first blank wells, marker wells, remaining blank wells
    well_order = (
        input_param.blank_wells[:1]
        + list(marker_panel.well_name_dict.values())
        + input_param.blank_wells[1:]
    )
    base_info.wells = sorted(
        base_info.wells, key=lambda well: well_order.index(well.wellName)
    )

    # Output the xpd file
    with open(input_param.output_f, "w") as f:
        f.write(base_info.model_dump_json(indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Generate an xpd file for the CODEX panel."
    )
    parser.add_argument(
        "--param",
        type=str,
        default="./input_param.json",
        help="Path to the input parameter JSON file",
    )
    args = parser.parse_args()

    generate_fusion_xpd(args.param)


if __name__ == "__main__":
    main()
